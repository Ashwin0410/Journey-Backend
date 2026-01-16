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


# =============================================================================
# AUTO-MIGRATION: Database migrations on startup
# =============================================================================
def run_migrations():
    """Run database migrations on startup."""
    if engine is None:
        return
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            # -----------------------------------------------------------------
            # Migration 1: Add user_hash column to activities table
            # -----------------------------------------------------------------
            result = conn.execute(text("PRAGMA table_info(activities)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'user_hash' not in columns:
                conn.execute(text("ALTER TABLE activities ADD COLUMN user_hash TEXT"))
                conn.commit()
                print("[migration] Added user_hash column to activities table")
            
            # Check if index exists
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_activities_user_hash'"))
            if not result.fetchone():
                conn.execute(text("CREATE INDEX ix_activities_user_hash ON activities (user_hash)"))
                conn.commit()
                print("[migration] Created index ix_activities_user_hash")
            
            # -----------------------------------------------------------------
            # Migration 2: Add deleted_at column to users table (Soft Delete)
            # -----------------------------------------------------------------
            result = conn.execute(text("PRAGMA table_info(users)"))
            user_columns = [row[1] for row in result.fetchall()]
            
            if 'deleted_at' not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN deleted_at DATETIME"))
                conn.commit()
                print("[migration] Added deleted_at column to users table")
            
            # Check if index exists for deleted_at
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND name='ix_users_deleted_at'"))
            if not result.fetchone():
                conn.execute(text("CREATE INDEX ix_users_deleted_at ON users (deleted_at)"))
                conn.commit()
                print("[migration] Created index ix_users_deleted_at")
            
            # -----------------------------------------------------------------
            # Migration 3: Create ML-related tables for video recommendations
            # -----------------------------------------------------------------
            # Check if ml_questionnaire_responses table exists
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ml_questionnaire_responses'"
            ))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE ml_questionnaire_responses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_hash TEXT NOT NULL,
                        question_code TEXT NOT NULL,
                        response_value TEXT,
                        response_numeric REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX ix_ml_questionnaire_user_hash ON ml_questionnaire_responses (user_hash)"))
                conn.commit()
                print("[migration] Created ml_questionnaire_responses table")
            
            # Check if stimuli_suggestions table exists
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='stimuli_suggestions'"
            ))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE stimuli_suggestions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_hash TEXT NOT NULL,
                        stimulus_rank INTEGER NOT NULL,
                        stimulus_name TEXT NOT NULL,
                        stimulus_url TEXT,
                        stimulus_description TEXT,
                        score REAL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX ix_stimuli_suggestions_user_hash ON stimuli_suggestions (user_hash)"))
                conn.execute(text("CREATE INDEX ix_stimuli_suggestions_rank ON stimuli_suggestions (user_hash, stimulus_rank)"))
                conn.commit()
                print("[migration] Created stimuli_suggestions table")
            
            # Check if ml_questionnaire_complete column exists in users
            result = conn.execute(text("PRAGMA table_info(users)"))
            user_columns = [row[1] for row in result.fetchall()]
            
            if 'ml_questionnaire_complete' not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN ml_questionnaire_complete BOOLEAN DEFAULT 0"))
                conn.commit()
                print("[migration] Added ml_questionnaire_complete column to users table")
            
            # -----------------------------------------------------------------
            # Migration 4: Create chills tracking tables
            # -----------------------------------------------------------------
            # Check if chills_timestamps table exists
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chills_timestamps'"
            ))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE chills_timestamps (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        video_time_seconds REAL NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX ix_chills_timestamps_session_id ON chills_timestamps (session_id)"))
                conn.commit()
                print("[migration] Created chills_timestamps table")
            
            # Check if body_map_spots table exists
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='body_map_spots'"
            ))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE body_map_spots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        x_percent REAL NOT NULL,
                        y_percent REAL NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX ix_body_map_spots_session_id ON body_map_spots (session_id)"))
                conn.commit()
                print("[migration] Created body_map_spots table")
            
            # Check if post_video_responses table exists
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='post_video_responses'"
            ))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE post_video_responses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL UNIQUE,
                        insights_text TEXT,
                        value_selected TEXT,
                        value_custom TEXT,
                        action_selected TEXT,
                        action_custom TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX ix_post_video_responses_session_id ON post_video_responses (session_id)"))
                conn.commit()
                print("[migration] Created post_video_responses table")
            
    except Exception as e:
        print(f"[migration] Error running migrations: {e}")

run_migrations()
# =============================================================================


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
# Therapist Dashboard Routes (New)
from app.routes.therapist_auth import r as therapist_auth_r
from app.routes.therapist_patients import r as therapist_patients_r
from app.routes.therapist_dashboard import r as therapist_dashboard_r
from app.routes.therapist_notes import r as therapist_notes_r
from app.routes.therapist_guidance import r as therapist_guidance_r
from app.routes.therapist_activities import r as therapist_activities_r
from app.routes.therapist_resources import r as therapist_resources_r
# Push Notifications (CHANGE #7)
from app.routes.notifications import r as notifications_r
# CHANGE #10: Admin Console Routes
from app.routes.admin_auth import r as admin_auth_r
from app.routes.admin_dashboard import r as admin_dashboard_r
# ML Video Refactor: Chills tracking routes
from app.routes.chills import r as chills_r

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
# Therapist Dashboard Routers (New)
app.include_router(therapist_auth_r)
app.include_router(therapist_patients_r)
app.include_router(therapist_dashboard_r)
app.include_router(therapist_notes_r)
app.include_router(therapist_guidance_r)
app.include_router(therapist_activities_r)
app.include_router(therapist_resources_r)
# Push Notifications Router (CHANGE #7)
app.include_router(notifications_r)
# CHANGE #10: Admin Console Routers
app.include_router(admin_auth_r)
app.include_router(admin_dashboard_r)
# ML Video Refactor: Chills tracking router
app.include_router(chills_r)
