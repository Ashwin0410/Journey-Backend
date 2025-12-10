import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import cfg as c
try:
    from app.core.logging import configure_logging
    configure_logging()
except Exception:
    pass
try:
    from app.db import engine
    from app.models import Base
except Exception:
    engine = None
    Base = None
app = FastAPI(
    title="ReWire Beta Backend",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=c.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
os.makedirs(c.out_dir_path, exist_ok=True)
app.mount("/public", StaticFiles(directory=str(c.out_dir_path)), name="public")

# ISSUE 8: Mount assets folder to serve static Day 1 audio (videoplayback.m4a)
# This allows /assets/videoplayback.m4a to be accessible
assets_path = Path(__file__).parent / "assets"
if assets_path.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_path)), name="assets")

if Base is not None and engine is not None:
    try:
        Base.metadata.create_all(bind=engine)
    except Exception:
        pass
from app.routes.health import r as health_r
from app.routes.journey import r as journey_r
from app.routes.feedback import r as feedback_r
from app.routes.events import r as events_r
from app.routes.activity import r as activity_r
from app.routes.journal import r as journal_r
from app.routes.today import r as today_r
from app.routes.settings import r as settings_r
from app.routes import auth as auth_routes
from app.routes import intake as intake_routes  # NEW
from app.routes.profile import r as profile_r
from app.routes.intake_edit import r as intake_edit_r
app.include_router(health_r)
app.include_router(journey_r)
app.include_router(feedback_r)
app.include_router(events_r)
app.include_router(activity_r)
app.include_router(journal_r)
app.include_router(today_r)
app.include_router(settings_r)
app.include_router(auth_routes.r)
app.include_router(intake_routes.r)
app.include_router(profile_r)
app.include_router(intake_edit_r)
