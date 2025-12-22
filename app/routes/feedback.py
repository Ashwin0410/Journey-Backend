from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
import threading

from ..schemas import FeedbackIn
from ..db import SessionLocal
from ..models import Feedback, Sessions, Users, PreGeneratedAudio

r = APIRouter()


def db():
    q = SessionLocal()
    try:
        yield q
    finally:
        q.close()


# =============================================================================
# CHANGE #1: Pre-generate audio for Day 2+ users
# =============================================================================


def _get_user_journey_day(db_session: Session, user_hash: str) -> Optional[int]:
    """Get the user's current journey day."""
    if not user_hash:
        return None
    try:
        user = db_session.query(Users).filter(Users.user_hash == user_hash).first()
        if user:
            return user.journey_day
    except Exception as e:
        print(f"[feedback] Error getting journey day: {e}")
    return None


def _trigger_pre_generation(
    user_hash: str,
    current_journey_day: int,
    emotion_word: Optional[str],
    chills_detail: Optional[str],
    session_insight: Optional[str],
    session_id: str,
):
    """
    Trigger pre-generation of audio for the user's next session.
    
    This runs in a background thread to not block the feedback response.
    The actual audio generation happens asynchronously.
    """
    # Create a new database session for the background task
    db_session = SessionLocal()
    
    try:
        next_journey_day = current_journey_day + 1
        
        # Check if we already have pre-generated audio for this user's next day
        existing = (
            db_session.query(PreGeneratedAudio)
            .filter(
                PreGeneratedAudio.user_hash == user_hash,
                PreGeneratedAudio.for_journey_day == next_journey_day,
                PreGeneratedAudio.status.in_(["pending", "generating", "ready"]),
            )
            .first()
        )
        
        if existing:
            print(f"[feedback] Pre-generated audio already exists for user {user_hash} day {next_journey_day}, status: {existing.status}")
            return
        
        # Get the session to find track_id and voice_id preferences
        session = db_session.query(Sessions).filter(Sessions.id == session_id).first()
        track_id = session.track_id if session else None
        voice_id = session.voice_id if session else None
        mood = session.mood if session else None
        schema_hint = session.schema_hint if session else None
        
        # Create a pending pre-generation record
        pre_gen = PreGeneratedAudio(
            user_hash=user_hash,
            for_journey_day=next_journey_day,
            audio_path="",  # Will be filled when generation completes
            script_text=None,
            track_id=track_id,
            voice_id=voice_id,
            mood=mood,
            schema_hint=schema_hint,
            emotion_word=emotion_word,
            chills_detail=chills_detail,
            session_insight=session_insight,
            status="pending",
            created_at=datetime.utcnow(),
        )
        db_session.add(pre_gen)
        db_session.commit()
        db_session.refresh(pre_gen)
        
        print(f"[feedback] Created pre-generation record id={pre_gen.id} for user {user_hash} day {next_journey_day}")
        
        # Now trigger the actual generation
        _generate_audio_for_record(pre_gen.id)
        
    except Exception as e:
        print(f"[feedback] Error in pre-generation trigger: {e}")
    finally:
        db_session.close()


