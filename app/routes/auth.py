from __future__ import annotations

from datetime import date, datetime
import json
from typing import Dict
from urllib.parse import urlencode
import uuid

import bcrypt
import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import cfg as c
from app.db import SessionLocal
from app import models, schemas
from app.auth_utils import create_access_token, get_current_user

r = APIRouter(prefix="/api/auth", tags=["auth"])


# ============================================================================
# PASSWORD HASHING UTILITIES
# ============================================================================


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    password_bytes = password.encode("utf-8")
    hashed_bytes = hashed.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# ============================================================================
# DATABASE DEPENDENCY
# ============================================================================


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# HELPER: AUTO-LINK PATIENT TO THERAPIST FROM PENDING INVITES
# ============================================================================


def auto_link_patient_from_invites(db: Session, user: models.Users) -> None:
    """
    Check if there are any pending invites for this user's email.
    If found, automatically link the patient to the therapist.
    """
    if not user.email:
        return
    
    try:
        # Find all pending invites for this email
        pending_invites = (
            db.query(models.PatientInvites)
            .filter(
                models.PatientInvites.patient_email == user.email.lower(),
                models.PatientInvites.status == "pending",
            )
            .all()
        )
        
        for invite in pending_invites:
            # Check if invite has expired
            if invite.expires_at and invite.expires_at < datetime.utcnow():
                invite.status = "expired"
                continue
            
            # Check if link already exists
            existing_link = (
                db.query(models.TherapistPatients)
                .filter(
                    models.TherapistPatients.therapist_id == invite.therapist_id,
                    models.TherapistPatients.patient_user_id == user.id,
                )
                .first()
            )
            
            if existing_link:
                # Reactivate if needed
                if existing_link.status != "active":
                    existing_link.status = "active"
                    existing_link.initial_focus = invite.initial_focus
            else:
                # Create new link
                new_link = models.TherapistPatients(
                    therapist_id=invite.therapist_id,
                    patient_user_id=user.id,
                    initial_focus=invite.initial_focus,
                    status="active",
                    ba_week=1,
                )
                db.add(new_link)
            
            # Mark invite as accepted
            invite.status = "accepted"
            invite.accepted_user_id = user.id
            invite.accepted_at = datetime.utcnow()
        
        db.commit()
    except Exception as e:
        # Log error but don't fail the auth flow
        print(f"Error auto-linking patient from invites: {e}")
        db.rollback()


# ============================================================================
# GOOGLE OAUTH ENDPOINTS (EXISTING)
# ============================================================================


@r.get("/google/login")
def google_login() -> Dict[str, str]:

    if not c.GOOGLE_CLIENT_ID or not c.GOOGLE_REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    params = {
        "client_id": c.GOOGLE_CLIENT_ID,
        "redirect_uri": c.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "consent",
    }
    url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


    return {"auth_url": url}



