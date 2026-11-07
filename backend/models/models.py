"""SQLAlchemy models for Favemus platform."""
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from ..core.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    domain = Column(String(255))
    plan = Column(String(20), default="starter")
    status = Column(String(20), default="active")
    stripe_customer_id = Column(String(255))
    subscription_status = Column(String(20), default="trial")
    owner_email = Column(String(255))
    created_at = Column(DateTime, server_default=func.now())

    users = relationship("User", back_populates="tenant")
    orders = relationship("Order", back_populates="tenant")
    products = relationship("Product", back_populates="tenant")
    sessions = relationship("Session", back_populates="tenant")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False, index=True)
    name = Column(String(100))
    pass_hash = Column(String(255), nullable=False)
    role = Column(String(20), default="user")
    is_active = Column(Boolean, default=True)
    tenant_id = Column(String(50), ForeignKey("tenants.slug"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    tenant = relationship("Tenant", back_populates="users")

    __table_args__ = (
        Index("idx_users_email_tenant", "email", "tenant_id", unique=True),
    )


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    token_hash = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(String(50), nullable=False)
    expires_at = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String(100), primary_key=True)
    user_id = Column(String(255))
    channel = Column(String(50))
    shop = Column(String(100), default="favemus")
    state = Column(String(50), default="idle")
    pending_tool = Column(String(100))
    collected = Column(Text, default="{}")
    tenant_id = Column(String(50), ForeignKey("tenants.slug"), nullable=False, default="default")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="sessions")
    messages = relationship("Message", back_populates="session")
    tickets = relationship("Ticket", back_populates="session")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), ForeignKey("sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)
    content = Column(Text)
    meta = Column(Text)
    tenant_id = Column(String(50), nullable=False, default="default")
    created_at = Column(DateTime, server_default=func.now())

    session = relationship("Session", back_populates="messages")


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), ForeignKey("sessions.id"))
    shop = Column(String(100), default="favemus")
    kind = Column(String(50))
    status = Column(String(20), default="open")
    payload = Column(Text)
    tenant_id = Column(String(50), ForeignKey("tenants.slug"), nullable=False, default="default")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    session = relationship("Session", back_populates="tickets")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(100), ForeignKey("sessions.id"))
    message = Column(Text)
    analysis = Column(Text)
    tool_call = Column(Text)
    action = Column(String(50))
    latency_ms = Column(Float)
    tenant_id = Column(String(50), nullable=False, default="default")
    created_at = Column(DateTime, server_default=func.now())


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(100), nullable=False)
    item = Column(String(255))
    amount = Column(Float, default=0)
    currency = Column(String(10), default="INR")
    status = Column(String(50), default="processing")
    eta = Column(String(50))
    refund = Column(Text)
    tracking_json = Column(Text, default="[]")
    tenant_id = Column(String(50), ForeignKey("tenants.slug"), nullable=False, default="default")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="orders")

    __table_args__ = (
        Index("idx_orders_order_id_tenant", "order_id", "tenant_id", unique=True),
    )


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(100), nullable=False)
    name = Column(String(255))
    fabric = Column(String(100))
    colors_json = Column(Text, default="[]")
    price = Column(Float, default=0)
    currency = Column(String(10), default="INR")
    sizes_json = Column(Text, default="[]")
    available = Column(Boolean, default=True)
    tenant_id = Column(String(50), ForeignKey("tenants.slug"), nullable=False, default="default")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    tenant = relationship("Tenant", back_populates="products")

    __table_args__ = (
        Index("idx_products_sku_tenant", "sku", "tenant_id", unique=True),
    )


class WhatsAppSeen(Base):
    __tablename__ = "whatsapp_seen"

    message_id = Column(String(255), primary_key=True)
    wa_id = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())


class TelegramSeen(Base):
    __tablename__ = "telegram_seen"

    message_id = Column(String(255), primary_key=True)
    chat_id = Column(String(100))
    created_at = Column(DateTime, server_default=func.now())
