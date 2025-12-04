# from __future__ import annotations

# import json
# from typing import Dict
# from urllib.parse import urlencode

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from fastapi.responses import HTMLResponse
# from sqlalchemy.orm import Session

# from app.core.config import cfg as c
# from app.db import SessionLocal
# from app import models, schemas
# from app.auth_utils import create_access_token, get_current_user

# r = APIRouter(prefix="/api/auth", tags=["auth"])


# # ---- DB dependency ----
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---- 1) Get Google OAuth URL ----
# @r.get("/google/login")
# def google_login() -> Dict[str, str]:
#     """
#     Returns the Google OAuth URL that the frontend should redirect to.
#     """
#     if not c.GOOGLE_CLIENT_ID or not c.GOOGLE_REDIRECT_URI:
#         raise HTTPException(status_code=500, detail="Google OAuth not configured")

#     params = {
#         "client_id": c.GOOGLE_CLIENT_ID,
#         "redirect_uri": c.GOOGLE_REDIRECT_URI,
#         "response_type": "code",
#         "scope": "openid email profile",
#         "access_type": "online",
#         "prompt": "consent",
#     }
#     url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
#     return {"auth_url": url}


# # ---- 2) Google callback: exchange code -> user, issue JWT ----
# @r.get("/google/callback", response_class=HTMLResponse)
# def google_callback(
#     code: str = Query(..., description="Authorization code from Google"),
#     db: Session = Depends(get_db),
# ):
#     """
#     Endpoint that Google redirects to.
#     - Exchanges `code` for tokens
#     - Fetches user info
#     - Upserts user in DB
#     - Issues our own JWT
#     - Returns small HTML that can postMessage back to SPA
#     """

#     # Exchange code for tokens
#     token_data = {
#         "code": code,
#         "client_id": c.GOOGLE_CLIENT_ID,
#         "client_secret": c.GOOGLE_CLIENT_SECRET,
#         "redirect_uri": c.GOOGLE_REDIRECT_URI,
#         "grant_type": "authorization_code",
#     }

#     token_resp = requests.post(
#         "https://oauth2.googleapis.com/token",
#         data=token_data,
#         timeout=10,
#     )

#     if not token_resp.ok:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Google token exchange failed: {token_resp.text}",
#         )

#     token_json = token_resp.json()
#     access_token = token_json.get("access_token")
#     if not access_token:
#         raise HTTPException(status_code=400, detail="No access_token from Google")

#     # Fetch user info
#     userinfo_resp = requests.get(
#         "https://www.googleapis.com/oauth2/v3/userinfo",
#         headers={"Authorization": f"Bearer {access_token}"},
#         timeout=10,
#     )

#     if not userinfo_resp.ok:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Failed to fetch user info: {userinfo_resp.text}",
#         )

#     ui = userinfo_resp.json()
#     email = ui.get("email")
#     sub = ui.get("sub")       # stable Google user id
#     name = ui.get("name")

#     if not email or not sub:
#         raise HTTPException(status_code=400, detail="Google user info incomplete")

#     user_hash = f"google_{sub}"

#     # Upsert user
#     user = (
#         db.query(models.Users)
#         .filter(
#             models.Users.provider == "google",
#             models.Users.provider_id == sub,
#         )
#         .first()
#     )

#     if not user:
#         user = models.Users(
#             user_hash=user_hash,
#             email=email,
#             name=name,
#             provider="google",
#             provider_id=sub,
#             profile_json=json.dumps(ui),
#         )
#         db.add(user)
#         db.commit()
#         db.refresh(user)
#     else:
#         user.email = email
#         user.name = name
#         user.profile_json = json.dumps(ui)
#         db.commit()
#         db.refresh(user)

#     # Issue our own JWT
#     jwt_token = create_access_token({"sub": user.user_hash})

#     html = f"""
#     <html>
#       <body>
#         <h2>Login successful</h2>
#         <p>You can now close this tab.</p>
#         <pre id="payload">{{
#   "access_token": "{jwt_token}",
#   "token_type": "bearer",
#   "user_hash": "{user.user_hash}",
#   "email": "{user.email}",
#   "name": "{user.name or ""}"
# }}</pre>
#         <script>
#           if (window.opener && typeof window.opener.postMessage === "function") {{
#             window.opener.postMessage(
#               {{
#                 type: "journey-auth",
#                 access_token: "{jwt_token}",
#                 token_type: "bearer",
#                 user_hash: "{user.user_hash}",
#                 email: "{user.email}",
#                 name: "{user.name or ""}"
#               }},
#               "*"
#             );
#           }}
#         </script>
#       </body>
#     </html>
#     """
#     return HTMLResponse(content=html)


