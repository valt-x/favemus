# Favemus Troubleshooting

## Service won't start
```bash
sudo journalctl -u favemus --no-pager -n 50
```
Common issues:
- Port 8091 in use → `sudo ss -tlnp | grep 8091`
- Python error → check tracebacks
- Model fails to load → check `HF_HOME` and disk space

## AI always returns "clarify"
- `FAVEMUS_CONFIDENCE_FLOOR` too high → lower it in `favemus.env`
- Laya model needs more examples → retrain or add more data
- Message is truly ambiguous → AI can't guess, that's expected

## WhatsApp not replying
- Webhook URL wrong → must be `https://your-domain/whatsapp/webhook`
- Verify token mismatch → check `WHATSAPP_VERIFY_TOKEN` in `favemus.env`
- Meta requires 24h window for free-form replies

## Telegram not replying
- Webhook not set → `curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo`
- Bot not started → send `/start` to the bot first

## Static files 404
- Check `/var/www/favemus/static/` exists and has JS files
- `sudo chown -R www-data:www-data /var/www/favemus`
- Cloudflare cache → Purge Everything

## 502 Bad Gateway
- favemus.service is down → `sudo systemctl status favemus`
- nginx config error → `sudo nginx -T`
- Check `/var/log/nginx/error.log`

## Database corruption
```bash
cp favemus.db favemus.db.bak
sqlite3 favemus.db ".recover" > recovery.sql
sqlite3 favemus.db < recovery.sql
```
