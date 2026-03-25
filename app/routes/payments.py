"""
Stripe Payment / Subscription routes for ReWire (Issue #2 - Paywall)

Flow:
1. User completes onboarding (ML questionnaire)
2. Frontend checks subscription status before showing first video
3. If no active subscription -> show paywall screen
4. User clicks "Subscribe" -> frontend calls POST /api/payments/create-checkout
5. Backend creates Stripe Checkout Session -> returns URL
6. User redirected to Stripe-hosted checkout page
7. On success, Stripe redirects back to app + sends webhook
8. Webhook updates user's subscription_status to "active"
9. Frontend polls GET /api/payments/status until active
10. Video experience unlocked

Endpoints:
- POST /api/payments/create-checkout  - Create Stripe Checkout Session
- GET  /api/payments/status           - Check subscription status
- POST /api/payments/webhook          - Stripe webhook handler
- POST /api/payments/portal           - Customer portal for managing subscription
- GET  /api/payments/config           - Get publishable key for frontend
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import cfg as c
from app.db import SessionLocal
from app import models
from app.auth_utils import get_current_user

logger = logging.getLogger(__name__)

r = APIRouter(prefix="/api/payments", tags=["payments"])


# ============================================================================
# Stripe SDK initialization
# ============================================================================

stripe = None

def _get_stripe():
    """Lazy-load stripe module to avoid crash if not installed."""
    global stripe
    if stripe is None:
        try:
            import stripe as _stripe
            _stripe.api_key = c.STRIPE_SECRET_KEY
            stripe = _stripe
        except ImportError:
            raise HTTPException(
                status_code=500,
                detail="Stripe SDK not installed. Run: pip install stripe",
            )
    return stripe


# ============================================================================
# Database dependency
# ============================================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# GET /api/payments/config - Frontend needs publishable key
# ============================================================================

@r.get("/config")
def get_payments_config():
    """Return Stripe publishable key and price for frontend."""
    if not c.STRIPE_PUBLISHABLE_KEY:
        raise HTTPException(status_code=500, detail="Stripe not configured")
    
    return {
        "publishable_key": c.STRIPE_PUBLISHABLE_KEY,
        "price_id": c.STRIPE_PRICE_ID,
        "amount": "4.90",
        "currency": "usd",
        "interval": "week",
    }


# ============================================================================
# GET /api/payments/status - Check user's subscription status
# ============================================================================

@r.get("/status")
def get_subscription_status(
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Check if user has an active subscription.
    Frontend polls this after Stripe checkout to know when to unlock video.
    """
    user = current_user
    
    if user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Account not found.")
    
    is_active = user.subscription_status in ("active", "trialing")
    
    return {
        "has_subscription": is_active,
        "subscription_status": user.subscription_status,
        "subscription_id": user.subscription_id,
        "stripe_customer_id": user.stripe_customer_id,
    }


# ============================================================================
# POST /api/payments/create-checkout - Create Stripe Checkout Session
# ============================================================================

