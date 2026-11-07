import base64
import json
import os
import pathlib
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.request
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import laya
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from laya import Router
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

DB_PATH = os.getenv("FAVEMUS_DB", "/home/baymax/favemus/favemus.db")
CONFIDENCE_FLOOR = float(os.getenv("FAVEMUS_CONFIDENCE_FLOOR", "0.35"))
PLATFORM = "manual"
TEMPLATE_DIR = pathlib.Path("/home/baymax/favemus/templates")
def _tpl(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")
  # standalone: manual users, manual orders/products. No Shopify/BigCommerce/WooCommerce.
HARNESS_ADMIN_TOKEN = os.getenv("HARNESS_ADMIN_TOKEN", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
GREETINGS = {"hi", "hii", "hello", "hey", "hlo", "namaste", "namaskar", "good morning", "good afternoon", "good evening", "start", "/start"}
import time as _time
_START_TIME = _time.time()

QUESTIONS = {
    "tool": {
        "type": "choice",
        "instructions": "Which function should handle this customer message?",
        "criteria": {
            "order_status": "asks where the order is, tracking, or the delivery date",
            "refund_status": "asks about the progress or status of an existing refund",
            "initiate_return": "wants to return an item and get money back",
            "exchange_item": "wants a different size or colour, or a replacement item",
            "search_products": "asks about stock, availability, fabric, sizing, or care",
            "human_handoff": "explicitly asks for a human agent or wants to escalate a serious complaint",
        },
    },
    "issue": {
        "type": "choice",
        "instructions": "What is the problem with the item or order?",
        "criteria": {
            "damaged": "broken, torn, stained, or defective item",
            "wrong_item": "received a different product, size, or colour",
            "size_fit": "does not fit or the sizing is wrong",
            "not_as_described": "item differs from the product page",
            "delivery": "late, missing, or undelivered order",
            "none": "no problem with the item",
            "other": "anything else",
        },
    },
    "sentiment": {"type": "score", "instructions": "How upset is the customer?", "criteria": ["calm", "annoyed", "angry"]},
}

CONFIRM_Q = {"confirms": {"type": "noul", "instructions": "Does the customer agree, confirm, or say yes?"}}

ORDER_TOOLS = {"order_status", "refund_status", "initiate_return", "exchange_item"}

ORDERS = {
    "FAV-1042": {"item": "blue cotton kurti", "amount": 1499, "status": "out_for_delivery", "eta": "2026-11-03", "refund": None},
    "FAV-2231": {"item": "green wrap dress", "amount": 2299, "status": "delivered", "eta": "2026-10-29", "refund": "processing, expected 2026-11-05"},
    "FAV-3005": {"item": "white linen shirt", "amount": 999, "status": "processing", "eta": "2026-11-05", "refund": None},
}

CATALOG = [
    {"sku": "DRS-GRN-8", "name": "green wrap dress", "fabric": "viscose", "colors": ["green"], "price": 2299, "sizes": ["6", "8", "10", "12"]},
    {"sku": "KRT-BLU-M", "name": "blue cotton kurti", "fabric": "cotton", "colors": ["blue"], "price": 1499, "sizes": ["S", "M", "L", "XL"]},
    {"sku": "SHT-WHT-M", "name": "white linen shirt", "fabric": "linen", "colors": ["white"], "price": 999, "sizes": ["S", "M", "L"]},
    {"sku": "LEG-BLK-M", "name": "black leggings", "fabric": "cotton blend", "colors": ["black"], "price": 699, "sizes": ["S", "M", "L", "XL"]},
]

class OrderLookupError(RuntimeError):
    pass


class ProductLookupError(RuntimeError):
    pass


PRODUCT_STOPWORDS = {
    "the", "a", "an", "do", "does", "you", "have", "has", "any", "is", "are",
    "for", "of", "in", "on", "to", "and", "or", "with", "i", "we", "my", "me",
    "it", "this", "that", "these", "those", "can", "could", "would", "please",
    "looking", "look", "want", "need", "buy", "get", "sell", "carry", "stock",
    "available", "availability", "price", "cost", "much", "how", "what",
    "which", "where", "when", "your", "store", "shop", "product", "products",
    "item", "items", "show", "tell", "about", "there", "some", "from", "by",
    "at", "as", "be", "am", "was", "were", "size", "sizes",
}


def _product_keywords(text):
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [w for w in words if len(w) >= 3 and w not in PRODUCT_STOPWORDS]


def _word_match(word, words):
    if word in words:
        return True
    if word.endswith("s") and word[:-1] in words:
        return True
    return (word + "s") in words


def lookup_order(shop, order_id, tenant_id="default"):
    """Manual order lookup: tenant-scoped DB table first, then built-in demo ORDERS."""
    if not order_id:
        return None
    oid = str(order_id).strip()
    con = db()
    row = None
    try:
        row = con.execute("SELECT * FROM orders WHERE order_id=? AND tenant_id=?", (oid, tenant_id)).fetchone()
        if row is None:
            row = con.execute("SELECT * FROM orders WHERE order_id=? AND tenant_id=?", (oid.lstrip("#"), tenant_id)).fetchone()
    finally:
        con.close()
    if row is not None:
        d = dict(row)
        return {"id": d["order_id"], "item": d.get("item") or "your order", "amount": d.get("amount") or 0,
                "currency": d.get("currency") or "", "status": d.get("status") or "processing",
                "eta": d.get("eta"), "refund": d.get("refund"),
                "tracking": json.loads(d.get("tracking_json") or "[]")}
    return ORDERS.get(oid) or ORDERS.get(oid.lstrip("#"))


def lookup_products(shop, text, size=None, tenant_id="default"):
    """Manual product search: tenant-scoped DB table first, then built-in CATALOG."""
    con = db()
    rows = con.execute("SELECT * FROM products WHERE tenant_id=?", (tenant_id,)).fetchall()
    con.close()
    keywords = _product_keywords(text)
    scored = []
    for r in rows:
        d = dict(r)
        sizes = json.loads(d.get("sizes_json") or "[]")
        if size and size.upper() not in [str(x).upper() for x in sizes]:
            continue
        hay = set(re.findall(r"[a-z0-9]+", ((d.get("name") or "") + " " + (d.get("fabric") or "") + " " + " ".join(json.loads(d.get("colors_json") or "[]"))).lower()))
        matched = [w for w in keywords if _word_match(w, hay)]
        if keywords and not matched:
            continue
        scored.append((len(matched), {"name": d.get("name") or "Product", "fabric": d.get("fabric") or "",
                                       "price": d.get("price") or 0, "currency": d.get("currency") or "",
                                       "price_text": "", "sizes": sizes, "available": bool(d.get("available", 1))}))
    scored.sort(key=lambda x: -x[0])
    if scored:
        return [p for _, p in scored[:8]]
    return search_catalog(text, size)


router = None
_lock = threading.Lock()


def ts():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def db():
    con = sqlite3.connect(DB_PATH, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    return con


def init_db():
    con = db()
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            channel TEXT,
            shop TEXT DEFAULT 'favemus',
            state TEXT DEFAULT 'idle',
            pending_tool TEXT,
            collected TEXT DEFAULT '{}',
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT,
            content TEXT,
            meta TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS tickets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            shop TEXT DEFAULT 'favemus',
            kind TEXT,
            status TEXT DEFAULT 'open',
            payload TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            message TEXT,
            analysis TEXT,
            tool_call TEXT,
            action TEXT,
            latency_ms REAL,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            pass_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            is_active INTEGER DEFAULT 1,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS auth_sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at REAL NOT NULL,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            item TEXT,
            amount REAL DEFAULT 0,
            currency TEXT DEFAULT 'INR',
            status TEXT DEFAULT 'processing',
            eta TEXT,
            refund TEXT,
            tracking_json TEXT DEFAULT '[]',
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS whatsapp_seen (
            message_id TEXT PRIMARY KEY,
            wa_id TEXT,
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS products (
            sku TEXT PRIMARY KEY,
            name TEXT,
            fabric TEXT DEFAULT '',
            colors_json TEXT DEFAULT '[]',
            price REAL DEFAULT 0,
            currency TEXT DEFAULT 'INR',
            sizes_json TEXT DEFAULT '[]',
            available INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        );
        """
    )
    for table in ("sessions", "tickets"):
        cols = [r[1] for r in con.execute(f"PRAGMA table_info({table})")]
        if "shop" not in cols:
            con.execute(f"ALTER TABLE {table} ADD COLUMN shop TEXT DEFAULT 'favemus'")
    con.commit()
    con.close()
    try:
        _seed_manual_data()
    except Exception:
        pass
    try:
        _migrate_to_tenants(con := db())
        _seed_default_tenant_data()
        con.close()
    except Exception as exc:
        print("tenant migration seed warning:", exc, flush=True)


def load_session(sid, user_id=None, channel=None, shop="favemus"):
    con = db()
    row = con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if row is None:
        con.execute(
            "INSERT INTO sessions(id,user_id,channel,shop,state,pending_tool,collected,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
            (sid, user_id, channel, shop, "idle", None, "{}", ts(), ts()),
        )
        con.commit()
        row = con.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    con.close()
    return dict(row)


def save_session(sid, state, pending_tool, collected):
    con = db()
    con.execute(
        "UPDATE sessions SET state=?, pending_tool=?, collected=?, updated_at=? WHERE id=?",
        (state, pending_tool, json.dumps(collected), ts(), sid),
    )
    con.commit()
    con.close()


def add_message(sid, role, content, meta=None):
    con = db()
    con.execute(
        "INSERT INTO messages(session_id,role,content,meta,created_at) VALUES(?,?,?,?,?)",
        (sid, role, content, json.dumps(meta, default=str) if meta else None, ts()),
    )
    con.commit()
    con.close()


def create_ticket(sid, kind, payload, shop="favemus"):
    con = db()
    cur = con.execute(
        "INSERT INTO tickets(session_id,shop,kind,status,payload,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
        (sid, shop, kind, "open", json.dumps(payload, default=str), ts(), ts()),
    )
    con.commit()
    tid = cur.lastrowid
    con.close()
    return tid


def log_decision(sid, message, analysis, tool_call, action, latency_ms):
    con = db()
    con.execute(
        "INSERT INTO decisions(session_id,message,analysis,tool_call,action,latency_ms,created_at) VALUES(?,?,?,?,?,?,?)",
        (sid, message, json.dumps(analysis, default=str), json.dumps(tool_call, default=str) if tool_call else None, action, latency_ms, ts()),
    )
    con.commit()
    con.close()


def _post_json(url, payload, headers=None):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"content-type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def _predict(text, questions):
    with _lock:
        return router.predict(text, questions, model="english")


def analyse_message(text):
    res = _predict(text, QUESTIONS)
    a = res["answers"]
    analysis = {
        "tool": a["tool"]["choice"],
        "tool_confidence": a["tool"]["answer_confidence"],
        "tool_probabilities": a["tool"]["probabilities"],
        "issue": a["issue"]["choice"],
        "issue_confidence": a["issue"]["answer_confidence"],
        "sentiment": a["sentiment"]["score"],
    }
    return analysis, res["routing"]


def confirms(text):
    res = _predict(text, CONFIRM_Q)
    return res["answers"]["confirms"]["noul"]


def extract_entities(text):
    out = {}
    m = re.search(r"\bFAV[-\s]?(\d{3,6})\b", text, re.I)
    if m:
        out["order_id"] = "FAV-" + m.group(1)
    else:
        m = re.search(r"(?:order\s*(?:number|no\.?|#)?\s*|#)(\d{3,8})\b", text, re.I)
        if m:
            out["order_id"] = "#" + m.group(1)
        else:
            for m in re.finditer(r"\b([A-Z0-9]{8,12})\b", text, re.I):
                token = m.group(1)
                if re.search(r"\d", token) and re.search(r"[A-Z]", token, re.I):
                    out["order_id"] = token.upper()
                    break
    m = re.search(r"\b(?:size|sz)\b\s*([0-9]{1,2}|xs|s|m|l|xl|xxl)\b", text, re.I)
    if m:
        out["size"] = m.group(1).upper()
    return out


def search_catalog(text, size=None):
    words = set(re.findall(r"[a-z]+", text.lower()))
    scored = []
    for p in CATALOG:
        hay = set(re.findall(r"[a-z]+", (p["name"] + " " + p["fabric"] + " " + " ".join(p["colors"])).lower()))
        score = len(words & hay)
        if score and (not size or size in p["sizes"]):
            scored.append((score, p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored]


def fetch_order(shop, oid, tenant_id="default"):
    try:
        return lookup_order(shop, oid, tenant_id), None
    except OrderLookupError:
        return None, (
            {"ok": False, "error": "order_lookup_unavailable", "order_id": oid},
            "I can't access order details right now. Please try again in a moment, or reply 'human' to reach an agent.",
        )


def fetch_products(shop, text, size=None, tenant_id="default"):
    try:
        return lookup_products(shop, text, size, tenant_id), None
    except Exception as exc:
        print(f"product lookup failed for {shop} {text}: {exc}", flush=True)
        return [], (
            {"ok": False, "error": "product_lookup_unavailable"},
            "I can't search products right now. Please try again in a moment, or reply 'human' to reach an agent.",
        )


def execute_tool(sid, name, args, message, shop="favemus"):
    if name == "order_status":
        oid = args.get("order_id")
        order, failure = fetch_order(shop, oid)
        if failure:
            return failure
        if not order:
            return {"ok": False, "error": "order_not_found", "order_id": oid}, (
                f"I couldn't find order {oid}. Please check the number, or reply 'human' to reach an agent."
            )
        amount = order.get("amount")
        currency = order.get("currency")
        money = ""
        if amount:
            if currency in (None, "", "INR"):
                money = f"Rs {amount:g}"
            elif currency == "USD":
                money = f"${amount:g}"
            else:
                money = f"{currency} {amount:g}"
        detail = f"{order['item']}, {money})" if money else f"{order['item']})"
        reply = f"Order {oid} ({detail} is {order['status'].replace('_', ' ')}."
        if order.get("eta") and order["status"] != "delivered":
            reply += f" Estimated delivery: {order['eta']}."
        tracking = order.get("tracking") or []
        if tracking and tracking[0].get("number"):
            reply += f" Tracking: {tracking[0]['number']}."
        return {"ok": True, "order_id": oid, **order}, reply
    if name == "refund_status":
        oid = args.get("order_id")
        order, failure = fetch_order(shop, oid)
        if failure:
            return failure
        if not order:
            return {"ok": False, "error": "order_not_found", "order_id": oid}, (
                f"I couldn't find order {oid}. Please check the number, or reply 'human' to reach an agent."
            )
        if order.get("refund"):
            return {"ok": True, "order_id": oid, "refund": order["refund"]}, (
                f"Your refund for {oid} is {order['refund']}. Refunds usually reach the original payment method in 3-5 business days after processing."
            )
        return {"ok": True, "order_id": oid, "refund": None}, (
            f"I don't see a refund started for {oid}. If you want to return the item, say 'I want to return it' and I'll start the request."
        )
    if name == "initiate_return":
        oid = args.get("order_id")
        order, failure = fetch_order(shop, oid)
        if failure:
            return failure
        if not order:
            return {"ok": False, "error": "order_not_found", "order_id": oid}, (
                f"I couldn't find order {oid}. Please check the number, or reply 'human' to reach an agent."
            )
        args["analysis"] = args.get("analysis")
        tid = create_ticket(sid, "return", {"order_id": args.get("order_id"), "reason": message, "analysis": args.get("analysis")}, shop)
        return {"ok": True, "ticket_id": tid}, (
            f"Done - return request #{tid} is created for {args.get('order_id')}. "
            "A pickup will be scheduled and the refund starts once the item is received."
        )
    if name == "exchange_item":
        oid = args.get("order_id")
        order, failure = fetch_order(shop, oid)
        if failure:
            return failure
        if not order:
            return {"ok": False, "error": "order_not_found", "order_id": oid}, (
                f"I couldn't find order {oid}. Please check the number, or reply 'human' to reach an agent."
            )
        tid = create_ticket(sid, "exchange", {"order_id": args.get("order_id"), "size": args.get("size"), "reason": message, "analysis": args.get("analysis")}, shop)
        extra = f" in size {args['size']}" if args.get("size") else ""
        return {"ok": True, "ticket_id": tid}, (
            f"Done - exchange request #{tid} is created for {args.get('order_id')}{extra}. The team will confirm availability."
        )
    if name == "search_products":
        hits, failure = fetch_products(shop, message, args.get("size"))
        if failure:
            return failure
        if not hits:
            return {"ok": True, "results": []}, "I couldn't find a matching item. Could you share the product name, colour, or size?"
        lines = []
        for h in hits[:4]:
            fabric = f"{h['fabric']}, " if h.get("fabric") else ""
            price = h.get("price_text") or (f"Rs {h['price']:.0f}" if isinstance(h.get("price"), (int, float)) and h.get("price") else "")
            size_text = f" sizes: {', '.join(h['sizes'])}" if h.get("sizes") else ""
            sold_out = "" if "gift card" in h["name"].lower() else (" (sold out)" if h.get("available") is False else "")
            lines.append(f"- {h['name']} ({fabric}{price}){size_text}{sold_out}")
        return {"ok": True, "results": hits[:4]}, "Here's what I found:\n" + "\n".join(lines)
    if name == "human_handoff":
        tid = create_ticket(sid, "handoff", {"reason": message, "analysis": args.get("analysis")}, shop)
        return {"ok": True, "ticket_id": tid}, (
            f"I've passed this to a human agent (ticket #{tid}). Someone will reply in this conversation shortly."
        )
    return {"ok": False, "error": "unknown_tool"}, "Sorry, I couldn't handle that request."


def handle_message(sid, user_id, channel, text, shop="favemus"):
    try:
        return _handle_message(sid, user_id, channel, text, shop)
    except Exception as exc:
        print(f"handle_message error: {exc}", flush=True)
        import traceback
        traceback.print_exc()
        return {
            "session_id": sid,
            "reply": f"Internal error: {str(exc)}",
            "state": "error",
            "action": "error",
            "analysis": {"error": str(exc)},
            "tool_call": None,
            "handoff": False,
            "routing": None,
        }


# ---------------------------------------------------------------------------
# Dynamic, conversational response templates (no static scripts)
# ---------------------------------------------------------------------------

GREETING_REPLIES = [
    "Hi there! I'm your support assistant. How can I help you today?",
    "Hello! What can I do for you — order status, returns, exchanges, or product questions?",
    "Hey! I'm here to help. What do you need assistance with?",
    "Hi! How can I support you today?",
]

HANDOFF_REPLIES = [
    "I've passed this to a human agent (ticket #{tid}). They'll be with you shortly.",
    "I'm creating a support ticket (#{tid}) for a human agent to take over. Please hold on.",
    "Let me get a human on this — ticket #{tid} has been created. They'll reply soon.",
]

CLARIFY_REPLIES = [
    "I want to make sure I get this right — is it about an order, a return or exchange, a refund, or a product question?",
    "Could you clarify? Are you asking about an order, a return/exchange, a refund, or a product?",
    "Just to be sure I help you correctly: is this about an order, return, refund, or product?",
]

ASK_ORDER_REPLIES = [
    "Sure! What's your order number? It looks like #1001 or FAV-1042.",
    "I'd be happy to check — could you share your order number (e.g., FAV-1042 or #1001)?",
    "What's the order number? Something like #1001 or FAV-1042 works.",
]

CONFIRM_REPLIES = [
    "I can start {article} {word} for order {order_id}. Should I go ahead? Just say yes or no.",
    "Shall I create a {word} request for order {order_id}? Reply yes to confirm, or no to cancel.",
    "Ready to set up a {word} for order {order_id}? Say yes if that's what you want.",
]

CANCEL_REPLIES = [
    "No problem at all — I won't create that request. Anything else I can help with?",
    "Noted, I've cancelled that. What else can I do for you?",
    "No worries, cancelled. Is there anything else you need?",
]

RESET_REPLIES = [
    "Sure, let's start fresh. What can I help you with?",
    "No problem — new topic. What would you like to talk about?",
    "Got it, let's reset. How can I help?",
]

ORDER_NOT_FOUND_REPLIES = [
    "I couldn't find order {order_id}. Could you double-check the number? It's in your confirmation email.",
    "Hmm, I don't see an order by that number ({order_id}). Want to try again?",
    "I wasn't able to locate order {order_id}. Please check the number and let me know.",
]

ORDER_FOUND_REPLIES = [
    "Order {order_id} ({item}, {money}) is {status}.{eta}",
    "Here's what I found for {order_id}: {item} — status: {status}.{eta}",
    "Looking at {order_id}: {item}, currently {status}.{eta}",
]

PRODUCT_FOUND_REPLIES = [
    "Here's what I found:\n{items}",
    "I found these items:\n{items}",
    "Here are the products matching your search:\n{items}",
]

PRODUCT_NOT_FOUND_REPLIES = [
    "I couldn't find anything matching that. Could you share the product name, colour, or size?",
    "No matches came up. Want to try describing it differently?",
    "I didn't see any products matching. Could you tell me more about what you're looking for?",
]

CLARIFY_2X_HANDOFF = "I'm having trouble understanding — let me get a human agent to help you directly."

SUGGESTION_PROMPTS = [
    "Is there anything else I can help you with?",
    "Anything else you need help with?",
    "What else can I do for you?",
]


def _pick(options):
    import random
    return random.choice(options)


def _format_order_reply(order, eta_suffix=""):
    item = order.get("item") or "your order"
    amount = order.get("amount") or 0
    currency = order.get("currency") or ""
    if currency == "INR":
        money = f"Rs {amount:g}"
    elif currency == "USD":
        money = f"${amount:g}"
    else:
        money = f"{currency} {amount:g}" if amount else ""
    status = order.get("status") or "processing"
    eta = ""
    if order.get("eta") and order.get("status") != "delivered":
        eta = f" Estimated delivery: {order['eta']}."
    if eta_suffix:
        eta = eta_suffix
    tracking = ""
    tracks = order.get("tracking") or []
    if tracks and tracks[0].get("number"):
        tracking = f" Tracking: {tracks[0]['number']}."
    return f"Order {order.get('order_id')} ({item}, {money}) is {status.replace('_', ' ')}.{eta}{tracking}"


def _format_product_item(h):
    fabric = f"{h.get('fabric', '')}, " if h.get("fabric") else ""
    price = h.get("price_text") or (f"Rs {h.get('price', 0):g}" if isinstance(h.get("price"), (int, float)) and h.get("price") else "")
    size_text = f" sizes: {', '.join(h.get('sizes', []))}" if h.get("sizes") else ""
    return f"- {h.get('name', 'Product')} ({fabric}{price}){size_text}"


def _get_customer_name(user_id, shop="favemus"):
    if not user_id or user_id == "anonymous":
        return None
    if user_id.startswith("user:"):
        email = user_id.replace("user:", "", 1)
        return email.split("@")[0]
    if user_id.startswith("wa-") or user_id.startswith("tg-"):
        return None  # WhatsApp/Telegram users — keep it neutral
    return user_id


def _get_conversation_context(sid):
    """Pull recent messages to reference context."""
    con = db()
    rows = con.execute(
        "SELECT role, content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT 6",
        (sid,),
    ).fetchall()
    con.close()
    return [dict(r) for r in reversed(rows)]


def _add_suggestion(reply):
    """Add a random follow-up suggestion prompt."""
    if not reply:
        return reply
    suggestion = _pick(SUGGESTION_PROMPTS)
    if suggestion.lower() not in reply.lower():
        reply = f"{reply}\n\n{suggestion}"
    return reply


def _handle_message(sid, user_id, channel, text, shop="favemus"):
    started = time.time()
    session = load_session(sid, user_id, channel, shop)
    add_message(sid, "user", text)

    collected = json.loads(session["collected"] or "{}")
    collected.update(extract_entities(text))
    state = session["state"]
    pending_tool = session["pending_tool"]
    reply = None
    action = None
    tool_call = None
    analysis = None
    routing = None
    customer_name = _get_customer_name(user_id)

    if state == "handed_off":
        reply = _pick(HANDOFF_REPLIES).format(tid=collected.get("handoff_ticket_id", "pending"))
        analysis = {"tool": "human_handoff", "tool_confidence": 1.0}
        routing = None
        tool_call = None
        action = "handed_off"
        add_message(sid, "assistant", reply, {"action": action})
        save_session(sid, state, pending_tool, collected)
        log_decision(sid, text, analysis, tool_call, action, (time.time() - started) * 1000)
        return {"session_id": sid, "reply": reply, "state": state, "action": action, "analysis": analysis, "tool_call": None, "handoff": True}

    greeting = text.strip().lower().strip("!.,")
    if greeting in GREETINGS:
        reply = _pick(GREETING_REPLIES)
        if customer_name:
            reply = f"Hi {customer_name}! " + reply[3:] if reply.startswith("Hi ") else reply
        action = "greeting"
        state = "idle"
        pending_tool = None
        tool_call = None
        analysis = {"tool": "greeting", "tool_confidence": 1.0}
        routing = None
        save_session(sid, state, pending_tool, collected)
        add_message(sid, "assistant", reply, {"action": action, "analysis": analysis})
        log_decision(sid, text, analysis, tool_call, action, (time.time() - started) * 1000)
        return {"session_id": sid, "reply": reply, "state": state, "action": action, "analysis": analysis, "tool_call": None, "handoff": False, "routing": None}

    pending_action = collected.pop("pending_action", None)
    # Detect if user is starting a NEW topic instead of answering the pending question
    wants_human = bool(re.search(r"\b(human|agent|representative|someone real|talk to (?:a )?(?:human|person)\b)", text, re.I))
    new_topic = bool(
        greeting
        or wants_human
        or re.search(r"\border\b|FAV-\d+|#\d+", text, re.I)
        or re.search(r"\b(do you (?:have|sell|carry|stock)|are you (?:selling|stocking)|in stock|looking for|price of|how much (?:is|are)|product)\b", text, re.I)
    )
    if state == "awaiting_confirmation" and pending_action and not new_topic:
        ok = confirms(text) >= 0.6
        if ok:
            name = pending_action["name"]
            args = pending_action.get("arguments", {})
            result, reply = execute_tool(sid, name, args, text, shop)
            tool_call = {"name": name, "arguments": {k: v for k, v in args.items() if k in ("order_id", "size")}}
            action = "tool:" + name
            state = "idle"
            pending_tool = None
            # Add handoff ticket id to collected for reference
            if name == "human_handoff" and result and result.get("ticket_id"):
                collected["handoff_ticket_id"] = result["ticket_id"]
        else:
            reply = _pick(CANCEL_REPLIES)
            action = "cancelled"
            state = "idle"
            pending_tool = None
            tool_call = None
        analysis = {"tool": pending_action.get("name"), "tool_confidence": 1.0}
        routing = None
    elif state == "awaiting_confirmation" and pending_action and new_topic:
        # User started a new topic — drop the pending confirmation
        collected["pending_action"] = None
        reply = _pick(RESET_REPLIES)
        action = "reset"
        state = "idle"
        pending_tool = None
        tool_call = None
        analysis = {"tool": "reset", "tool_confidence": 1.0}
        routing = None
    elif state == "awaiting_order_id" and pending_tool and not new_topic:
        if collected.get("order_id"):
            name = pending_tool
            args = {"order_id": collected["order_id"]}
            if collected.get("size"):
                args["size"] = collected["size"]
            result, reply = execute_tool(sid, name, args, text, shop)
            tool_call = {"name": name, "arguments": args}
            action = "tool:" + name
            state = "idle"
            pending_tool = None
            analysis = {"tool": name, "tool_confidence": 1.0}
            routing = None
            # Add proactive suggestion after order lookup
            if name == "order_status" and result and result.get("ok"):
                reply = _add_suggestion(reply)
        elif re.search(r"\b(cancel|never mind|stop|start over)\b", text, re.I):
            reply = _pick(CANCEL_REPLIES)
            action = "cancelled"
            state = "idle"
            pending_tool = None
            tool_call = None
            analysis = {"tool": "cancelled", "tool_confidence": 1.0}
            routing = None
        else:
            reply = _pick(ASK_ORDER_REPLIES)
            action = "ask_order_id"
            state = "awaiting_order_id"
            tool_call = None
            analysis = {"tool": pending_tool, "tool_confidence": 1.0}
            routing = None
    elif state == "awaiting_order_id" and pending_tool and new_topic:
        # User started a new topic — drop the pending order lookup
        collected["pending_tool"] = None
        collected.pop("order_id", None)
        reply = _pick(RESET_REPLIES)
        action = "reset"
        state = "idle"
        pending_tool = None
        tool_call = None
        analysis = {"tool": "reset", "tool_confidence": 1.0}
        routing = None
    else:
        analysis, routing = analyse_message(text)
        tool = analysis["tool"]
        confidence = analysis["tool_confidence"]

        product_question = bool(
            re.search(
                r"\b(do you (?:have|sell|carry|stock)|are you (?:selling|stocking)|in stock|looking for|price of|how much (?:is|are)|product)\b",
                text,
                re.I,
            )
        ) and not re.search(r"\border\b|FAV-\d+|#\d+", text, re.I)
        if product_question:
            analysis = {**analysis, "tool": "search_products", "tool_confidence": 1.0}
            tool = "search_products"
            confidence = 1.0

        if tool == "human_handoff" or wants_human or analysis["sentiment"] >= 1.7:
            args = {"reason": text, "analysis": analysis}
            result, reply = execute_tool(sid, "human_handoff", args, text, shop)
            tool_call = {"name": "human_handoff", "arguments": {}}
            action = "human_handoff"
            state = "handed_off"
            pending_tool = None
            if result and result.get("ticket_id"):
                collected["handoff_ticket_id"] = result["ticket_id"]
                reply = reply.format(tid=result["ticket_id"])
        elif confidence < CONFIDENCE_FLOOR:
            clarify_count = int(collected.get("clarify_count", 0)) + 1
            collected["clarify_count"] = clarify_count
            if clarify_count >= 2:
                collected["clarify_count"] = 0
                args = {"reason": text, "analysis": analysis}
                result, reply = execute_tool(sid, "human_handoff", args, text, shop)
                tool_call = {"name": "human_handoff", "arguments": {}}
                action = "human_handoff"
                state = "handed_off"
                pending_tool = None
                if result and result.get("ticket_id"):
                    collected["handoff_ticket_id"] = result["ticket_id"]
                    reply = reply.format(tid=result["ticket_id"])
            else:
                reply = _pick(CLARIFY_REPLIES)
                action = "clarify"
                state = "idle"
                pending_tool = None
                tool_call = None
            analysis = {"tool": "clarify", "tool_confidence": confidence, "clarify_count": clarify_count}
            routing = None
        else:
            args = {}
            if collected.get("order_id"):
                args["order_id"] = collected["order_id"]
            if collected.get("size"):
                args["size"] = collected["size"]

            if tool in ORDER_TOOLS and not args.get("order_id"):
                state = "awaiting_order_id"
                pending_tool = tool
                reply = _pick(ASK_ORDER_REPLIES)
                action = "ask_order_id"
                tool_call = None
            elif tool in ("initiate_return", "exchange_item"):
                collected["pending_action"] = {"name": tool, "arguments": {**args, "analysis": analysis}}
                state = "awaiting_confirmation"
                pending_tool = tool
                word = "return" if tool == "initiate_return" else "exchange"
                article = "a" if tool == "initiate_return" else "an"
                order_id = args.get("order_id") or "this order"
                reply = _pick(CONFIRM_REPLIES).format(article=article, word=word, order_id=order_id)
                action = "confirm"
                tool_call = None
            else:
                result, reply = execute_tool(sid, tool, {**args, "analysis": analysis}, text, shop)
                tool_call = {"name": tool, "arguments": {k: v for k, v in args.items() if k in ("order_id", "size")}}
                action = "tool:" + tool
                state = "idle"
                pending_tool = None
                # Format dynamic replies based on tool result
                if tool == "order_status" and result and result.get("ok"):
                    reply = _format_order_reply(result)
                    reply = _add_suggestion(reply)
                elif tool == "search_products" and result and result.get("results"):
                    items = "\n".join(_format_product_item(h) for h in result["results"][:4])
                    reply = _pick(PRODUCT_FOUND_REPLIES).format(items=items)
                    reply = _add_suggestion(reply)
                elif tool == "search_products" and result and not result.get("results"):
                    reply = _pick(PRODUCT_NOT_FOUND_REPLIES)
                    reply = _add_suggestion(reply)

    save_session(sid, state, pending_tool, collected)
    add_message(sid, "assistant", reply, {"action": action, "tool_call": tool_call, "analysis": analysis})
    log_decision(sid, text, analysis, tool_call, action, (time.time() - started) * 1000)

    return {
        "session_id": sid,
        "reply": reply,
        "state": state,
        "action": action,
        "analysis": analysis,
        "tool_call": tool_call,
        "handoff": state == "handed_off",
        "routing": routing,
    }
@asynccontextmanager
async def lifespan(app):
    global router
    init_db()
    router = Router(default="english", max_loaded=1, device=os.getenv("LAYA_DEVICE", "cpu"))
    router.preload(["english"])
    try:
        router.predict("warmup message about an order", QUESTIONS, model="english")
        router.predict("yes", CONFIRM_Q, model="english")
        print("model warmed", flush=True)
    except Exception as exc:
        print("warmup failed:", exc, flush=True)
    yield
    router.unload()


app = FastAPI(title="Favemus Support Harness", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class ChatIn(BaseModel):
    message: str
    session_id: str | None = None
    user_id: str | None = None
    channel: str = "web"
    shop: str = "favemus"


class PurgeIn(BaseModel):
    shop: str
    customer_id: str | None = None


def _require_admin_token(request: Request):
    if not HARNESS_ADMIN_TOKEN:
        raise HTTPException(503, "admin token not configured")
    if request.headers.get("x-harness-token") != HARNESS_ADMIN_TOKEN:
        raise HTTPException(403, "forbidden")



@app.get("/healthz")
async def healthz():
    counts = {}
    try:
        con = db()
        for t in ("users", "sessions", "messages", "tickets", "decisions", "orders", "products", "tenants"):
            try:
                counts[t] = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            except Exception:
                counts[t] = 0
        con.close()
    except Exception:
        counts = {}

    return {
        "status": "ok",
        "ready": router is not None,
        "uptime_seconds": round(time.time() - _START_TIME, 1) if '_START_TIME' in globals() else 0,
        "layers": {
            "ai": "laya",
            "db": "sqlite",
            "web_server": "nginx",
            "process_manager": "systemd",
        },
        "data": counts,
        "service": "favemus",
        "version": "2.0.0",
    }


@app.get("/health")
def health():
    return {"status": "ok", "ready": router is not None, "laya": laya.__version__, "model": "english", "harness": "2.0.0"}


@app.get("/harness/tools")
def tools():
    return {
        "tools": [
            {"name": "order_status", "requires": ["order_id"]},
            {"name": "refund_status", "requires": ["order_id"]},
            {"name": "initiate_return", "requires": ["order_id"], "confirm": True},
            {"name": "exchange_item", "requires": ["order_id", "size?"], "confirm": True},
            {"name": "search_products", "requires": []},
            {"name": "human_handoff", "requires": []},
        ]
    }


@app.post("/chat")
async def chat(req: ChatIn, request: Request):
    sid = req.session_id or ("s-" + uuid.uuid4().hex[:12])
    # Client layer: if a logged-in user chats, tie the session to their account
    user_id = req.user_id
    if not user_id:
        me = _current_user(request)
        if me and me.get("id"):
            user_id = f"user:{me['email']}"
    result = await run_in_threadpool(handle_message, sid, user_id, req.channel, req.message, req.shop)
    return result


@app.post("/support/triage")
async def triage(req: ChatIn):
    def run():
        return analyse_message(req.message)

    analysis, routing = await run_in_threadpool(run)
    return {"analysis": analysis, "routing": routing}





@app.post("/harness/tickets/{tid}/close")
def close_ticket(tid: int, request: Request):
    _require_admin(request)
    con = db()
    con.execute("UPDATE tickets SET status='closed', updated_at=? WHERE id=?", (ts(), tid))
    con.commit()
    con.close()
    return {"ticket_id": tid, "status": "closed"}


@app.post("/harness/purge")
def purge(req: PurgeIn, request: Request):
    _require_admin(request)
    con = db()
    if req.customer_id:
        rows = con.execute(
            "SELECT id FROM sessions WHERE shop=? AND user_id=?",
            (req.shop, req.customer_id),
        ).fetchall()
    else:
        rows = con.execute("SELECT id FROM sessions WHERE shop=?", (req.shop,)).fetchall()
    session_ids = [row["id"] for row in rows]
    for sid in session_ids:
        con.execute("DELETE FROM messages WHERE session_id=?", (sid,))
        con.execute("DELETE FROM decisions WHERE session_id=?", (sid,))
        con.execute("DELETE FROM tickets WHERE session_id=?", (sid,))
        con.execute("DELETE FROM sessions WHERE id=?", (sid,))
    if not req.customer_id:
        con.execute("DELETE FROM tickets WHERE shop=?", (req.shop,))
    con.commit()
    con.close()
    return {
        "shop": req.shop,
        "customer_id": req.customer_id,
        "sessions_deleted": len(session_ids),
    }


@app.get("/channels")
def channels():
    return {"manual": True, "platform": "manual", "whatsapp_configured": _whatsapp_configured()}


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Favemus Support Harness</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: system-ui, sans-serif; margin: 0; background: #f6f1ec; color: #241d18; }
  header { padding: 14px 20px; background: #7a3e2e; color: #fff; display: flex; justify-content: space-between; align-items: center; }
  header b { font-size: 17px; }
  header button { background: #a35c46; color: #fff; border: 0; padding: 8px 14px; border-radius: 8px; cursor: pointer; font: inherit; }
  main { display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; max-width: 1100px; margin: 16px auto; padding: 0 16px; height: calc(100vh - 90px); }
  .panel { background: #fff; border: 1px solid #e6dcd2; border-radius: 12px; display: flex; flex-direction: column; overflow: hidden; }
  .panel h2 { margin: 0; padding: 12px 16px; font-size: 14px; text-transform: uppercase; letter-spacing: .04em; color: #8a6f60; border-bottom: 1px solid #eee4da; }
  #log { flex: 1; overflow: auto; padding: 16px; display: flex; flex-direction: column; gap: 10px; }
  .msg { max-width: 85%; padding: 10px 14px; border-radius: 14px; line-height: 1.45; white-space: pre-wrap; font-size: 14px; }
  .user { align-self: flex-end; background: #7a3e2e; color: #fff; border-bottom-right-radius: 4px; }
  .bot { align-self: flex-start; background: #f1e9e1; border-bottom-left-radius: 4px; }
  .sys { align-self: center; font-size: 12px; color: #9a8578; }
  form { display: flex; gap: 8px; padding: 12px; border-top: 1px solid #eee4da; }
  input { flex: 1; padding: 12px; font: inherit; border: 1px solid #d8cabd; border-radius: 10px; }
  form button { padding: 0 20px; font: inherit; background: #7a3e2e; color: #fff; border: 0; border-radius: 10px; cursor: pointer; }
  pre { margin: 0; padding: 14px; overflow: auto; font-size: 12px; line-height: 1.5; flex: 1; }
  .badge { display: inline-block; font-size: 11px; padding: 2px 8px; border-radius: 999px; background: #efe2d6; margin-bottom: 8px; }
</style>
</head>
<body>
<header><b>Favemus support harness</b><span><a style="color:#fff" href="/client">Client layer</a> · <a style="color:#fff" href="/owner">My layer (Owner)</a> <button onclick="reset()">New session</button></span></header>
<main>
  <section class="panel">
    <h2>Conversation</h2>
    <div id="log"></div>
    <form onsubmit="send(event)">
      <input id="msg" placeholder="Type a customer message..." autocomplete="off">
      <button>Send</button>
    </form>
  </section>
  <section class="panel">
    <h2>Harness trace</h2>
    <pre id="trace">Waiting for a message...</pre>
  </section>
</main>
<script>
let sid = localStorage.getItem('favemus_sid');
if (!sid) { sid = 'web-' + Math.random().toString(36).slice(2, 12); localStorage.setItem('favemus_sid', sid); }
const log = document.getElementById('log');
const trace = document.getElementById('trace');

function add(text, cls) {
  const d = document.createElement('div');
  d.className = 'msg ' + cls;
  d.textContent = text;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}
function reset() {
  localStorage.removeItem('favemus_sid');
  location.reload();
}
async function send(e) {
  e.preventDefault();
  const input = document.getElementById('msg');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  add(text, 'user');
  add('Favemus is typing...', 'bot');
  trace.textContent = 'Thinking... (AI takes 2-5s)';
  try {
    const res = await fetch('/chat', {
      method: 'POST',
      headers: {'content-type': 'application/json'},
      body: JSON.stringify({message: text, session_id: sid, channel: 'web', shop: 'favemus'})
    });
    const data = await res.json();
    sid = data.session_id;
    localStorage.setItem('favemus_sid', sid);
    log.lastChild.textContent = data.reply;
    const badge = 'action=' + data.action + '  state=' + data.state + '  session=' + data.session_id;
    trace.innerHTML = '';
    const b = document.createElement('span');
    b.className = 'badge';
    b.textContent = badge;
    trace.appendChild(b);
    trace.appendChild(document.createTextNode('\\n\\n' + JSON.stringify({analysis: data.analysis, tool_call: data.tool_call, routing: data.routing}, null, 2)));
  } catch (err) {
    add('Error: ' + err, 'sys');
    trace.textContent = String(err);
  }
}
add('Hi! Try: "Where is my order FAV-1042?" or "I want to return FAV-2231, the dress is torn."', 'sys');
</script>
</body>
</html>"""



# ---------------------------------------------------------------------------
# Manual users, auth, orders, products (standalone — no Shopify/BigCommerce)
# ---------------------------------------------------------------------------

import hashlib
import hmac
import secrets
from fastapi.responses import JSONResponse

SESSION_COOKIE = "favemus_session"
SESSION_TTL_SECONDS = 7 * 24 * 3600
PBKDF2_ITERS = 200_000
ADMIN_EMAIL = os.getenv("FAVEMUS_ADMIN_EMAIL", "").strip().lower()
ADMIN_PASSWORD = os.getenv("FAVEMUS_ADMIN_PASSWORD", "").strip()
ALLOW_REGISTRATION = os.getenv("FAVEMUS_ALLOW_REGISTRATION", "true").strip().lower() not in ("false", "0", "no", "off")

def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERS)
    return f"pbkdf2_sha256${PBKDF2_ITERS}${salt.hex()}${dk.hex()}"

def _check_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_hex, hash_hex = stored.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(dk.hex(), hash_hex)
    except Exception:
        return False

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

def _create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc).timestamp() + SESSION_TTL_SECONDS
    con = db()
    con.execute("INSERT INTO auth_sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
                (_hash_token(token), user_id, expires, ts()))
    con.commit(); con.close()
    return token

def _user_from_session_token(token: str | None):
    if not token:
        return None
    con = db()
    row = con.execute(
        "SELECT u.* FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.is_active=1",
        (_hash_token(token), datetime.now(timezone.utc).timestamp()),
    ).fetchone()
    con.close()
    return dict(row) if row else None

def _current_user(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    user = _user_from_session_token(token)
    if user:
        return user
    # Legacy/service token fallback (keeps old integrations working)
    if HARNESS_ADMIN_TOKEN and request.headers.get("x-harness-token") == HARNESS_ADMIN_TOKEN:
        return {"id": 0, "email": "service", "name": "Service", "role": "admin", "is_active": 1}
    return None

def _require_login(request: Request):
    user = _current_user(request)
    if not user:
        raise HTTPException(401, "login required")
    return user

def _require_admin(request: Request):
    user = _require_login(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "admin required")
    return user

def _public_user(user: dict) -> dict:
    return {"id": user["id"], "email": user["email"], "name": user.get("name") or "",
            "role": user.get("role") or "user", "is_active": bool(user.get("is_active", 1)),
            "created_at": user.get("created_at")}

def _seed_manual_data():
    con = db()
    now = ts()
    for oid, o in ORDERS.items():
        con.execute(
            "INSERT OR IGNORE INTO orders(order_id,item,amount,currency,status,eta,refund,tracking_json,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (oid, o.get("item"), o.get("amount"), o.get("currency") or "INR", o.get("status"),
             o.get("eta"), o.get("refund"), json.dumps(o.get("tracking") or []), now, now))
    for p in CATALOG:
        con.execute(
            "INSERT OR IGNORE INTO products(sku,name,fabric,colors_json,price,currency,sizes_json,available,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
            (p["sku"], p["name"], p.get("fabric") or "", json.dumps(p.get("colors") or []),
             p.get("price") or 0, "INR", json.dumps(p.get("sizes") or []), 1, now, now))
    if ADMIN_EMAIL and ADMIN_PASSWORD:
        con.execute("INSERT OR IGNORE INTO users(email,name,pass_hash,role,is_active,created_at) VALUES(?,?,?,?,1,?)",
                    (ADMIN_EMAIL, "Admin", _hash_password(ADMIN_PASSWORD), "admin", now))
    con.commit(); con.close()

class RegisterIn(BaseModel):
    email: str
    password: str
    name: str | None = None

class LoginIn(BaseModel):
    email: str
    password: str

class UserCreateIn(BaseModel):
    email: str
    password: str
    name: str | None = None
    role: str = "user"

class OrderIn(BaseModel):
    order_id: str
    item: str = "your order"
    amount: float = 0
    currency: str = "INR"
    status: str = "processing"
    eta: str | None = None
    refund: str | None = None
    tracking: list | None = None

class ProductIn(BaseModel):
    sku: str
    name: str
    fabric: str = ""
    colors: list = []
    price: float = 0
    currency: str = "INR"
    sizes: list = []
    available: bool = True

@app.post("/auth/logout")
async def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        con = db(); con.execute("DELETE FROM auth_sessions WHERE token_hash=?", (_hash_token(token),)); con.commit(); con.close()
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp

@app.get("/auth/me")
async def me(request: Request):
    tid = get_tenant_id(request)
    user = _current_user_in_tenant(request, tid)
    if not user:
        raise HTTPException(401, "login required")
    return {"user": _public_user_tenant(user), "tenant_id": tid}

@app.get("/chat.js")
def chat_js():
    js = ""
    js += "(() => {\n"
    js += "  const root = document.getElementById('fv-root') || (() => { const d = document.createElement('div'); d.id='fv-root'; document.body.appendChild(d); return d; })();\n"
    js += "  const style = document.createElement('style');\n"
    js += "  style.textContent = [ '.fv-btn{position:fixed;right:20px;bottom:20px;z-index:99999;border:0;border-radius:999px;background:#7a3e2e;color:#fff;padding:14px 20px;font:inherit;cursor:pointer}', '.fv-panel{position:fixed;right:20px;bottom:76px;z-index:99999;width:340px;max-width:calc(100vw - 40px);height:430px;background:#fff;border:1px solid #e6dcd2;border-radius:14px;box-shadow:0 20px 50px rgba(0,0,0,.2);display:none;flex-direction:column;overflow:hidden}', '.fv-panel.open{display:flex}', '.fv-log{flex:1;overflow:auto;padding:14px;display:flex;flex-direction:column;gap:8px}', '.fv-msg{max-width:85%;padding:10px 12px;border-radius:14px;line-height:1.4;font-size:14px;white-space:pre-wrap}', '.fv-user{align-self:flex-end;background:#7a3e2e;color:#fff}', '.fv-bot{align-self:flex-start;background:#f1e9e1}', '.fv-form{display:flex;gap:8px;padding:10px;border-top:1px solid #eee}', '.fv-form input{flex:1;padding:10px;border:1px solid #ddd;border-radius:10px;font:inherit}', '.fv-form button{border:0;border-radius:10px;background:#7a3e2e;color:#fff;padding:0 16px;font:inherit;cursor:pointer}' ].join('\\n');\n"
    js += "  document.head.appendChild(style);\n"
    js += "  let sessionId = localStorage.getItem('favemus_sid'); if (!sessionId) { sessionId = 'web-' + Math.random().toString(36).slice(2,12); localStorage.setItem('favemus_sid', sessionId); }\n"
    js += "  const btn=document.createElement('button'); btn.className='fv-btn'; btn.textContent='Support';\n"
    js += "  const panel=document.createElement('div'); panel.className='fv-panel'; panel.innerHTML='<div class=\"fv-log\"></div><form class=\"fv-form\"><input placeholder=\"Ask about an order or product...\" autocomplete=\"off\"><button>Send</button></form>';\n"
    js += "  root.append(btn,panel); const logEl=panel.querySelector('.fv-log'); const form=panel.querySelector('.fv-form'); const input=panel.querySelector('input');\n"
    js += "  function add(t,c){const d=document.createElement('div');d.className='fv-msg '+c;d.textContent=t;logEl.appendChild(d);logEl.scrollTop=logEl.scrollHeight;}\n"
    js += "  btn.addEventListener('click',()=>panel.classList.toggle('open'));\n"
    js += "  form.addEventListener('submit',async(e)=>{e.preventDefault();const m=input.value.trim();if(!m)return;input.value='';add(m,'fv-user');add('Typing...','fv-bot');try{const ctl=new AbortController();const to=setTimeout(()=>ctl.abort(),60000);const r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},signal:ctl.signal,body:JSON.stringify({message:m,session_id:sessionId,channel:'web',shop:'favemus'})});clearTimeout(to);const d=await r.json();sessionId=d.session_id||sessionId;localStorage.setItem('favemus_sid',sessionId);logEl.lastChild.textContent=d.reply||'Sorry, I could not answer.';}catch{logEl.lastChild.textContent='Support service is unavailable. Try again.';}});\n"
    js += "  add('Hi! Ask about an order, return, exchange, or product.','fv-bot');\n"
    js += "})();\n"
    return Response(js, media_type="application/javascript; charset=utf-8")

AUTH_PAGE_CSS = "body{font-family:system-ui,sans-serif;background:#f6f1ec;margin:0;display:grid;place-items:center;min-height:100vh}.card{background:#fff;border:1px solid #e6dcd2;border-radius:14px;padding:28px;width:min(420px,92vw);box-sizing:border-box}h1{margin:0 0 8px;font-size:22px}label{display:block;margin:14px 0 6px;font-size:14px}input{width:100%;padding:11px;border:1px solid #d8cabd;border-radius:10px;font:inherit;box-sizing:border-box}button{width:100%;margin-top:18px;padding:12px;background:#7a3e2e;color:#fff;border:0;border-radius:10px;font:inherit;cursor:pointer}.err{color:#b00020;font-size:14px;margin-top:10px}.muted{font-size:14px;color:#8a6f60}"

@app.get("/login", response_class=HTMLResponse)
def login_page():
    html = _tpl("auth.html")
    html = html.replace("{{TITLE}}", "Login").replace("{{HEADING}}", "Welcome back").replace("{{SUB}}", "Log in to your Favemus account.")
    html = html.replace("{{FIELDS}}", '<label>Email<input id="email" type="email" required></label><label>Password<input id="pw" type="password" required></label>')
    html = html.replace("{{BUTTON}}", "Login").replace("{{ENDPOINT}}", "/auth/login")
    html = html.replace("{{BODY}}", "{email:document.getElementById('email').value,password:document.getElementById('pw').value}")
    html = html.replace("{{FOOT}}", 'No account? <a href="/register">Register</a> · <a href="/">Home</a>')
    return HTMLResponse(html)

@app.get("/register", response_class=HTMLResponse)
def register_page():
    html = _tpl("auth.html")
    html = html.replace("{{TITLE}}", "Register").replace("{{HEADING}}", "Create your account").replace("{{SUB}}", "Manual setup — the first account becomes admin.")
    html = html.replace("{{FIELDS}}", '<label>Name<input id="name" type="text"></label><label>Email<input id="email" type="email" required></label><label>Password (8+ chars)<input id="pw" type="password" required minlength="8"></label>')
    html = html.replace("{{BUTTON}}", "Register").replace("{{ENDPOINT}}", "/auth/register")
    html = html.replace("{{BODY}}", "{name:document.getElementById('name').value,email:document.getElementById('email').value,password:document.getElementById('pw').value}")
    html = html.replace("{{FOOT}}", 'Already registered? <a href="/login">Login</a> · <a href="/">Home</a>')
    return HTMLResponse(html)

@app.get("/admin", response_class=HTMLResponse)
def admin_page():
    return RedirectResponse("/owner", status_code=302)

@app.get("/owner", response_class=HTMLResponse)
def owner_page():
    # MY LAYER (owner): modern console. APIs enforce admin role.
    return HTMLResponse(_tpl("owner.html"))

def _owner_dashboard_html():
    html = _unused_dashboard().body.decode()
    return html.replace("<title>Admin — Favemus</title>", "<title>Owner (My Layer) — Favemus</title>").replace("Favemus admin", "Favemus · MY LAYER (Owner)").replace('href="/">Chat', 'href="/">Chat</a> · <a style="color:#fff" href="/client">Client layer')

def _unused_dashboard():
    return HTMLResponse("""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin — Favemus</title><style>body{font-family:system-ui,sans-serif;background:#f6f1ec;margin:0;color:#241d18}header{padding:14px 20px;background:#7a3e2e;color:#fff;display:flex;justify-content:space-between;align-items:center}header button{background:#a35c46;color:#fff;border:0;padding:8px 14px;border-radius:8px;cursor:pointer;font:inherit}main{max-width:1100px;margin:16px auto;padding:0 16px}.panel{background:#fff;border:1px solid #e6dcd2;border-radius:12px;padding:16px;margin-bottom:16px}table{width:100%;border-collapse:collapse;font-size:14px}td,th{padding:8px;border-bottom:1px solid #eee;text-align:left}input,select{padding:8px;border:1px solid #d8cabd;border-radius:8px;font:inherit;margin:4px}button{background:#7a3e2e;color:#fff;border:0;padding:8px 14px;border-radius:8px;cursor:pointer;font:inherit}.small{background:#efe2d6;color:#241d18;padding:4px 10px;font-size:13px}.muted{color:#8a6f60;font-size:14px}</style></head><body><header><b>Favemus admin <span id="who" class="muted"></span></b><span><a style="color:#fff" href="/">Chat</a> <button onclick="logout()">Logout</button></span></header><main>
<div class="panel"><h2>Dashboard</h2><div id="metrics">Loading…</div></div>
<div class="panel" id="users-panel"><h2>Manual users (admin only)</h2><form onsubmit="return addUser(event)"><input id="nu-email" type="email" placeholder="email" required><input id="nu-pw" type="password" placeholder="password (8+)" required minlength="8"><input id="nu-name" placeholder="name"><select id="nu-role"><option value="user">user</option><option value="admin">admin</option></select><button>Create user</button></form><table id="users"></table></div>
<div class="panel"><h2>Manual orders</h2><form onsubmit="return addOrder(event)"><input id="no-id" placeholder="order_id e.g. FAV-1042" required><input id="no-item" placeholder="item"><input id="no-amount" type="number" step="0.01" placeholder="amount"><input id="no-status" placeholder="status e.g. processing"><input id="no-eta" placeholder="eta YYYY-MM-DD"><button>Save order</button></form><table id="orders"></table></div>
<div class="panel"><h2>Products</h2><form onsubmit="return addProduct(event)"><input id="np-sku" placeholder="sku" required><input id="np-name" placeholder="name" required><input id="np-price" type="number" step="0.01" placeholder="price"><input id="np-sizes" placeholder="sizes comma,separated"><button>Save product</button></form><table id="products"></table></div>
<div class="panel"><h2>WhatsApp AI customer service</h2><div id="wa-status" class="muted">Loading…</div><form onsubmit="return waTest(event)"><input id="wa-to" placeholder="phone e.g. 919876543210" required><input id="wa-msg" placeholder="test message"><button>Send WhatsApp test</button></form><p class="muted">Webhook: <code>https://favemus.zealstore.me/whatsapp/webhook</code> · Setup guide: <a href="/whatsapp-guide.html">/whatsapp-guide.html</a></p></div>
<div class="panel"><h2>Conversations</h2><table id="sessions"></table></div>
<div class="panel"><h2>Tickets</h2><table id="tickets"></table></div>
</main><script>
const $=id=>document.getElementById(id);
async function api(p,opt){const ctl=new AbortController();const _t=setTimeout(()=>ctl.abort(),15000);opt={...(opt||{}),signal:ctl.signal};const r=await fetch(p,opt);clearTimeout(_t);if(r.status===401){location.href='/login';throw new Error('login')}if(!r.ok)throw new Error(await r.text());return r.json()}
async function logout(){await fetch('/auth/logout',{method:'POST'});location.href='/login'}
async function addUser(e){e.preventDefault();await api('/harness/users',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({email:$('nu-email').value,password:$('nu-pw').value,name:$('nu-name').value,role:$('nu-role').value})});load()}
async function addOrder(e){e.preventDefault();await api('/harness/orders',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({order_id:$('no-id').value,item:$('no-item').value||'your order',amount:Number($('no-amount').value||0),status:$('no-status').value||'processing',eta:$('no-eta').value||null})});load()}
async function addProduct(e){e.preventDefault();await api('/harness/products',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({sku:$('np-sku').value,name:$('np-name').value,price:Number($('np-price').value||0),sizes:$('np-sizes').value.split(',').map(s=>s.trim()).filter(Boolean)})});load()}
async function toggle(u){await api('/harness/users/'+u+'/toggle-active',{method:'POST'});load()}
async function del(u){await api('/harness/users/'+u,{method:'DELETE'});load()}
async function delO(o){await api('/harness/orders/'+encodeURIComponent(o),{method:'DELETE'});load()}
async function delP(s){await api('/harness/products/'+encodeURIComponent(s),{method:'DELETE'});load()}
async function closeT(t){await api('/harness/tickets/'+t+'/close',{method:'POST'});load()}
async function waTest(e){e.preventDefault();const r=await api('/harness/whatsapp/test',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({to:$('wa-to').value,message:$('wa-msg').value||'Hello from Favemus AI Support (test message).'})});alert(r.ok?'Sent!':'Not sent (check config/logs)')}
async function load(){
  const me=await api('/auth/me'); $('who').textContent='('+me.user.email+' · '+me.user.role+')';
  try{const w=await api('/whatsapp/status');$('wa-status').textContent=w.configured?'✅ Configured (Phone Number ID set, API '+w.api_version+')':'⚠️ Not configured yet — set WHATSAPP tokens in favemus.env (see /whatsapp-guide.html)'}catch(e){}
  let m={decisions:0,open_tickets:0,handoff_rate:0,avg_latency_ms:0}; try{m=await api('/harness/metrics')}catch(e){} $('metrics').textContent=m.decisions+' AI decisions · '+m.open_tickets+' open tickets · '+Math.round(m.handoff_rate*100)+'% handoffs · '+m.avg_latency_ms+' ms avg';
  $('sessions').innerHTML='<tr><th>Session</th><th>User</th><th>State</th><th>Updated</th></tr>'+((await api('/harness/sessions')).sessions||[]).map(s=>'<tr><td>'+s.id+'</td><td>'+(s.user_id||'anonymous')+'</td><td>'+(s.state||'')+'</td><td>'+(s.updated_at||'')+'</td></tr>').join('');
  $('tickets').innerHTML='<tr><th>#</th><th>Kind</th><th>Status</th><th></th></tr>'+((await api('/harness/tickets')).tickets||[]).map(t=>'<tr><td>#'+t.id+'</td><td>'+(t.kind||'')+'</td><td>'+(t.status||'')+'</td><td>'+(t.status==='open'?'<button class="small" onclick="closeT('+t.id+')">Close</button>':'')+'</td></tr>').join('');
  let orders=[]; try{orders=(await api('/harness/orders')).orders||[]}catch(e){}
  $('orders').innerHTML='<tr><th>Order</th><th>Item</th><th>Status</th><th></th></tr>'+orders.map(o=>'<tr><td>'+o.order_id+'</td><td>'+(o.item||'')+'</td><td>'+(o.status||'')+'</td><td><button class="small" onclick="delO(\''+o.order_id+'\')">Delete</button></td></tr>').join('');
  let prods=[]; try{prods=(await api('/harness/products')).products||[]}catch(e){}
  $('products').innerHTML='<tr><th>SKU</th><th>Name</th><th>Price</th><th></th></tr>'+prods.map(p=>'<tr><td>'+p.sku+'</td><td>'+(p.name||'')+'</td><td>'+(p.price||'')+'</td><td><button class="small" onclick="delP(\''+p.sku+'\')">Delete</button></td></tr>').join('');
  try{const u=await api('/harness/users');$('users').innerHTML='<tr><th>ID</th><th>Email</th><th>Role</th><th>Active</th><th></th></tr>'+u.users.map(x=>'<tr><td>'+x.id+'</td><td>'+x.email+'</td><td>'+x.role+'</td><td>'+x.is_active+'</td><td><button class="small" onclick="toggle('+x.id+')">Toggle</button> <button class="small" onclick="del('+x.id+')">Delete</button></td></tr>').join('');}catch(e){$('users-panel').innerHTML='<h2>Manual users</h2><p class="muted">Admin only — your account is not an admin.</p>'}
}
load().catch(e=>{if(String(e)!=='login')document.body.insertAdjacentHTML('beforeend','<p>'+e+'</p>')});
</script></body></html>""")



# ---------------------------------------------------------------------------
# WhatsApp channel (Meta WhatsApp Business Cloud API)
# Customer messages in -> AI harness (same brain as /chat) -> reply on WhatsApp.
# Setup (one-time, in Meta dashboard):
#   1. Create a Meta app -> add WhatsApp product -> get a phone number.
#   2. Webhook URL: https://favemus.zealstore.me/whatsapp/webhook
#      Verify token: set WHATSAPP_VERIFY_TOKEN (same value in Meta dashboard).
#   3. Subscribe to "messages" field. Set env vars below, restart favemus.service.
# Env is read from favemus.env / systemd — never commit real tokens.
# ---------------------------------------------------------------------------

WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "").strip()
WHATSAPP_ACCESS_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "").strip()
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "").strip()
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "").strip()
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v21.0").strip() or "v21.0"

