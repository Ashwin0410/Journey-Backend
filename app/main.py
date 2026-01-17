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
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_activities_user_hash ON activities (user_hash)"))
                conn.commit()
                print("[migration] Created index ix_activities_user_hash")
            
            # Add action_intention column if missing
            if 'action_intention' not in columns:
                conn.execute(text("ALTER TABLE activities ADD COLUMN action_intention TEXT"))
                conn.commit()
                print("[migration] Added action_intention column to activities table")
            
            # Add source_type column if missing
            if 'source_type' not in columns:
                conn.execute(text("ALTER TABLE activities ADD COLUMN source_type TEXT"))
                conn.commit()
                print("[migration] Added source_type column to activities table")
            
            # Add video_session_id column if missing
            if 'video_session_id' not in columns:
                conn.execute(text("ALTER TABLE activities ADD COLUMN video_session_id TEXT"))
                conn.commit()
                print("[migration] Added video_session_id column to activities table")
            
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
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_users_deleted_at ON users (deleted_at)"))
                conn.commit()
                print("[migration] Created index ix_users_deleted_at")
            
            # Add ml_questionnaire_complete column if missing
            if 'ml_questionnaire_complete' not in user_columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN ml_questionnaire_complete BOOLEAN DEFAULT 0"))
                conn.commit()
                print("[migration] Added ml_questionnaire_complete column to users table")
            
            # -----------------------------------------------------------------
            # Migration 3: Create/Fix ML Questionnaire Responses table
            # The model expects individual columns for each question, NOT generic rows
            # -----------------------------------------------------------------
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ml_questionnaire_responses'"
            ))
            table_exists = result.fetchone() is not None
            
            needs_recreate = False
            if table_exists:
                # Check if table has the CORRECT schema (individual question columns)
                result = conn.execute(text("PRAGMA table_info(ml_questionnaire_responses)"))
                existing_cols = [row[1] for row in result.fetchall()]
                # If it has the old wrong schema (question_code), we need to recreate
                if 'question_code' in existing_cols or 'dpes_1' not in existing_cols:
                    needs_recreate = True
                    print("[migration] ml_questionnaire_responses has wrong schema, will recreate")
            
            if not table_exists or needs_recreate:
                # Drop old table if exists (it had wrong schema)
                if needs_recreate:
                    conn.execute(text("DROP TABLE IF EXISTS ml_questionnaire_responses"))
                    conn.commit()
                    print("[migration] Dropped old ml_questionnaire_responses table")
                
                # Create with CORRECT schema matching MLQuestionnaireResponse model
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS ml_questionnaire_responses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_hash TEXT NOT NULL,
                        dpes_1 INTEGER,
                        dpes_4 INTEGER,
                        dpes_29 INTEGER,
                        neo_ffi_10 INTEGER,
                        neo_ffi_14 INTEGER,
                        neo_ffi_16 INTEGER,
                        neo_ffi_45 INTEGER,
                        neo_ffi_46 INTEGER,
                        kamf_4_1 INTEGER,
                        age TEXT,
                        gender TEXT,
                        ethnicity TEXT,
                        education TEXT,
                        depression_status TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ml_questionnaire_responses_user_hash ON ml_questionnaire_responses (user_hash)"))
                conn.commit()
                print("[migration] Created ml_questionnaire_responses table with correct schema")
            
            # -----------------------------------------------------------------
            # Migration 4: Create/Fix Stimuli Suggestions table
            # -----------------------------------------------------------------
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='stimuli_suggestions'"
            ))
            table_exists = result.fetchone() is not None
            
            if not table_exists:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS stimuli_suggestions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_hash TEXT NOT NULL,
                        stimulus_rank INTEGER NOT NULL,
                        stimulus_name TEXT NOT NULL,
                        stimulus_url TEXT NOT NULL,
                        stimulus_description TEXT,
                        score REAL,
                        questionnaire_id INTEGER,
                        was_shown BOOLEAN DEFAULT 0,
                        was_watched BOOLEAN DEFAULT 0,
                        was_completed BOOLEAN DEFAULT 0,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_stimuli_suggestions_user_hash ON stimuli_suggestions (user_hash)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_stimuli_suggestions_rank ON stimuli_suggestions (user_hash, stimulus_rank)"))
                conn.commit()
                print("[migration] Created stimuli_suggestions table")
            else:
                # Add missing columns to existing table
                result = conn.execute(text("PRAGMA table_info(stimuli_suggestions)"))
                stim_cols = [row[1] for row in result.fetchall()]
                
                if 'questionnaire_id' not in stim_cols:
                    conn.execute(text("ALTER TABLE stimuli_suggestions ADD COLUMN questionnaire_id INTEGER"))
                    conn.commit()
                    print("[migration] Added questionnaire_id column to stimuli_suggestions")
                
                if 'was_shown' not in stim_cols:
                    conn.execute(text("ALTER TABLE stimuli_suggestions ADD COLUMN was_shown BOOLEAN DEFAULT 0"))
                    conn.commit()
                    print("[migration] Added was_shown column to stimuli_suggestions")
                
                if 'was_watched' not in stim_cols:
                    conn.execute(text("ALTER TABLE stimuli_suggestions ADD COLUMN was_watched BOOLEAN DEFAULT 0"))
                    conn.commit()
                    print("[migration] Added was_watched column to stimuli_suggestions")
                
                if 'was_completed' not in stim_cols:
                    conn.execute(text("ALTER TABLE stimuli_suggestions ADD COLUMN was_completed BOOLEAN DEFAULT 0"))
                    conn.commit()
                    print("[migration] Added was_completed column to stimuli_suggestions")
            
            # -----------------------------------------------------------------
            # Migration 5: Create chills_timestamps table
            # -----------------------------------------------------------------
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='chills_timestamps'"
            ))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS chills_timestamps (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        video_time_seconds REAL NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chills_timestamps_session_id ON chills_timestamps (session_id)"))
                conn.commit()
                print("[migration] Created chills_timestamps table")
            
            # -----------------------------------------------------------------
            # Migration 6: Create body_map_spots table
            # -----------------------------------------------------------------
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='body_map_spots'"
            ))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS body_map_spots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        x_percent REAL NOT NULL,
                        y_percent REAL NOT NULL,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_body_map_spots_session_id ON body_map_spots (session_id)"))
                conn.commit()
                print("[migration] Created body_map_spots table")
            
            # -----------------------------------------------------------------
            # Migration 7: Create/Fix post_video_responses table
            # -----------------------------------------------------------------
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='post_video_responses'"
            ))
            table_exists = result.fetchone() is not None
            
            if not table_exists:
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS post_video_responses (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL UNIQUE,
                        user_hash TEXT,
                        insights_text TEXT,
                        value_selected TEXT,
                        value_custom TEXT,
                        action_selected TEXT,
                        action_custom TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_post_video_responses_session_id ON post_video_responses (session_id)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_post_video_responses_user_hash ON post_video_responses (user_hash)"))
                conn.commit()
                print("[migration] Created post_video_responses table")
            else:
                # Add user_hash column if missing
                result = conn.execute(text("PRAGMA table_info(post_video_responses)"))
                pvr_cols = [row[1] for row in result.fetchall()]
                
                if 'user_hash' not in pvr_cols:
                    conn.execute(text("ALTER TABLE post_video_responses ADD COLUMN user_hash TEXT"))
                    conn.commit()
                    print("[migration] Added user_hash column to post_video_responses")
            
            # -----------------------------------------------------------------
            # Migration 8: Create ml_questionnaires table (if model uses it)
            # -----------------------------------------------------------------
            result = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='ml_questionnaires'"
            ))
            if not result.fetchone():
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS ml_questionnaires (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_hash TEXT NOT NULL,
                        responses_json TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME
                    )
                """))
                conn.execute(text("CREATE INDEX IF NOT EXISTS ix_ml_questionnaires_user_hash ON ml_questionnaires (user_hash)"))
                conn.commit()
                print("[migration] Created ml_questionnaires table")
            
            print("[migration] All migrations completed successfully")
            
    except Exception as e:
        print(f"[migration] Error running migrations: {e}")
        import traceback
        traceback.print_exc()

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
