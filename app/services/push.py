"""
Push Notification Service (CHANGE #7)

Handles sending Web Push notifications to users.
Used for:
- Notifying when pre-generated audio is ready
- Activity reminders
- Journey session reminders
- Engagement notifications
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any, List

from pywebpush import webpush, WebPushException
from sqlalchemy.orm import Session

from ..models import PushSubscription, Users
from ..core.config import cfg


def _get_vapid_claims() -> Dict[str, str]:
    """Get VAPID claims for push authentication."""
    return {
        "sub": cfg.VAPID_CLAIM_EMAIL or "mailto:hello@rewire.bio"
    }


def send_push_to_user(
    db: Session,
    user_hash: str,
    title: str,
    body: str,
    data: Optional[Dict[str, Any]] = None,
    icon: Optional[str] = None,
    badge: Optional[str] = None,
    tag: Optional[str] = None,
    url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Send a push notification to all active subscriptions for a user.
    
    Args:
        db: Database session
        user_hash: User identifier
        title: Notification title
        body: Notification body text
        data: Optional extra data to send with notification
        icon: Optional icon URL
        badge: Optional badge URL (small icon)
        tag: Optional tag for notification grouping/replacement
        url: Optional URL to open when notification is clicked
    
    Returns:
        Dict with success count, failure count, and details
    """
    if not cfg.VAPID_PUBLIC_KEY or not cfg.VAPID_PRIVATE_KEY:
        print("[push] VAPID keys not configured, skipping push notification")
        return {
            "success": False,
            "error": "VAPID keys not configured",
            "sent": 0,
            "failed": 0,
        }
    
    # Get all active subscriptions for this user
    subscriptions = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.user_hash == user_hash,
            PushSubscription.is_active == True,
        )
        .all()
    )
    
    if not subscriptions:
        print(f"[push] No active subscriptions for user {user_hash}")
        return {
            "success": True,
            "sent": 0,
            "failed": 0,
            "message": "No active subscriptions",
        }
    
    # Build notification payload
    notification_payload = {
        "title": title,
        "body": body,
        "icon": icon or "/icons/icon-192x192.png",
        "badge": badge or "/icons/badge-72x72.png",
        "tag": tag,
        "data": {
            "url": url or "/",
            **(data or {}),
        },
    }
    
    payload_json = json.dumps(notification_payload)
    
    sent_count = 0
    failed_count = 0
    results = []
    
    for sub in subscriptions:
        try:
            # Build subscription info for pywebpush
            subscription_info = {
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh_key,
                    "auth": sub.auth_key,
                },
            }
            
            # Send the push notification
            webpush(
                subscription_info=subscription_info,
                data=payload_json,
                vapid_private_key=cfg.VAPID_PRIVATE_KEY,
                vapid_claims=_get_vapid_claims(),
            )
            
            # Update subscription success status
            sub.last_push_at = datetime.utcnow()
            sub.last_push_status = "success"
            sub.consecutive_failures = 0
            
            sent_count += 1
            results.append({
                "subscription_id": sub.id,
                "status": "sent",
            })
            
            print(f"[push] Sent notification to subscription {sub.id} for user {user_hash}")
            
        except WebPushException as e:
            failed_count += 1
            error_msg = str(e)
            
            # Update subscription failure status
            sub.last_push_at = datetime.utcnow()
            sub.last_push_status = "failed"
            sub.consecutive_failures += 1
            
            # Check if subscription is expired/invalid (410 Gone or 404 Not Found)
            if e.response is not None and e.response.status_code in (404, 410):
                sub.is_active = False
                print(f"[push] Subscription {sub.id} expired, marking inactive")
            
            # Deactivate after too many consecutive failures
            if sub.consecutive_failures >= 5:
                sub.is_active = False
                print(f"[push] Subscription {sub.id} has {sub.consecutive_failures} failures, marking inactive")
            
            results.append({
                "subscription_id": sub.id,
                "status": "failed",
                "error": error_msg[:200],
            })
            
            print(f"[push] Failed to send to subscription {sub.id}: {error_msg[:100]}")
            
        except Exception as e:
            failed_count += 1
            results.append({
                "subscription_id": sub.id,
                "status": "error",
                "error": str(e)[:200],
            })
            print(f"[push] Unexpected error sending to subscription {sub.id}: {e}")
    
    # Commit subscription status updates
    try:
        db.commit()
    except Exception as e:
        print(f"[push] Error committing subscription updates: {e}")
    
    return {
        "success": sent_count > 0,
        "sent": sent_count,
        "failed": failed_count,
        "total_subscriptions": len(subscriptions),
        "results": results,
    }


def send_audio_ready_notification(
    db: Session,
    user_hash: str,
    journey_day: int,
) -> Dict[str, Any]:
    """
    Send notification that pre-generated audio is ready.
    
    Called after feedback.py successfully generates audio for next session.
    """
    return send_push_to_user(
        db=db,
        user_hash=user_hash,
        title="Your journey awaits ✨",
        body=f"Day {journey_day} is ready. Tap to begin when you're ready.",
        tag="audio-ready",
        url="/",
        data={
            "type": "audio_ready",
            "journey_day": journey_day,
        },
    )


