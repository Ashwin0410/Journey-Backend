# app/routes/chills.py
"""
Chills Tracking Routes for ReWire

This module handles all API endpoints related to tracking chills (frisson)
during the immersive video experience:

1. Chills Timestamps - When user presses "I feel chills!" button
2. Body Map - Where user felt the chills on their body
3. Post-Video Responses - Insights, values, and action intentions

These endpoints support the new video-based therapeutic experience
that replaces the audio generation system.

FIX Issue #2: Added VideoSession auto-creation to fix foreign key constraint
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from ..db import SessionLocal
from ..models import (
    Sessions,
    Users,
    ChillsTimestamp,
    BodyMapSpot,
    PostVideoResponse,
    VideoSession,
    VideoStimulus,
)

# ============================================================================
# ROUTER SETUP
# ============================================================================

r = APIRouter()


def db():
    """Database session dependency."""
    q = SessionLocal()
    try:
        yield q
    finally:
        q.close()


# ============================================================================
# PYDANTIC SCHEMAS (Request/Response Models)
# ============================================================================

class ChillsTimestampIn(BaseModel):
    """Request model for recording a chills timestamp."""
    session_id: str
    video_time_seconds: float = Field(
        ge=0,
        description="Video playback time in seconds when chills were felt"
    )
    # Video name for tracking which video was being watched
    video_name: Optional[str] = Field(
        None,
        max_length=500,
        description="Name/title of the video being watched"
    )
    # FIX Issue #2: Add user_hash for VideoSession creation
    user_hash: Optional[str] = Field(
        None,
        description="User hash for linking chills to user"
    )


class ChillsTimestampOut(BaseModel):
    """Response model for chills timestamp."""
    id: int
    session_id: str
    video_time_seconds: float
    video_name: Optional[str] = None
    created_at: datetime


class BodyMapSpotIn(BaseModel):
    """Request model for recording a body map spot."""
    session_id: str
    x_percent: float = Field(
        ge=0,
        le=100,
        description="X coordinate as percentage (0-100) of body figure width"
    )
    y_percent: float = Field(
        ge=0,
        le=100,
        description="Y coordinate as percentage (0-100) of body figure height"
    )
    # FIX Issue #2: Add user_hash for consistency
    user_hash: Optional[str] = Field(
        None,
        description="User hash for linking to user"
    )


class BodyMapSpotOut(BaseModel):
    """Response model for body map spot."""
    id: int
    session_id: str
    x_percent: float
    y_percent: float
    created_at: datetime


class BodyMapBatchIn(BaseModel):
    """Request model for recording multiple body map spots at once."""
    session_id: str
    spots: List[dict] = Field(
        description="List of spots, each with x_percent and y_percent"
    )
    # FIX Issue #2: Add user_hash for consistency
    user_hash: Optional[str] = Field(
        None,
        description="User hash for linking to user"
    )


class PostVideoResponseIn(BaseModel):
    """Request model for post-video response."""
    session_id: str
    insights_text: Optional[str] = Field(
        None,
        max_length=2000,
        description="What came up for the user during the video"
    )
    value_selected: Optional[str] = Field(
        None,
        max_length=100,
        description="Selected value chip: Connection, Gratitude, Creativity, Peace, Other"
    )
    value_custom: Optional[str] = Field(
        None,
        max_length=200,
        description="Custom value text if 'Other' was selected"
    )
    action_selected: Optional[str] = Field(
        None,
        max_length=100,
        description="Selected action chip: Call someone, Go outside, Write, Create, Other"
    )
    action_custom: Optional[str] = Field(
        None,
        max_length=500,
        description="Custom action text - THIS IS USED FOR ACTIVITY GENERATION"
    )
    # FIX Issue #2: Add user_hash for consistency
    user_hash: Optional[str] = Field(
        None,
        description="User hash for linking to user"
    )


class PostVideoResponseOut(BaseModel):
    """Response model for post-video response."""
    id: int
    session_id: str
    insights_text: Optional[str]
    value_selected: Optional[str]
    value_custom: Optional[str]
    action_selected: Optional[str]
    action_custom: Optional[str]
    created_at: datetime


class SessionChillsSummary(BaseModel):
    """Summary of all chills data for a session."""
    session_id: str
    chills_count: int
    chills_timestamps: List[float]
    body_map_spots: List[dict]
    post_video_response: Optional[dict]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _ensure_video_session(
    db_session: Session,
    session_id: str,
    user_hash: Optional[str] = None,
    video_name: Optional[str] = None,
) -> bool:
    """
    FIX Issue #2: Ensure a VideoSession exists for the given session_id.
    
    Creates one if it doesn't exist. This is needed because ChillsTimestamp
    has a foreign key to video_sessions.session_id.
    
    Args:
        db_session: Database session
        session_id: Client-generated session ID
        user_hash: User hash (optional but recommended)
        video_name: Video name to look up video_id
    
    Returns:
        True if VideoSession exists or was created, False if creation failed
    """
    # Check if VideoSession already exists
    existing = (
        db_session.query(VideoSession)
        .filter(VideoSession.session_id == session_id)
        .first()
    )
    
    if existing:
        print(f"[chills] VideoSession already exists for {session_id}")
        return True
    
    # Try to find video_id by matching video_name to stimulus_name
    video_id = None
    if video_name:
        video = (
            db_session.query(VideoStimulus)
            .filter(VideoStimulus.stimulus_name == video_name)
            .first()
        )
        if video:
            video_id = video.id
            print(f"[chills] Found video_id={video_id} for '{video_name}'")
        else:
            # Try partial match
            video = (
                db_session.query(VideoStimulus)
                .filter(VideoStimulus.stimulus_name.ilike(f"%{video_name}%"))
                .first()
            )
            if video:
                video_id = video.id
                print(f"[chills] Found video_id={video_id} via partial match for '{video_name}'")
    
    # If no video_id found, try to get any video as fallback
    if video_id is None:
        fallback_video = db_session.query(VideoStimulus).first()
        if fallback_video:
            video_id = fallback_video.id
            print(f"[chills] Using fallback video_id={video_id}")
    
    # If still no video_id, we can't create VideoSession (FK constraint)
    if video_id is None:
        print(f"[chills] No video found, cannot create VideoSession for {session_id}")
        return False
    
    # Create VideoSession
    try:
        new_session = VideoSession(
            session_id=session_id,
            user_hash=user_hash or "unknown",
            video_id=video_id,
            started_at=datetime.utcnow(),
            completed=False,
        )
        db_session.add(new_session)
        db_session.commit()
        print(f"[chills] Created VideoSession for {session_id}, video_id={video_id}")
        return True
    except Exception as e:
        print(f"[chills] Failed to create VideoSession: {e}")
        db_session.rollback()
        return False


def _validate_session_optional(db_session: Session, session_id: str) -> Optional[Sessions]:
    """
    Optionally validate that a session exists in the old Sessions table.
    
    IMPORTANT: The frontend generates client-side UUIDs for video sessions,
    which don't exist in the old Sessions table. This function now returns
    None instead of raising 404 to support client-generated session IDs.
    
    Args:
        db_session: Database session
        session_id: Session ID to validate
    
    Returns:
        Sessions object if found, None otherwise (no longer raises 404)
    """
    session = db_session.query(Sessions).filter(Sessions.id == session_id).first()
    if not session:
        # Log but don't fail - session_id is likely a client-generated UUID
        print(f"[chills] Session not in Sessions table (client-generated UUID): {session_id}")
    return session


def _validate_session(db_session: Session, session_id: str) -> Sessions:
    """
    Validate that a session exists.
    
    NOTE: This now uses soft validation for chills-related operations.
    For strict validation, use in post-video response only.
    
    Args:
        db_session: Database session
        session_id: Session ID to validate
    
    Returns:
        Sessions object if found
    
    Raises:
        HTTPException: If session not found (only for strict endpoints)
    """
    session = db_session.query(Sessions).filter(Sessions.id == session_id).first()
    if not session:
        # For backward compatibility, still raise for strict endpoints
        # But log the session_id for debugging
        print(f"[chills] Session validation failed for: {session_id}")
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session


def _get_user_hash_from_session(db_session: Session, session_id: str) -> Optional[str]:
    """
    Get user_hash from a session ID.
    
    Args:
        db_session: Database session
        session_id: Session ID
    
    Returns:
        user_hash if found, None otherwise
    """
    session = db_session.query(Sessions).filter(Sessions.id == session_id).first()
    if session:
        return session.user_hash
    return None


def _get_action_for_activity_generation(response: PostVideoResponse) -> Optional[str]:
    """
    Extract the action text that should be used for activity generation.
    
    Priority:
    1. action_custom (if provided)
    2. action_selected (if not "Other")
    
    Args:
        response: PostVideoResponse object
    
    Returns:
        Action text to use for activity generation, or None
    """
    if response.action_custom:
        return response.action_custom.strip()
    
    if response.action_selected and response.action_selected.lower() != "other":
        return response.action_selected.strip()
    
    return None


# ============================================================================
# CHILLS TIMESTAMP ENDPOINTS
# ============================================================================

@r.post("/api/chills/timestamp", response_model=ChillsTimestampOut)
def record_chills_timestamp(x: ChillsTimestampIn, q: Session = Depends(db)):
    """
    Record a chills timestamp during video playback.
    
    Called each time user presses the "I feel chills!" button.
    Multiple timestamps can be recorded per session.
    
    FIX Issue #2: Now auto-creates VideoSession if it doesn't exist.
    
    Args:
        x: ChillsTimestampIn with session_id, video_time_seconds, video_name, user_hash
        q: Database session
    
    Returns:
        Created ChillsTimestamp record
    """
    print(f"[chills] Recording timestamp: session={x.session_id}, time={x.video_time_seconds}, video={x.video_name}, user={x.user_hash}")
    
    # FIX Issue #2: Ensure VideoSession exists before inserting ChillsTimestamp
    # This fixes the foreign key constraint error
    session_created = _ensure_video_session(
        q,
        session_id=x.session_id,
        user_hash=x.user_hash,
        video_name=x.video_name,
    )
    
    if not session_created:
        print(f"[chills] Warning: Could not ensure VideoSession exists, attempting insert anyway")
    
    # Create timestamp record
    try:
        timestamp = ChillsTimestamp(
            session_id=x.session_id,
            video_time_seconds=x.video_time_seconds,
            video_name=x.video_name,
            user_hash=x.user_hash,  # FIX: Also store user_hash on the timestamp
            created_at=datetime.utcnow(),
        )
        q.add(timestamp)
        q.commit()
        q.refresh(timestamp)
        
        print(f"[chills] Recorded timestamp id={timestamp.id} for session {x.session_id} at {x.video_time_seconds}s")
        
        return ChillsTimestampOut(
            id=timestamp.id,
            session_id=timestamp.session_id,
            video_time_seconds=timestamp.video_time_seconds,
            video_name=getattr(timestamp, 'video_name', None),
            created_at=timestamp.created_at,
        )
    except Exception as e:
        print(f"[chills] ERROR recording timestamp: {e}")
        q.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record chills timestamp: {str(e)}")


@r.get("/api/chills/timestamps/{session_id}", response_model=List[ChillsTimestampOut])
def get_chills_timestamps(session_id: str, q: Session = Depends(db)):
    """
    Get all chills timestamps for a session.
    
    Args:
        session_id: Session ID
        q: Database session
    
    Returns:
        List of ChillsTimestamp records
    """
    timestamps = (
        q.query(ChillsTimestamp)
        .filter(ChillsTimestamp.session_id == session_id)
        .order_by(ChillsTimestamp.video_time_seconds.asc())
        .all()
    )
    
    return [
        ChillsTimestampOut(
            id=t.id,
            session_id=t.session_id,
            video_time_seconds=t.video_time_seconds,
            video_name=getattr(t, 'video_name', None),
            created_at=t.created_at,
        )
        for t in timestamps
    ]


# ============================================================================
# BODY MAP ENDPOINTS
# ============================================================================

@r.post("/api/chills/bodymap", response_model=BodyMapSpotOut)
def record_body_map_spot(x: BodyMapSpotIn, q: Session = Depends(db)):
    """
    Record a single body map spot.
    
    Called when user taps on the body figure to indicate
    where they felt the chills physically.
    
    Args:
        x: BodyMapSpotIn with session_id, x_percent, y_percent
        q: Database session
    
    Returns:
        Created BodyMapSpot record
    """
    # FIX Issue #2: Ensure VideoSession exists
    _ensure_video_session(q, x.session_id, x.user_hash)
    
    # Create body map spot
    try:
        spot = BodyMapSpot(
            session_id=x.session_id,
            x_percent=x.x_percent,
            y_percent=x.y_percent,
            created_at=datetime.utcnow(),
        )
        q.add(spot)
        q.commit()
        q.refresh(spot)
        
        print(f"[chills] Recorded body map spot for session {x.session_id} at ({x.x_percent}, {x.y_percent})")
        
        return BodyMapSpotOut(
            id=spot.id,
            session_id=spot.session_id,
            x_percent=spot.x_percent,
            y_percent=spot.y_percent,
            created_at=spot.created_at,
        )
    except Exception as e:
        print(f"[chills] ERROR recording body map spot: {e}")
        q.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record body map spot: {str(e)}")


@r.post("/api/chills/bodymap/batch")
def record_body_map_spots_batch(x: BodyMapBatchIn, q: Session = Depends(db)):
    """
    Record multiple body map spots at once.
    
    More efficient than calling /bodymap multiple times.
    Used when user has tapped multiple locations.
    
    Args:
        x: BodyMapBatchIn with session_id and list of spots
        q: Database session
    
    Returns:
        Count of created spots
    """
    # FIX Issue #2: Ensure VideoSession exists
    _ensure_video_session(q, x.session_id, x.user_hash)
    
    # Create all spots
    try:
        created_spots = []
        for spot_data in x.spots:
            spot = BodyMapSpot(
                session_id=x.session_id,
                x_percent=spot_data.get("x_percent", 0),
                y_percent=spot_data.get("y_percent", 0),
                created_at=datetime.utcnow(),
            )
            q.add(spot)
            created_spots.append(spot)
        
        q.commit()
        
        print(f"[chills] Recorded {len(created_spots)} body map spots for session {x.session_id}")
        
        return {
            "ok": True,
            "count": len(created_spots),
            "session_id": x.session_id,
        }
    except Exception as e:
        print(f"[chills] ERROR recording body map spots batch: {e}")
        q.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to record body map spots: {str(e)}")


@r.get("/api/chills/bodymap/{session_id}", response_model=List[BodyMapSpotOut])
def get_body_map_spots(session_id: str, q: Session = Depends(db)):
    """
    Get all body map spots for a session.
    
    Args:
        session_id: Session ID
        q: Database session
    
    Returns:
        List of BodyMapSpot records
    """
    spots = (
        q.query(BodyMapSpot)
        .filter(BodyMapSpot.session_id == session_id)
        .all()
    )
    
    return [
        BodyMapSpotOut(
            id=s.id,
            session_id=s.session_id,
            x_percent=s.x_percent,
            y_percent=s.y_percent,
            created_at=s.created_at,
        )
        for s in spots
    ]


@r.delete("/api/chills/bodymap/{session_id}")
def clear_body_map_spots(session_id: str, q: Session = Depends(db)):
    """
    Clear all body map spots for a session.
    
    Useful if user wants to redo their body map selection.
    
    Args:
        session_id: Session ID
        q: Database session
    
    Returns:
        Count of deleted spots
    """
    deleted = (
        q.query(BodyMapSpot)
        .filter(BodyMapSpot.session_id == session_id)
        .delete()
    )
    q.commit()
    
    print(f"[chills] Cleared {deleted} body map spots for session {session_id}")
    
    return {
        "ok": True,
        "deleted": deleted,
        "session_id": session_id,
    }


# ============================================================================
# POST-VIDEO RESPONSE ENDPOINTS
# ============================================================================

@r.post("/api/chills/response", response_model=PostVideoResponseOut)
def record_post_video_response(x: PostVideoResponseIn, q: Session = Depends(db)):
    """
    Record post-video response (insights, values, action).
    
    This is the CRITICAL endpoint for the new flow:
    - action_custom or action_selected feeds into activity generation
    - value_selected helps personalize future recommendations
    - insights_text is stored for journaling/reflection
    
    Args:
        x: PostVideoResponseIn with all response fields
        q: Database session
    
    Returns:
        Created PostVideoResponse record
    """
    # Get user_hash from request or try to find from old Sessions table
    user_hash = x.user_hash
    if not user_hash:
        session = _validate_session_optional(q, x.session_id)
        if session:
            user_hash = session.user_hash
    
    # Check if response already exists (update instead of create)
    existing = (
        q.query(PostVideoResponse)
        .filter(PostVideoResponse.session_id == x.session_id)
        .first()
    )
    
    if existing:
        # Update existing response
        existing.insights_text = x.insights_text
        existing.value_selected = x.value_selected
        existing.value_custom = x.value_custom
        existing.action_selected = x.action_selected
        existing.action_custom = x.action_custom
        if user_hash:
            existing.user_hash = user_hash
        q.commit()
        q.refresh(existing)
        
        print(f"[chills] Updated post-video response for session {x.session_id}")
        
        response = existing
    else:
        # Create new response
        response = PostVideoResponse(
            session_id=x.session_id,
            user_hash=user_hash,
            insights_text=x.insights_text,
            value_selected=x.value_selected,
            value_custom=x.value_custom,
            action_selected=x.action_selected,
            action_custom=x.action_custom,
            created_at=datetime.utcnow(),
        )
        q.add(response)
        q.commit()
        q.refresh(response)
        
        print(f"[chills] Created post-video response for session {x.session_id}")
    
    # Log the action for activity generation
    action_for_activities = _get_action_for_activity_generation(response)
    if action_for_activities:
        print(f"[chills] Action for activity generation: '{action_for_activities}'")
    
    return PostVideoResponseOut(
        id=response.id,
        session_id=response.session_id,
        insights_text=response.insights_text,
        value_selected=response.value_selected,
        value_custom=response.value_custom,
        action_selected=response.action_selected,
        action_custom=response.action_custom,
        created_at=response.created_at,
    )


@r.get("/api/chills/response/{session_id}", response_model=Optional[PostVideoResponseOut])
def get_post_video_response(session_id: str, q: Session = Depends(db)):
    """
    Get post-video response for a session.
    
    Args:
        session_id: Session ID
        q: Database session
    
    Returns:
        PostVideoResponse record or None
    """
    response = (
        q.query(PostVideoResponse)
        .filter(PostVideoResponse.session_id == session_id)
        .first()
    )
    
    if not response:
        return None
    
    return PostVideoResponseOut(
        id=response.id,
        session_id=response.session_id,
        insights_text=response.insights_text,
        value_selected=response.value_selected,
        value_custom=response.value_custom,
        action_selected=response.action_selected,
        action_custom=response.action_custom,
        created_at=response.created_at,
    )


# ============================================================================
# SESSION SUMMARY ENDPOINT
# ============================================================================

@r.get("/api/chills/summary/{session_id}", response_model=SessionChillsSummary)
def get_session_chills_summary(session_id: str, q: Session = Depends(db)):
    """
    Get complete chills summary for a session.
    
    Combines all chills data:
    - Number of times chills were felt
    - All timestamp points
    - Body map coordinates
    - Post-video response
    
    Useful for therapist dashboard and analytics.
    
    Args:
        session_id: Session ID
        q: Database session
    
    Returns:
        Complete SessionChillsSummary
    """
    # Get timestamps
    timestamps = (
        q.query(ChillsTimestamp)
        .filter(ChillsTimestamp.session_id == session_id)
        .order_by(ChillsTimestamp.video_time_seconds.asc())
        .all()
    )
    
    # Get body map spots
    spots = (
        q.query(BodyMapSpot)
        .filter(BodyMapSpot.session_id == session_id)
        .all()
    )
    
    # Get post-video response
    response = (
        q.query(PostVideoResponse)
        .filter(PostVideoResponse.session_id == session_id)
        .first()
    )
    
    return SessionChillsSummary(
        session_id=session_id,
        chills_count=len(timestamps),
        chills_timestamps=[t.video_time_seconds for t in timestamps],
        body_map_spots=[
            {"x_percent": s.x_percent, "y_percent": s.y_percent}
            for s in spots
        ],
        post_video_response={
            "insights_text": response.insights_text,
            "value_selected": response.value_selected,
            "value_custom": response.value_custom,
            "action_selected": response.action_selected,
            "action_custom": response.action_custom,
        } if response else None,
    )


# ============================================================================
# ACTION EXTRACTION ENDPOINT (for activity generation)
# ============================================================================

@r.get("/api/chills/action/{session_id}")
def get_action_for_activities(session_id: str, q: Session = Depends(db)):
    """
    Get the action text to use for activity generation.
    
    This endpoint is called by the activity generation service
    to get the user's stated intention from the post-video response.
    
    Args:
        session_id: Session ID
        q: Database session
    
    Returns:
        Action text and source
    """
    response = (
        q.query(PostVideoResponse)
        .filter(PostVideoResponse.session_id == session_id)
        .first()
    )
    
    if not response:
        return {
            "ok": False,
            "action": None,
            "source": None,
            "message": "No post-video response found for this session",
        }
    
    action = _get_action_for_activity_generation(response)
    
    if action:
        source = "custom" if response.action_custom else "selected"
        return {
            "ok": True,
            "action": action,
            "source": source,
            "session_id": session_id,
        }
    else:
        return {
            "ok": False,
            "action": None,
            "source": None,
            "message": "No action specified in post-video response",
        }


# ============================================================================
# CHILLS COUNT ENDPOINT (quick stat)
# ============================================================================

@r.get("/api/chills/count/{session_id}")
def get_chills_count(session_id: str, q: Session = Depends(db)):
    """
    Get quick count of chills timestamps for a session.
    
    Lightweight endpoint for displaying chills count in UI.
    
    Args:
        session_id: Session ID
        q: Database session
    
    Returns:
        Chills count
    """
    count = (
        q.query(ChillsTimestamp)
        .filter(ChillsTimestamp.session_id == session_id)
        .count()
    )
    
    return {
        "session_id": session_id,
        "chills_count": count,
    }
