# Favemus — Architecture

## Overview

Favemus is a **self-hosted AI customer support system**. It runs entirely on one server with no external dependencies for AI inference or database storage.

## Layers

```
Layer 2 · Channels (public-facing)
├─ Web chat (/client, /chat)
├─ WhatsApp webhook (/whatsapp/webhook)
└─ Telegram webhook (/telegram/webhook)

Layer 1 · Admin (authenticated: admin role)
├─ Owner console (/owner)
├─ Dashboard: decisions, tickets, handoff rate
├─ CRUD: users, orders, products
└─ WhatsApp test sender

Layer 3 · AI + Data (internal)
├─ Laya Router (loaded in-process)
│  └─ 6 intents: order_status, refund_status,
│     initiate_return, exchange_item,
│     search_products, human_handoff
├─ SQLite database (favemus.db)
│  └─ tenants, users, auth_sessions, sessions,
│     messages, tickets, decisions, orders,
│     products, whatsapp_seen, telegram_seen
└─ nginx (443) → uvicorn (127.0.0.1:8091)
```

## Request Flow

### Chat (web)
```
Customer → POST /chat → handle_message()
  → load or create session
  → analyse_message(text) [Laya model]
  → determine intent & confidence
  → if confidence < CONFIDENCE_FLOOR (default 0.35):
       clarify, up to 2x, then escalate to human
  → else: execute tool (order_status / search_products / …)
  → save decisions & messages
  → return reply JSON
```

### WhatsApp
```
Customer → WhatsApp message
  → POST /whatsapp/webhook
  → dedup check (whatsapp_seen)
  → handle_message() in background thread
  → POST to Meta Cloud API sendMessage
```

### Telegram
```
Customer → Telegram message
  → POST /telegram/webhook
  → dedup check (telegram_seen)
  → handle_message() in background thread
  → sendMessage via Telegram Bot API
```

## Multi-Tenancy

- nginx sets `X-Tenant-Id` from Host subdomain or `/t/<slug>/` path
- FastAPI middleware scopes all queries by `tenant_id`
- Each tenant: isolated users, orders, products, sessions, tickets, metrics
- Super admin (`X-Harness-Token`) manages tenants at `/saas/tenants`

## Security

- nginx terminates TLS (self-signed cert, Cloudflare Full mode)
- Security headers: HSTS, CSP `script-src 'self'`, X-Frame-Options DENY, nosniff
- Passwords: PBKDF2-HMAC-SHA256, 200k iterations
- Session tokens stored as hashes only
- Rate limit: `limit_req zone=app burst=40 nodelay` (10r/s per IP)

## Data Flow

```
Message in → handle_message() → analyse_message() [Laya]
                                     ↓
                              confidence ≥ 0.35?
                              ├─ yes → execute_tool() → reply
                              └─ no  → clarify (max 2x) → handoff
                                     ↓
                              save to sessions/messages/decisions
```

## Constraints & Limitations

- AI is limited to 6 fixed intents — cannot reason about arbitrary topics
- No conversation memory beyond session (customer + order history not injected into prompt)
- No automated retraining or feedback loop
- Manual data entry required (no API import from Shopify/BigCommerce)
- Single-server (no horizontal scaling without sticky sessions)

## Scaling Path

1. Add Redis for session state → allows multiple uvicorn workers
2. Add Postgres → allows horizontal DB scaling
3. Add prompt templating with full conversation history
4. Add active learning from agent confirmations/corrections
5. Split channels (WhatsApp/Telegram/Web) into separate services
