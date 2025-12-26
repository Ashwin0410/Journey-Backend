# routes/admin_auth.py
# CHANGE #10: Admin Console Authentication Routes
"""
Admin authentication endpoints for the ReWire Admin Console.
Provides login, logout, and session verification for admin users.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from ..auth_utils import (
    get_db,
    create_admin_access_token,
    verify_admin_password,
    get_current_admin,
    require_admin,
    ADMIN_USERNAME,
)

r = APIRouter(prefix="/api/admin", tags=["admin-auth"])


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================

class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminLoginResponse(BaseModel):
    success: bool
    token: Optional[str] = None
    username: Optional[str] = None
    message: Optional[str] = None


class AdminMeResponse(BaseModel):
    username: str
    role: str


class AdminLogoutResponse(BaseModel):
    success: bool
    message: str


# =============================================================================
# ENDPOINTS
# =============================================================================

@r.post("/login")
def admin_login(request: AdminLoginRequest):
    """
    Admin login endpoint.
    Validates username and password, returns JWT token on success.
    """
    # Validate username
    if request.username != ADMIN_USERNAME:
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Invalid username or password"}
        )
    
    # Validate password
    if not verify_admin_password(request.password):
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Invalid username or password"}
        )
    
    # Create admin token
    try:
        token = create_admin_access_token(data={"sub": request.username})
    except Exception as e:
        print(f"[admin_auth] Token creation failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"success": False, "message": f"Token creation failed: {str(e)}"}
        )
    
    # Return success response
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "token": token,
            "username": request.username,
            "message": "Login successful"
        }
    )


@r.get("/me", response_model=AdminMeResponse)
def admin_me(admin: dict = Depends(require_admin)):
    """
    Get current admin info.
    Requires valid admin JWT token.
    """
    return AdminMeResponse(
        username=admin["username"],
        role=admin["role"],
    )


@r.post("/logout", response_model=AdminLogoutResponse)
def admin_logout(admin: dict = Depends(require_admin)):
    """
    Admin logout endpoint.
    Client should discard the token after calling this.
    Note: JWT tokens are stateless, so this is mainly for client-side cleanup.
    """
    return AdminLogoutResponse(
        success=True,
        message="Logged out successfully",
    )


@r.get("/verify")
def admin_verify_token(admin: dict = Depends(require_admin)):
    """
    Verify admin token is still valid.
    Returns 200 if valid, 401 if invalid/expired.
    Useful for checking session status on page load.
    """
    return {
        "valid": True,
        "username": admin["username"],
    }
