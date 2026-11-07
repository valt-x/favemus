"""Favemus — FastAPI application entry point."""
import os
import time
import sys
import pathlib
from contextlib import asynccontextmanager

# Add project root to path
BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse

from backend.core.config import PORT
from backend.core.database import init_db
from backend.core.auth import hash_password, verify_password

# Import all route modules
from backend.api import auth, chat, orders, products, users, tenants, webhooks, health

_START_TIME = time.time()

app = FastAPI(
    title="Favemus",
    description="AI Customer Support Platform",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), html=True), name="static")

# Mount templates
templates_dir = BASE_DIR / "templates"
if templates_dir.exists():
    @app.get("/", response_class=HTMLResponse)
    async def home():
        return FileResponse(str(templates_dir / "home.html"))

    @app.get("/client", response_class=HTMLResponse)
    async def client():
        return FileResponse(str(templates_dir / "client.html"))

    @app.get("/owner", response_class=HTMLResponse)
    async def owner():
        return FileResponse(str(templates_dir / "owner.html"))

    @app.get("/login", response_class=HTMLResponse)
    async def login_page():
        return FileResponse(str(templates_dir / "auth.html"))

    @app.get("/register", response_class=HTMLResponse)
    async def register_page():
        return FileResponse(str(templates_dir / "auth.html"))

# Include routers
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(orders.router)
app.include_router(products.router)
app.include_router(users.router)
app.include_router(tenants.router)
app.include_router(webhooks.router)

# Serve root-level static files
@app.get("/favicon.svg")
async def favicon():
    return FileResponse(str(BASE_DIR / "favicon.svg"))

@app.get("/robots.txt")
async def robots():
    return FileResponse(str(BASE_DIR / "robots.txt"))

@app.get("/404.html")
async def not_found():
    return FileResponse(str(BASE_DIR / "404.html"))

@app.get("/500.html")
async def server_error():
    return FileResponse(str(BASE_DIR / "500.html"))


@asynccontextmanager
async def lifespan(app):
    init_db()
    # Seed default tenant + data
    from backend.services.seed import seed_default_data
    seed_default_data()
    print("Favemus platform started", flush=True)
    yield
    print("Favemus platform shutting down", flush=True)


app.router.lifespan_context = lifespan
app._start_time = _START_TIME
