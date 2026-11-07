# Favemus — AI Customer Support Harness

**Standalone AI-powered customer support with WhatsApp, Telegram, and Web layers — all on one server, no external AI provider, no external database.**

---

## 🎯 What is Favemus?

Favemus is a self-hosted AI customer service system. Customers message you via WhatsApp, Telegram, or web chat, and an AI assistant answers using **your** manual order/product data — no Shopify, no BigCommerce, no WooCommerce, no external API costs for AI inference.

It's designed for small merchants who want automated support without paying per-message SaaS fees.

---

## 🏗️ Architecture — 3 Layers, 1 Server

Everything runs on **this same host** (one nginx, one systemd service, one SQLite database).

```
                    THIS SERVER
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 1 · MY LAYER (Owner)        /owner   🔒 admin only        │
│  Create users, orders, products, WhatsApp config, view all       │
│  conversations & tickets, AI metrics dashboard                   │
├──────────────────────────────────────────────────────────────────┤
│  LAYER 2 · CLIENT LAYER            /client  🌐 public + login    │
│  AI chat widget (/chat.js embed), WhatsApp, Telegram,            │
│  logged-in clients see ONLY their own conversations/tickets      │
├──────────────────────────────────────────────────────────────────┤
│  LAYER 3 · AI + DATA LAYER         in-process, same server       │
│  🤖 AI: Laya model loaded in favemus.service (HTTP 127.0.0.1:8091)│
│  💾 Data: SQLite at favemus.db                                   │
│  Tables: users, auth_sessions, sessions, messages, tickets,      │
│          decisions, orders, products, whatsapp_seen              │
└──────────────────────────────────────────────────────────────────┘
         nginx 443 → 127.0.0.1:8091 (favemus.service)
```

**No external AI provider. No external database. No Shopify/BigCommerce/WooCommerce.**

---

## ✨ Features

### For Customers (Layer 2)
- ✅ Web chat at `https://your-domain/client`
- ✅ Embeddable chat widget (`<script src="/chat.js">`)
- ✅ WhatsApp Business Cloud API webhook
- ✅ Telegram bot webhook
- ✅ Order status, refund status, returns, exchanges, product search
- ✅ Human handoff (escalation to admin)
- ✅ Login to view their own conversations & tickets

### For Admins (Layer 1 — "My Layer")
- ✅ Create manual user accounts (no public registration by default)
- ✅ Add/edit/delete orders and products manually
- ✅ View ALL conversations, tickets, AI metrics
- ✅ Create/suspend tenants (multi-tenant SaaS mode)
- ✅ WhatsApp test sender from admin panel
- ✅ Role-based access (admin / user)

### SaaS / Multi-Tenant
- ✅ Subdomain routing: `acme.your-domain.com` → tenant `acme`
- ✅ Path prefix routing: `/t/acme/...` → tenant `acme`
- ✅ Tenant-scoped auth (login scoped to tenant)
- ✅ Tenant-scoped data isolation (orders, products, sessions)
- ✅ Per-tenant rate limiting (starter/pro/enterprise)
- ✅ Super-admin tenant management via `X-Harness-Token`
- ✅ Stripe webhook stub (`/saas/webhooks/stripe`)

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone https://github.com/valt-x/favemus.git
cd favemus

# Copy env template and fill in your values
cp favemus.env.example favemus.env
chmod 600 favemus.env
# Edit favemus.env with your tokens (see Configuration below)
```

### 2. Install System Dependencies

```bash
# Python dependencies (in your venv)
pip install fastapi uvicorn laya pydantic

# Nginx (already installed on most servers)
sudo apt install nginx
```

### 3. Set Up systemd Service

```bash
sudo cp favemus.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now favemus
```

### 4. Set Up nginx

Copy the vhost config to `/etc/nginx/sites-available/` and symlink to `sites-enabled/`, then:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 5. First Admin Account

Since public registration is disabled by default (`FAVEMUS_ALLOW_REGISTRATION=false`):

```bash
# Temporarily enable registration to create the first admin:
# Set FAVEMUS_ALLOW_REGISTRATION=true in favemus.env, restart,
# register at /register, then set back to false.

# Or create via super-admin API:
curl -X POST https://your-domain/saas/tenants \
  -H "X-Harness-Token: YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"slug":"mybiz","name":"My Business","owner_email":"you@your.com","owner_password":"ChangeMe123!"}'
```

Then log in at `https://your-domain/login` or `https://mybiz.your-domain.com/login`.

---

## 🔧 Configuration

### Environment Variables (`favemus.env`)

