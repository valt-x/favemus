# Favemus API Reference

All responses are JSON unless otherwise noted.

## Health
- `GET /health` — basic health check

## Web Chat
- `POST /chat` — send a message

### Request
```json
{
  "message": "Where is my order FAV-1042?",
  "session_id": "web-abc123",
  "channel": "web",
  "shop": "favemus"
}
```

### Response
```json
{
  "session_id": "web-abc123",
  "reply": "Order FAV-1042 is out for delivery. Estimated delivery: 2026-11-03.",
  "state": "idle",
  "action": "tool:order_status",
  "analysis": { "tool": "order_status", "tool_confidence": 0.9983 },
  "tool_call": { "name": "order_status", "arguments": {"order_id": "FAV-1042"} },
  "handoff": false,
  "routing": { "model": "english" }
}
```

## Auth
- `POST /auth/register` — register a user (tenant-scoped)
- `POST /auth/login` — login
- `POST /auth/logout` — logout
- `GET /auth/me` — current user

## Admin (requires admin role)
- `GET /harness/users` — list users
- `POST /harness/users` — create user
- `POST /harness/users/{id}/toggle-active` — enable/disable
- `DELETE /harness/users/{id}` — delete
- `GET|POST /harness/orders` — orders CRUD
- `GET|POST /harness/products` — products CRUD
- `GET /harness/sessions` — all conversations
- `GET /harness/tickets` — tickets
- `GET /harness/metrics` — AI metrics

## Super Admin (`X-Harness-Token` header)
- `GET /saas/tenants` — list tenants
- `POST /saas/tenants` — create tenant
- `POST /saas/tenants/{slug}/suspend` — suspend tenant
- `POST /saas/webhooks/stripe` — Stripe stub

## WhatsApp
- `GET /whatsapp/webhook` — verify handshake
- `POST /whatsapp/webhook` — receive messages
- `POST /harness/whatsapp/test` — send test (admin)

## Telegram
- `GET /telegram/webhook` — status
- `POST /telegram/webhook` — receive messages
- `POST /saas/telegram/set-webhook` — set webhook (super admin)

## My Data (requires login)
- `GET /harness/my/sessions` — my conversations
- `GET /harness/my/tickets` — my tickets
