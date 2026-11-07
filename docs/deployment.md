# Favemus Deployment Guide

## Server Requirements

- Ubuntu 22.04/24.04 or Debian 12
- nginx
- Python 3.12+
- systemd
- Public IP with HTTPS (Cloudflare or Let's Encrypt)
- ~2 GB free RAM (Laya model)
- ~5 GB disk (venv + model cache)

## Quick Deploy

```bash
git clone https://github.com/valt-x/favemus.git /opt/favemus
cd /opt/favemus
./deploy.sh
```

## Manual Step-by-Step

### 1. Clone
```bash
sudo mkdir -p /opt/favemus
sudo chown $USER:$USER /opt/favemus
git clone https://github.com/valt-x/favemus.git /opt/favemus
cd /opt/favemus
```

### 2. Python venv
```bash
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install fastapi uvicorn laya pydantic
```

### 3. Environment
```bash
cp .env.example .env
chmod 600 .env
nano .env  # Fill in: HARNESS_ADMIN_TOKEN, WHATSAPP_*, TELEGRAM_*
```

### 4. Static assets
```bash
sudo mkdir -p /var/www/favemus/static
sudo cp static/*.js /var/www/favemus/static/
sudo chown -R www-data:www-data /var/www/favemus
```

### 5. systemd
```bash
sudo cp favemus.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now favemus
```

### 6. nginx
Create `/etc/nginx/sites-available/favemus.zealstore.me` with the included config, symlink to sites-enabled, then:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 7. Cloudflare (if using)
- SSL/TLS → Full
- DNS: A record for favemus.zealstore.me → your server IP
- After deploy, go to **Caching → Purge Everything** to clear stale 404s

## Verification
```bash
curl -sk https://favemus.zealstore.me/health
```
Should return `{"status":"ok","ready":true,...}`.

## Troubleshooting
```bash
sudo journalctl -u favemus -f
sudo tail -f /var/log/nginx/error.log
```
