from __future__ import annotations

import json
import math
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from .. import models, schemas


DEFAULT_JOURNEY_COOLDOWN_MINUTES = 45


def compute_journey_state(
    db: Session,
    user_hash: Optional[str],
    cooldown_minutes: int = DEFAULT_JOURNEY_COOLDOWN_MINUTES,
) -> Dict[str, Any]:

    if not user_hash:
        return {
            "status": "ready",
            "cooldown_minutes_remaining": 0,
            "last_session_at": None,
        }

    last = (
        db.query(models.Sessions)
        .filter(models.Sessions.user_hash == user_hash)
        .order_by(models.Sessions.created_at.desc())
        .first()
    )
    if not last or not last.created_at:
        return {
            "status": "ready",
            "cooldown_minutes_remaining": 0,
            "last_session_at": None,
        }

    
    now = datetime.utcnow()
    last_dt = last.created_at
    if getattr(last_dt, "tzinfo", None) is not None:
        last_dt = last_dt.replace(tzinfo=None)

    elapsed_min = (now - last_dt).total_seconds() / 60.0
    if elapsed_min >= cooldown_minutes:
        return {
            "status": "ready",
            "cooldown_minutes_remaining": 0,
            "last_session_at": last_dt.isoformat(),
        }

    remaining = max(0, math.ceil(cooldown_minutes - elapsed_min))
    return {
        "status": "cooldown",
        "cooldown_minutes_remaining": int(remaining),
        "last_session_at": last_dt.isoformat(),
    }


def _time_of_day_greeting(now: Optional[datetime] = None) -> str:
    now = now or datetime.utcnow()
    h = now.hour
    if 5 <= h < 12:
        return "Good morning"
    if 12 <= h < 18:
        return "Good afternoon"
    if 18 <= h < 23:
        return "Good evening"
    return "Hey"


def _first_name(full_name: Optional[str]) -> Optional[str]:
    if not full_name:
        return None
    parts = full_name.strip().split()
    return parts[0] if parts else None


def _pick_schema_label(db: Session, user_hash: str) -> Optional[str]:
    last_session = (
        db.query(models.Sessions)
        .filter(models.Sessions.user_hash == user_hash)
        .order_by(models.Sessions.created_at.desc())
        .first()
    )
    if last_session and last_session.schema_hint:
        return last_session.schema_hint

    
    item = (
        db.query(models.SchemaItemResponse)
        .filter(models.SchemaItemResponse.user_hash == user_hash)
        .order_by(
            models.SchemaItemResponse.score.desc(),
            models.SchemaItemResponse.id.asc(),
        )
        .first()
    )
    if item and item.schema_key:
        return item.schema_key
    return None


def _last_session_feedback(db: Session, user_hash: str) -> Dict[str, Any]:
    """
    Get the last session and its feedback for a user.
    Returns session info including mood, schema_hint, and full feedback data.
    """
    session = (
        db.query(models.Sessions)
        .filter(models.Sessions.user_hash == user_hash)
        .order_by(models.Sessions.created_at.desc())
        .first()
    )
    if not session:
        return {
            "has_session": False,
            "session_id": None,
            "track_id": None,
            "mood": None,
            "schema_hint": None,
            "feedback": None,
        }

    fb = (
        db.query(models.Feedback)
        .filter(models.Feedback.session_id == session.id)
        .order_by(models.Feedback.created_at.desc())
        .first()
    )

    feedback_obj = None
    if fb:
        feedback_obj = {
            "chills": fb.chills,
            "relevance": fb.relevance,
            "emotion_word": fb.emotion_word,
            "chills_option": fb.chills_option,
            "chills_detail": fb.chills_detail,
            "session_insight": fb.session_insight,
        }

    return {
        "has_session": True,
        "session_id": session.id,
        "track_id": session.track_id,
        "mood": session.mood,
        "schema_hint": session.schema_hint or None,
        "feedback": feedback_obj,
    }


