"""Health check endpoints."""
from fastapi import APIRouter
from backend.core.database import SessionLocal
from backend.models.models import User, Session, Message, Ticket, Order, Product, Tenant
import time

router = APIRouter(tags=["health"])

_START_TIME = time.time()


@router.get("/health")
async def health():
    return {"status": "ok", "ready": True, "service": "favemus", "version": "3.0.0"}


@router.get("/healthz")
async def healthz():
    db = SessionLocal()
    counts = {}
    for model, name in [(User, "users"), (Session, "sessions"), (Message, "messages"),
                        (Ticket, "tickets"), (Order, "orders"), (Product, "products"),
                        (Tenant, "tenants")]:
        try:
            counts[name] = db.query(model).count()
        except Exception:
            counts[name] = 0
    db.close()
    return {
        "status": "ok",
        "ready": True,
        "uptime_seconds": round(time.time() - _START_TIME, 1),
        "service": "favemus",
        "version": "3.0.0",
        "data": counts,
    }