# # ---- 3) /me endpoint for frontend ----
# @r.get("/me", response_model=schemas.UserOut)
# def get_me(current_user: models.Users = Depends(get_current_user)):
#     return current_user

# from __future__ import annotations

# from datetime import date
# import json
# from typing import Dict
# from urllib.parse import urlencode

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from fastapi.responses import HTMLResponse
# from sqlalchemy.orm import Session

# from app.core.config import cfg as c
# from app.db import SessionLocal
# from app import models, schemas
# from app.auth_utils import create_access_token, get_current_user

# r = APIRouter(prefix="/api/auth", tags=["auth"])


# # ---- DB dependency ----
# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---- 1) Get Google OAuth URL ----
# @r.get("/google/login")
# def google_login() -> Dict[str, str]:
#     """
#     Returns the Google OAuth URL that the frontend should redirect to.
#     """
#     if not c.GOOGLE_CLIENT_ID or not c.GOOGLE_REDIRECT_URI:
#         raise HTTPException(status_code=500, detail="Google OAuth not configured")

#     params = {
#         "client_id": c.GOOGLE_CLIENT_ID,
#         "redirect_uri": c.GOOGLE_REDIRECT_URI,
#         "response_type": "code",
#         "scope": "openid email profile",
#         "access_type": "online",
#         "prompt": "consent",
#     }
#     url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
#     return {"auth_url": url}


# # ---- 2) Google callback: exchange code -> user, issue JWT ----
# @r.get("/google/callback", response_class=HTMLResponse)
# def google_callback(
#     code: str = Query(..., description="Authorization code from Google"),
#     db: Session = Depends(get_db),
# ):
#     """
#     Endpoint that Google redirects to.
#     - Exchanges `code` for tokens
#     - Fetches user info
#     - Upserts user in DB
#     - Issues our own JWT
#     - Returns small HTML that can postMessage back to SPA
#     """

#     # Exchange code for tokens
#     token_data = {
#         "code": code,
#         "client_id": c.GOOGLE_CLIENT_ID,
#         "client_secret": c.GOOGLE_CLIENT_SECRET,
#         "redirect_uri": c.GOOGLE_REDIRECT_URI,
#         "grant_type": "authorization_code",
#     }

#     token_resp = requests.post(
#         "https://oauth2.googleapis.com/token",
#         data=token_data,
#         timeout=10,
#     )

#     if not token_resp.ok:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Google token exchange failed: {token_resp.text}",
#         )

#     token_json = token_resp.json()
#     access_token = token_json.get("access_token")
#     if not access_token:
#         raise HTTPException(status_code=400, detail="No access_token from Google")

#     # Fetch user info
#     userinfo_resp = requests.get(
#         "https://www.googleapis.com/oauth2/v3/userinfo",
#         headers={"Authorization": f"Bearer {access_token}"},
#         timeout=10,
#     )

#     if not userinfo_resp.ok:
#         raise HTTPException(
#             status_code=400,
#             detail=f"Failed to fetch user info: {userinfo_resp.text}",
#         )

#     ui = userinfo_resp.json()
#     email = ui.get("email")
#     sub = ui.get("sub")       # stable Google user id
#     name = ui.get("name")

#     if not email or not sub:
#         raise HTTPException(status_code=400, detail="Google user info incomplete")

#     user_hash = f"google_{sub}"

#     # Upsert user
#     user = (
#         db.query(models.Users)
#         .filter(
#             models.Users.provider == "google",
#             models.Users.provider_id == sub,
#         )
#         .first()
#     )

#     today = date.today()

#     if not user:
#         # New user → start streak at day 1
#         user = models.Users(
#             user_hash=user_hash,
#             email=email,
#             name=name,
#             provider="google",
#             provider_id=sub,
#             profile_json=json.dumps(ui),
#             journey_day=1,
#             last_journey_date=today,
#         )
#         db.add(user)
#         db.commit()
#         db.refresh(user)
#     else:
#         # Existing user → update basic profile; streak handled in /me
#         user.email = email
#         user.name = name
#         user.profile_json = json.dumps(ui)
#         if user.journey_day is None:
#             user.journey_day = 1
#         if user.last_journey_date is None:
#             user.last_journey_date = today
#         db.commit()
#         db.refresh(user)