def _extract_intake_weekly_plan(db: Session, user_hash: Optional[str]) -> Dict[str, Any]:
    """
    Extract weekly plan data from user's clinical intake.
    
    Returns:
        Dict with life_area, life_focus, and week_actions (list of strings)
    """
    out = {
        "life_area": None,
        "life_focus": None,
        "week_actions": [],
    }
    
    if not user_hash:
        return out
    
    if not hasattr(models, "ClinicalIntake"):
        return out
    
    try:
        intake = (
            db.query(models.ClinicalIntake)
            .filter(models.ClinicalIntake.user_hash == user_hash)
            .order_by(models.ClinicalIntake.created_at.desc())
            .first()
        )
        
        if not intake:
            return out
        
        # Get life_area and life_focus
        out["life_area"] = getattr(intake, "life_area", None)
        out["life_focus"] = getattr(intake, "life_focus", None)
        
        # Parse week_actions_json
        week_actions_json = getattr(intake, "week_actions_json", None)
        if week_actions_json:
            try:
                actions = json.loads(week_actions_json)
                if isinstance(actions, list):
                    out["week_actions"] = [str(a) for a in actions if a]
            except (json.JSONDecodeError, TypeError):
                pass
        
    except Exception as e:
        print(f"[narrative] Error extracting intake weekly plan: {e}")
    
    return out


def get_chills_context_for_generation(db: Session, user_hash: Optional[str]) -> Dict[str, Any]:
    """
    Get chills-based context from the last session's feedback for use in 
    journey generation and activity recommendations.
    
    This replaces the mini check-in data with insights from the user's
    last session feedback (chills, emotion_word, session_insight, etc.)
    
    Also fetches intake weekly plan data (life_area, life_focus, week_actions)
    for personalization.
    
    Returns a dict with:
        - feeling: derived from emotion_word or mood
        - schema_choice: from last session's schema_hint
        - goal_today: derived from session_insight (what user wants to focus on)
        - last_insight: the session_insight text for context
        - chills_level: none/low/medium/high based on chills_option
        - emotion_word: what emotion resonated
        - chills_detail: specific trigger for chills
        - had_chills: boolean
        - postal_code: from clinical intake
        - place: inferred from chills_detail or default
        - life_area: from clinical intake (e.g., "Relationships")
        - life_focus: from clinical intake (e.g., "Reconnecting with a friend")
        - week_actions: list of specific actions from clinical intake
    """
    out = {
        "feeling": None,
        "schema_choice": None,
        "goal_today": None,
        "last_insight": None,
        "chills_level": "none",
        "emotion_word": None,
        "chills_detail": None,
        "had_chills": False,
        "postal_code": None,
        "place": None,
        # NEW: Intake weekly plan fields
        "life_area": None,
        "life_focus": None,
        "week_actions": [],
    }
    
    if not user_hash:
        return out
    
    # NEW: Get intake weekly plan data
    intake_plan = _extract_intake_weekly_plan(db, user_hash)
    out["life_area"] = intake_plan.get("life_area")
    out["life_focus"] = intake_plan.get("life_focus")
    out["week_actions"] = intake_plan.get("week_actions", [])
    
    # Get last session feedback
    session_info = _last_session_feedback(db, user_hash)
    
    if not session_info.get("has_session"):
        # Even without session, we still have intake data
        out["postal_code"] = _extract_postal_code(db, user_hash)
        return out
    
    # Extract from session
    out["schema_choice"] = session_info.get("schema_hint")
    
    # Get feedback data
    feedback = session_info.get("feedback")
    if feedback:
        # Emotion word becomes the "feeling" for next session
        emotion_word = feedback.get("emotion_word")
        if emotion_word:
            out["emotion_word"] = emotion_word
            out["feeling"] = emotion_word  # Use emotion as feeling
        
        # Session insight becomes context for goal
        session_insight = feedback.get("session_insight")
        if session_insight:
            out["last_insight"] = session_insight
            # Use insight to inform goal (what the user reflected on)
            out["goal_today"] = session_insight[:200] if len(session_insight) > 200 else session_insight
        
        # Chills detail provides specific trigger info
        chills_detail = feedback.get("chills_detail")
        if chills_detail:
            out["chills_detail"] = chills_detail
        
        # Determine chills level from chills_option
        chills_option = feedback.get("chills_option")
        if chills_option:
            if chills_option in ("many", "yes", "several"):
                out["chills_level"] = "high"
                out["had_chills"] = True
            elif chills_option in ("one_or_two", "subtle"):
                out["chills_level"] = "medium"
                out["had_chills"] = True
            else:
                out["chills_level"] = "none"
                out["had_chills"] = False
        
        # Also check numeric chills value
        chills_numeric = feedback.get("chills")
        if chills_numeric and chills_numeric > 0:
            out["had_chills"] = True
            if chills_numeric >= 3:
                out["chills_level"] = "high"
            elif chills_numeric >= 1:
                out["chills_level"] = "medium"
    
    # If no emotion from feedback, fall back to session mood
    if not out["feeling"] and session_info.get("mood"):
        out["feeling"] = session_info.get("mood")
    
    # Get postal code from clinical intake
    out["postal_code"] = _extract_postal_code(db, user_hash)
    
    # Try to infer place preference from chills_detail
    # (e.g., if they mentioned "walking in the park", prefer outdoors)
    if out["chills_detail"]:
        detail_lower = out["chills_detail"].lower()
        if any(word in detail_lower for word in ["outside", "park", "walk", "nature", "garden", "fresh air"]):
            out["place"] = "outdoors"
        elif any(word in detail_lower for word in ["home", "couch", "bed", "room", "inside"]):
            out["place"] = "indoors"
    
    return out