def _generate_audio_for_record(pre_gen_id: int):
    """
    Generate audio for a PreGeneratedAudio record.
    
    This imports the narrative service to do the actual generation,
    similar to how journey.py generates audio on-demand.
    """
    db_session = SessionLocal()
    
    try:
        # Get the pre-generation record
        pre_gen = db_session.query(PreGeneratedAudio).filter(PreGeneratedAudio.id == pre_gen_id).first()
        if not pre_gen:
            print(f"[feedback] Pre-gen record {pre_gen_id} not found")
            return
        
        if pre_gen.status != "pending":
            print(f"[feedback] Pre-gen record {pre_gen_id} is not pending (status: {pre_gen.status})")
            return
        
        # Mark as generating
        pre_gen.status = "generating"
        db_session.commit()
        
        print(f"[feedback] Starting audio generation for pre-gen id={pre_gen_id}, user={pre_gen.user_hash}, day={pre_gen.for_journey_day}")
        
        # Import narrative service for generation
        from ..services import narrative as narrative_service
        
        # Build context for generation using chills-based personalization
        context = {
            "user_hash": pre_gen.user_hash,
            "journey_day": pre_gen.for_journey_day,
            "mood": pre_gen.mood,
            "schema_hint": pre_gen.schema_hint,
            "emotion_word": pre_gen.emotion_word,
            "chills_detail": pre_gen.chills_detail,
            "session_insight": pre_gen.session_insight,
        }
        
        # Generate the script using chills-based context
        chills_context = {
            "emotion_word": pre_gen.emotion_word,
            "chills_detail": pre_gen.chills_detail,
            "last_insight": pre_gen.session_insight,
            "feeling": pre_gen.mood,
            "schema_choice": pre_gen.schema_hint,
        }
        
        # Generate narrative script
        script_text = narrative_service.generate_narrative_script(
            db=db_session,
            user_hash=pre_gen.user_hash,
            journey_day=pre_gen.for_journey_day,
            mood=pre_gen.mood,
            schema_hint=pre_gen.schema_hint,
            chills_context=chills_context,
        )
        
        if not script_text:
            pre_gen.status = "failed"
            pre_gen.error_message = "Failed to generate script"
            db_session.commit()
            print(f"[feedback] Failed to generate script for pre-gen id={pre_gen_id}")
            return
        
        pre_gen.script_text = script_text
        db_session.commit()
        
        # Generate audio from script
        voice_id = pre_gen.voice_id or "default"
        
        audio_result = narrative_service.generate_audio_from_script(
            script_text=script_text,
            voice_id=voice_id,
        )
        
        if not audio_result or not audio_result.get("audio_path"):
            pre_gen.status = "failed"
            pre_gen.error_message = "Failed to generate audio"
            db_session.commit()
            print(f"[feedback] Failed to generate audio for pre-gen id={pre_gen_id}")
            return
        
        # Success - update record
        pre_gen.audio_path = audio_result["audio_path"]
        pre_gen.status = "ready"
        pre_gen.updated_at = datetime.utcnow()
        db_session.commit()
        
        print(f"[feedback] Successfully pre-generated audio for user {pre_gen.user_hash} day {pre_gen.for_journey_day}, path: {pre_gen.audio_path}")
        
        # =================================================================
        # CHANGE #7: Send push notification that audio is ready
        # =================================================================
        try:
            from ..services import push as push_service
            
            push_result = push_service.send_audio_ready_notification(
                db=db_session,
                user_hash=pre_gen.user_hash,
                journey_day=pre_gen.for_journey_day,
            )
            
            if push_result.get("sent", 0) > 0:
                print(f"[feedback] Sent push notification to user {pre_gen.user_hash} for day {pre_gen.for_journey_day}")
            else:
                print(f"[feedback] No push subscriptions for user {pre_gen.user_hash}")
                
        except Exception as push_error:
            # Don't fail if push notification fails
            print(f"[feedback] Error sending push notification: {push_error}")
        
    except Exception as e:
        print(f"[feedback] Error generating audio for pre-gen id={pre_gen_id}: {e}")
        try:
            pre_gen = db_session.query(PreGeneratedAudio).filter(PreGeneratedAudio.id == pre_gen_id).first()
            if pre_gen:
                pre_gen.status = "failed"
                pre_gen.error_message = str(e)[:500]
                db_session.commit()
        except Exception as e2:
            print(f"[feedback] Error updating failed status: {e2}")
    finally:
        db_session.close()


def _run_pre_generation_in_background(
    user_hash: str,
    current_journey_day: int,
    emotion_word: Optional[str],
    chills_detail: Optional[str],
    session_insight: Optional[str],
    session_id: str,
):
    """Run pre-generation in a separate thread to not block the response."""
    thread = threading.Thread(
        target=_trigger_pre_generation,
        args=(user_hash, current_journey_day, emotion_word, chills_detail, session_insight, session_id),
        daemon=True,
    )
    thread.start()


# =============================================================================
# FEEDBACK ENDPOINT
# =============================================================================


@r.post("/api/journey/feedback")
def submit(x: FeedbackIn, q: Session = Depends(db)):
    # Save feedback (existing logic)
    z = Feedback(
        session_id=x.session_id,
        chills=x.chills,
        relevance=x.relevance,
        emotion_word=x.emotion_word,
        chills_option=x.chills_option,
        chills_detail=x.chills_detail,
        session_insight=x.session_insight,
    )
    q.add(z)
    q.commit()
    
    # CHANGE #1: Trigger pre-generation for Day 2+ users
    # Get user_hash from the session
    try:
        session = q.query(Sessions).filter(Sessions.id == x.session_id).first()
        if session and session.user_hash:
            user_hash = session.user_hash
            current_journey_day = _get_user_journey_day(q, user_hash)
            
            # Only pre-generate if user has completed at least day 1
            if current_journey_day and current_journey_day >= 1:
                print(f"[feedback] Triggering pre-generation for user {user_hash}, current day {current_journey_day}")
                
                # Run in background thread to not block response
                _run_pre_generation_in_background(
                    user_hash=user_hash,
                    current_journey_day=current_journey_day,
                    emotion_word=x.emotion_word,
                    chills_detail=x.chills_detail,
                    session_insight=x.session_insight,
                    session_id=x.session_id,
                )
    except Exception as e:
        # Don't fail the feedback submission if pre-generation fails
        print(f"[feedback] Error triggering pre-generation: {e}")
    
    return {"ok": True}