| Variable | Required | Description |
|---|---|---|
| `HARNESS_ADMIN_TOKEN` | ✅ | Super admin token for tenant management |
| `TELEGRAM_BOT_TOKEN` | ❌ | Telegram bot token from @BotFather |
| `WHATSAPP_VERIFY_TOKEN` | ❌ | Webhook verify token (you pick) |
| `WHATSAPP_ACCESS_TOKEN` | ❌ | Permanent system-user token from Meta |
| `WHATSAPP_PHONE_NUMBER_ID` | ❌ | From Meta API Setup |
| `WHATSAPP_APP_SECRET` | ❌ | For webhook signature verification |
| `FAVEMUS_ALLOW_REGISTRATION` | ❌ | `true`/`false` (default: `false`) |
| `FAVEMUS_CONFIDENCE_FLOOR` | ❌ | AI confidence threshold (default: `0.35`) |
| `FAVEMUS_DB` | ❌ | SQLite path (default: `./favemus.db`) |

### nginx Site Config

See the example nginx config in the project. Key points:
- Proxy passes to `127.0.0.1:8091` (favemus.service)
- Security headers included (`sec-headers.conf`)
- Rate limiting via `limit_req zone=app`
- Tenant resolution via `X-Tenant-Id` header from Host subdomain or `/t/<slug>/` path

---

## 📱 WhatsApp Setup

### One-time Meta Setup (5–10 min)

1. Go to **developers.facebook.com → My Apps → Create App** (type: Business)
2. Add the **WhatsApp** product
3. Add your real business phone number (SMS/voice OTP verified)
4. **WhatsApp → Configuration → Webhook**:
   - Callback URL: `https://your-domain/whatsapp/webhook`
   - Verify token: pick a random string
   - Subscribe to `messages` field
5. Copy the **Permanent access token** and **Phone number ID**

### Set on Server

Edit `favemus.env`:

```ini
WHATSAPP_VERIFY_TOKEN=your-verify-token
WHATSAPP_ACCESS_TOKEN=your-permanent-token
WHATSAPP_PHONE_NUMBER_ID=your-phone-number-id
WHATSAPP_APP_SECRET=your-app-secret
```

```bash
sudo systemctl restart favemus
```

### Test

- Admin panel → WhatsApp section → **Send WhatsApp test**
- Message your WhatsApp number: "Where is my order FAV-1042?"

### Guide Page

Visit `https://your-domain/whatsapp-guide.html` for a customer-facing setup guide.

---

## 🤖 Telegram Setup

### Create Bot

1. Message **@BotFather** on Telegram
2. `/newbot` → follow prompts
3. Copy the **bot token**

### Set on Server

```ini
# favemus.env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
```

```bash
sudo systemctl restart favemus
```

### Set Webhook

```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://your-domain/telegram/webhook"}'
```

### Test

Message your bot on Telegram: "Where is my order FAV-1042?"

### Admin Endpoints

- `GET /telegram/webhook` — webhook info
- `POST /saas/telegram/set-webhook` — set webhook (super admin)
- `GET /saas/telegram/webhook-info` — current webhook status (super admin)

---

## 🏢 Multi-Tenant (SaaS) Setup

Favemus supports multiple tenants on one domain via subdomains or path prefixes.

### Create a Tenant (Super Admin)

```bash
curl -X POST https://your-domain/saas/tenants \
  -H "X-Harness-Token: YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"slug":"acme","name":"Acme Store","plan":"pro","owner_email":"owner@acme.test","owner_password":"ChangeMe123!"}'
```

### Access

- Subdomain: `https://acme.your-domain.com/login`
- Path prefix: `https://your-domain/t/acme/login`

### Tenant Isolation

Each tenant has:
- Separate users (login scoped to tenant)
- Separate orders & products
- Separate conversations & tickets
- Separate rate limits based on plan

### Suspend a Tenant

```bash
curl -X POST https://your-domain/saas/tenants/acme/suspend \
  -H "X-Harness-Token: YOUR_ADMIN_TOKEN"
```

---

## 📊 API Reference

### Public Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | AI support chat (web) |
| GET | `/client` | Client layer portal |
| GET | `/chat.js` | Embeddable chat widget |
| POST | `/chat` | AI chat API |
| GET | `/privacy`, `/terms.html`, etc. | Static pages |
| GET | `/whatsapp/webhook` | WhatsApp webhook verify |
| POST | `/whatsapp/webhook` | WhatsApp webhook |
| GET | `/telegram/webhook` | Telegram webhook info |
| POST | `/telegram/webhook` | Telegram webhook |

