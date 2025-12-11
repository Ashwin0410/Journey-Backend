from __future__ import annotations

from datetime import date
import hashlib
import json
from typing import Dict
from urllib.parse import urlencode

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



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==================== CHANGE #2: Password Hashing Utilities ====================

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except Exception:
        return False


def generate_user_hash_from_email(email: str) -> str:
    """Generate a unique user_hash from email for email/password users"""
    email_lower = email.lower().strip()
    hash_input = f"email_{email_lower}"
    return f"email_{hashlib.sha256(hash_input.encode()).hexdigest()[:16]}"


# ==================== END Password Hashing Utilities ====================



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

    if not user:

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

    
    jwt_token = create_access_token({"sub": user.user_hash})

    
    frontend_url = f"{c.FRONTEND_BASE_URL}/?token={jwt_token}"

    return RedirectResponse(url=frontend_url, status_code=302)


# ==================== CHANGE #2: Email/Password Registration ====================

@r.post("/register", response_model=schemas.TokenOut)
def register_with_email(
    payload: schemas.EmailRegisterIn,
    db: Session = Depends(get_db),
):
    """Register a new user with email and password"""
    
    email = payload.email.lower().strip()
    password = payload.password
    name = payload.name
    
    # Validate email format (basic check)
    if not email or "@" not in email or "." not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")
    
    # Check if email already exists
    existing_user = (
        db.query(models.Users)
        .filter(models.Users.email == email)
        .first()
    )
    
    if existing_user:
        raise HTTPException(
            status_code=400, 
            detail="An account with this email already exists"
        )
    
    # Generate user_hash and password_hash
    user_hash = generate_user_hash_from_email(email)
    password_hash = hash_password(password)
    
    today = date.today()
    
    # Create new user
    user = models.Users(
        user_hash=user_hash,
        email=email,
        name=name,
        provider="email",
        provider_id=email,  # For email users, provider_id is the email
        password_hash=password_hash,
        journey_day=1,
        last_journey_date=today,
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    # Create JWT token
    jwt_token = create_access_token({"sub": user.user_hash})
    
    return schemas.TokenOut(
        access_token=jwt_token,
        token_type="bearer",
        user=schemas.UserOut.from_orm(user),
    )


# ==================== CHANGE #2: Email/Password Login ====================

@r.post("/login", response_model=schemas.TokenOut)
def login_with_email(
    payload: schemas.EmailLoginIn,
    db: Session = Depends(get_db),
):
    """Login with email and password"""
    
    email = payload.email.lower().strip()
    password = payload.password
    
    # Find user by email
    user = (
        db.query(models.Users)
        .filter(models.Users.email == email)
        .first()
    )
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Check if this is an email/password user
    if user.provider != "email":
        raise HTTPException(
            status_code=400,
            detail=f"This account uses {user.provider} login. Please sign in with {user.provider.title()}."
        )
    
    # Verify password
    if not user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Update journey_day if needed
    today = date.today()
    changed = False
    
    if user.journey_day is None:
        user.journey_day = 1
        changed = True
    
    if user.last_journey_date is None:
        user.last_journey_date = today
        changed = True
    elif user.last_journey_date != today:
        user.journey_day = (user.journey_day or 1) + 1
        user.last_journey_date = today
        changed = True
    
    if changed:
        db.commit()
        db.refresh(user)
    
    # Create JWT token
    jwt_token = create_access_token({"sub": user.user_hash})
    
    return schemas.TokenOut(
        access_token=jwt_token,
        token_type="bearer",
        user=schemas.UserOut.from_orm(user),
    )


# ==================== END CHANGE #2 ====================



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
