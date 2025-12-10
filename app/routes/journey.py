from pathlib import Path
import os
import tempfile

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydub import AudioSegment

from ..schemas import IntakeIn, GenerateOut
from ..db import SessionLocal
from ..models import Sessions, Scripts, Activities, ActivitySessions, Users, MiniCheckins  # ← added MiniCheckins
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

    out = {
        "feeling": None,
        "schema_choice": None,
        "postal_code": None,
        "goal_today": None,
        "place": None,
        "journey_day": None,
    }
    if not user_hash:
        return out

    last_sess = (
        q.query(Sessions)
        .filter(Sessions.user_hash == user_hash)
        .order_by(Sessions.created_at.desc())
        .first()
    )
    if last_sess:
        out["feeling"] = last_sess.mood or out["feeling"]
        out["schema_choice"] = last_sess.schema_hint or out["schema_choice"]

    try:
        u = q.query(Users).filter(Users.user_hash == user_hash).first()
        if u and getattr(u, "postal_code", None):
            out["postal_code"] = getattr(u, "postal_code")
        if u and getattr(u, "journey_day", None):
            out["journey_day"] = getattr(u, "journey_day")
    except Exception:
        pass

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

    return out




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
    }

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