def _build_hero_narrative(
    *,
    user_name: Optional[str],
    schema_label: Optional[str],
    mood: Optional[str],
    feedback: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    name_piece = _first_name(user_name) or "you"
    schema_phrase = schema_label or "an old story about yourself"
    mood_phrase = mood or "mixed"

    base = (
        f"You're quietly collecting evidence that you're more than {schema_phrase}. "
        f"Even on {mood_phrase} days, the fact that {name_piece} keeps showing up "
        "is proof of agency, not failure."
    )

    if feedback:
        emotion = feedback.get("emotion_word") or "something subtle"
        chills_opt = feedback.get("chills_option")
        if chills_opt == "yes":
            chills_line = (
                f" There was a real chills moment last time – that spark of {emotion} "
                "is part of your story now, not an accident."
            )
        elif chills_opt == "subtle":
            chills_line = (
                f" Last time the shift was quieter, more like a small wave of {emotion}; "
                "those small waves still count."
            )
        else:
            chills_line = (
                " Even if nothing dramatic happened in the last session, staying with the process "
                "is already changing the shape of your days."
            )
        text = base + chills_line
    else:
        text = (
            base
            + " You're building a track record of small, boring, solid evidence that you can move "
              "through this, one step at a time."
        )

    highlight_terms: List[str] = []
    if schema_label:
        highlight_terms.append(schema_label)
    highlight_terms.extend(["agency", "evidence", "small steps"])
    # dedupe while preserving order
    seen = set()
    highlight_terms = [t for t in highlight_terms if not (t in seen or seen.add(t))]

    return {
        "hero_narrative": text,
        "highlight_terms": highlight_terms,
    }


# =============================================================================
# BUG FIX: _pick_recommended_activity now filters by user_hash
# =============================================================================

def _pick_recommended_activity(
    db: Session, 
    user_hash: Optional[str] = None  # BUG FIX: Added user_hash parameter
) -> Optional[schemas.ActivityRecommendationOut]:
    """
    Pick a recommended activity for the user.
    
    BUG FIX: Now filters by user_hash to return only the user's own activities,
    preventing cross-user data pollution where Patient B would see Patient A's activities.
    
    Args:
        db: Database session
        user_hash: User identifier to filter activities (optional for backward compatibility)
    
    Returns:
        ActivityRecommendationOut or None if no activities found
    """
    # BUG FIX: Build query with user_hash filter
    query = db.query(models.Activities).filter(models.Activities.is_active == True)
    
    if user_hash:
        # Return only this user's activities (or activities with no user_hash for backward compatibility)
        query = query.filter(
            (models.Activities.user_hash == user_hash) | 
            (models.Activities.user_hash == None)
        )
    
    row = query.order_by(models.Activities.created_at.desc()).first()
    
    if not row:
        return None

    tags: List[str] = []
    if row.tags_json:
        try:
            tags = json.loads(row.tags_json) or []
        except Exception:
            tags = []

    return schemas.ActivityRecommendationOut(
        id=row.id,
        title=row.title,
        description=row.description,
        life_area=row.life_area,
        effort_level=row.effort_level,
        reward_type=row.reward_type,
        default_duration_min=row.default_duration_min,
        location_label=row.location_label,
        tags=tags,
        user_hash=row.user_hash,  # BUG FIX: Include user_hash in output
        lat=getattr(row, 'lat', None),
        lng=getattr(row, 'lng', None),
        place_id=getattr(row, 'place_id', None),
    )


def _extract_postal_code(db: Session, user_hash: Optional[str]) -> Optional[str]:
    if not user_hash:
        return None

    
    if not hasattr(models, "ClinicalIntake"):
        return None

    try:
        row = (
            db.query(models.ClinicalIntake)
            .filter(models.ClinicalIntake.user_hash == user_hash)
            .order_by(models.ClinicalIntake.created_at.desc())
            .first()
        )
    except Exception:
        return None

    if not row:
        return None

    return getattr(row, "postal_code", None)


def build_today_summary(db: Session, user: models.Users) -> schemas.TodaySummaryOut:
    """
    Build the today summary for a user.
    
    BUG FIX: Now passes user_hash to _pick_recommended_activity to ensure
    the user only sees their own personalized activities.
    """
    now = datetime.utcnow()
    greeting = _time_of_day_greeting(now)
    fname = _first_name(user.name)
    if fname:
        greeting = f"{greeting}, {fname}"
    else:
        greeting = f"{greeting}"


    session_info = _last_session_feedback(db, user.user_hash)
    schema_label = _pick_schema_label(db, user.user_hash)
    hero_bits = _build_hero_narrative(
        user_name=user.name,
        schema_label=schema_label or session_info.get("schema_hint"),
        mood=session_info.get("mood"),
        feedback=session_info.get("feedback"),
    )

    
    j_state = compute_journey_state(db, user.user_hash)
    journey_ready = j_state.get("status") == "ready"
    cooldown_remaining = int(j_state.get("cooldown_minutes_remaining", 0))

    
    # BUG FIX: Pass user_hash to get user-specific activity
    rec_act = _pick_recommended_activity(db, user.user_hash)


    postal_code = _extract_postal_code(db, user.user_hash)

    return schemas.TodaySummaryOut(
        greeting=greeting,
        current_date=now.date(),
        journey_day=user.journey_day,
        hero_narrative=hero_bits["hero_narrative"],
        highlight_terms=hero_bits["highlight_terms"],
        has_recent_session=bool(session_info.get("has_session")),
        journey_ready=journey_ready,
        journey_cooldown_minutes_remaining=cooldown_remaining,
        recommended_activity=rec_act,
        postal_code=postal_code,
    )


# =============================================================================
# CHANGE #1: Pre-generation functions for Day 2+ audio
# =============================================================================


def generate_narrative_script(
    db: Session,
    user_hash: str,
    journey_day: int,
    mood: Optional[str] = None,
    schema_hint: Optional[str] = None,
    chills_context: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    Generate a narrative script for pre-generation.
    
    This uses the same logic as journey.py but returns just the script text.
    Called by feedback.py when triggering background pre-generation.
    
    Args:
        db: Database session
        user_hash: User identifier
        journey_day: The journey day this script is FOR
        mood: User's mood/feeling
        schema_hint: Schema theme
        chills_context: Dict with emotion_word, chills_detail, last_insight, etc.
    
    Returns:
        Script text string, or None if generation fails
    """
    try:
        # Import services here to avoid circular imports
        from ..services import prompt as pr
        from ..services import llm
        from ..services import selector as sel
        from ..core.config import cfg
        from ..utils.audio import clean_script, load_audio, duration_ms
        
        # Load music index and pick a track for this journey day
        idx = sel.load_index()
        ti = sel.pick_track_by_day(idx, journey_day)
        
        if ti is None:
            # Fallback to folder-based selection
            folders = sel.choose_folder(mood or "mixed", schema_hint or "default")
            ti = sel.pick_track(idx, folders, [])
        
        if ti is None:
            print(f"[narrative] Could not pick track for day {journey_day}")
            return None
        
        track_id, music_path, chosen_folder, music_file = ti
        
        # Get music duration to calculate target words
        MUSIC_INTRO_MS = 6000
        music_ms = duration_ms(load_audio(music_path))
        spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
        target_words = min(_estimate_target_words(spoken_target_ms, wps=1.7), 1200)
        
        # Build the prompt context
        jdict = {
            "user_hash": user_hash,
            "journey_day": journey_day,
            "feeling": mood or "mixed",
            "schema_choice": schema_hint or "default",
            "music_ms": music_ms,
            "spoken_target_ms": spoken_target_ms,
            "intro_ms": MUSIC_INTRO_MS,
        }
        
        # Add chills-based context if available
        if chills_context:
            jdict["last_insight"] = chills_context.get("last_insight")
            jdict["chills_level"] = chills_context.get("chills_level")
            jdict["emotion_word"] = chills_context.get("emotion_word")
            jdict["chills_detail"] = chills_context.get("chills_detail")
            jdict["had_chills"] = chills_context.get("had_chills", False)
            jdict["goal_today"] = chills_context.get("goal_today") or "continue the journey"
            jdict["place"] = chills_context.get("place")
            # NEW: Add intake weekly plan data
            jdict["life_area"] = chills_context.get("life_area")
            jdict["life_focus"] = chills_context.get("life_focus")
            jdict["week_actions"] = chills_context.get("week_actions", [])
        
        # Choose narrative arc
        arc_name = pr.choose_arc(jdict)
        jdict["arc_name"] = arc_name
        
        # Build prompt and generate script
        prompt_txt = pr.build(jdict, target_words=target_words)
        script = clean_script(llm.generate_text(prompt_txt, cfg.OPENAI_API_KEY))
        
        if not script:
            print(f"[narrative] LLM returned empty script for day {journey_day}")
            return None
        
        # Extend if too short
        if _word_count(script) < int(0.9 * target_words):
            need = max(30, target_words - _word_count(script))
            tail = _last_n_words(script, 40)
            cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
            more = clean_script(llm.generate_text(cont_prompt, cfg.OPENAI_API_KEY))
            if more and more not in script:
                script = (script + " " + more).strip()
        
        # Clean up ending
        script = _sentence_safe(script)
        if not script.endswith((".", "!", "?")):
            script = script.rstrip() + "."
        
        print(f"[narrative] Generated script for day {journey_day}, {_word_count(script)} words")
        return script
        
    except Exception as e:
        print(f"[narrative] Error generating script: {e}")
        return None


def generate_audio_from_script(
    script_text: str,
    voice_id: str = "default",
    track_id: Optional[str] = None,
    journey_day: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Generate audio from a script for pre-generation.
    
    This synthesizes TTS and mixes with music, similar to journey.py.
    Called by feedback.py during background pre-generation.
    
    Args:
        script_text: The narrative script text
        voice_id: ElevenLabs voice ID
        track_id: Optional specific track ID to use
        journey_day: Journey day (used for track selection if track_id not provided)
    
    Returns:
        Dict with audio_path and duration_ms, or None if generation fails
    """
    try:
        # Import services here to avoid circular imports
        from ..services import tts
        from ..services import mix as mixr
        from ..services import selector as sel
        from ..services import store as st
        from ..core.config import cfg
        from ..utils.audio import load_audio, duration_ms
        from ..utils.text import finalize_script
        from ..utils.hash import sid
        from pydub import AudioSegment
        
        MUSIC_INTRO_MS = 6000
        
        # Ensure output directory exists
        st.ensure_dir(cfg.OUT_DIR)
        
        # Select music track
        idx = sel.load_index()
        ti = None
        
        if journey_day:
            ti = sel.pick_track_by_day(idx, journey_day)
        
        if ti is None:
            folders = sel.choose_folder("mixed", "default")
            ti = sel.pick_track(idx, folders, [])
        
        if ti is None:
            print("[narrative] Could not pick music track for audio generation")
            return None
        
        _, music_path, chosen_folder, music_file = ti
        
        # Finalize script for TTS
        script_for_tts = finalize_script(script_text)
        
        # Generate TTS
        tts_tmp_wav = tts.synth(script_for_tts, voice_id, cfg.ELEVENLABS_API_KEY)
        if not tts_tmp_wav or not os.path.exists(tts_tmp_wav):
            print("[narrative] TTS synthesis failed")
            return None
        
        # Generate unique session ID for output file
        session_id = sid()
        out_path = st.out_file(cfg.OUT_DIR, session_id)
        
        # Process audio
        raw_voice = load_audio(tts_tmp_wav).set_frame_rate(44100).set_channels(2)
        
        # Add intro silence
        intro = AudioSegment.silent(duration=MUSIC_INTRO_MS, frame_rate=raw_voice.frame_rate)
        voice_with_intro = intro + raw_voice
        
        # Export to temp file for mixing
        tmp_vo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        voice_with_intro.export(tmp_vo.name, format="wav")
        voice_for_mix = tmp_vo.name
        
        # Mix voice with music
        duration_ms_final = mixr.mix(
            voice_for_mix,
            music_path,
            out_path,
            duck_db=10.0,
            sync_mode="retime_music_to_voice",
            ffmpeg_bin=cfg.FFMPEG_BIN,
        )
        
        # Clean up temp file
        try:
            os.unlink(voice_for_mix)
        except Exception:
            pass
        
        print(f"[narrative] Generated audio: {out_path}, duration: {duration_ms_final}ms")
        
        return {
            "audio_path": out_path,
            "duration_ms": duration_ms_final,
            "session_id": session_id,
        }
        
    except Exception as e:
        print(f"[narrative] Error generating audio: {e}")
        return None


# Helper functions for script generation (duplicated from journey.py to avoid circular imports)

def _estimate_target_words(music_ms: int, wps: float = 1.7) -> int:
    seconds = max(1, music_ms // 1000)
    return max(120, int(seconds * wps))


def _word_count(txt: str) -> int:
    return len((txt or "").strip().split())


def _last_n_words(txt: str, n: int = 35) -> str:
    w = (txt or "").strip().split()
    return " ".join(w[-n:]) if len(w) > n else (txt or "").strip()


def _sentence_safe(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return text
    last_dot = text.rfind(".")
    last_ex = text.rfind("!")
    last_q = text.rfind("?")
    last_punct = max(last_dot, last_ex, last_q)
    if last_punct != -1:
        return text[: last_punct + 1].strip()
    return text


def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
    """Build a continuation prompt for extending a script."""
    try:
        from ..services import prompt as pr
        head = pr.build(base_json, target_words=None)
        head_lines = head.splitlines()
        head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
    except Exception:
        head_short = "Continue the narrative."
    
    return (
        f"{head_short}\n"
        "Continue the SAME single spoken narration about the SAME unnamed person, "
        "in the SAME day and setting.\n"
        "Do NOT restart the story, do NOT introduce a new character name, "
        "and do NOT describe a new morning, a new apartment, or a second beginning.\n"
        f"Add approximately {need_more} new words.\n"
        "No stage directions except the literal token [pause] where a slightly longer silence makes sense.\n"
        "No summaries. Keep cadence natural. End decisively with a clear emotional landing.\n"
        f"Pick up seamlessly from this tail: \"{last_tail}\""
    )