### Auth Endpoints
| Method | Path | Description |
|--------|------|-------------|
| POST | `/auth/register` | Register (tenant-scoped) |
| POST | `/auth/login` | Login (tenant-scoped) |
| POST | `/auth/logout` | Logout |
| GET | `/auth/me` | Current user |

### Admin Endpoints (Tenant-Scoped)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/harness/users` | List users (admin) |
| POST | `/harness/users` | Create user (admin) |
| DELETE | `/harness/users/{id}` | Delete user (admin) |
| POST | `/harness/users/{id}/toggle-active` | Toggle user (admin) |
| GET | `/harness/orders` | List orders |
| POST | `/harness/orders` | Create/update order (admin) |
| DELETE | `/harness/orders/{id}` | Delete order (admin) |
| GET | `/harness/products` | List products |
| POST | `/harness/products` | Create/update product (admin) |
| DELETE | `/harness/products/{sku}` | Delete product (admin) |
| GET | `/harness/sessions` | List conversations |
| GET | `/harness/tickets` | List tickets |
| GET | `/harness/metrics` | AI metrics |
| GET | `/harness/my/sessions` | My conversations (client) |
| GET | `/harness/my/tickets` | My tickets (client) |

### Super Admin (X-Harness-Token)
| Method | Path | Description |
|--------|------|-------------|
| GET | `/saas/tenants` | List tenants |
| POST | `/saas/tenants` | Create tenant |
| POST | `/saas/tenants/{slug}/suspend` | Suspend tenant |
| POST | `/saas/webhooks/stripe` | Stripe webhook stub |
| POST | `/saas/telegram/set-webhook` | Set Telegram webhook |
| GET | `/saas/telegram/webhook-info` | Telegram webhook info |

---

## 🔐 Security

- Passwords stored as PBKDF2-HMAC-SHA256 (200k iterations)
- Login sessions use httpOnly, SameSite=Lax cookies
- Session tokens stored as hashes (never plain text)
- Admin APIs require admin role
- Client APIs scoped to tenant (no cross-tenant access)
- `server_tokens off` in nginx
- `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`
- HSTS with preload
- Rate limiting per tenant

### ⚠️ Never Commit
- `favemus.env` — contains real tokens
- `favemus.db` — contains user data
- `*.bak*` — backup files

Use `favemus.env.example` as a template.

---

## 🐛 Troubleshooting

| Issue | Fix |
|-------|-----|
| 500 on `/chat` | Check `sudo journalctl -u favemus -f` for Python errors |
| WhatsApp not replying | Verify webhook URL and token in Meta dashboard |
| Telegram not replying | Verify webhook is set via `getWebhookInfo` |
| Can't login | Check `FAVEMUS_ALLOW_REGISTRATION` and user exists in DB |
| Cross-tenant data leak | Verify `X-Tenant-Id` header is set by nginx |
| AI always says "clarify" | Lower `FAVEMUS_CONFIDENCE_FLOOR` or add more training data |

### View Logs

```bash
sudo journalctl -u favemus -f
sudo tail -f /var/log/nginx/error.log
```

---

## 📁 File Structure

```
favemus/
├── harness.py              # Main FastAPI application (AI + API + webhook handlers)
├── favemus.env.example     # Environment template (copy to favemus.env)
├── favemus.service         # systemd unit file
├── ARCHITECTURE.md         # Detailed architecture document
├── README.md               # This file
├── templates/
│   ├── owner.html          # Owner/admin console (dark theme)
│   ├── client.html         # Client chat portal (light theme)
│   ├── home.html           # Raw chat interface
│   └── auth.html           # Login/register page template
├── _archive/               # Archived Shopify/BigCommerce code
│   └── favemus-shopify-20261106/
└── favemus.db              # SQLite database (gitignored)
```

---

## 📜 License

MIT License. Feel free to fork, modify, and deploy.

---

## 🤝 For My Fellow Developer

If you're picking this up:

1. **Read `ARCHITECTURE.md` first** — it explains the 3-layer design in detail.
2. **Start with `/owner`** — create your first admin account, add some test orders/products.
3. **Test the chat** at `/client` — try "Where is my order FAV-1042?".
4. **Set up WhatsApp** — follow the guide at `/whatsapp-guide.html`.
5. **Add tenants** — use `/saas/tenants` (super admin) to onboard customers.

The AI uses the **Laya** model (loaded locally). It classifies messages into: order_status, refund_status, initiate_return, exchange_item, search_products, human_handoff. Orders and products are entered manually in `/owner` — the AI answers from that data.

Questions? Check the existing issues or open a new one.

— Igris, Red Team Lead