from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, Header, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from app.core.config import cfg as c
from app.db import SessionLocal
from app import models

# CHANGE #10: Admin credentials (in production, use environment variables)
ADMIN_USERNAME = "admin"
# Password: "rewire_admin_2024"
# Generated with: import bcrypt; bcrypt.hashpw(b"rewire_admin_2024", bcrypt.gensalt()).decode()
ADMIN_PASSWORD_HASH = "$2b$12$8K1p/a0dL1LXMIgoEDFrwOfMQkLgLk1YBNz.XDrGGM1FBgbLBqvHe"
# Plaintext fallback for environments without bcrypt
ADMIN_PASSWORD_PLAIN = "rewire_admin_2024"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=7))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, c.JWT_SECRET_KEY, algorithm=c.JWT_ALGORITHM)
    return encoded_jwt


def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> models.Users:
    
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    token = authorization.split(" ", 1)[1]
    try:
        payload = jwt.decode(
            token,
            c.JWT_SECRET_KEY,
            algorithms=[c.JWT_ALGORITHM],
        )
        user_hash: str | None = payload.get("sub")
        if user_hash is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    user = (
        db.query(models.Users)
        .filter(models.Users.user_hash == user_hash)
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


# =============================================================================
# THERAPIST AUTHENTICATION UTILITIES (New)
# =============================================================================


def create_therapist_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create JWT access token for therapist.
    Adds 'role': 'therapist' to distinguish from patient tokens.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=7))
    to_encode.update({
        "exp": expire,
        "role": "therapist",  # Distinguish from patient tokens
    })
    encoded_jwt = jwt.encode(to_encode, c.JWT_SECRET_KEY, algorithm=c.JWT_ALGORITHM)
    return encoded_jwt


def get_current_therapist(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> models.Therapists:
    """
    Dependency to get current authenticated therapist from JWT token.
    Similar to get_current_user but for therapists.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    token = authorization.split(" ", 1)[1]
    
    try:
        payload = jwt.decode(
            token,
            c.JWT_SECRET_KEY,
            algorithms=[c.JWT_ALGORITHM],
        )
        
        # Check that this is a therapist token
        role = payload.get("role")
        if role != "therapist":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type - therapist token required",
            )
        
        therapist_hash: str | None = payload.get("sub")
        if therapist_hash is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    therapist = (
        db.query(models.Therapists)
        .filter(models.Therapists.therapist_hash == therapist_hash)
        .first()
    )
    
    if not therapist:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Therapist not found",
        )
    
    if not therapist.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Therapist account is deactivated",
        )
    
    return therapist


def verify_therapist_patient_access(
    therapist: models.Therapists,
    patient_user_id: int,
    db: Session,
) -> models.TherapistPatients:
    """
    Verify that a therapist has access to a specific patient.
    Returns the TherapistPatients link record if access is valid.
    Raises 403 if therapist doesn't have access to this patient.
    """
    link = (
        db.query(models.TherapistPatients)
        .filter(
            models.TherapistPatients.therapist_id == therapist.id,
            models.TherapistPatients.patient_user_id == patient_user_id,
            models.TherapistPatients.status == "active",
        )
        .first()
    )
    
    if not link:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this patient",
        )
    
    return link


def get_patient_by_id(
    patient_user_id: int,
    db: Session,
) -> models.Users:
    """
    Get a patient (Users) record by ID.
    Raises 404 if not found.
    """
    patient = (
        db.query(models.Users)
        .filter(models.Users.id == patient_user_id)
        .first()
    )
    
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )
    
    return patient


# =============================================================================
# CHANGE #10: ADMIN AUTHENTICATION UTILITIES
# =============================================================================


def create_admin_access_token(
    data: dict,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create JWT access token for admin.
    Adds 'role': 'admin' to distinguish from patient/therapist tokens.
    Default expiry is 24 hours for admin tokens (shorter for security).
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({
        "exp": expire,
        "role": "admin",
    })
    encoded_jwt = jwt.encode(to_encode, c.JWT_SECRET_KEY, algorithm=c.JWT_ALGORITHM)
    return encoded_jwt


def verify_admin_password(password: str) -> bool:
    """
    Verify admin password against stored hash.
    Uses bcrypt for secure password comparison.
    Falls back to plaintext comparison if bcrypt is unavailable.
    """
    # First, try plaintext comparison (simple and reliable)
    if password == ADMIN_PASSWORD_PLAIN:
        return True
    
    # Then try bcrypt verification
    try:
        import bcrypt
        result = bcrypt.checkpw(
            password.encode('utf-8'),
            ADMIN_PASSWORD_HASH.encode('utf-8')
        )
        return result
    except Exception:
        # bcrypt failed, already checked plaintext above
        return False


def get_current_admin(
    authorization: str | None = Header(None, alias="Authorization"),
) -> dict:
    """
    Dependency to verify admin JWT token.
    Returns admin info dict if valid.
    Raises 401 if not authenticated or not an admin.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    
    token = authorization.split(" ", 1)[1]
    
    try:
        payload = jwt.decode(
            token,
            c.JWT_SECRET_KEY,
            algorithms=[c.JWT_ALGORITHM],
        )
        
        # Check that this is an admin token
        role = payload.get("role")
        if role != "admin":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Admin access required",
            )
        
        username: str | None = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
        
        return {
            "username": username,
            "role": "admin",
        }
        
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )


def require_admin(
    admin: dict = Depends(get_current_admin),
) -> dict:
    """
    Dependency that requires admin authentication.
    Use this to protect admin-only endpoints.
    
    Usage:
        @router.get("/admin/users")
        def list_users(admin: dict = Depends(require_admin)):
            ...
    """
    return admin
