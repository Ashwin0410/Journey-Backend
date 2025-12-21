"""
Push Notifications API Routes (CHANGE #7)

Endpoints for managing Web Push subscriptions.
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..db import SessionLocal
from ..models import Users
from ..services import push as push_service
from ..core.config import cfg


r = APIRouter()


def db():
    q = SessionLocal()
    try:
        yield q
    finally:
        q.close()


# =============================================================================
# SCHEMAS
# =============================================================================


class PushSubscriptionIn(BaseModel):
    """Input schema for registering a push subscription."""
    endpoint: str
    p256dh: str
    auth: str
    user_hash: Optional[str] = None


class PushUnsubscribeIn(BaseModel):
    """Input schema for unregistering a push subscription."""
    endpoint: str


class TestPushIn(BaseModel):
    """Input schema for testing push notifications."""
    user_hash: str
    title: Optional[str] = "Test Notification"
    body: Optional[str] = "This is a test push notification from ReWire."


# =============================================================================
# ENDPOINTS
# =============================================================================


@r.get("/api/push/vapid-public-key")
def get_vapid_public_key():
    """
    Get the VAPID public key for push subscription.
    
    The frontend needs this key to subscribe to push notifications.
    """
    if not cfg.VAPID_PUBLIC_KEY:
        raise HTTPException(
            status_code=503,
            detail="Push notifications not configured"
        )
    
    return {
        "publicKey": cfg.VAPID_PUBLIC_KEY,
    }


@r.post("/api/push/subscribe")
def subscribe(
    payload: PushSubscriptionIn,
    request: Request,
    q: Session = Depends(db),
):
    """
    Register a push subscription for a user.
    
    Called by the frontend after successfully subscribing to push notifications.
    """
    if not cfg.VAPID_PUBLIC_KEY or not cfg.VAPID_PRIVATE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Push notifications not configured"
        )
    
    if not payload.endpoint:
        raise HTTPException(
            status_code=400,
            detail="Endpoint is required"
        )
    
    if not payload.p256dh or not payload.auth:
        raise HTTPException(
            status_code=400,
            detail="Encryption keys (p256dh, auth) are required"
        )
    
    user_hash = payload.user_hash
    
    # If no user_hash provided, try to get from existing subscription
    if not user_hash:
        raise HTTPException(
            status_code=400,
            detail="user_hash is required"
        )
    
    # Get user agent for device detection
    user_agent = request.headers.get("user-agent", "")
    
    # Register the subscription
    subscription = push_service.register_subscription(
        db=q,
        user_hash=user_hash,
        endpoint=payload.endpoint,
        p256dh_key=payload.p256dh,
        auth_key=payload.auth,
        user_agent=user_agent,
    )
    
    return {
        "ok": True,
        "subscription_id": subscription.id,
        "device_type": subscription.device_type,
        "message": "Push subscription registered successfully",
    }


@r.post("/api/push/unsubscribe")
def unsubscribe(
    payload: PushUnsubscribeIn,
    q: Session = Depends(db),
):
    """
    Unregister a push subscription.
    
    Called when user disables notifications or unsubscribes.
    """
    if not payload.endpoint:
        raise HTTPException(
            status_code=400,
            detail="Endpoint is required"
        )
    
    success = push_service.unregister_subscription(
        db=q,
        endpoint=payload.endpoint,
    )
    
    return {
        "ok": True,
        "unsubscribed": success,
        "message": "Subscription removed" if success else "Subscription not found",
    }


@r.get("/api/push/status")
def get_push_status(
    user_hash: str,
    q: Session = Depends(db),
):
    """
    Get push notification status for a user.
    
    Returns info about active subscriptions.
    """
    subscriptions = push_service.get_user_subscriptions(
        db=q,
        user_hash=user_hash,
        active_only=True,
    )
    
    return {
        "enabled": len(subscriptions) > 0,
        "subscription_count": len(subscriptions),
        "devices": [
            {
                "id": sub.id,
                "device_type": sub.device_type,
                "created_at": sub.created_at.isoformat() if sub.created_at else None,
                "last_push_at": sub.last_push_at.isoformat() if sub.last_push_at else None,
                "last_push_status": sub.last_push_status,
            }
            for sub in subscriptions
        ],
    }


@r.post("/api/push/test")
def test_push(
    payload: TestPushIn,
    q: Session = Depends(db),
):
    """
    Send a test push notification to a user.
    
    For testing/debugging push notification setup.
    """
    if not cfg.VAPID_PUBLIC_KEY or not cfg.VAPID_PRIVATE_KEY:
        raise HTTPException(
            status_code=503,
            detail="Push notifications not configured"
        )
    
    result = push_service.send_push_to_user(
        db=q,
        user_hash=payload.user_hash,
        title=payload.title or "Test Notification",
        body=payload.body or "This is a test push notification from ReWire.",
        tag="test",
        url="/",
        data={
            "type": "test",
        },
    )
    
    return {
        "ok": result.get("success", False),
        "sent": result.get("sent", 0),
        "failed": result.get("failed", 0),
        "total_subscriptions": result.get("total_subscriptions", 0),
        "message": f"Sent to {result.get('sent', 0)} device(s)",
    }