@r.post("/create-checkout")
def create_checkout_session(
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Checkout Session for the $4.90/week subscription.
    
    Returns: { "checkout_url": "https://checkout.stripe.com/..." }
    Frontend redirects user to this URL.
    """
    s = _get_stripe()
    
    if not c.STRIPE_PRICE_ID:
        raise HTTPException(status_code=500, detail="Stripe price not configured")
    
    user = current_user
    
    if user.deleted_at is not None:
        raise HTTPException(status_code=401, detail="Account not found.")
    
    # If user already has active subscription, return early
    if user.subscription_status in ("active", "trialing"):
        return {
            "checkout_url": None,
            "message": "You already have an active subscription.",
            "already_active": True,
        }
    
    # Create or retrieve Stripe customer
    customer_id = user.stripe_customer_id
    
    if not customer_id:
        try:
            customer = s.Customer.create(
                email=user.email,
                name=user.name or "",
                metadata={
                    "user_hash": user.user_hash,
                    "rewire_user_id": str(user.id),
                },
            )
            customer_id = customer.id
            user.stripe_customer_id = customer_id
            db.commit()
            logger.info(f"[payments] Created Stripe customer {customer_id} for user {user.user_hash}")
        except Exception as e:
            logger.error(f"[payments] Failed to create Stripe customer: {e}")
            raise HTTPException(status_code=500, detail="Failed to create payment customer")
    
    # Build success/cancel URLs
    # After checkout, Stripe redirects here. Frontend detects and polls status.
    base_url = c.FRONTEND_BASE_URL.rstrip("/")
    success_url = f"{base_url}/?payment=success&session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/?payment=cancelled"
    
    try:
        checkout_session = s.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[
                {
                    "price": c.STRIPE_PRICE_ID,
                    "quantity": 1,
                },
            ],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "user_hash": user.user_hash,
                "rewire_user_id": str(user.id),
            },
        )
        
        logger.info(f"[payments] Created checkout session {checkout_session.id} for user {user.user_hash}")
        
        return {
            "checkout_url": checkout_session.url,
            "session_id": checkout_session.id,
            "already_active": False,
        }
        
    except Exception as e:
        logger.error(f"[payments] Failed to create checkout session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create checkout session")


# ============================================================================
# POST /api/payments/portal - Stripe Customer Portal (manage subscription)
# ============================================================================

@r.post("/portal")
def create_customer_portal(
    current_user: models.Users = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Customer Portal session so user can manage/cancel subscription.
    Returns: { "portal_url": "https://billing.stripe.com/..." }
    """
    s = _get_stripe()
    user = current_user
    
    if not user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No subscription found")
    
    base_url = c.FRONTEND_BASE_URL.rstrip("/")
    
    try:
        portal_session = s.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=base_url,
        )
        
        return {"portal_url": portal_session.url}
        
    except Exception as e:
        logger.error(f"[payments] Failed to create portal session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create billing portal")


# ============================================================================
# POST /api/payments/webhook - Stripe Webhook Handler
# ============================================================================