def _whatsapp_configured() -> bool:
    return bool(WHATSAPP_ACCESS_TOKEN and WHATSAPP_PHONE_NUMBER_ID)

def _whatsapp_send(to: str, text: str) -> bool:
    """Send one text message via Cloud API. Returns True on success."""
    if not _whatsapp_configured():
        print("whatsapp send skipped: not configured (missing token or phone_number_id)", flush=True)
        return False
    url = f"https://graph.facebook.com/{WHATSAPP_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    body = json.dumps({
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
        print(f"whatsapp sent to {to}: {data.get('messages', [{}])[0].get('id', '?')}", flush=True)
        return True
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        print(f"whatsapp send failed ({exc.code}) to {to}: {detail}", flush=True)
        return False
    except Exception as exc:
        print(f"whatsapp send error to {to}: {exc}", flush=True)
        return False

def _whatsapp_send_long(to: str, text: str) -> bool:
    """WhatsApp text limit is 4096 chars — split if needed."""
    ok = True
    for i in range(0, max(len(text), 1), 4000):
        ok = _whatsapp_send(to, text[i:i + 4000]) and ok
    return ok

def _process_whatsapp_message(wa_id: str, text: str, msg_id: str | None = None):
    """Run the AI harness for one WhatsApp message and reply on WhatsApp."""
    if msg_id:
        con = db()
        cur = con.execute("INSERT OR IGNORE INTO whatsapp_seen(message_id,wa_id,created_at) VALUES(?,?,?)",
                          (msg_id, wa_id, ts()))
        con.commit(); con.close()
        if cur.rowcount == 0:
            print(f"whatsapp duplicate {msg_id} ignored", flush=True)
            return
    sid = f"wa-{wa_id}"
    try:
        result = handle_message(sid, wa_id, "whatsapp", text, "favemus")
    except Exception as exc:
        print(f"whatsapp harness error {wa_id}: {exc}", flush=True)
        reply = "Sorry, I could not process that. Please try again or reply 'human' to reach an agent."
        _whatsapp_send_long(wa_id, reply)
        return
    reply = (result.get("reply") or "Sorry, I could not answer.").strip()
    _whatsapp_send_long(wa_id, reply)

