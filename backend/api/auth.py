"""Authentication endpoints (JWT-based)."""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.auth import (
    hash_password, verify_password,
    create_access_token, create_refresh_token, decode_token,
)
from backend.core.database import get_db
from backend.models.models import User, Tenant

router = APIRouter(tags=["auth"])


class RegisterIn(BaseModel):
    email: str
    password: str
    name: str | None = None


class LoginIn(BaseModel):
    email: str
    password: str


def _current_user(request: Request, db: Session) -> dict | None:
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        token = request.cookies.get("favemus_token", "")
    from backend.core.auth import get_current_user
    user_data = get_current_user(token)
    if user_data is None:
        return None
    user = db.query(User).filter(User.id == user_data["id"]).first()
    if not user or not user.is_active:
        return None
    return user


def _require_login(request: Request, db: Session) -> User:
    user = _current_user(request, db)
    if not user:
        raise HTTPException(401, "Login required")
    return user


def _require_admin(request: Request, db: Session) -> User:
    user = _require_login(request, db)
    if user.role != "admin":
        raise HTTPException(403, "Admin required")
    return user


@router.post("/auth/register")
async def register(req: RegisterIn, request: Request, db: Session = Depends(get_db)):
    tenant_slug = request.headers.get("X-Tenant-Id", "default")
    tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()
    if not tenant:
        raise HTTPException(404, "Tenant not found")

    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "Valid email required")
    if not req.password or len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    existing = db.query(User).filter(User.email == email, User.tenant_id == tenant_slug).first()
    if existing:
        raise HTTPException(409, "Email already registered")

    user_count = db.query(User).filter(User.tenant_id == tenant_slug).count()
    role = "admin" if user_count == 0 else "user"

    user = User(
        email=email,
        name=req.name or email.split("@")[0],
        pass_hash=hash_password(req.password),
        role=role,
        tenant_id=tenant_slug,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    access_token = create_access_token(user.id, tenant_slug, role)
    refresh_token = create_refresh_token(user.id, tenant_slug)

    return JSONResponse({
        "ok": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "tenant_id": tenant_slug,
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
    }, headers={
        "Set-Cookie": f"favemus_token={access_token}; Path=/; HttpOnly; SameSite=Lax; Secure",
    })


@router.post("/auth/login")
async def login(req: LoginIn, request: Request, db: Session = Depends(get_db)):
    tenant_slug = request.headers.get("X-Tenant-Id", "default")
    email = req.email.strip().lower()

    user = db.query(User).filter(User.email == email, User.tenant_id == tenant_slug).first()
    if not user or not user.is_active or not verify_password(req.password, user.pass_hash):
        raise HTTPException(401, "Invalid email or password")

    access_token = create_access_token(user.id, tenant_slug, user.role)
    refresh_token = create_refresh_token(user.id, tenant_slug)

    return JSONResponse({
        "ok": True,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "tenant_id": tenant_slug,
        },
        "access_token": access_token,
        "refresh_token": refresh_token,
    }, headers={
        "Set-Cookie": f"favemus_token={access_token}; Path=/; HttpOnly; SameSite=Lax; Secure",
    })


@router.post("/auth/logout")
async def logout(request: Request, db: Session = Depends(get_db)):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if not token:
        token = request.cookies.get("favemus_token", "")
    payload = decode_token(token)
    if payload:
        # Invalidate refresh token sessions if needed
        pass
    resp = JSONResponse({"ok": True})
    resp.delete_cookie("favemus_token", path="/")
    return resp


@router.get("/auth/me")
async def me(request: Request, db: Session = Depends(get_db)):
    user = _require_login(request, db)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "tenant_id": user.tenant_id,
        },
        "tenant_id": user.tenant_id,
    }
