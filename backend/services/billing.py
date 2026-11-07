"""Stripe billing integration."""
import stripe
import os
from backend.core.config import STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


def create_checkout_session(tenant_slug: str, plan: str, success_url: str, cancel_url: str) -> dict:
    """Create a Stripe Checkout session for a tenant subscription."""
    if not STRIPE_SECRET_KEY:
        return {"error": "Stripe not configured", "url": None}

    price_map = {
        "starter": os.getenv("STRIPE_PRICE_STARTER", ""),
        "pro": os.getenv("STRIPE_PRICE_PRO", ""),
        "enterprise": os.getenv("STRIPE_PRICE_ENTERPRISE", ""),
    }
    price_id = price_map.get(plan)
    if not price_id:
        return {"error": f"No price configured for plan: {plan}", "url": None}

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"tenant_slug": tenant_slug, "plan": plan},
        )
        return {"url": session.url, "session_id": session.id}
    except Exception as e:
        return {"error": str(e), "url": None}


def handle_webhook(payload: bytes, sig_header: str) -> dict:
    """Handle Stripe webhook events."""
    if not STRIPE_WEBHOOK_SECRET:
        return {"error": "Stripe webhook secret not configured"}

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except ValueError:
        return {"error": "Invalid payload"}
    except stripe.error.SignatureVerificationError:
        return {"error": "Invalid signature"}

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        tenant_slug = data.get("metadata", {}).get("tenant_slug")
        plan = data.get("metadata", {}).get("plan")
        customer_id = data.get("customer")
        return {
            "action": "checkout_completed",
            "tenant_slug": tenant_slug,
            "plan": plan,
            "customer_id": customer_id,
        }

    if event_type == "customer.subscription.updated":
        return {
            "action": "subscription_updated",
            "status": data.get("status"),
            "customer_id": data.get("customer"),
        }

    if event_type == "customer.subscription.deleted":
        return {
            "action": "subscription_deleted",
            "customer_id": data.get("customer"),
        }

    return {"action": event_type, "handled": False}


def get_billing_status(tenant_slug: str) -> dict:
    """Get billing status for a tenant."""
    return {
        "plan": "starter",
        "status": "trial",
        "stripe_customer_id": None,
        "note": "Connect Stripe to enable billing",
    }
