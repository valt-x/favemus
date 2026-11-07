#!/usr/bin/env bash
set -euo pipefail

# Favemus — one-command deploy
# Usage: ./deploy.sh

ROOT="$(cd "$(dirname "$0")" && pwd)"
echo "=== Favemus Deploy ==="

# 1. Dependencies check
echo "[1/6] Checking dependencies..."
command -v python3 >/dev/null 2>&1 || { echo "python3 is required"; exit 1; }
command -v systemctl >/dev/null 2>&1 || { echo "systemd is required"; exit 1; }
command -v nginx >/dev/null 2>&1 || { echo "nginx is required"; exit 1; }

# 2. Python venv setup
echo "[2/6] Setting up Python venv..."
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install fastapi uvicorn laya pydantic

# 3. Env file
if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
  echo "  → Created .env from example. Edit it with real values."
else
  echo "  → .env exists, leaving untouched"
fi

# 4. Static assets & permissions
echo "[3/6] Copying static assets to /var/www/favemus..."
sudo mkdir -p /var/www/favemus/static
sudo cp static/*.js /var/www/favemus/static/
sudo chown -R www-data:www-data /var/www/favemus

# 5. systemd service
echo "[4/6] Installing systemd service..."
sudo cp favemus.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable favemus
sudo systemctl restart favemus

# 6. nginx config
echo "[5/6] Installing nginx config..."
CFG="/etc/nginx/sites-available/favemus.zealstore.me"
if [ ! -f "$CFG" ]; then
  echo "  → You need to install nginx config manually. See docs/deployment.md"
fi
sudo nginx -t && sudo systemctl reload nginx

# 7. Health check
echo "[6/6] Verifying..."
sleep 5
if curl -sk -o /dev/null -w "%{http_code}" https://favemus.zealstore.me/health | grep -q 200; then
  echo "  ✅ Favemus is up!"
  echo "  URL: https://favemus.zealstore.me"
  echo "  Docs: https://github.com/valt-x/favemus"
else
  echo "  ⚠️ Health check failed. Check: sudo journalctl -u favemus -f"
  exit 1
fi