#     # Issue our own JWT (auth_utils expects a payload dict)
#     jwt_token = create_access_token({"sub": user.user_hash})

#     html = f"""
#     <html>
#       <body>
#         <h2>Login successful</h2>
#         <p>You can now close this tab.</p>
#         <pre id="payload">{{
#   "access_token": "{jwt_token}",
#   "token_type": "bearer",
#   "user_hash": "{user.user_hash}",
#   "email": "{user.email}",
#   "name": "{user.name or ""}",
#   "journey_day": {user.journey_day or 1},
#   "last_journey_date": "{user.last_journey_date.isoformat() if user.last_journey_date else ""}"
# }}</pre>
#         <script>
#           if (window.opener && typeof window.opener.postMessage === "function") {{
#             window.opener.postMessage(
#               {{
#                 type: "journey-auth",
#                 access_token: "{jwt_token}",
#                 token_type: "bearer",
#                 user_hash: "{user.user_hash}",
#                 email: "{user.email}",
#                 name: "{user.name or ""}",
#                 journey_day: {user.journey_day or 1},
#                 last_journey_date: "{user.last_journey_date.isoformat() if user.last_journey_date else ""}"
#               }},
#               "*"
#             );
#           }}
#         </script>
#       </body>
#     </html>
#     """
#     return HTMLResponse(content=html)


# # ---- 3) /me endpoint for frontend (streak-style journey_day) ----
# @r.get("/me", response_model=schemas.UserOut)
# def get_me(
#     current_user: models.Users = Depends(get_current_user),
#     db: Session = Depends(get_db),
# ):
#     """
#     Returns current user profile and AUTO-ADVANCES journey_day like a streak:

#     - First time (no journey_day) → set to 1 for today.
#     - On a new calendar day (last_journey_date != today) → journey_day += 1.
#     - No upper cap: 1, 2, 3, 4, ... forever.
#     """
#     today = date.today()
#     changed = False

#     user = current_user

#     if user.journey_day is None:
#         user.journey_day = 1
#         changed = True

#     if user.last_journey_date is None:
#         user.last_journey_date = today
#         changed = True
#     else:
#         if user.last_journey_date != today:
#             user.journey_day = (user.journey_day or 1) + 1
#             user.last_journey_date = today
#             changed = True

#     if changed:
#         db.add(user)
#         db.commit()
#         db.refresh(user)

#     return user

from __future__ import annotations

from datetime import date
import json
from typing import Dict
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import cfg as c
from app.db import SessionLocal
from app import models, schemas
from app.auth_utils import create_access_token, get_current_user

r = APIRouter(prefix="/api/auth", tags=["auth"])


# ---- DB dependency ----
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---- 1) Get Google OAuth URL ----
@r.get("/google/login")
def google_login() -> Dict[str, str]:
    """
    Returns the Google OAuth URL that the frontend should redirect to.
    """
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

    # Frontend expects { auth_url: ... }
    return {"auth_url": url}


# ---- 2) Google callback: exchange code -> user, issue JWT, redirect to SPA ----
@r.get("/google/callback")
def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    db: Session = Depends(get_db),
):
    """
    Endpoint that Google redirects to.
    - Exchanges `code` for tokens
    - Fetches user info
    - Upserts user in DB
    - Issues our own JWT
    - Redirects to frontend: /?token=...
    """

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

    # Fetch user info
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

    # Upsert user
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
        # New user → start streak at day 1
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
        # Existing user → update basic profile; streak handled in /me
        user.email = email
        user.name = name
        user.profile_json = json.dumps(ui)
        if user.journey_day is None:
            user.journey_day = 1
        if user.last_journey_date is None:
            user.last_journey_date = today
        db.commit()
        db.refresh(user)

    # Issue our own JWT (auth_utils expects a payload dict)
    jwt_token = create_access_token({"sub": user.user_hash})

    # ✅ Redirect to SPA root with token query param
    # FRONTEND_BASE_URL must be like: http://localhost:5174
    frontend_url = f"{c.FRONTEND_BASE_URL}/?token={jwt_token}"

    return RedirectResponse(url=frontend_url, status_code=302)


# ---- 3) /me endpoint for frontend (streak-style journey_day) ----
@r.get("/me", response_model=schemas.UserOut)
def get_me(
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns current user profile and AUTO-ADVANCES journey_day like a streak.
    """
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
        # ✅ avoid "already attached to session" error
        user = db.merge(user)
        db.commit()
        db.refresh(user)

    return user
