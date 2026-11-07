# Favemus architecture — 3 layers, one server

Everything runs on **this same server** (no external AI provider, no external database, no Shopify/BigCommerce).

```
                    this server (one host, one nginx, one systemd service)
┌────────────────────────────────────────────────────────────────────────┐
│  LAYER 1 · MY LAYER (Owner)        /owner  (admin only)                │
│  Manage users, orders, products, WhatsApp config, tickets, metrics.    │
├────────────────────────────────────────────────────────────────────────┤
│  LAYER 2 · CLIENT LAYER            /client (public + logged-in)        │
│  AI chat widget (/chat.js, /chat), WhatsApp (/whatsapp/webhook),       │
│  logged-in clients see ONLY their own conversations/tickets.           │
├────────────────────────────────────────────────────────────────────────┤
│  LAYER 3 · AI + DATA LAYER         in-process, same server             │
│  AI: Laya model loaded in favemus.service (HTTP 127.0.0.1:8091)        │
│  Data: SQLite at /home/baymax/favemus/favemus.db                       │
│  Tables: users, auth_sessions, sessions, messages, tickets, decisions, │
│          orders, products, whatsapp_seen                               │
└────────────────────────────────────────────────────────────────────────┘
         nginx (443) → 127.0.0.1:8091 (favemus.service)
```

## Requests flow
- **Owner** (`/owner`, login as admin) → owner APIs (`/harness/users`, `/harness/orders`, `/harness/products`, `/harness/whatsapp/test`, `/harness/sessions|tickets|metrics`) → Layer 3 DB + AI.
- **Client chat** (`/client` or `/chat.js` embed) → `POST /chat` → Layer 3 `handle_message()` (AI triage → tools: order_status / refund_status / initiate_return / exchange_item / search_products / human_handoff) → reply.
- **Client WhatsApp** → Meta webhook `/whatsapp/webhook` → same `handle_message()` → Cloud API reply. Session id `wa-<phone>`.
- **Logged-in client** chat sessions are tied to their account (`user:<email>`), so `/client` "My conversations" shows only theirs.

## Security
- Owner APIs require admin role (cookie session or `X-Harness-Token).
- Client "my" APIs require login and filter by owner — no cross-client access.
- Public: `/chat`, `/chat.js`, `/whatsapp/webhook` (Meta signature-checked when `WHATSAPP_APP_SECRET` set), `/`, `/privacy`, guides.
- Passwords: PBKDF2-HMAC-SHA256, 200k iterations. Sessions: opaque tokens, only hashes stored.

## Manual setup
- First admin: register once at `/register` (bootstrap), then public registration is closed (`FAVEMUS_ALLOW_REGISTRATION=false`).
- Owner creates every other account in `/owner` (e.g. after a WhatsApp conversation).
- Orders/products are entered manually in `/owner` — the AI answers from that data.

## Status
Check any time: `GET /layers/status` (login) or `/admin` → dashboard metrics.