def send_journey_reminder(
    db: Session,
    user_hash: str,
    journey_day: int,
) -> Dict[str, Any]:
    """
    Send a reminder to continue the journey.
    
    Can be triggered by a scheduled task or activity completion.
    """
    return send_push_to_user(
        db=db,
        user_hash=user_hash,
        title="Continue your journey 🌱",
        body="Take a moment for yourself today. Your next session is waiting.",
        tag="journey-reminder",
        url="/",
        data={
            "type": "journey_reminder",
            "journey_day": journey_day,
        },
    )


def send_activity_reminder(
    db: Session,
    user_hash: str,
    activity_title: str,
    activity_id: int,
) -> Dict[str, Any]:
    """
    Send a reminder about a planned activity.
    """
    return send_push_to_user(
        db=db,
        user_hash=user_hash,
        title="Activity reminder 🎯",
        body=f"Ready for: {activity_title}?",
        tag=f"activity-{activity_id}",
        url="/",
        data={
            "type": "activity_reminder",
            "activity_id": activity_id,
            "activity_title": activity_title,
        },
    )


def send_streak_notification(
    db: Session,
    user_hash: str,
    streak_days: int,
) -> Dict[str, Any]:
    """
    Celebrate a streak milestone.
    """
    messages = {
        3: "3 days in a row! You're building momentum 🔥",
        7: "One week strong! Your consistency is inspiring ⭐",
        14: "Two weeks! You're rewiring your patterns 🧠",
        30: "One month! This is real change happening 🎉",
    }
    
    body = messages.get(streak_days, f"{streak_days} days! Keep going 💪")
    
    return send_push_to_user(
        db=db,
        user_hash=user_hash,
        title="Streak milestone!",
        body=body,
        tag="streak",
        url="/",
        data={
            "type": "streak",
            "streak_days": streak_days,
        },
    )


def register_subscription(
    db: Session,
    user_hash: str,
    endpoint: str,
    p256dh_key: str,
    auth_key: str,
    user_agent: Optional[str] = None,
) -> PushSubscription:
    """
    Register or update a push subscription for a user.
    
    If a subscription with the same endpoint exists, update it.
    Otherwise, create a new one.
    """
    # Check for existing subscription with same endpoint
    existing = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == endpoint)
        .first()
    )
    
    # Detect device type from user agent
    device_type = "desktop"
    if user_agent:
        ua_lower = user_agent.lower()
        if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
            device_type = "mobile"
        elif "tablet" in ua_lower or "ipad" in ua_lower:
            device_type = "tablet"
    
    if existing:
        # Update existing subscription
        existing.user_hash = user_hash
        existing.p256dh_key = p256dh_key
        existing.auth_key = auth_key
        existing.user_agent = user_agent
        existing.device_type = device_type
        existing.is_active = True
        existing.consecutive_failures = 0
        existing.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(existing)
        
        print(f"[push] Updated subscription {existing.id} for user {user_hash}")
        return existing
    
    # Create new subscription
    new_sub = PushSubscription(
        user_hash=user_hash,
        endpoint=endpoint,
        p256dh_key=p256dh_key,
        auth_key=auth_key,
        user_agent=user_agent,
        device_type=device_type,
        is_active=True,
        consecutive_failures=0,
    )
    
    db.add(new_sub)
    db.commit()
    db.refresh(new_sub)
    
    print(f"[push] Created subscription {new_sub.id} for user {user_hash}")
    return new_sub


def unregister_subscription(
    db: Session,
    endpoint: str,
) -> bool:
    """
    Unregister a push subscription by endpoint.
    
    Returns True if subscription was found and deactivated.
    """
    sub = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == endpoint)
        .first()
    )
    
    if sub:
        sub.is_active = False
        sub.updated_at = datetime.utcnow()
        db.commit()
        print(f"[push] Deactivated subscription {sub.id}")
        return True
    
    return False


def get_user_subscriptions(
    db: Session,
    user_hash: str,
    active_only: bool = True,
) -> List[PushSubscription]:
    """
    Get all push subscriptions for a user.
    """
    query = db.query(PushSubscription).filter(PushSubscription.user_hash == user_hash)
    
    if active_only:
        query = query.filter(PushSubscription.is_active == True)
    
    return query.all()


def cleanup_stale_subscriptions(
    db: Session,
    max_failures: int = 5,
) -> int:
    """
    Deactivate subscriptions that have too many consecutive failures.
    
    Returns count of deactivated subscriptions.
    """
    stale = (
        db.query(PushSubscription)
        .filter(
            PushSubscription.is_active == True,
            PushSubscription.consecutive_failures >= max_failures,
        )
        .all()
    )
    
    count = 0
    for sub in stale:
        sub.is_active = False
        count += 1
    
    if count > 0:
        db.commit()
        print(f"[push] Deactivated {count} stale subscriptions")
    
    return count
