from pathlib import Path
import os
import tempfile
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydub import AudioSegment

from ..schemas import IntakeIn, GenerateOut
from ..db import SessionLocal
from ..models import Sessions, Scripts, Activities, ActivitySessions, Users, MiniCheckins, TherapistPatients, TherapistAIGuidance, PreGeneratedAudio
from ..services import prompt as pr
from ..services import llm
from ..services import selector as sel
from ..services import tts as tts
from ..services import mix as mixr
from ..services import store as st
from ..services import narrative as narrative_service
from ..utils.hash import sid
from ..utils.audio import clean_script, load_audio, duration_ms
from ..utils.text import finalize_script
from ..core.config import cfg  

r = APIRouter()

MUSIC_INTRO_MS = 6000   

# ISSUE 8: Static audio file for Day 1 (no generation needed)
DAY1_STATIC_AUDIO_FILENAME = "videoplayback.m4a"


def db():
    q = SessionLocal()
    try:
        yield q
    finally:
        q.close()




def _estimate_target_words(music_ms: int, wps: float = 1.7) -> int:
    seconds = max(1, music_ms // 1000)
    return max(120, int(seconds * wps))


def _within(ms: int, target: int, tol: float = 0.03) -> bool:
    return abs(ms - target) <= int(target * tol)


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


def _trim_tail_words_by_count(txt: str, drop_words: int) -> str:
    if drop_words <= 0:
        return (txt or "").strip()
    words = (txt or "").strip().split()
    if not words:
        return ""
    if len(words) <= drop_words:
        base = " ".join(words[: max(1, len(words) - 5)])
        out = _sentence_safe(base)
        if not out.endswith((".", "!", "?")):
            out = out.rstrip() + "."
        return out
    kept = words[: len(words) - drop_words]
    base = " ".join(kept).strip()
    out = _sentence_safe(base)
    if not out.endswith((".", "!", "?")):
        out = out.rstrip() + "."
    return out


def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
    head = pr.build(base_json, target_words=None)
    head_lines = head.splitlines()
    head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
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


def _fallback_from_history(q: Session, user_hash: str | None) -> dict:
    """
    Get context for journey generation from user history.
    
    For Day 2+ users: Uses chills-based context from last session's feedback
    (emotion_word, session_insight, chills_detail) instead of mini check-in.
    
    Also includes intake weekly plan data (life_area, life_focus, week_actions).
    
    Falls back to session/activity history if no feedback available.
    """
    out = {
        "feeling": None,
        "schema_choice": None,
        "postal_code": None,
        "goal_today": None,
        "place": None,
        "journey_day": None,
        # Chills-based fields
        "last_insight": None,
        "chills_level": None,
        "emotion_word": None,
        "chills_detail": None,
        "had_chills": False,
        # NEW: Intake weekly plan fields
        "life_area": None,
        "life_focus": None,
        "week_actions": [],
    }
    if not user_hash:
        return out

    # First, try to get chills-based context from last session's feedback
    # This now also includes intake data (life_area, life_focus, week_actions)
    chills_ctx = narrative_service.get_chills_context_for_generation(q, user_hash)
    
    # If we have chills context with meaningful data, use it
    if chills_ctx.get("feeling") or chills_ctx.get("last_insight") or chills_ctx.get("emotion_word"):
        out["feeling"] = chills_ctx.get("feeling")
        out["schema_choice"] = chills_ctx.get("schema_choice")
        out["postal_code"] = chills_ctx.get("postal_code")
        out["goal_today"] = chills_ctx.get("goal_today")
        out["place"] = chills_ctx.get("place")
        out["last_insight"] = chills_ctx.get("last_insight")
        out["chills_level"] = chills_ctx.get("chills_level")
        out["emotion_word"] = chills_ctx.get("emotion_word")
        out["chills_detail"] = chills_ctx.get("chills_detail")
        out["had_chills"] = chills_ctx.get("had_chills", False)
        # NEW: Get intake weekly plan data
        out["life_area"] = chills_ctx.get("life_area")
        out["life_focus"] = chills_ctx.get("life_focus")
        out["week_actions"] = chills_ctx.get("week_actions", [])
    else:
        # Even without chills context, still get intake weekly plan data
        out["life_area"] = chills_ctx.get("life_area")
        out["life_focus"] = chills_ctx.get("life_focus")
        out["week_actions"] = chills_ctx.get("week_actions", [])
        out["postal_code"] = chills_ctx.get("postal_code")
        
        # Fallback to old behavior: get from last session directly
        last_sess = (
            q.query(Sessions)
            .filter(Sessions.user_hash == user_hash)
            .order_by(Sessions.created_at.desc())
            .first()
        )
        if last_sess:
            out["feeling"] = last_sess.mood or out["feeling"]
            out["schema_choice"] = last_sess.schema_hint or out["schema_choice"]

        # Try to get place/goal from activity history
        try:
            asess = (
                q.query(ActivitySessions)
                .filter(ActivitySessions.user_hash == user_hash)
                .order_by(ActivitySessions.started_at.desc())
                .first()
            )
            if asess:
                act = q.query(Activities).filter(Activities.id == asess.activity_id).first()
                if act:
                    out["goal_today"] = getattr(act, "title", None) or out["goal_today"]
                    out["place"] = getattr(act, "location_label", None) or out["place"]
        except Exception:
            pass

    # Always try to get journey_day and postal_code from user record
    try:
        u = q.query(Users).filter(Users.user_hash == user_hash).first()
        if u and getattr(u, "postal_code", None):
            out["postal_code"] = getattr(u, "postal_code")
        if u and getattr(u, "journey_day", None):
            out["journey_day"] = getattr(u, "journey_day")
    except Exception:
        pass

    return out


def _get_therapist_guidance(q: Session, user_hash: str | None) -> str | None:
    """
    Fetch active therapist AI guidance for a patient by user_hash.
    
    Returns the guidance text if found and active, None otherwise.
    """
    if not user_hash:
        return None
    
    try:
        # Find the user
        user = q.query(Users).filter(Users.user_hash == user_hash).first()
        if not user:
            return None
        
        # Find active guidance for this patient
        guidance = (
            q.query(TherapistAIGuidance)
            .filter(
                TherapistAIGuidance.patient_user_id == user.id,
                TherapistAIGuidance.is_active == True,
            )
            .order_by(TherapistAIGuidance.updated_at.desc())
            .first()
        )
        
        if guidance and guidance.guidance_text:
            return guidance.guidance_text.strip()
        
        return None
    except Exception as e:
        print(f"[journey] Error fetching therapist guidance: {e}")
        return None


# =============================================================================
# CHANGE #1: Check for and serve pre-generated audio
# =============================================================================


def _check_pre_generated_audio(q: Session, user_hash: str, journey_day: int) -> PreGeneratedAudio | None:
    """
    Check if there's pre-generated audio ready for this user's journey day.
    
    Returns the PreGeneratedAudio record if found and ready, None otherwise.
    """
    if not user_hash or not journey_day:
        return None
    
    try:
        pre_gen = (
            q.query(PreGeneratedAudio)
            .filter(
                PreGeneratedAudio.user_hash == user_hash,
                PreGeneratedAudio.for_journey_day == journey_day,
                PreGeneratedAudio.status == "ready",
            )
            .order_by(PreGeneratedAudio.created_at.desc())
            .first()
        )
        
        if pre_gen and pre_gen.audio_path:
            print(f"[journey] Found pre-generated audio for user {user_hash} day {journey_day}, id={pre_gen.id}")
            return pre_gen
        
        return None
    except Exception as e:
        print(f"[journey] Error checking pre-generated audio: {e}")
        return None


def _use_pre_generated_audio(
    q: Session,
    pre_gen: PreGeneratedAudio,
    user_hash: str,
    effective: dict,
) -> GenerateOut:
    """
    Use pre-generated audio instead of generating on-demand.
    
    Creates a session record and marks the pre-generated audio as used.
    """
    c = cfg
    
    session_id = sid()
    
    # Get the audio URL
    # The audio_path from pre-generation should be a full path or filename
    audio_path = pre_gen.audio_path
    
    # Determine if it's a full path or just a filename
    if os.path.isabs(audio_path) or audio_path.startswith(c.OUT_DIR):
        # Full path - extract filename
        audio_filename = Path(audio_path).name
    else:
        # Just a filename
        audio_filename = audio_path
    
    public_url = st.public_url(c.PUBLIC_BASE_URL, audio_filename)
    
    # Get script excerpt
    script_text = pre_gen.script_text or ""
    excerpt = script_text[:600] + ("..." if len(script_text) > 600 else "")
    
    # Try to get duration from the audio file
    duration_ms_final = 600000  # Default 10 minutes
    try:
        full_audio_path = os.path.join(c.OUT_DIR, audio_filename) if not os.path.isabs(audio_path) else audio_path
        if os.path.exists(full_audio_path):
            duration_ms_final = duration_ms(load_audio(full_audio_path))
    except Exception as e:
        print(f"[journey] Could not get duration from pre-generated audio: {e}")
    
    # Create session record
    row = Sessions(
        id=session_id,
        user_hash=user_hash,
        track_id=pre_gen.track_id or "pre_generated",
        voice_id=pre_gen.voice_id or "default",
        audio_path=audio_filename,
        mood=pre_gen.mood or effective.get("feeling"),
        schema_hint=pre_gen.schema_hint or effective.get("schema_choice"),
    )
    q.add(row)
    
    # Add script record
    if script_text:
        q.add(Scripts(session_id=session_id, script_text=script_text))
    
    # Mark pre-generated audio as used
    pre_gen.status = "used"
    pre_gen.used_at = datetime.utcnow()
    pre_gen.used_session_id = session_id
    
    q.commit()
    
    print(f"[journey] Using pre-generated audio for session {session_id}, pre_gen_id={pre_gen.id}")
    
    return GenerateOut(
        session_id=session_id,
        audio_url=public_url,
        duration_ms=duration_ms_final,
        script_excerpt=excerpt,
        script_text=script_text,
        track_id=pre_gen.track_id or "pre_generated",
        voice_id=pre_gen.voice_id or "default",
        music_folder="pre_generated",
        music_file=audio_filename,
        journey_day=pre_gen.for_journey_day,
    )


# =============================================================================
# FIX: Pre-gen status endpoint for instant playback (frontend checks this first)
# =============================================================================


@r.get("/api/journey/pre-gen-status")
def get_pre_gen_status(
    user_hash: str = Query(..., description="User hash to check pre-generated audio for"),
    q: Session = Depends(db),
):
    """
    Quick check if pre-generated audio exists for the user's current journey day.
    
    This endpoint is called by the frontend BEFORE showing any loading screen.
    If pre-gen exists, the frontend can skip the loader and go straight to the player.
    
    Returns:
        - has_pre_gen: bool - whether pre-generated audio is available
        - audio_url: str | None - the audio URL if available
        - session_id: str | None - a new session ID if pre-gen is available
        - duration_ms: int | None - audio duration if available
        - journey_day: int | None - the journey day this audio is for
    """
    c = cfg
    
    # Get user's current journey day
    try:
        user = q.query(Users).filter(Users.user_hash == user_hash).first()
        if not user:
            return {
                "has_pre_gen": False,
                "audio_url": None,
                "session_id": None,
                "duration_ms": None,
                "journey_day": None,
            }
        
        journey_day = getattr(user, "journey_day", None) or 1
        
        # Day 1 uses static audio - return it directly
        if journey_day == 1:
            static_audio_url = f"/assets/{DAY1_STATIC_AUDIO_FILENAME}"
            return {
                "has_pre_gen": True,
                "audio_url": static_audio_url,
                "session_id": f"day1_static_{int(datetime.utcnow().timestamp())}",
                "duration_ms": 720000,  # 12 minutes
                "journey_day": 1,
                "title": "Your First Journey",
                "subtitle": "Welcome to ReWire",
                "session_number": 1,
            }
        
        # Day 2+: Check for pre-generated audio
        pre_gen = _check_pre_generated_audio(q, user_hash, journey_day)
        
        if not pre_gen:
            return {
                "has_pre_gen": False,
                "audio_url": None,
                "session_id": None,
                "duration_ms": None,
                "journey_day": journey_day,
            }
        
        # Pre-gen exists! Build the response
        audio_path = pre_gen.audio_path
        
        # Determine if it's a full path or just a filename
        if os.path.isabs(audio_path) or audio_path.startswith(c.OUT_DIR):
            audio_filename = Path(audio_path).name
        else:
            audio_filename = audio_path
        
        public_url = st.public_url(c.PUBLIC_BASE_URL, audio_filename)
        
        # Try to get duration
        duration_ms_val = 600000  # Default 10 minutes
        try:
            full_audio_path = os.path.join(c.OUT_DIR, audio_filename) if not os.path.isabs(audio_path) else audio_path
            if os.path.exists(full_audio_path):
                duration_ms_val = duration_ms(load_audio(full_audio_path))
        except Exception:
            pass
        
        # Generate a session ID for this pre-gen
        # Note: We don't create the session record here - that happens when /generate is called
        # This is just a status check
        
        # Actually, to make this truly instant, we should create the session here
        # and return all the data needed for the player
        session_id = sid()
        
        # Create session record
        row = Sessions(
            id=session_id,
            user_hash=user_hash,
            track_id=pre_gen.track_id or "pre_generated",
            voice_id=pre_gen.voice_id or "default",
            audio_path=audio_filename,
            mood=pre_gen.mood,
            schema_hint=pre_gen.schema_hint,
        )
        q.add(row)
        
        # Add script record
        script_text = pre_gen.script_text or ""
        if script_text:
            q.add(Scripts(session_id=session_id, script_text=script_text))
        
        # Mark pre-generated audio as used
        pre_gen.status = "used"
        pre_gen.used_at = datetime.utcnow()
        pre_gen.used_session_id = session_id
        
        q.commit()
        
        print(f"[journey] Pre-gen status check: found and using pre-gen for day {journey_day}, session={session_id}")
        
        return {
            "has_pre_gen": True,
            "audio_url": public_url,
            "session_id": session_id,
            "duration_ms": duration_ms_val,
            "journey_day": journey_day,
            "title": f"Day {journey_day} Journey",
            "subtitle": "Your personalized session",
            "session_number": journey_day,
            "script_excerpt": script_text[:600] + ("..." if len(script_text) > 600 else ""),
            "track_id": pre_gen.track_id or "pre_generated",
            "voice_id": pre_gen.voice_id or "default",
        }
        
    except Exception as e:
        print(f"[journey] Error in pre-gen-status: {e}")
        return {
            "has_pre_gen": False,
            "audio_url": None,
            "session_id": None,
            "duration_ms": None,
            "journey_day": None,
            "error": str(e),
        }


@r.post("/api/journey/generate", response_model=GenerateOut)
def generate(x: IntakeIn, q: Session = Depends(db)):
    c = cfg
    st.ensure_dir(c.OUT_DIR)

    
    fb = _fallback_from_history(q, getattr(x, "user_hash", None))

    
    def eff(val, fallback, default):
        if val is None or (isinstance(val, str) and val.strip() == ""):
            return fallback if (fallback is not None and str(fallback).strip() != "") else default
        return val

    effective = {
        "feeling": eff(getattr(x, "feeling", None), fb.get("feeling"), "mixed"),
        "schema_choice": eff(getattr(x, "schema_choice", None), fb.get("schema_choice"), "default"),
        "postal_code": eff(getattr(x, "postal_code", None), fb.get("postal_code"), ""),
        "goal_today": eff(getattr(x, "goal_today", None), fb.get("goal_today"), "show up for the day"),
        "place": eff(getattr(x, "place", None), fb.get("place"), None),
        "journey_day": getattr(x, "journey_day", None) or fb.get("journey_day", None),
        # Chills-based fields for prompt building
        "last_insight": fb.get("last_insight"),
        "chills_level": fb.get("chills_level"),
        "emotion_word": fb.get("emotion_word"),
        "chills_detail": fb.get("chills_detail"),
        "had_chills": fb.get("had_chills", False),
        # NEW: Intake weekly plan fields for prompt building
        "life_area": fb.get("life_area"),
        "life_focus": fb.get("life_focus"),
        "week_actions": fb.get("week_actions", []),
    }

    # ISSUE 8: Check if Day 1 - return static audio without generation
    journey_day = effective.get("journey_day")
    if journey_day is not None and journey_day == 1:
        # Return static audio for Day 1
        session_id = sid()
        static_audio_url = f"/assets/{DAY1_STATIC_AUDIO_FILENAME}"
        
        # Create session record for tracking
        row = Sessions(
            id=session_id,
            user_hash=x.user_hash or "",
            track_id="day1_static",
            voice_id="static",
            audio_path=DAY1_STATIC_AUDIO_FILENAME,
            mood=effective["feeling"],
            schema_hint=effective["schema_choice"],
        )
        q.add(row)
        
        # Add script record
        day1_script = "Welcome to your first journey with ReWire. This is the beginning of something meaningful."
        q.add(Scripts(session_id=session_id, script_text=day1_script))
        
        # Save mini check-in snapshot (keeping for Day 1 since no prior feedback exists)
        try:
            if x.user_hash:
                q.add(
                    MiniCheckins(
                        user_hash=x.user_hash,
                        feeling=getattr(x, "feeling", None),
                        body=getattr(x, "body", None),
                        energy=getattr(x, "energy", None),
                        goal_today=getattr(x, "goal_today", None),
                        why_goal=getattr(x, "why_goal", None),
                        last_win=getattr(x, "last_win", None),
                        hard_thing=getattr(x, "hard_thing", None),
                        schema_choice=effective["schema_choice"],
                        postal_code=effective["postal_code"],
                        place=getattr(x, "place", None) or effective["place"],
                    )
                )
        except Exception:
            pass
        
        q.commit()
        
        return GenerateOut(
            session_id=session_id,
            audio_url=static_audio_url,
            duration_ms=720000,  # 12 minutes default
            script_excerpt=day1_script,
            script_text=day1_script,
            track_id="day1_static",
            voice_id="static",
            music_folder="day1",
            music_file=DAY1_STATIC_AUDIO_FILENAME,
            journey_day=1,
        )

    # =============================================================================
    # CHANGE #1: Check for pre-generated audio for Day 2+
    # =============================================================================
    if journey_day is not None and journey_day >= 2 and x.user_hash:
        pre_gen = _check_pre_generated_audio(q, x.user_hash, journey_day)
        if pre_gen:
            print(f"[journey] Found pre-generated audio for day {journey_day}, using it instead of generating")
            return _use_pre_generated_audio(q, pre_gen, x.user_hash, effective)
        else:
            print(f"[journey] No pre-generated audio found for day {journey_day}, generating on-demand")

    idx = sel.load_index()

    
    recent_track_ids: list[str] = []
    last_voice = None
    srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
    for s in srows:
        if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
            if s.track_id:
                recent_track_ids.append(s.track_id)
            if not last_voice and s.voice_id:
                last_voice = s.voice_id

    
    ti = None
    if getattr(x, "journey_day", None) or effective["journey_day"]:
        ti = sel.pick_track_by_day(idx, getattr(x, "journey_day", None) or effective["journey_day"])
    if ti is None:
        folders = sel.choose_folder(effective["feeling"], effective["schema_choice"])
        ti = sel.pick_track(idx, folders, recent_track_ids)
    track_id, music_path, chosen_folder, music_file = ti
    voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

    
    music_ms = duration_ms(load_audio(music_path))
    spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
    target_words = min(_estimate_target_words(spoken_target_ms, wps=1.7), 1200)

    
    jdict = x.model_dump()
    jdict["music_ms"] = music_ms
    jdict["spoken_target_ms"] = spoken_target_ms
    jdict["intro_ms"] = MUSIC_INTRO_MS

    
    jdict["feeling"] = effective["feeling"]
    jdict["schema_choice"] = effective["schema_choice"]
    jdict["postal_code"] = effective["postal_code"]
    jdict["goal_today"] = effective["goal_today"]
    jdict["place"] = effective["place"]
    
    # Add chills-based fields for prompt building
    jdict["last_insight"] = effective.get("last_insight")
    jdict["chills_level"] = effective.get("chills_level")
    jdict["emotion_word"] = effective.get("emotion_word")
    jdict["chills_detail"] = effective.get("chills_detail")
    jdict["had_chills"] = effective.get("had_chills", False)
    
    # NEW: Add intake weekly plan fields for prompt building
    jdict["life_area"] = effective.get("life_area")
    jdict["life_focus"] = effective.get("life_focus")
    jdict["week_actions"] = effective.get("week_actions", [])
    
    # Fetch and add therapist guidance
    therapist_guidance = _get_therapist_guidance(q, x.user_hash)
    jdict["therapist_guidance"] = therapist_guidance

    
    arc_name = pr.choose_arc(jdict)
    jdict["arc_name"] = arc_name

    prompt_txt = pr.build(jdict, target_words=target_words)
    script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

    
    if _word_count(script) < int(0.9 * target_words):
        need = max(30, target_words - _word_count(script))
        tail = _last_n_words(script, 40)
        cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
        more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
        if more and more not in script:
            script = (script + " " + more).strip()

    
    max_corrections = 4
    attempt = 0
    best_script = script
    best_tts_path = None
    ema_wps = 2.0

    while True:
        script_for_tts = finalize_script(best_script)

        tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
        tts_ms = duration_ms(load_audio(tts_tmp_wav))
        wc = _word_count(script_for_tts)
        observed_wps = wc / max(1.0, tts_ms / 1000.0)
        ema_wps = 0.7 * ema_wps + 0.3 * observed_wps

        if _within(tts_ms, spoken_target_ms, tol=0.04) or attempt >= max_corrections:
            best_script, best_tts_path = script_for_tts, tts_tmp_wav
            break

        delta_ms = spoken_target_ms - tts_ms
        delta_words = int(abs(delta_ms) / 1000.0 * ema_wps)
        delta_words = max(30, min(delta_words, 200))

        if delta_ms > 0:
            # extend
            tail = _last_n_words(script_for_tts, 40)
            cont_prompt = _build_continue_prompt(jdict, tail, need_more=delta_words)
            addition = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
            if addition:
                best_script = (script_for_tts + " " + addition).strip()
        else:
            # trim
            best_script = _trim_tail_words_by_count(script_for_tts, delta_words)

        attempt += 1


    session_id = sid()
    out_path = st.out_file(c.OUT_DIR, session_id)

    raw_voice = load_audio(best_tts_path).set_frame_rate(44100).set_channels(2)

    best_script = _sentence_safe(best_script)
    if not best_script.endswith((".", "!", "?")):
        best_script = best_script.rstrip() + "."

    intro = AudioSegment.silent(duration=MUSIC_INTRO_MS, frame_rate=raw_voice.frame_rate)
    voice_with_intro = intro + raw_voice

    tmp_vo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    voice_with_intro.export(tmp_vo.name, format="wav")
    voice_for_mix = tmp_vo.name

    duration_ms_final = mixr.mix(
        voice_for_mix,
        music_path,
        out_path,
        duck_db=10.0,
        sync_mode="retime_music_to_voice",
        ffmpeg_bin=c.FFMPEG_BIN,
    )

    
    public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
    excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

    row = Sessions(
        id=session_id,
        user_hash=x.user_hash or "",
        track_id=track_id,
        voice_id=voice_id,
        audio_path=Path(out_path).name,
        mood=effective["feeling"],
        schema_hint=effective["schema_choice"],
    )
    q.add(row)
    q.add(Scripts(session_id=session_id, script_text=best_script))

    
    # For Day 2+, we no longer need mini check-in since we use feedback from last session
    # But we still save it for record-keeping if data was provided
    try:
        if x.user_hash:
            # Check if any check-in data was actually provided in the request
            has_checkin_data = any([
                getattr(x, "feeling", None),
                getattr(x, "body", None),
                getattr(x, "energy", None),
                getattr(x, "goal_today", None),
            ])
            if has_checkin_data:
                q.add(
                    MiniCheckins(
                        user_hash=x.user_hash,
                        feeling=getattr(x, "feeling", None),
                        body=getattr(x, "body", None),
                        energy=getattr(x, "energy", None),
                        goal_today=getattr(x, "goal_today", None),
                        why_goal=getattr(x, "why_goal", None),
                        last_win=getattr(x, "last_win", None),
                        hard_thing=getattr(x, "hard_thing", None),
                        schema_choice=effective["schema_choice"],
                        postal_code=effective["postal_code"],
                        place=getattr(x, "place", None) or effective["place"],
                    )
                )
    except Exception:
        # don't fail journey creation on snapshot errors
        pass

    q.commit()

    return GenerateOut(
        session_id=session_id,
        audio_url=public_url,
        duration_ms=duration_ms_final,
        script_excerpt=excerpt,
        script_text=best_script,
        track_id=track_id,
        voice_id=voice_id,
        music_folder=chosen_folder,
        music_file=music_file,
        journey_day=effective["journey_day"],
    )


@r.get("/api/journey/recent")
def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
    c = cfg
    idx = sel.load_index()
    id2path = {row["id"]: row["path"] for row in idx["tracks"]}

    s = q.query(Sessions)
    if user_hash:
        s = s.filter(Sessions.user_hash == user_hash)
    rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

    out = []
    for z in rows:
        url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
        relpath = id2path.get(z.track_id, "")
        music_file = os.path.basename(relpath) if relpath else ""
        music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
        out.append({
            "session_id": z.id,
            "audio_url": url,
            "track_id": z.track_id,
            "voice_id": z.voice_id,
            "mood": z.mood,
            "schema_hint": z.schema_hint,
            "music_folder": music_folder,
            "music_file": music_file,
            "created_at": z.created_at.isoformat(),
        })
    return out


@r.get("/api/journey/session/{sid}")
def get_session(sid: str, q: Session = Depends(db)):
    c = cfg
    z = q.query(Sessions).filter(Sessions.id == sid).first()
    if not z:
        raise HTTPException(status_code=404, detail="session not found")

    idx = sel.load_index()
    id2path = {row["id"]: row["path"] for row in idx["tracks"]}
    relpath = id2path.get(z.track_id, "")
    music_file = os.path.basename(relpath) if relpath else ""
    music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

    url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
    return {
        "session_id": z.id,
        "audio_url": url,
        "track_id": z.track_id,
        "voice_id": z.voice_id,
        "mood": z.mood,
        "schema_hint": z.schema_hint,
        "music_folder": music_folder,
        "music_file": music_file,
        "created_at": z.created_at.isoformat(),
    }


@r.get("/api/journey/state")
def journey_state(
    user_hash: str | None = Query(
        None,
        description="Optional user hash; if omitted, state is computed as 'ready' by default.",
    ),
    q: Session = Depends(db),
):
    return narrative_service.compute_journey_state(q, user_hash)
