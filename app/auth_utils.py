from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Header, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import cfg as c
from app.db import SessionLocal
from app import models


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
    """
    Create a signed JWT carrying at least {"sub": user_hash}.
    Default expiry = 7 days.
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=7))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, c.JWT_SECRET_KEY, algorithm=c.JWT_ALGORITHM)
    return encoded_jwt


def get_current_user(
    authorization: str | None = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
) -> models.Users:
    """
    Simple Bearer token auth:
    - Expect header: Authorization: Bearer <jwt>
    - JWT payload must contain "sub" = user_hash.
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
