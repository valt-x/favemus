import os
import threading
from contextlib import asynccontextmanager

import laya
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from laya import Router
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

QUESTIONS = {
    "intent": {
        "type": "choice",
        "instructions": "What does the customer mainly want?",
        "criteria": {
            "refund": "wants money back for an order",
            "exchange": "wants a different size, colour, or a replacement item",
            "return": "wants to send the item back",
            "delivery": "asks where the order is or reports a late or missing delivery",
            "product_question": "asks about fabric, sizing, stock, or care instructions",
            "other": "anything else",
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
    "wants_refund": {
        "type": "noul",
        "instructions": "Does the customer ask for a refund?",
    },
    "wants_exchange": {
        "type": "noul",
        "instructions": "Does the customer ask for an exchange or replacement?",
    },
    "urgency": {
        "type": "score",
        "instructions": "How urgent is the request?",
        "criteria": ["low", "medium", "high"],
    },
    "sentiment": {
        "type": "score",
        "instructions": "How upset is the customer?",
        "criteria": ["calm", "annoyed", "angry"],
    },
}

router = None
_lock = threading.Lock()


@asynccontextmanager
async def lifespan(app):
    global router
    router = Router(default="english", max_loaded=1, device=os.getenv("LAYA_DEVICE", "cpu"))
    router.preload(["english"])
    yield
    router.unload()


app = FastAPI(title="Favemus Support Triage", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    message: str
    order_id: str | None = None
    channel: str | None = None


def choose_action(answers):
    intent = answers["intent"]["choice"]
    issue = answers["issue"]["choice"]
    confidence = answers["intent"]["answer_confidence"]
    if confidence < 0.45 or intent == "other":
        return "human_handoff"
    if intent == "product_question":
        return "faq_reply"
    if issue == "damaged":
        return "replacement_or_refund"
    if issue == "wrong_item":
        return "replacement"
    if issue == "size_fit":
        return "size_exchange"
    if issue == "delivery" or intent == "delivery":
        return "delivery_investigation"
    if intent == "refund":
        return "refund_review"
    if intent == "exchange":
        return "exchange"
    if intent == "return":
        return "return_review"
    return "human_handoff"


@app.get("/health")
def health():
    return {
        "status": "ok",
        "ready": router is not None,
        "laya": laya.__version__,
        "model": "english",
    }


@app.get("/support/schema")
def schema():
    return {"questions": QUESTIONS}


@app.post("/support/triage")
async def triage(req: Message):
    def run():
        with _lock:
            return router.predict(req.message, QUESTIONS, model="english")

    result = await run_in_threadpool(run)
    answers = result["answers"]
    return {
        "order_id": req.order_id,
        "channel": req.channel,
        "action": choose_action(answers),
        "answers": answers,
        "routing": result["routing"],
    }


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Favemus Support Triage</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 760px; margin: 40px auto; padding: 0 16px; background: #faf7f4; color: #221; }
  h1 { font-size: 22px; }
  textarea { width: 100%; min-height: 110px; padding: 12px; font: inherit; border: 1px solid #ccb; border-radius: 8px; box-sizing: border-box; }
  button { margin-top: 10px; padding: 10px 18px; font: inherit; border: 0; border-radius: 8px; background: #7a3e2e; color: #fff; cursor: pointer; }
  pre { background: #fff; border: 1px solid #e6ded6; border-radius: 8px; padding: 14px; overflow: auto; font-size: 13px; }
  .tag { display: inline-block; padding: 3px 10px; border-radius: 999px; background: #eee3d8; font-size: 13px; }
</style>
</head>
<body>
<h1>Favemus support triage</h1>
<p>Paste a customer message. Laya returns intent, issue, refund/exchange flags and a routing action.</p>
<textarea id="msg">Hi, I received my dress today but the zip is broken. I want a refund.</textarea>
<button onclick="run()">Triage</button>
<p>Action: <span class="tag" id="action">-</span></p>
<pre id="out">-</pre>
<script>
async function run() {
  const out = document.getElementById('out');
  const action = document.getElementById('action');
  out.textContent = 'Thinking...';
  const res = await fetch('/support/triage', {
    method: 'POST',
    headers: {'content-type': 'application/json'},
    body: JSON.stringify({message: document.getElementById('msg').value, channel: 'web'})
  });
  const data = await res.json();
  action.textContent = data.action || 'error';
  out.textContent = JSON.stringify(data, null, 2);
}
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return PAGE