@app.get("/whatsapp/webhook")
async def whatsapp_verify(request: Request):
    """Meta webhook verification handshake."""
    params = request.query_params
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN and WHATSAPP_VERIFY_TOKEN:
        return Response(params.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(403, "verification failed")

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    raw = await request.body()
    if WHATSAPP_APP_SECRET:
        sig = request.headers.get("x-hub-signature-256", "")
        expected = "sha256=" + hmac.new(WHATSAPP_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise HTTPException(403, "invalid signature")
    try:
        payload = json.loads(raw.decode() or "{}")
    except Exception:
        return {"ok": True}  # ack junk so Meta does not retry forever
    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {}) or {}
            # statuses (delivered/read receipts) have no messages — ignore
            for msg in value.get("messages", []) or []:
                wa_id = msg.get("from")
                if not wa_id:
                    continue
                msg_id = msg.get("id")
                mtype = msg.get("type")
                text = ""
                if mtype == "text":
                    text = (msg.get("text", {}) or {}).get("body", "") or ""
                else:
                    _whatsapp_send_long(wa_id, "I can only read text messages right now. Please type your question (for example: 'Where is my order FAV-1042?').")
                    continue
                if not text.strip():
                    continue
                print(f"whatsapp inbound from {wa_id}: {text[:80]}", flush=True)
                threading.Thread(target=_process_whatsapp_message, args=(wa_id, text[:2000], msg_id), daemon=True).start()
    return {"ok": True}

class WhatsAppTestIn(BaseModel):
    to: str
    message: str = "Hello from Favemus AI Support (test message)."

@app.get("/whatsapp/status")
async def whatsapp_status(request: Request):
    _require_login(request)
    return {
        "configured": _whatsapp_configured(),
        "phone_number_id_set": bool(WHATSAPP_PHONE_NUMBER_ID),
        "verify_token_set": bool(WHATSAPP_VERIFY_TOKEN),
        "app_secret_set": bool(WHATSAPP_APP_SECRET),
        "api_version": WHATSAPP_API_VERSION,
        "webhook_url": "https://favemus.zealstore.me/whatsapp/webhook",
        "note": "Set WHATSAPP_VERIFY_TOKEN + WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_NUMBER_ID in favemus.env, then restart favemus.service.",
    }

@app.post("/harness/whatsapp/test")
async def whatsapp_test(req: WhatsAppTestIn, request: Request):
    _require_admin(request)
    to = (req.to or "").strip().lstrip("+")
    if not to or not to.isdigit():
        raise HTTPException(400, "to must be digits only (country code + number, no +)")
    sent = _whatsapp_send_long(to, (req.message or "")[:4000])
    return {"ok": sent, "to": to, "configured": _whatsapp_configured()}



# ---------------------------------------------------------------------------
# LAYERS — all on the SAME server (this host), one process, three layers:
#
#   LAYER 1 · MY LAYER (Owner)   -> /owner  (admin only APIs: users, orders,
#                                   products, WhatsApp config, all sessions/tickets)
#   LAYER 2 · CLIENT LAYER       -> /client (public chat + WhatsApp; logged-in
#                                   clients see only their own chats/tickets)
#   LAYER 3 · AI + DATA LAYER    -> same server: Laya AI model + SQLite DB at
#                                   DB_PATH (users, sessions, messages, tickets,
#                                   decisions, orders, products, auth_sessions)
#
# Layer 1 and Layer 2 both talk to Layer 3 (handle_message / DB) in-process.
# No external AI provider, no external database — everything lives on this host.
# ---------------------------------------------------------------------------

@app.get("/harness/my/sessions")
async def my_sessions(request: Request):
    """CLIENT LAYER: a logged-in user sees only their own conversations."""
    me = _require_login(request)
    uid = f"user:{me['email']}"
    con = db()
    rows = con.execute("SELECT * FROM sessions WHERE user_id=? ORDER BY updated_at DESC LIMIT 50", (uid,)).fetchall()
    con.close()
    return {"sessions": [dict(r) for r in rows]}

@app.get("/harness/my/tickets")
async def my_tickets(request: Request):
    """CLIENT LAYER: a logged-in user sees only their own tickets."""
    me = _require_login(request)
    uid = f"user:{me['email']}"
    con = db()
    rows = con.execute(
        "SELECT t.* FROM tickets t JOIN sessions s ON s.id=t.session_id WHERE s.user_id=? ORDER BY t.id DESC LIMIT 50",
        (uid,)).fetchall()
    con.close()
    return {"tickets": [dict(r) for r in rows]}

@app.get("/layers/status")
async def layers_status(request: Request):
    """LAYER 3 introspection: confirms AI + data live on this same server."""
    con = db()
    counts = {}
    for t in ("users", "sessions", "messages", "tickets", "decisions", "orders", "products"):
        try:
            counts[t] = con.execute(f"SELECT COUNT(*) c FROM {t}").fetchone()["c"]
        except Exception:
            counts[t] = 0
    con.close()
    return {
        "architecture": "3 layers on the same server (this host)",
        "layers": [
            {"name": "MY LAYER (Owner)", "path": "/owner", "access": "admin only", "role": "manage users, orders, products, WhatsApp, all chats/tickets"},
            {"name": "CLIENT LAYER", "path": "/client", "access": "public chat + logged-in own data", "role": "chat widget, WhatsApp, own conversations/tickets"},
            {"name": "AI + DATA LAYER", "path": "in-process (same server)", "access": "internal", "role": "Laya AI model + SQLite DB", "db_path": DB_PATH},
        ],
        "ai": {"ready": router is not None, "model": "english", "laya": laya.__version__},
        "data_counts": counts,
        "whatsapp_configured": _whatsapp_configured(),
    }

@app.get("/client", response_class=HTMLResponse)
def client_page():
    """CLIENT LAYER portal: public AI chat + (when logged in) my chats/tickets."""
    return HTMLResponse(_tpl("client.html"))

# -*- coding: utf-8 -*-
"""SaaS multi-tenant extension for Favemus harness.py.
Insert before the @app.get('/', ...) index route.
Requires: _hash_password, _check_password, _create_session, _hash_token,
          _user_from_session_token, db(), ts(), HARNESS_ADMIN_TOKEN,
          RegisterIn, LoginIn, OrderIn, ProductIn, ORDERS, CATALOG,
          lookup_order, lookup_products, execute_tool already defined.
"""

import sqlite3 as _sqlite3

# ---------------------------------------------------------------------------
# 0. Multi-tenant DB migration (runs inside init_db)
# ---------------------------------------------------------------------------
def _migrate_to_tenants(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS tenants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT,
            domain TEXT,
            plan TEXT DEFAULT 'starter',
            status TEXT DEFAULT 'active',
            stripe_customer_id TEXT,
            subscription_status TEXT DEFAULT 'trial',
            owner_email TEXT,
            created_at TEXT
        )
    """)
    def _col(table, col):
        return any(r[1] == col for r in con.execute(f"PRAGMA table_info({table})").fetchall())
    for table, col in [
        ("users", "tenant_id"),
        ("auth_sessions", "tenant_id"),
        ("sessions", "tenant_id"),
        ("messages", "tenant_id"),
        ("tickets", "tenant_id"),
        ("decisions", "tenant_id"),
        ("orders", "tenant_id"),
        ("products", "tenant_id"),
    ]:
        if not _col(table, col):
            con.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
    row = con.execute("SELECT id FROM tenants WHERE slug='default' LIMIT 1").fetchone()
    if not row:
        con.execute(
            "INSERT INTO tenants(slug,name,domain,plan,status,subscription_status,owner_email,created_at) "
            "VALUES('default','Default','favemus.zealstore.me','starter','active','active',NULL,?)",
            (ts(),))
    for table in ("users","auth_sessions","sessions","messages","tickets","decisions","orders","products"):
        try:
            con.execute(f"UPDATE {table} SET tenant_id='default' WHERE tenant_id IS NULL")
        except Exception:
            pass
    _ensure_telegram_table(con)
    con.commit()

def _seed_default_tenant_data():
    con = db()
    try:
        tid_row = con.execute("SELECT id FROM tenants WHERE slug='default' LIMIT 1").fetchone()
        default_tid = "default"
        now = ts()
        for p in CATALOG:
            con.execute("INSERT INTO products(sku,name,fabric,colors_json,price,currency,sizes_json,available,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(sku) DO UPDATE SET name=excluded.name,fabric=excluded.fabric,colors_json=excluded.colors_json,price=excluded.price,currency=excluded.currency,sizes_json=excluded.sizes_json,available=excluded.available,updated_at=excluded.updated_at,tenant_id=excluded.tenant_id",
                        (p["sku"], p["name"], p.get("fabric") or "", json.dumps(p.get("colors") or []),
                         p.get("price") or 0, "INR", json.dumps(p.get("sizes") or []), 1, now, now, default_tid))
        now = ts()
        for oid, o in ORDERS.items():
            con.execute("INSERT INTO orders(order_id,item,amount,currency,status,eta,refund,tracking_json,created_at,updated_at,tenant_id) VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                        "ON CONFLICT(order_id) DO UPDATE SET item=excluded.item,amount=excluded.amount,currency=excluded.currency,status=excluded.status,eta=excluded.eta,refund=excluded.refund,tracking_json=excluded.tracking_json,updated_at=excluded.updated_at,tenant_id=excluded.tenant_id",
                        (oid, o.get("item"), o.get("amount"), o.get("currency") or "INR", o.get("status"),
                         o.get("eta"), o.get("refund"), json.dumps(o.get("tracking") or []), now, now, default_tid))
        con.commit()
    finally:
        con.close()

# ---------------------------------------------------------------------------
# 1. Tenant resolution
# ---------------------------------------------------------------------------
TENANT_HOST_SUFFIX = ".favemus.zealstore.me"

def _resolve_tenant_from_host(host: str | None):
    if not host:
        return None
    h = host.split(":")[0].lower()
    if h.endswith(TENANT_HOST_SUFFIX):
        return h[: -len(TENANT_HOST_SUFFIX)]
    if h in ("favemus.zealstore.me", "www.favemus.zealstore.me"):
        return "default"
    return None

def _resolve_tenant_from_path(path: str):
    parts = [p for p in path.split("/") if p]
    if parts and parts[0] == "t" and len(parts) >= 2:
        return parts[1]
    return None

def get_tenant_id(request: Request) -> str:
    # X-Tenant-Id set by nginx from Host subdomain or /t/<slug>/ path prefix
    hdr = request.headers.get("x-tenant-id")
    if hdr:
        return hdr.strip().lower()
    return (_resolve_tenant_from_host(request.headers.get("host"))
            or _resolve_tenant_from_path(request.url.path)
            or "default")

def require_tenant(request: Request):
    tid = get_tenant_id(request)
    con = db()
    row = con.execute("SELECT * FROM tenants WHERE slug=?", (tid,)).fetchone()
    con.close()
    if not row:
        raise HTTPException(404, "tenant not found")
    if row["status"] != "active":
        raise HTTPException(403, "tenant suspended")
    return dict(row)

# ---------------------------------------------------------------------------
# 2. Super admin (HARNESS_ADMIN_TOKEN) — NOT per-tenant admin check
# ---------------------------------------------------------------------------
def _require_super_admin(request: Request):
    if not HARNESS_ADMIN_TOKEN or request.headers.get("x-harness-token") != HARNESS_ADMIN_TOKEN:
        raise HTTPException(403, "super admin token required (X-Harness-Token)")

# ---------------------------------------------------------------------------
# 3. Tenant-scoped auth helpers
# ---------------------------------------------------------------------------
def _current_user_in_tenant(request: Request, tenant_id: str):
    token = request.cookies.get(SESSION_COOKIE)
    user = _user_from_session_token(token)
    if user and user.get("tenant_id") == tenant_id:
        return user
    if HARNESS_ADMIN_TOKEN and request.headers.get("x-harness-token") == HARNESS_ADMIN_TOKEN:
        return {"id": 0, "email": "service", "name": "Service", "role": "admin", "is_active": 1, "tenant_id": tenant_id}
    return None

def require_login_in_tenant(request: Request):
    tid = get_tenant_id(request)
    user = _current_user_in_tenant(request, tid)
    if not user:
        raise HTTPException(401, "login required")
    return user, tid

def require_admin_in_tenant(request: Request):
    user, tid = require_login_in_tenant(request)
    if user.get("role") != "admin":
        raise HTTPException(403, "admin required")
    return user, tid

def _public_user_tenant(user: dict) -> dict:
    return {
        "id": user["id"], "email": user.get("email") or "", "name": user.get("name") or "",
        "role": user.get("role") or "user", "is_active": bool(user.get("is_active", 1)),
        "tenant_id": user.get("tenant_id"), "created_at": user.get("created_at"),
    }

# ---------------------------------------------------------------------------
# 4. Super-admin tenant management
# ---------------------------------------------------------------------------
@app.get("/saas/tenants")
async def saas_list_tenants(request: Request):
    _require_super_admin(request)
    con = db()
    rows = con.execute("SELECT * FROM tenants ORDER BY id").fetchall()
    con.close()
    return {"tenants": [dict(r) for r in rows]}

class TenantCreateIn(BaseModel):
    slug: str
    name: str | None = None
    domain: str | None = None
    plan: str = "starter"
    owner_email: str | None = None
    owner_password: str | None = None
    owner_name: str | None = None

@app.post("/saas/tenants")
async def saas_create_tenant(req: TenantCreateIn, request: Request):
    _require_super_admin(request)
    slug = (req.slug or "").strip().lower()
    if not slug or not slug.replace("-", "").isalnum():
        raise HTTPException(400, "slug must be lowercase alphanumeric with hyphens")
    con = db()
    if con.execute("SELECT id FROM tenants WHERE slug=?", (slug,)).fetchone():
        con.close(); raise HTTPException(409, "tenant slug already exists")
    now = ts()
    cur = con.execute(
        "INSERT INTO tenants(slug,name,domain,plan,status,subscription_status,owner_email,created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (slug, req.name or slug, req.domain, req.plan, "active", "trial", req.owner_email, now))
    tid = cur.lastrowid
    owner_email = (req.owner_email or f"owner@{slug}.example.local").strip().lower()
    owner_pw = req.owner_password or "ChangeMe123!"
    if len(owner_pw) < 8:
        owner_pw = "ChangeMe123!"
    cur2 = con.execute(
        "INSERT INTO users(email,name,pass_hash,role,is_active,tenant_id,created_at) "
        "VALUES(?,?,?,?,1,?,?)",
        (owner_email, (req.owner_name or "Owner").strip(), _hash_password(owner_pw), "admin", slug, now))
    uid = cur2.lastrowid
    con.commit(); con.close()
    token = _create_session(uid)
    return {
        "tenant": {"id": tid, "slug": slug, "name": req.name or slug, "plan": req.plan},
        "owner_email": owner_email,
        "owner_password": owner_pw,
        "login_url": f"https://{slug}.favemus.zealstore.me/login",
        "session_token": token,
    }

@app.post("/saas/tenants/{slug}/suspend")
async def saas_suspend_tenant(slug: str, request: Request):
    _require_super_admin(request)
    con = db()
    con.execute("UPDATE tenants SET status='suspended' WHERE slug=?", (slug,))
    con.commit(); con.close()
    return {"ok": True, "slug": slug, "status": "suspended"}

@app.post("/saas/webhooks/stripe")
async def saas_stripe_webhook(request: Request):
    body = await request.body()
    try:
        payload = json.loads(body.decode() or "{}")
    except Exception:
        return {"ok": True}
    event_type = payload.get("type", "")
    data = payload.get("data", {}).get("object", {}) or {}
    customer_id = data.get("customer")
    sub_status = data.get("status")
    con = db()
    if customer_id:
        con.execute("UPDATE tenants SET subscription_status=? WHERE stripe_customer_id=?", (sub_status or "active", customer_id))
    con.commit(); con.close()
    return {"ok": True, "event": event_type}

# ---------------------------------------------------------------------------
# 5. Tenant-scoped user auth (signup/login within a tenant)
# ---------------------------------------------------------------------------
@app.post("/auth/register")
async def register(req: RegisterIn, request: Request):
    tid = get_tenant_id(request)
    if not ALLOW_REGISTRATION:
        con0 = db(); n = con0.execute("SELECT COUNT(*) c FROM users WHERE tenant_id=?", (tid,)).fetchone()["c"]; con0.close()
        if n > 0:
            raise HTTPException(403, "registration is closed — accounts are created manually by the admin")
    email = (req.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "valid email required")
    if not req.password or len(req.password) < 8:
        raise HTTPException(400, "password must be at least 8 characters")
    con = db()
    exists = con.execute("SELECT id FROM users WHERE email=? AND tenant_id=?", (email, tid)).fetchone()
    if exists:
        con.close(); raise HTTPException(409, "email already registered in this tenant")
    count = con.execute("SELECT COUNT(*) c FROM users WHERE tenant_id=?", (tid,)).fetchone()["c"]
    role = "admin" if count == 0 else "user"
    cur = con.execute(
        "INSERT INTO users(email,name,pass_hash,role,is_active,tenant_id,created_at) VALUES(?,?,?,?,1,?,?)",
        (email, (req.name or "").strip() or email.split("@")[0], _hash_password(req.password), role, tid, ts()))
    con.commit(); uid = cur.lastrowid
    row = con.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone(); con.close()
    token = _create_session(uid)
    con = db(); con.execute("UPDATE auth_sessions SET tenant_id=? WHERE token_hash=?", (tid, _hash_token(token))); con.commit(); con.close()
    resp = JSONResponse({"ok": True, "user": _public_user_tenant(dict(row)), "tenant_id": tid})
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", secure=True, max_age=SESSION_TTL_SECONDS, path="/")
    return resp

@app.post("/auth/login")
async def login(req: LoginIn, request: Request):
    tid = get_tenant_id(request)
    email = (req.email or "").strip().lower()
    con = db()
    row = con.execute("SELECT * FROM users WHERE email=? AND tenant_id=?", (email, tid)).fetchone()
    con.close()
    if not row or not row["is_active"] or not _check_password(req.password, row["pass_hash"]):
        raise HTTPException(401, "invalid email or password")
    token = _create_session(row["id"])
    con = db(); con.execute("UPDATE auth_sessions SET tenant_id=? WHERE token_hash=?", (tid, _hash_token(token))); con.commit(); con.close()
    resp = JSONResponse({"ok": True, "user": _public_user_tenant(dict(row)), "tenant_id": tid})
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", secure=True, max_age=SESSION_TTL_SECONDS, path="/")
    return resp

@app.get("/auth/me")
async def me(request: Request):
    tid = get_tenant_id(request)
    user = _current_user_in_tenant(request, tid)
    if not user:
        raise HTTPException(401, "login required")
    return {"user": _public_user_tenant(user), "tenant_id": tid}

# ---------------------------------------------------------------------------
# 6. Tenant-scoped harness data endpoints
# ---------------------------------------------------------------------------
@app.get("/harness/my/sessions")
async def my_sessions(request: Request):
    user, tid = require_login_in_tenant(request)
    con = db()
    rows = con.execute("SELECT * FROM sessions WHERE user_id=? AND tenant_id=? ORDER BY updated_at DESC LIMIT 50", (f"user:{user['email']}", tid)).fetchall()
    con.close()
    return {"sessions": [dict(r) for r in rows], "tenant_id": tid}

@app.get("/harness/my/tickets")
async def my_tickets(request: Request):
    user, tid = require_login_in_tenant(request)
    con = db()
    rows = con.execute(
        "SELECT t.* FROM tickets t JOIN sessions s ON s.id=t.session_id WHERE s.user_id=? AND s.tenant_id=? ORDER BY t.id DESC LIMIT 50",
        (f"user:{user['email']}", tid)).fetchall()
    con.close()
    return {"tickets": [dict(r) for r in rows], "tenant_id": tid}

@app.get("/harness/orders")
async def list_orders(request: Request):
    user, tid = require_login_in_tenant(request)
    con = db(); rows = con.execute("SELECT * FROM orders WHERE tenant_id=? ORDER BY updated_at DESC LIMIT 200", (tid,)).fetchall(); con.close()
    out = []
    for r in rows:
        d = dict(r); d["tracking"] = json.loads(d.pop("tracking_json") or "[]"); out.append(d)
    return {"orders": out, "tenant_id": tid}

@app.post("/harness/orders")
async def upsert_order(req: OrderIn, request: Request):
    user, tid = require_admin_in_tenant(request)
    oid = (req.order_id or "").strip()
    if not oid: raise HTTPException(400, "order_id required")
    con = db()
    con.execute("INSERT INTO orders(order_id,item,amount,currency,status,eta,refund,tracking_json,created_at,updated_at,tenant_id) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(order_id,tenant_id) DO UPDATE SET item=excluded.item,amount=excluded.amount,currency=excluded.currency,status=excluded.status,eta=excluded.eta,refund=excluded.refund,tracking_json=excluded.tracking_json,updated_at=excluded.updated_at",
                (oid, req.item, req.amount, req.currency, req.status, req.eta, req.refund, json.dumps(req.tracking or []), ts(), ts(), tid))
    con.commit(); con.close()
    return {"ok": True, "order_id": oid, "tenant_id": tid}

@app.delete("/harness/orders/{oid}")
async def delete_order(oid: str, request: Request):
    user, tid = require_admin_in_tenant(request)
    con = db(); con.execute("DELETE FROM orders WHERE order_id=? AND tenant_id=?", (oid, tid)); con.commit(); con.close()
    return {"ok": True}

@app.get("/harness/products")
async def list_products(request: Request):
    user, tid = require_login_in_tenant(request)
    con = db(); rows = con.execute("SELECT * FROM products WHERE tenant_id=? ORDER BY name", (tid,)).fetchall(); con.close()
    out = []
    for r in rows:
        d = dict(r); d["colors"] = json.loads(d.pop("colors_json") or "[]"); d["sizes"] = json.loads(d.pop("sizes_json") or "[]"); out.append(d)
    return {"products": out, "tenant_id": tid}

@app.post("/harness/products")
async def upsert_product(req: ProductIn, request: Request):
    user, tid = require_admin_in_tenant(request)
    if not req.sku.strip() or not req.name.strip():
        raise HTTPException(400, "sku and name required")
    con = db()
    con.execute("INSERT INTO products(sku,name,fabric,colors_json,price,currency,sizes_json,available,created_at,updated_at,tenant_id) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(sku,tenant_id) DO UPDATE SET name=excluded.name,fabric=excluded.fabric,colors_json=excluded.colors_json,price=excluded.price,currency=excluded.currency,sizes_json=excluded.sizes_json,available=excluded.available,updated_at=excluded.updated_at",
                (req.sku.strip(), req.name.strip(), req.fabric, json.dumps(req.colors), req.price, req.currency, json.dumps(req.sizes), 1 if req.available else 0, ts(), ts(), tid))
    con.commit(); con.close()
    return {"ok": True, "sku": req.sku.strip(), "tenant_id": tid}

@app.delete("/harness/products/{sku}")
async def delete_product(sku: str, request: Request):
    user, tid = require_admin_in_tenant(request)
    con = db(); con.execute("DELETE FROM products WHERE sku=? AND tenant_id=?", (sku, tid)); con.commit(); con.close()
    return {"ok": True}

@app.get("/harness/sessions")
async def sessions(request: Request, shop: str | None = None):
    user, tid = require_login_in_tenant(request)
    con = db()
    if shop:
        rows = con.execute("SELECT * FROM sessions WHERE shop=? AND tenant_id=? ORDER BY updated_at DESC LIMIT 50", (shop, tid)).fetchall()
    else:
        rows = con.execute("SELECT * FROM sessions WHERE tenant_id=? ORDER BY updated_at DESC LIMIT 50", (tid,)).fetchall()
    con.close()
    return {"sessions": [dict(r) for r in rows], "tenant_id": tid}

@app.get("/harness/tickets")
async def tickets(request: Request, shop: str | None = None):
    user, tid = require_login_in_tenant(request)
    con = db()
    if shop:
        rows = con.execute("SELECT * FROM tickets WHERE shop=? AND tenant_id=? ORDER BY id DESC LIMIT 100", (shop, tid)).fetchall()
    else:
        rows = con.execute("SELECT * FROM tickets WHERE tenant_id=? ORDER BY id DESC LIMIT 100", (tid,)).fetchall()
    con.close()
    return {"tickets": [dict(r) for r in rows], "tenant_id": tid}

@app.get("/harness/metrics")
async def metrics(request: Request, shop: str | None = None):
    user, tid = require_login_in_tenant(request)
    con = db()
    base = "WHERE s.tenant_id=?"
    params = [tid]
    if shop:
        base += " AND s.shop=?"; params.append(shop)
    total = con.execute(f"SELECT COUNT(*) FROM decisions d JOIN sessions s ON s.id=d.session_id {base}", params).fetchone()[0]
    handoffs = con.execute(f"SELECT COUNT(*) FROM decisions d JOIN sessions s ON s.id=d.session_id {base} AND d.action='human_handoff'", params).fetchone()[0]
    avg = con.execute(f"SELECT AVG(d.latency_ms) FROM decisions d JOIN sessions s ON s.id=d.session_id {base}", params).fetchone()[0]
    open_tickets = con.execute("SELECT COUNT(*) FROM tickets WHERE status='open' AND tenant_id=?", (tid,)).fetchone()[0]
    by_action = con.execute(f"SELECT d.action, COUNT(*) c FROM decisions d JOIN sessions s ON s.id=d.session_id {base} GROUP BY d.action ORDER BY c DESC", params).fetchall()
    con.close()
    return {"decisions": total, "handoff_rate": round(handoffs/total, 3) if total else 0,
            "avg_latency_ms": round(avg,1) if avg else 0, "open_tickets": open_tickets,
            "by_action": {r["action"]: r["c"] for r in by_action}, "tenant_id": tid}

# ---------------------------------------------------------------------------
# 7. Per-tenant rate limiting (Redis if available)
# ---------------------------------------------------------------------------
try:
    import redis as _redis
    _r = _redis.Redis(host="127.0.0.1", port=6379, decode_responses=True)
    _r.ping()
    _REDIS_OK = True
except Exception:
    _REDIS_OK = False
    _r = None

_TENANT_RATE = {"starter": 20, "pro": 100, "enterprise": 1000}

def check_tenant_rate(request: Request, tenant_id: str):
    plan = "starter"
    con = db()
    row = con.execute("SELECT plan FROM tenants WHERE slug=?", (tenant_id,)).fetchone()
    con.close()
    if row: plan = row["plan"]
    limit = _TENANT_RATE.get(plan, 20)
    key = f"ratelimit:{tenant_id}"
    now = int(time.time())
    window = now // 60
    if _REDIS_OK:
        full_key = f"{key}:{window}"
        cur = _r.incr(full_key)
        _r.expire(full_key, 70)
        if cur > limit:
            raise HTTPException(429, f"rate limit exceeded for plan {plan} ({limit}/min)")
    return limit


# -*- coding: utf-8 -*-
"""Telegram customer-service channel for Favemus."""
import urllib.error
import urllib.request
import json as _json

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}" if TELEGRAM_BOT_TOKEN else ""

def _telegram_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN and TELEGRAM_API)

def _telegram_send(chat_id: int | str, text: str) -> bool:
    if not _telegram_configured():
        print("telegram send skipped: TELEGRAM_BOT_TOKEN not configured", flush=True)
        return False
    url = f"{TELEGRAM_API}/sendMessage"
    body = _json.dumps({
        "chat_id": chat_id,
        "text": text[:4096],
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = _json.loads(resp.read().decode())
        if not data.get("ok"):
            print(f"telegram send API error: {data}", flush=True)
            return False
        return True
    except Exception as exc:
        print(f"telegram send error to {chat_id}: {exc}", flush=True)
        return False

def _telegram_send_long(chat_id: int | str, text: str) -> bool:
    ok = True
    for i in range(0, max(len(text), 1), 4000):
        ok = _telegram_send(chat_id, text[i:i + 4000]) and ok
    return ok

def _process_telegram_message(chat_id, text, msg_id):
    if not text or not text.strip():
        return
    sid = f"tg-{chat_id}"
    con = db()
    cur = con.execute("INSERT OR IGNORE INTO telegram_seen(message_id,chat_id,created_at) VALUES(?,?,?)",
                      (msg_id, str(chat_id), ts()))
    con.commit(); con.close()
    if cur.rowcount == 0:
        print(f"telegram duplicate {msg_id} ignored", flush=True)
        return
    try:
        result = handle_message(sid, str(chat_id), "telegram", text.strip(), "favemus")
    except Exception as exc:
        print(f"telegram harness error {chat_id}: {exc}", flush=True)
        _telegram_send_long(chat_id, "Sorry, I could not process that. Please try again.")
        return
    reply = (result.get("reply") or "Sorry, I could not answer.").strip()
    _telegram_send_long(chat_id, reply)

@app.get("/telegram/webhook")
async def telegram_webhook_info(request: Request):
    if not _telegram_configured():
        return {"configured": False, "note": "Set TELEGRAM_BOT_TOKEN in favemus.env and restart favemus.service"}
    return {
        "configured": True,
        "webhook_url": "https://favemus.zealstore.me/telegram/webhook",
        "bot": "@belfyre_bot",
    }

@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    if not _telegram_configured():
        raise HTTPException(503, "telegram not configured")
    try:
        payload = await request.json()
    except Exception:
        return {"ok": True}
    message = payload.get("message") or payload.get("edited_message")
    if not message:
        return {"ok": True}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if not chat_id:
        return {"ok": True}
    msg_id = message.get("message_id")
    text = message.get("text") or ""
    if not text.strip():
        _telegram_send_long(chat_id, "I can read text messages. Please type your question (e.g. 'Where is my order FAV-1042?').")
        return {"ok": True}
    threading.Thread(target=_process_telegram_message, args=(chat_id, text[:2000], msg_id), daemon=True).start()
    return {"ok": True}

class TelegramSetWebhookIn(BaseModel):
    url: str | None = None

@app.post("/saas/telegram/set-webhook")
async def saas_telegram_set_webhook(req: TelegramSetWebhookIn, request: Request):
    _require_super_admin(request)
    if not _telegram_configured():
        raise HTTPException(503, "telegram not configured")
    url = req.url or "https://favemus.zealstore.me/telegram/webhook"
    try:
        req2 = urllib.request.Request(f"{TELEGRAM_API}/setWebhook", data=_json.dumps({"url": url}).encode(),
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req2, timeout=20) as resp:
            data = _json.loads(resp.read().decode())
        return {"ok": data.get("ok"), "description": data.get("description"), "url": url}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

@app.get("/saas/telegram/webhook-info")
async def saas_telegram_webhook_info(request: Request):
    _require_super_admin(request)
    if not _telegram_configured():
        return {"configured": False}
    try:
        with urllib.request.urlopen(f"{TELEGRAM_API}/getWebhookInfo", timeout=20) as resp:
            return _json.loads(resp.read().decode())
    except Exception as exc:
        return {"ok": False, "error": str(exc)}

def _ensure_telegram_table(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS telegram_seen (
            message_id TEXT,
            chat_id TEXT,
            created_at TEXT,
            PRIMARY KEY(message_id, chat_id)
        )
    """)
    con.commit()

@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(_tpl("home.html"))
