"""
Therapist Authentication Routes

Handles therapist registration, login, and profile retrieval.
Separate from patient auth to maintain clear separation of concerns.
"""

from __future__ import annotations

import hashlib
import uuid
import base64
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from passlib.context import CryptContext

from app.db import SessionLocal
from app import models, schemas
from app.auth_utils import create_therapist_access_token, get_current_therapist


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Router with prefix for all therapist auth endpoints
r = APIRouter(prefix="/api/therapist/auth", tags=["therapist-auth"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _generate_therapist_hash(email: str) -> str:
    """Generate a unique hash for therapist based on email."""
    unique_str = f"therapist:{email}:{uuid.uuid4().hex}"
    return hashlib.sha256(unique_str.encode()).hexdigest()[:24]


def _hash_password(password: str) -> str:
    """
    Hash a password using bcrypt with SHA256 pre-hashing.
    
    This handles passwords of any length by first hashing with SHA256,
    then base64 encoding (44 chars), which is well under bcrypt's 72-byte limit.
    """
    # Ensure password is a string and encode to bytes
    password_bytes = password.encode('utf-8') if isinstance(password, str) else password
    # Pre-hash with SHA256 to handle passwords of any length
    sha256_hash = hashlib.sha256(password_bytes).digest()
    # Base64 encode to get a safe string (44 chars, well under 72 bytes)
    password_b64 = base64.b64encode(sha256_hash).decode('utf-8')
    # Extra safety: truncate to 72 bytes (though base64 of SHA256 is always 44 chars)
    return pwd_context.hash(password_b64[:72])


def _verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash using SHA256 pre-hashing.
    
    Must use the same pre-hashing method as _hash_password.
    """
    try:
        # Ensure password is a string and encode to bytes
        password_bytes = plain_password.encode('utf-8') if isinstance(plain_password, str) else plain_password
        # Pre-hash with SHA256 (same as during hashing)
        sha256_hash = hashlib.sha256(password_bytes).digest()
        password_b64 = base64.b64encode(sha256_hash).decode('utf-8')
        # Extra safety: truncate to 72 bytes
        return pwd_context.verify(password_b64[:72], hashed_password)
    except Exception:
        # If verification fails for any reason (e.g., malformed hash), return False
        return False


# =============================================================================
# REGISTRATION
# =============================================================================


@r.post("/register", response_model=schemas.TherapistTokenOut)
def register_therapist(
    payload: schemas.TherapistRegisterIn,
    db: Session = Depends(get_db),
):
    """
    Register a new therapist account.
    
    Returns JWT token and therapist data on success.
    """
    # Check if email already exists
    existing = (
        db.query(models.Therapists)
        .filter(models.Therapists.email == payload.email.lower().strip())
        .first()
    )
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Validate password length
    if len(payload.password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 6 characters",
        )
    
    # Create therapist record
    therapist_hash = _generate_therapist_hash(payload.email)
    password_hash = _hash_password(payload.password)
    
    therapist = models.Therapists(
        therapist_hash=therapist_hash,
        email=payload.email.lower().strip(),
        name=payload.name.strip() if payload.name else None,
        title=payload.title.strip() if payload.title else None,
        specialty=payload.specialty.strip() if payload.specialty else None,
        password_hash=password_hash,
        is_active=True,
        # Default settings
        settings_json=None,
    )
    
    db.add(therapist)
    db.commit()
    db.refresh(therapist)
    
    # Create JWT token
    access_token = create_therapist_access_token(
        data={"sub": therapist.therapist_hash}
    )
    
    return schemas.TherapistTokenOut(
        access_token=access_token,
        token_type="bearer",
        therapist=schemas.TherapistOut(
            id=therapist.id,
            therapist_hash=therapist.therapist_hash,
            email=therapist.email,
            name=therapist.name,
            title=therapist.title,
            specialty=therapist.specialty,
            profile_image_url=therapist.profile_image_url,
            is_active=therapist.is_active,
            created_at=therapist.created_at,
        ),
    )


# =============================================================================
# LOGIN
# =============================================================================


@r.post("/login", response_model=schemas.TherapistTokenOut)
def login_therapist(
    payload: schemas.TherapistLoginIn,
    db: Session = Depends(get_db),
):
    """
    Login with email and password.
    
    Returns JWT token and therapist data on success.
    """
    # Find therapist by email
    therapist = (
        db.query(models.Therapists)
        .filter(models.Therapists.email == payload.email.lower().strip())
        .first()
    )
    
    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Verify password
    if not _verify_password(payload.password, therapist.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    
    # Check if account is active
    if not therapist.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )
    
    # Create JWT token
    access_token = create_therapist_access_token(
        data={"sub": therapist.therapist_hash}
    )
    
    return schemas.TherapistTokenOut(
        access_token=access_token,
        token_type="bearer",
        therapist=schemas.TherapistOut(
            id=therapist.id,
            therapist_hash=therapist.therapist_hash,
            email=therapist.email,
            name=therapist.name,
            title=therapist.title,
            specialty=therapist.specialty,
            profile_image_url=therapist.profile_image_url,
            is_active=therapist.is_active,
            created_at=therapist.created_at,
        ),
    )


# =============================================================================
# GET CURRENT THERAPIST (ME)
# =============================================================================


@r.get("/me", response_model=schemas.TherapistOut)
def get_me(
    current_therapist: models.Therapists = Depends(get_current_therapist),
):
    """
    Get current authenticated therapist's profile.
    
    Requires valid therapist JWT token.
    """
    return schemas.TherapistOut(
        id=current_therapist.id,
        therapist_hash=current_therapist.therapist_hash,
        email=current_therapist.email,
        name=current_therapist.name,
        title=current_therapist.title,
        specialty=current_therapist.specialty,
        profile_image_url=current_therapist.profile_image_url,
        is_active=current_therapist.is_active,
        created_at=current_therapist.created_at,
    )


# =============================================================================
# UPDATE PROFILE
# =============================================================================


class TherapistProfileUpdateIn(schemas.BaseModel):
    """Schema for updating therapist profile."""
    name: str | None = None
    title: str | None = None
    specialty: str | None = None
    profile_image_url: str | None = None


@r.patch("/me", response_model=schemas.TherapistOut)
def update_profile(
    payload: TherapistProfileUpdateIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Update current therapist's profile.
    
    Only updates fields that are provided (non-None).
    """
    if payload.name is not None:
        current_therapist.name = payload.name.strip() if payload.name else None
    
    if payload.title is not None:
        current_therapist.title = payload.title.strip() if payload.title else None
    
    if payload.specialty is not None:
        current_therapist.specialty = payload.specialty.strip() if payload.specialty else None
    
    if payload.profile_image_url is not None:
        current_therapist.profile_image_url = payload.profile_image_url.strip() if payload.profile_image_url else None
    
    db.commit()
    db.refresh(current_therapist)
    
    return schemas.TherapistOut(
        id=current_therapist.id,
        therapist_hash=current_therapist.therapist_hash,
        email=current_therapist.email,
        name=current_therapist.name,
        title=current_therapist.title,
        specialty=current_therapist.specialty,
        profile_image_url=current_therapist.profile_image_url,
        is_active=current_therapist.is_active,
        created_at=current_therapist.created_at,
    )


# =============================================================================
# CHANGE PASSWORD
# =============================================================================


class ChangePasswordIn(schemas.BaseModel):
    """Schema for changing password."""
    current_password: str
    new_password: str


@r.post("/change-password")
def change_password(
    payload: ChangePasswordIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Change therapist's password.
    
    Requires current password for verification.
    """
    # Verify current password
    if not _verify_password(payload.current_password, current_therapist.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    
    # Validate new password (basic validation)
    if len(payload.new_password) < 6:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 6 characters",
        )
    
    # Update password
    current_therapist.password_hash = _hash_password(payload.new_password)
    db.commit()
    
    return {"ok": True, "message": "Password changed successfully"}


# =============================================================================
# GET/UPDATE SETTINGS
# =============================================================================


@r.get("/settings", response_model=schemas.TherapistSettingsOut)
def get_settings(
    current_therapist: models.Therapists = Depends(get_current_therapist),
):
    """
    Get therapist's settings.
    """
    import json
    
    # Parse settings from JSON, use defaults if not set
    defaults = {
        "notify_patient_inactivity": True,
        "notify_milestones": True,
        "notify_daily_summary_email": False,
        "auto_suggest_activities": True,
        "ai_companion_enabled": True,
    }
    
    if current_therapist.settings_json:
        try:
            saved = json.loads(current_therapist.settings_json)
            defaults.update(saved)
        except (json.JSONDecodeError, TypeError):
            pass
    
    return schemas.TherapistSettingsOut(**defaults)


@r.patch("/settings", response_model=schemas.TherapistSettingsOut)
def update_settings(
    payload: schemas.TherapistSettingsIn,
    current_therapist: models.Therapists = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Update therapist's settings.
    
    Only updates fields that are provided (non-None).
    """
    import json
    
    # Load existing settings
    existing = {}
    if current_therapist.settings_json:
        try:
            existing = json.loads(current_therapist.settings_json)
        except (json.JSONDecodeError, TypeError):
            existing = {}
    
    # Update with new values (only non-None)
    update_data = payload.dict(exclude_unset=True, exclude_none=True)
    existing.update(update_data)
    
    # Save back to database
    current_therapist.settings_json = json.dumps(existing)
    db.commit()
    db.refresh(current_therapist)
    
    # Return full settings with defaults
    defaults = {
        "notify_patient_inactivity": True,
        "notify_milestones": True,
        "notify_daily_summary_email": False,
        "auto_suggest_activities": True,
        "ai_companion_enabled": True,
    }
    defaults.update(existing)
    
    return schemas.TherapistSettingsOut(**defaults)