@r.post("/webhook")
async def stripe_webhook(request: Request):
    """
    Handle Stripe webhook events.
    
    Key events we handle:
    - checkout.session.completed: User completed checkout -> activate subscription
    - customer.subscription.updated: Subscription status changed
    - customer.subscription.deleted: Subscription cancelled/expired
    - invoice.payment_failed: Payment failed -> mark as past_due
    """
    s = _get_stripe()
    
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    # Verify webhook signature if secret is configured
    event = None
    if c.STRIPE_WEBHOOK_SECRET and c.STRIPE_WEBHOOK_SECRET != "placeholder_will_update_later":
        try:
            event = s.Webhook.construct_event(
                payload, sig_header, c.STRIPE_WEBHOOK_SECRET
            )
        except ValueError:
            logger.error("[payments] Webhook: Invalid payload")
            return JSONResponse(status_code=400, content={"error": "Invalid payload"})
        except s.error.SignatureVerificationError:
            logger.error("[payments] Webhook: Invalid signature")
            return JSONResponse(status_code=400, content={"error": "Invalid signature"})
    else:
        # No webhook secret configured — parse payload directly (dev/test mode)
        import json
        try:
            event = json.loads(payload)
        except Exception:
            return JSONResponse(status_code=400, content={"error": "Invalid JSON"})
    
    event_type = event.get("type") if isinstance(event, dict) else event.type
    event_data = event.get("data", {}).get("object", {}) if isinstance(event, dict) else event.data.object
    
    logger.info(f"[payments] Webhook received: {event_type}")
    
    db = SessionLocal()
    try:
        if event_type == "checkout.session.completed":
            _handle_checkout_completed(db, event_data)
        
        elif event_type == "customer.subscription.updated":
            _handle_subscription_updated(db, event_data)
        
        elif event_type == "customer.subscription.deleted":
            _handle_subscription_deleted(db, event_data)
        
        elif event_type == "invoice.payment_failed":
            _handle_payment_failed(db, event_data)
        
        else:
            logger.info(f"[payments] Unhandled webhook event: {event_type}")
        
    except Exception as e:
        logger.error(f"[payments] Webhook handler error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()
    
    return JSONResponse(status_code=200, content={"status": "ok"})


# ============================================================================
# Webhook event handlers
# ============================================================================

def _find_user_by_customer_id(db: Session, customer_id: str) -> Optional[models.Users]:
    """Find user by Stripe customer ID."""
    if not customer_id:
        return None
    return (
        db.query(models.Users)
        .filter(models.Users.stripe_customer_id == customer_id)
        .first()
    )


def _find_user_by_metadata(db: Session, metadata: dict) -> Optional[models.Users]:
    """Find user by metadata in Stripe event."""
    user_hash = metadata.get("user_hash") if metadata else None
    if user_hash:
        return (
            db.query(models.Users)
            .filter(models.Users.user_hash == user_hash)
            .first()
        )
    return None


def _handle_checkout_completed(db: Session, session_data):
    """Handle successful checkout — activate subscription."""
    customer_id = session_data.get("customer") if isinstance(session_data, dict) else getattr(session_data, "customer", None)
    subscription_id = session_data.get("subscription") if isinstance(session_data, dict) else getattr(session_data, "subscription", None)
    metadata = session_data.get("metadata", {}) if isinstance(session_data, dict) else getattr(session_data, "metadata", {})
    
    # Find user
    user = _find_user_by_customer_id(db, customer_id)
    if not user:
        user = _find_user_by_metadata(db, metadata)
    
    if not user:
        logger.error(f"[payments] checkout.session.completed: Could not find user for customer {customer_id}")
        return
    
    user.stripe_customer_id = customer_id
    user.subscription_id = subscription_id
    user.subscription_status = "active"
    db.commit()
    
    logger.info(f"[payments] Activated subscription for user {user.user_hash} (sub: {subscription_id})")


def _handle_subscription_updated(db: Session, sub_data):
    """Handle subscription status change."""
    customer_id = sub_data.get("customer") if isinstance(sub_data, dict) else getattr(sub_data, "customer", None)
    sub_id = sub_data.get("id") if isinstance(sub_data, dict) else getattr(sub_data, "id", None)
    status = sub_data.get("status") if isinstance(sub_data, dict) else getattr(sub_data, "status", None)
    
    user = _find_user_by_customer_id(db, customer_id)
    if not user:
        logger.error(f"[payments] subscription.updated: Could not find user for customer {customer_id}")
        return
    
    user.subscription_id = sub_id
    user.subscription_status = status
    db.commit()
    
    logger.info(f"[payments] Updated subscription for user {user.user_hash}: status={status}")


def _handle_subscription_deleted(db: Session, sub_data):
    """Handle subscription cancellation/expiration."""
    customer_id = sub_data.get("customer") if isinstance(sub_data, dict) else getattr(sub_data, "customer", None)
    
    user = _find_user_by_customer_id(db, customer_id)
    if not user:
        logger.error(f"[payments] subscription.deleted: Could not find user for customer {customer_id}")
        return
    
    user.subscription_status = "canceled"
    db.commit()
    
    logger.info(f"[payments] Subscription canceled for user {user.user_hash}")


def _handle_payment_failed(db: Session, invoice_data):
    """Handle failed payment — mark subscription as past_due."""
    customer_id = invoice_data.get("customer") if isinstance(invoice_data, dict) else getattr(invoice_data, "customer", None)
    
    user = _find_user_by_customer_id(db, customer_id)
    if not user:
        logger.error(f"[payments] invoice.payment_failed: Could not find user for customer {customer_id}")
        return
    
    # Only mark past_due if currently active (don't overwrite "canceled")
    if user.subscription_status == "active":
        user.subscription_status = "past_due"
        db.commit()
        logger.info(f"[payments] Payment failed for user {user.user_hash}, marked as past_due")