@r.get("/google/callback")
def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    db: Session = Depends(get_db),
):


    # Exchange code for tokens
    token_data = {
        "code": code,
        "client_id": c.GOOGLE_CLIENT_ID,
        "client_secret": c.GOOGLE_CLIENT_SECRET,
        "redirect_uri": c.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    token_resp = requests.post(
        "https://oauth2.googleapis.com/token",
        data=token_data,
        timeout=10,
    )

    if not token_resp.ok:
        raise HTTPException(
            status_code=400,
            detail=f"Google token exchange failed: {token_resp.text}",
        )

    token_json = token_resp.json()
    access_token = token_json.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="No access_token from Google")


    userinfo_resp = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )

    if not userinfo_resp.ok:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to fetch user info: {userinfo_resp.text}",
        )

    ui = userinfo_resp.json()
    email = ui.get("email")
    sub = ui.get("sub")  # stable Google user id
    name = ui.get("name")

    if not email or not sub:
        raise HTTPException(status_code=400, detail="Google user info incomplete")

    user_hash = f"google_{sub}"

    user = (
        db.query(models.Users)
        .filter(
            models.Users.provider == "google",
            models.Users.provider_id == sub,
        )
        .first()
    )

    today = date.today()
    is_new_user = False

    if not user:
        is_new_user = True
        user = models.Users(
            user_hash=user_hash,
            email=email,
            name=name,
            provider="google",
            provider_id=sub,
            profile_json=json.dumps(ui),
            journey_day=1,
            last_journey_date=today,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
      
        user.email = email
        user.name = name
        user.profile_json = json.dumps(ui)
        if user.journey_day is None:
            user.journey_day = 1
        if user.last_journey_date is None:
            user.last_journey_date = today
        db.commit()
        db.refresh(user)

    # Auto-link patient to therapist if there are pending invites
    auto_link_patient_from_invites(db, user)

    jwt_token = create_access_token({"sub": user.user_hash})

    
    frontend_url = f"{c.FRONTEND_BASE_URL}/?token={jwt_token}"

    return RedirectResponse(url=frontend_url, status_code=302)


# ============================================================================
# CURRENT USER ENDPOINT (EXISTING)
# ============================================================================


@r.get("/me", response_model=schemas.UserOut)
def get_me(
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):

    today = date.today()
    changed = False

    user = current_user

    if user.journey_day is None:
        user.journey_day = 1
        changed = True

    if user.last_journey_date is None:
        user.last_journey_date = today
        changed = True
    else:
        if user.last_journey_date != today:
            user.journey_day = (user.journey_day or 1) + 1
            user.last_journey_date = today
            changed = True

    if changed:

        user = db.merge(user)
        db.commit()
        db.refresh(user)

    return user


# ============================================================================
# EMAIL/PASSWORD AUTHENTICATION ENDPOINTS (NEW)
# ============================================================================


@r.post("/register")
def register(
    payload: schemas.RegisterIn,
    db: Session = Depends(get_db),
):
    """
    Register a new user with email and password.
    
    - Creates a new user with provider="email"
    - Hashes the password using bcrypt
    - Returns the user object (frontend will need to call /login to get token)
    """
    
    # Check if email already exists
    existing_user = (
        db.query(models.Users)
        .filter(models.Users.email == payload.email)
        .first()
    )
    
    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="An account with this email already exists",
        )
    
    # Generate unique user_hash for email users
    unique_id = uuid.uuid4().hex[:12]
    user_hash = f"email_{unique_id}"
    
    # Hash the password
    password_hashed = hash_password(payload.password)
    
    today = date.today()
    
    # Create new user
    user = models.Users(
        user_hash=user_hash,
        email=payload.email,
        name=payload.name,
        provider="email",
        provider_id=None,
        password_hash=password_hashed,
        profile_json=None,
        journey_day=1,
        last_journey_date=today,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Auto-link patient to therapist if there are pending invites
    auto_link_patient_from_invites(db, user)
    
    # Return user as dictionary
    return {
        "id": user.id,
        "user_hash": user.user_hash,
        "email": user.email,
        "name": user.name,
        "provider": user.provider,
        "journey_day": user.journey_day,
        "last_journey_date": str(user.last_journey_date) if user.last_journey_date else None,
        "onboarding_complete": user.onboarding_complete,
        "safety_flag": user.safety_flag,
        "last_phq9_date": str(user.last_phq9_date) if user.last_phq9_date else None,
    }


@r.post("/login")
def login(
    payload: schemas.LoginIn,
    db: Session = Depends(get_db),
):
    """
    Login with email and password.
    
    - Validates email exists and password matches
    - Returns JWT token and user object
    """
    
    # Find user by email
    user = (
        db.query(models.Users)
        .filter(models.Users.email == payload.email)
        .first()
    )
    
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )
    
    # Check if this is an email user (has password_hash)
    if user.provider != "email" or not user.password_hash:
        raise HTTPException(
            status_code=401,
            detail="This account uses Google sign-in. Please use 'Sign in with Google'.",
        )
    
    # Verify password
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password",
        )
    
    # Update journey day if needed
    today = date.today()
    if user.journey_day is None:
        user.journey_day = 1
    if user.last_journey_date is None:
        user.last_journey_date = today
    elif user.last_journey_date != today:
        user.journey_day = (user.journey_day or 1) + 1
        user.last_journey_date = today
    
    db.commit()
    db.refresh(user)
    
    # Auto-link patient to therapist if there are pending invites
    auto_link_patient_from_invites(db, user)
    
    # Create JWT token
    jwt_token = create_access_token({"sub": user.user_hash})
    
    # Return as plain dictionary to avoid Pydantic validation issues
    return {
        "access_token": jwt_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "user_hash": user.user_hash,
            "email": user.email,
            "name": user.name,
            "provider": user.provider,
            "journey_day": user.journey_day,
            "last_journey_date": str(user.last_journey_date) if user.last_journey_date else None,
            "onboarding_complete": user.onboarding_complete,
            "safety_flag": user.safety_flag,
            "last_phq9_date": str(user.last_phq9_date) if user.last_phq9_date else None,
        },
    }
