"""Billing endpoints (Stripe)."""
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from backend.core.config import STRIPE_SECRET_KEY
from backend.services.billing import create_checkout_session, handle_webhook, get_billing_status

router = APIRouter(tags=["billing"])


class CheckoutIn(BaseModel):
    plan: str = "starter"
    success_url: str = "https://favemus.zealstore.me/owner?checkout=success"
    cancel_url: str = "https://favemus.zealstore.me/owner?checkout=cancelled"


@router.post("/saas/billing/checkout")
async def billing_checkout(req: CheckoutIn, request: Request):
    tenant_slug = request.headers.get("X-Tenant-Id", "default")
    if not STRIPE_SECRET_KEY:
        raise HTTPException(503, "Stripe not configured. Set STRIPE_SECRET_KEY in favemus.env")
    result = create_checkout_session(tenant_slug, req.plan, req.success_url, req.cancel_url)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result


@router.post("/saas/billing/webhook")
async def billing_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")
    result = handle_webhook(payload, sig_header)
    if result.get("error"):
        raise HTTPException(400, result["error"])
    return result


@router.get("/saas/billing/status")
async def billing_status(request: Request):
    tenant_slug = request.headers.get("X-Tenant-Id", "default")
    return get_billing_status(tenant_slug)
