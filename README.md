# Favemus — AI Customer Support

Local AI support assistant for your business. Customers reach you via **WhatsApp, Telegram, or web chat**. The AI answers from your own data — **no external AI provider, no external database.**

---

## What this is

Favemus is a self-hosted support chatbot. You enter your orders and products manually. The AI classifies incoming messages and answers — or escalates to a human.

If you outgrow this, the same architecture can power a real SaaS with multiple tenants.

---

## Current status

| Component | Status | Notes |
|---|---|---|
| AI classification | ✅ Working | Laya model, 6 intents |
| Web chat | ✅ Working | `/client` |
| WhatsApp webhook | ✅ Implemented | Needs Meta credentials |
| Telegram webhook | ✅ Implemented | `@belfyre_bot` configured |
| Multi-tenancy | ✅ Implemented | `/t/<slug>/` path or subdomain |
| Owner console | ✅ Working | `/owner` |
| Static assets | ✅ Working | `/static/*` served by nginx |
| Health check | ✅ Working | `/healthz` with real DB counts |
| CSP | ✅ Strict | `script-src 'self'` — all JS external |
| HTTPS | ✅ Live | Self-signed cert (Cloudflare Full mode) |
| Deploy script | ✅ Ready | `./deploy.sh` |

---

## Architecture

```
Customer (WhatsApp / Telegram / Web)
        │
        ▼
nginx (443, HTTPS, security headers, rate limit)
        │
        ▼
uvicorn on 127.0.0.1:8091 (favemus.service)
        ├─ /chat           → AI triage → tool → reply
        ├─ /whatsapp/*     → Meta webhook handler
        ├─ /telegram/*     → Telegram bot webhook
        ├─ /auth/*         → login/register/logout
        ├─ /harness/*      → CRUD + metrics (admin-only)
        ├─ /saas/*         → tenant management (super admin)
        └─ /healthz        → real metrics
                │
                ▼
         SQLite (one file: favemus.db)
```

---

## Quick start

```bash
git clone https://github.com/valt-x/favemus.git
cd favemus
./deploy.sh
```

Then edit `favemus.env` with your tokens and restart:
```bash
sudo systemctl restart favemus
```

Full guide: `docs/deployment.md`

---

## What you need to provide

| Variable | Where to get it |
|---|---|
| `HARNESS_ADMIN_TOKEN` | You pick a random string. Used for tenant management. |
| `WHATSAPP_VERIFY_TOKEN` | You pick. Enter same in Meta webhook config. |
| `WHATSAPP_ACCESS_TOKEN` | Meta developer dashboard → permanent system-user token |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta developer dashboard → API Setup |
| `TELEGRAM_BOT_TOKEN` | Message @BotFather → `/newbot` |

Without those, Favemus works as a web chat only.

---

## API

See `docs/api.md`.

---

## Documentation

- `docs/deployment.md` — server setup, nginx, systemd, verification
- `docs/api.md` — all endpoints with request/response examples
- `docs/troubleshooting.md` — common issues and fixes
- `ARCHITECTURE.md` — system design

---

## Security

- PBKDF2-HMAC-SHA256 password hashing (200k iterations)
- httpOnly, SameSite=Lax cookies
- `script-src 'self'` CSP — no inline scripts
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`
- HSTS with preload
- Rate limiting per tenant

Never commit: `favemus.env`, `favemus.db`, `*.bak*`

---

## License

MIT.
