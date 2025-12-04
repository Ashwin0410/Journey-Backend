# from pathlib import Path
# import os

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()


# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()


# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # --- recent history for this user (avoid immediate repeats; remember last voice) ---
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = (
#         q.query(Sessions)
#          .order_by(Sessions.created_at.desc())
#          .limit(20)
#          .all()
#     )
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # --- choose music (prefer day-specific mapping; else mood/schema logic) ---
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)  # may return None if no mapping
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)

#     track_id, music_path, chosen_folder, music_file = ti

#     # --- choose voice (privilege Sevan/Carter; avoid immediate repeat) ---
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # --- LLM script (no stage directions) ---
#     jdict = x.model_dump()
#     prompt_txt = pr.build(jdict)
#     raw_script = llm.generate_text(prompt_txt, c.OPENAI_API_KEY)
#     script = clean_script(raw_script)

#     # --- TTS ---
#     tts_tmp_wav = tts.synth(script, voice_id, c.ELEVENLABS_API_KEY)

#     # --- Mix (duration/ducking handled in mix.py) ---
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)
#     duration_ms = mixr.mix(tts_tmp_wav, music_path, out_path, duck_db=-3.0)  # tweak in mix.py if needed

#     # --- Persist session row (not storing script by design; just return it) ---
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = script[:600] + ("..." if len(script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms,
#         script_excerpt=excerpt,
#         script_text=script,            # <-- full script included
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )


# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out


# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }

# from pathlib import Path
# import os

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()

# def _estimate_target_words(music_ms: int, wps: float = 2.3) -> int:
#     """
#     Estimate spoken word count to naturally fit the music before micro-retiming.
#     ElevenLabs delivery is typically ~2.2–2.6 words/sec.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(60, int(seconds * wps))

# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # --- recent history for this user (avoid immediate repeats; remember last voice) ---
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = (
#         q.query(Sessions)
#          .order_by(Sessions.created_at.desc())
#          .limit(20)
#          .all()
#     )
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # --- choose music (prefer day-specific mapping; else mood/schema logic) ---
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)  # may return None if no mapping
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)

#     track_id, music_path, chosen_folder, music_file = ti

#     # --- choose voice (privilege Sevan/Carter; avoid immediate repeat) ---
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # --- determine target words from music duration ---
#     music_seg = load_audio(music_path)
#     target_words = _estimate_target_words(len(music_seg), wps=2.3)

#     # --- LLM script (no stage directions), length-guided ---
#     jdict = x.model_dump()
#     prompt_txt = pr.build(jdict, target_words=target_words)
#     raw_script = llm.generate_text(prompt_txt, c.OPENAI_API_KEY)
#     script = clean_script(raw_script)

#     # --- TTS ---
#     tts_tmp_wav = tts.synth(script, voice_id, c.ELEVENLABS_API_KEY)

#     # --- Mix (pitch-preserving retime to EXACT length; ducking handled in mix.py) ---
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)
#     duration_ms = mixr.mix(
#         tts_tmp_wav,
#         music_path,
#         out_path,
#         duck_db=-3.0,                # music is quieter than voice after normalization
#         ffmpeg_bin=c.FFMPEG_BIN      # set in .env if not in PATH
#     )

#     # --- Persist session row + full script ---
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = script[:600] + ("..." if len(script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms,
#         script_excerpt=excerpt,
#         script_text=script,            # full script included in API response
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )

# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out

# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }

# from pathlib import Path
# import os

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()

# # === length helpers ===
# def _estimate_target_words(music_ms: int, wps: float = 2.3) -> int:
#     """
#     Estimate spoken word count to naturally fit the music before micro-retiming.
#     ElevenLabs delivery is typically ~2.2–2.6 words/sec.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(60, int(seconds * wps))

# def _within(ms: int, target: int, tol: float = 0.08) -> bool:
#     return abs(ms - target) <= int(target * tol)

# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # --- recent history for this user (avoid immediate repeats; remember last voice) ---
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = (
#         q.query(Sessions)
#          .order_by(Sessions.created_at.desc())
#          .limit(20)
#          .all()
#     )
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # --- choose music (prefer day-specific mapping; else mood/schema logic) ---
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)  # may return None if no mapping
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)

#     track_id, music_path, chosen_folder, music_file = ti

#     # --- choose voice (privilege Sevan/Carter; avoid immediate repeat) ---
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # --- determine target words from music duration ---
#     music_seg = load_audio(music_path)
#     music_ms = duration_ms(music_seg)
#     target_words = _estimate_target_words(music_ms, wps=2.3)

#     # === AUTO-FIT LOOP: generate -> TTS -> check -> optionally re-generate ===
#     tries = 0
#     max_tries = 2      # one correction cycle is usually enough

#     best_script = None
#     best_tts_path = None

#     while True:
#         jdict = x.model_dump()
#         prompt_txt = pr.build(jdict, target_words=target_words)
#         raw_script = llm.generate_text(prompt_txt, c.OPENAI_API_KEY)
#         script = clean_script(raw_script)

#         # TTS
#         tts_tmp_wav = tts.synth(script, voice_id, c.ELEVENLABS_API_KEY)

#         # measure TTS duration
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         print(f"[Journey] music={music_ms}ms, tts={tts_ms}ms, target_words={target_words}, try={tries+1}")

#         if _within(tts_ms, music_ms, tol=0.08) or tries >= max_tries:
#             best_script, best_tts_path = script, tts_tmp_wav
#             break

#         # adjust words and try again (cap changes to avoid overshoot)
#         factor = music_ms / max(1, tts_ms)     # >1 means we need more words
#         target_words = int(target_words * min(1.35, max(0.70, 0.92 * factor)))
#         tries += 1

#     # --- Mix (pitch-preserving retime to EXACT length; ducking handled in mix.py) ---
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)
#     duration_ms_final = mixr.mix(
#         best_tts_path,
#         music_path,
#         out_path,
#         duck_db=-3.0,                # music is quieter than voice after normalization
#         ffmpeg_bin=c.FFMPEG_BIN      # set in .env if not in PATH
#     )

#     # --- Persist session row + full script ---
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,            # full script included in API response
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )

# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out

# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }


# Best code
# from pathlib import Path
# import os

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()

# # ---------- helpers ----------
# def _estimate_target_words(music_ms: int, wps: float = 2.25) -> int:
#     """
#     Estimate spoken word count that should naturally match music length.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))

# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     # tighter match so content "feels" full before micro-retime
#     return abs(ms - target) <= int(target * tol)

# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = txt.strip().split()
#     return " ".join(w[-n:]) if len(w) > n else txt.strip()

# def _word_count(txt: str) -> int:
#     return len(txt.strip().split())

# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     """
#     Ask the model to continue the narration with ~need_more NEW words.
#     We pass a short head (rules/tone) and only a small tail to avoid token bloat.
#     """
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head

#     return (
#         f"{head_short}\n"
#         "Continue the SAME single, second-person spoken narration WITHOUT repeating ideas or sentences.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions. No summaries. Keep cadence natural. End decisively.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )

# # ---------- routes ----------
# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # --- recent history for this user (avoid immediate repeats; remember last voice) ---
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = (
#         q.query(Sessions)
#          .order_by(Sessions.created_at.desc())
#          .limit(20)
#          .all()
#     )
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # --- choose music (prefer day-specific mapping; else mood/schema logic) ---
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)  # may return None if no mapping
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)

#     track_id, music_path, chosen_folder, music_file = ti

#     # --- choose voice (privilege Sevan/Carter; avoid immediate repeat) ---
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # --- determine target words from music duration ---
#     music_seg = load_audio(music_path)
#     music_ms = duration_ms(music_seg)

#     # Natural fit target; capped so we don't ask the model for excessive length
#     target_words = _estimate_target_words(music_ms, wps=2.25)
#     target_words = min(target_words, 1200)

#     # ================= PHASE 1: Base script near target_words =================
#     jdict = x.model_dump()
#     prompt_txt = pr.build(jdict, target_words=target_words)
#     raw_script = llm.generate_text(prompt_txt, c.OPENAI_API_KEY)
#     script = clean_script(raw_script)

#     # ================= PHASE 2: Extend until target is reached =================
#     max_extend_rounds = 2
#     round_i = 0
#     while _word_count(script) < int(0.95 * target_words) and round_i < max_extend_rounds:
#         need = target_words - _word_count(script)
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()
#         round_i += 1

#     # ================= PHASE 3: Minor auto-fit with TTS feedback ===============
#     tries = 0
#     max_tries = 2  # small corrections only; main length handled above

#     best_script = None
#     best_tts_path = None

#     while True:
#         tts_tmp_wav = tts.synth(script, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         print(f"[Journey] music={music_ms}ms, tts={tts_ms}ms, target_words={target_words}, try={tries+1}")

#         if _within(tts_ms, music_ms, tol=0.03) or tries >= max_tries:
#             best_script, best_tts_path = script, tts_tmp_wav
#             break

#         gap_ratio = music_ms / max(1, tts_ms)
#         if tts_ms < music_ms:
#             # add a small continuation based on the remaining gap
#             add_words = int(max(40, min(220, (gap_ratio - 1.0) * 200)))
#             tail = _last_n_words(script, 35)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=add_words)
#             script = (script + " " + clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))).strip()
#             target_words += add_words
#         else:
#             # slightly trim end if we overshoot
#             words = script.split()
#             script = " ".join(words[:-60]) if len(words) > 60 else " ".join(words[:-20])
#             target_words = max(120, int(0.95 * target_words))

#         tries += 1

#     # ================= PHASE 4: Mix to EXACT music length ======================
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)
#     duration_ms_final = mixr.mix(
#         best_tts_path,
#         music_path,
#         out_path,
#         duck_db=-3.0,                # music is quieter than voice after normalization
#         ffmpeg_bin=c.FFMPEG_BIN      # set in .env if not in PATH
#     )

#     # --- Persist session row + full script ---
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = script[:600] + ("..." if len(script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=script,            # full script included in API response
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )

# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out

# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }

# from pathlib import Path
# import os

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..utils.text import finalize_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()

# # ---------- helpers ----------
# def _estimate_target_words(music_ms: int, wps: float = 2.25) -> int:
#     """
#     Estimate spoken word count that should naturally match music length.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))

# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     # tighter match so content "feels" full before micro-retime
#     return abs(ms - target) <= int(target * tol)

# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = txt.strip().split()
#     return " ".join(w[-n:]) if len(w) > n else txt.strip()

# def _word_count(txt: str) -> int:
#     return len(txt.strip().split())

# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     """
#     Ask the model to continue the narration with ~need_more NEW words.
#     We pass a short head (rules/tone) and only a small tail to avoid token bloat.
#     """
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head

#     return (
#         f"{head_short}\n"
#         "Continue the SAME single, second-person spoken narration WITHOUT repeating ideas or sentences.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions. No summaries. Keep cadence natural. End decisively.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )

# # ---------- routes ----------
# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # --- recent history for this user (avoid immediate repeats; remember last voice) ---
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = (
#         q.query(Sessions)
#          .order_by(Sessions.created_at.desc())
#          .limit(20)
#          .all()
#     )
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # --- choose music (prefer day-specific mapping; else mood/schema logic) ---
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)  # may return None if no mapping
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)

#     track_id, music_path, chosen_folder, music_file = ti

#     # --- choose voice (privilege Sevan/Carter; avoid immediate repeat) ---
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # --- determine target words from music duration ---
#     music_seg = load_audio(music_path)
#     music_ms = duration_ms(music_seg)

#     # Natural fit target; capped so we don't ask the model for excessive length
#     target_words = _estimate_target_words(music_ms, wps=2.25)
#     target_words = min(target_words, 1200)

#     # ================= PHASE 1: Base script near target_words =================
#     jdict = x.model_dump()
#     prompt_txt = pr.build(jdict, target_words=target_words)
#     raw_script = llm.generate_text(prompt_txt, c.OPENAI_API_KEY)
#     script = clean_script(raw_script)

#     # ================= PHASE 2: Extend until target is reached =================
#     max_extend_rounds = 2
#     round_i = 0
#     while _word_count(script) < int(0.95 * target_words) and round_i < max_extend_rounds:
#         need = target_words - _word_count(script)
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()
#         round_i += 1

#     # ================= PHASE 3: Minor auto-fit with TTS feedback ===============
#     tries = 0
#     max_tries = 2  # small corrections only; main length handled above

#     best_script = None
#     best_tts_path = None

#     while True:
#         # ensure the script ends on a clean, decisive sentence before TTS
#         script_for_tts = finalize_script(script)

#         tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         print(f"[Journey] music={music_ms}ms, tts={tts_ms}ms, target_words={target_words}, try={tries+1}")

#         if _within(tts_ms, music_ms, tol=0.03) or tries >= max_tries:
#             best_script, best_tts_path = script_for_tts, tts_tmp_wav
#             break

#         gap_ratio = music_ms / max(1, tts_ms)
#         if tts_ms < music_ms:
#             # add a small continuation based on the remaining gap
#             add_words = int(max(40, min(220, (gap_ratio - 1.0) * 200)))
#             tail = _last_n_words(script_for_tts, 35)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=add_words)
#             script = (script_for_tts + " " + clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))).strip()
#             target_words += add_words
#         else:
#             # slightly trim end if we overshoot (words ≈ time)
#             words = script_for_tts.split()
#             script = " ".join(words[:-60]) if len(words) > 60 else " ".join(words[:-20])
#             target_words = max(120, int(0.95 * target_words))

#         tries += 1

#     # ================= PHASE 4: Mix to EXACT music length ======================
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)
#     duration_ms_final = mixr.mix(
#         best_tts_path,
#         music_path,
#         out_path,
#         duck_db=-3.0,                # music is quieter than voice after normalization
#         ffmpeg_bin=c.FFMPEG_BIN      # set in .env if not in PATH
#     )

#     # --- Persist session row + full script ---
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,            # full script included in API response
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )

# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out

# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }



#Best code till now

# from pathlib import Path
# import os

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..utils.text import finalize_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()

# # ---------- helpers ----------
# def _estimate_target_words(music_ms: int, wps: float = 2.25) -> int:
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))

# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     return abs(ms - target) <= int(target * tol)

# def _word_count(txt: str) -> int:
#     return len((txt or "").strip().split())

# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = (txt or "").strip().split()
#     return " ".join(w[-n:]) if len(w) > n else (txt or "").strip()

# def _trim_tail_words_by_count(txt: str, drop_words: int) -> str:
#     """Trim approximately `drop_words` from the end, sentence-safe-ish."""
#     if drop_words <= 0:
#         return txt
#     words = (txt or "").strip().split()
#     if len(words) <= drop_words:
#         return " ".join(words[: max(1, len(words) - 5)])
#     kept = words[: len(words) - drop_words]
#     out = " ".join(kept).strip()
#     return out

# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
#     return (
#         f"{head_short}\n"
#         "Continue the SAME single, second-person spoken narration WITHOUT repeating ideas or sentences.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions. No summaries. Keep cadence natural. End decisively.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )

# # ---------- routes ----------
# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # recent history (avoid repeats; remember last voice)
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # music + voice
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)
#     track_id, music_path, chosen_folder, music_file = ti
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     music_ms = duration_ms(load_audio(music_path))

#     # base target (capped to keep prompts manageable)
#     target_words = min(_estimate_target_words(music_ms, wps=2.25), 1200)

#     # PHASE 1: base script
#     jdict = x.model_dump()
#     prompt_txt = pr.build(jdict, target_words=target_words)
#     script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

#     # PHASE 2: if too short, extend once or twice to get near target
#     max_extend_rounds = 2
#     round_i = 0
#     while _word_count(script) < int(0.95 * target_words) and round_i < max_extend_rounds:
#         need = target_words - _word_count(script)
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()
#         round_i += 1

#     # PHASE 3: adaptive, time-aware correction with smoothed WPS
#     max_corrections = 4
#     attempt = 0
#     best_script = script
#     best_tts_path = None
#     ema_wps = 2.25  # start with prior; update from observed

#     while True:
#         script_for_tts = finalize_script(best_script)

#         tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         wc = _word_count(script_for_tts)
#         observed_wps = wc / max(1.0, tts_ms / 1000.0)
#         # Smooth to reduce oscillation from voice/style variability
#         ema_wps = 0.7 * ema_wps + 0.3 * observed_wps

#         print(f"[Journey] music={music_ms}ms, tts={tts_ms}ms, words={wc}, wps_obs={observed_wps:.2f}, wps_ema={ema_wps:.2f}, try={attempt+1}")

#         if _within(tts_ms, music_ms, tol=0.03) or attempt >= max_corrections:
#             best_script, best_tts_path = script_for_tts, tts_tmp_wav
#             break

#         delta_ms = music_ms - tts_ms
#         # Convert gap in time to gap in words using smoothed WPS
#         delta_words = int(abs(delta_ms) / 1000.0 * ema_wps)

#         # Clamp to avoid overreaction
#         delta_words = max(30, min(delta_words, 200))

#         if delta_ms > 0:
#             # Too short → extend by delta_words
#             tail = _last_n_words(script_for_tts, 40)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=delta_words)
#             addition = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#             if addition:
#                 best_script = (script_for_tts + " " + addition).strip()
#         else:
#             # Too long → trim roughly delta_words from the tail
#             trimmed = _trim_tail_words_by_count(script_for_tts, delta_words)
#             best_script = trimmed

#         attempt += 1

#     # PHASE 4: mix to EXACT music length (pitch-preserving retime)
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)
#     duration_ms_final = mixr.mix(
#         best_tts_path,
#         music_path,
#         out_path,
#         duck_db=10.0, # was previously -1.0
#         sync_mode="retime_voice_to_music", # guarantees music length = narration length,
#         ffmpeg_bin=c.FFMPEG_BIN
#     )

#     # persist + respond
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )

# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out

# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }

# from pathlib import Path
# import os
# import tempfile

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from pydub import AudioSegment

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..utils.text import finalize_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# MUSIC_INTRO_MS = 6000  # ~6s music-only intro before voice comes in


# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()


# # ---------- helpers ----------
# def _estimate_target_words(music_ms: int, wps: float = 2.0) -> int:
#     """
#     Estimate target word count for the SPOKEN portion only.
#     We assume a slightly slower average WPS to keep delivery clear.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))


# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     return abs(ms - target) <= int(target * tol)


# def _word_count(txt: str) -> int:
#     return len((txt or "").strip().split())


# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = (txt or "").strip().split()
#     return " ".join(w[-n:]) if len(w) > n else (txt or "").strip()


# def _trim_tail_words_by_count(txt: str, drop_words: int) -> str:
#     """Trim approximately `drop_words` from the end, sentence-safe-ish."""
#     if drop_words <= 0:
#         return txt
#     words = (txt or "").strip().split()
#     if len(words) <= drop_words:
#         return " ".join(words[: max(1, len(words) - 5)])
#     kept = words[: len(words) - drop_words]
#     out = " ".join(kept).strip()
#     return out


# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
#     return (
#         f"{head_short}\n"
#         "Continue the SAME single, second-person spoken narration WITHOUT repeating ideas or sentences.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions except the literal token [pause] where a slightly longer silence makes sense.\n"
#         "No summaries. Keep cadence natural. End decisively.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )


# # ---------- routes ----------
# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # recent history (avoid repeats; remember last voice)
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # music + voice
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)
#     track_id, music_path, chosen_folder, music_file = ti
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     music_ms = duration_ms(load_audio(music_path))

#     # We reserve MUSIC_INTRO_MS for a music-only intro.
#     # Spoken portion target is therefore slightly shorter than full music.
#     spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
#     target_words = min(_estimate_target_words(spoken_target_ms, wps=2.0), 1200)

#     # PHASE 1: base script
#     jdict = x.model_dump()
#     # pass high-level timing hints into the prompt (not strict, but helps structure)
#     jdict["music_ms"] = music_ms
#     jdict["spoken_target_ms"] = spoken_target_ms
#     jdict["intro_ms"] = MUSIC_INTRO_MS

#     prompt_txt = pr.build(jdict, target_words=target_words)
#     script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

#     # PHASE 2: if too short, extend once or twice to get near target
#     max_extend_rounds = 2
#     round_i = 0
#     while _word_count(script) < int(0.95 * target_words) and round_i < max_extend_rounds:
#         need = target_words - _word_count(script)
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()
#         round_i += 1

#     # PHASE 3: adaptive, time-aware correction with smoothed WPS
#     max_corrections = 4
#     attempt = 0
#     best_script = script
#     best_tts_path = None
#     ema_wps = 2.0  # start slightly slower; update from observed

#     while True:
#         script_for_tts = finalize_script(best_script)

#         tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         wc = _word_count(script_for_tts)
#         observed_wps = wc / max(1.0, tts_ms / 1000.0)
#         # Smooth to reduce oscillation from voice/style variability
#         ema_wps = 0.7 * ema_wps + 0.3 * observed_wps

#         print(
#             f"[Journey] music={music_ms}ms, spoken_target={spoken_target_ms}ms, "
#             f"tts={tts_ms}ms, words={wc}, wps_obs={observed_wps:.2f}, "
#             f"wps_ema={ema_wps:.2f}, try={attempt+1}"
#         )

#         if _within(tts_ms, spoken_target_ms, tol=0.04) or attempt >= max_corrections:
#             best_script, best_tts_path = script_for_tts, tts_tmp_wav
#             break

#         delta_ms = spoken_target_ms - tts_ms
#         # Convert gap in time to gap in words using smoothed WPS
#         delta_words = int(abs(delta_ms) / 1000.0 * ema_wps)

#         # Clamp to avoid overreaction
#         delta_words = max(30, min(delta_words, 200))

#         if delta_ms > 0:
#             # Too short → extend by delta_words
#             tail = _last_n_words(script_for_tts, 40)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=delta_words)
#             addition = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#             if addition:
#                 best_script = (script_for_tts + " " + addition).strip()
#         else:
#             # Too long → trim roughly delta_words from the tail
#             trimmed = _trim_tail_words_by_count(script_for_tts, delta_words)
#             best_script = trimmed

#         attempt += 1

#     # PHASE 4: build VO with a music-only intro, then mix to EXACT music length
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)

#     # prepend silence to create the intro Felix wants
#     raw_voice = load_audio(best_tts_path).set_frame_rate(44100).set_channels(2)
#     intro = AudioSegment.silent(duration=MUSIC_INTRO_MS, frame_rate=raw_voice.frame_rate)
#     voice_with_intro = intro + raw_voice

#     tmp_vo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     voice_with_intro.export(tmp_vo.name, format="wav")
#     voice_for_mix = tmp_vo.name

#     duration_ms_final = mixr.mix(
#         voice_for_mix,
#         music_path,
#         out_path,
#         duck_db=10.0,
#         sync_mode="retime_voice_to_music",
#         ffmpeg_bin=c.FFMPEG_BIN,
#     )

#     # persist + respond
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )


# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out


# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }

# from pathlib import Path
# import os
# import tempfile

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from pydub import AudioSegment

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..utils.text import finalize_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# MUSIC_INTRO_MS = 6000  # ~6s music-only intro before voice comes in


# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()


# # ---------- helpers ----------

# def _estimate_target_words(music_ms: int, wps: float = 2.0) -> int:
#     """
#     Estimate target word count for the SPOKEN portion only.
#     We assume a slightly slower average WPS to keep delivery clear.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))


# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     return abs(ms - target) <= int(target * tol)


# def _word_count(txt: str) -> int:
#     return len((txt or "").strip().split())


# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = (txt or "").strip().split()
#     return " ".join(w[-n:]) if len(w) > n else (txt or "").strip()


# def _trim_tail_words_by_count(txt: str, drop_words: int) -> str:
#     """Trim approximately `drop_words` from the end, sentence-safe-ish."""
#     if drop_words <= 0:
#         return txt
#     words = (txt or "").strip().split()
#     if len(words) <= drop_words:
#         return " ".join(words[: max(1, len(words) - 5)])
#     kept = words[: len(words) - drop_words]
#     out = " ".join(kept).strip()
#     return out


# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
#     return (
#         f"{head_short}\n"
#         "Continue the SAME single spoken narration, matching the same reflective voice and style, "
#         "WITHOUT repeating ideas or sentences.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions except the literal token [pause] where a slightly longer silence makes sense.\n"
#         "No summaries. Keep cadence natural. End decisively.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )


# # ---------- routes ----------

# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # recent history (avoid repeats; remember last voice)
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # music + voice selection
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)
#     track_id, music_path, chosen_folder, music_file = ti
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # base music timing
#     music_ms = duration_ms(load_audio(music_path))

#     # approximate drop analysis to inform the script pacing
#     drop_ms = None
#     try:
#         analysis = mixr.analyze_music(music_path)
#         drop_ms = analysis.get("drop_ms")
#     except Exception:
#         drop_ms = None

#     # We reserve MUSIC_INTRO_MS for a music-only intro.
#     # Spoken portion target is therefore slightly shorter than full music.
#     spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
#     target_words = min(_estimate_target_words(spoken_target_ms, wps=2.0), 1200)

#     # PHASE 1: base script
#     jdict = x.model_dump()
#     # pass high-level timing hints into the prompt (not strict, but helps structure)
#     jdict["music_ms"] = music_ms
#     jdict["spoken_target_ms"] = spoken_target_ms
#     jdict["intro_ms"] = MUSIC_INTRO_MS
#     jdict["drop_ms"] = drop_ms

#     prompt_txt = pr.build(jdict, target_words=target_words)
#     script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

#     # PHASE 2: if too short, extend once or twice to get near target
#     max_extend_rounds = 2
#     round_i = 0
#     while _word_count(script) < int(0.95 * target_words) and round_i < max_extend_rounds:
#         need = target_words - _word_count(script)
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()
#         round_i += 1

#     # PHASE 3: adaptive, time-aware correction with smoothed WPS
#     max_corrections = 4
#     attempt = 0
#     best_script = script
#     best_tts_path = None
#     ema_wps = 2.0  # start slightly slower; update from observed

#     while True:
#         script_for_tts = finalize_script(best_script)

#         tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         wc = _word_count(script_for_tts)
#         observed_wps = wc / max(1.0, tts_ms / 1000.0)
#         # Smooth to reduce oscillation from voice/style variability
#         ema_wps = 0.7 * ema_wps + 0.3 * observed_wps

#         print(
#             f"[Journey] music={music_ms}ms, spoken_target={spoken_target_ms}ms, "
#             f"tts={tts_ms}ms, words={wc}, wps_obs={observed_wps:.2f}, "
#             f"wps_ema={ema_wps:.2f}, try={attempt+1}"
#         )

#         if _within(tts_ms, spoken_target_ms, tol=0.04) or attempt >= max_corrections:
#             best_script, best_tts_path = script_for_tts, tts_tmp_wav
#             break

#         delta_ms = spoken_target_ms - tts_ms
#         # Convert gap in time to gap in words using smoothed WPS
#         delta_words = int(abs(delta_ms) / 1000.0 * ema_wps)

#         # Clamp to avoid overreaction
#         delta_words = max(30, min(delta_words, 200))

#         if delta_ms > 0:
#             # Too short → extend by delta_words
#             tail = _last_n_words(script_for_tts, 40)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=delta_words)
#             addition = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#             if addition:
#                 best_script = (script_for_tts + " " + addition).strip()
#         else:
#             # Too long → trim roughly delta_words from the tail
#             trimmed = _trim_tail_words_by_count(script_for_tts, delta_words)
#             best_script = trimmed

#         attempt += 1

#     # PHASE 4: build VO with a music-only intro, then mix to EXACT music length
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)

#     # prepend silence to create the intro Felix wants
#     raw_voice = load_audio(best_tts_path).set_frame_rate(44100).set_channels(2)
#     intro = AudioSegment.silent(duration=MUSIC_INTRO_MS, frame_rate=raw_voice.frame_rate)
#     voice_with_intro = intro + raw_voice

#     tmp_vo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     voice_with_intro.export(tmp_vo.name, format="wav")
#     voice_for_mix = tmp_vo.name

#     duration_ms_final = mixr.mix(
#         voice_for_mix,
#         music_path,
#         out_path,
#         duck_db=10.0,
#         sync_mode="retime_voice_to_music",
#         ffmpeg_bin=c.FFMPEG_BIN,
#     )

#     # persist + respond
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )


# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out


# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }


# from pathlib import Path
# import os
# import tempfile

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from pydub import AudioSegment

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..utils.text import finalize_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# MUSIC_INTRO_MS = 6000   # ~6s music-only intro before voice comes in
# TAIL_MARGIN_MS = 1500   # keep ~1.5s of music-only tail after VO ends


# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()


# # ---------- helpers ----------

# def _estimate_target_words(music_ms: int, wps: float = 2.0) -> int:
#     """
#     Estimate target word count for the SPOKEN portion only.
#     We assume a slightly slower average WPS to keep delivery clear.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))


# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     return abs(ms - target) <= int(target * tol)


# def _word_count(txt: str) -> int:
#     return len((txt or "").strip().split())


# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = (txt or "").strip().split()
#     return " ".join(w[-n:]) if len(w) > n else (txt or "").strip()


# def _trim_tail_words_by_count(txt: str, drop_words: int) -> str:
#     """Trim approximately `drop_words` from the end, sentence-safe-ish."""
#     if drop_words <= 0:
#         return txt
#     words = (txt or "").strip().split()
#     if len(words) <= drop_words:
#         return " ".join(words[: max(1, len(words) - 5)])
#     kept = words[: len(words) - drop_words]
#     out = " ".join(kept).strip()
#     return out


# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
#     return (
#         f"{head_short}\n"
#         "Continue the SAME single spoken narration, matching the same reflective voice and style, "
#         "WITHOUT repeating ideas or sentences.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions except the literal token [pause] where a slightly longer silence makes sense.\n"
#         "No summaries. Keep cadence natural. End decisively.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )


# # ---------- routes ----------

# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # recent history (avoid repeats; remember last voice)
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # music + voice selection
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)
#     track_id, music_path, chosen_folder, music_file = ti
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # base music timing
#     music_ms = duration_ms(load_audio(music_path))

#     # We reserve MUSIC_INTRO_MS for a music-only intro.
#     # Spoken portion target is therefore shorter than full music.
#     spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
#     target_words = min(_estimate_target_words(spoken_target_ms, wps=2.0), 1200)

#     # PHASE 1: base script
#     jdict = x.model_dump()
#     # pass high-level timing hints into the prompt (not strict, but helps structure)
#     jdict["music_ms"] = music_ms
#     jdict["spoken_target_ms"] = spoken_target_ms
#     jdict["intro_ms"] = MUSIC_INTRO_MS

#     prompt_txt = pr.build(jdict, target_words=target_words)
#     script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

#     # PHASE 2: if too short, extend once or twice to get near target
#     max_extend_rounds = 2
#     round_i = 0
#     while _word_count(script) < int(0.95 * target_words) and round_i < max_extend_rounds:
#         need = target_words - _word_count(script)
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()
#         round_i += 1

#     # PHASE 3: adaptive, time-aware correction with smoothed WPS
#     max_corrections = 4
#     attempt = 0
#     best_script = script
#     best_tts_path = None
#     ema_wps = 2.0  # start slightly slower; update from observed

#     while True:
#         script_for_tts = finalize_script(best_script)

#         tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         wc = _word_count(script_for_tts)
#         observed_wps = wc / max(1.0, tts_ms / 1000.0)
#         # Smooth to reduce oscillation from voice/style variability
#         ema_wps = 0.7 * ema_wps + 0.3 * observed_wps

#         print(
#             f"[Journey] music={music_ms}ms, spoken_target={spoken_target_ms}ms, "
#             f"tts={tts_ms}ms, words={wc}, wps_obs={observed_wps:.2f}, "
#             f"wps_ema={ema_wps:.2f}, try={attempt+1}"
#         )

#         if _within(tts_ms, spoken_target_ms, tol=0.04) or attempt >= max_corrections:
#             best_script, best_tts_path = script_for_tts, tts_tmp_wav
#             break

#         delta_ms = spoken_target_ms - tts_ms
#         # Convert gap in time to gap in words using smoothed WPS
#         delta_words = int(abs(delta_ms) / 1000.0 * ema_wps)

#         # Clamp to avoid overreaction
#         delta_words = max(30, min(delta_words, 200))

#         if delta_ms > 0:
#             # Too short → extend by delta_words
#             tail = _last_n_words(script_for_tts, 40)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=delta_words)
#             addition = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#             if addition:
#                 best_script = (script_for_tts + " " + addition).strip()
#         else:
#             # Too long → trim roughly delta_words from the tail
#             trimmed = _trim_tail_words_by_count(script_for_tts, delta_words)
#             best_script = trimmed

#         attempt += 1

#     # PHASE 4: build VO with a music-only intro, then mix
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)

#     # Load final TTS and enforce "voice ends before music" with a small music-only tail.
#     raw_voice = load_audio(best_tts_path).set_frame_rate(44100).set_channels(2)

#     # Max allowed spoken duration inside the track (leave some tail for music-only)
#     max_spoken_ms = max(
#         1000,
#         music_ms - MUSIC_INTRO_MS - TAIL_MARGIN_MS,
#     )
#     if max_spoken_ms < 1000:
#         max_spoken_ms = 1000

#     if len(raw_voice) > max_spoken_ms:
#         raw_voice = raw_voice[:max_spoken_ms]

#     # prepend silence to create the intro Felix wants
#     intro = AudioSegment.silent(duration=MUSIC_INTRO_MS, frame_rate=raw_voice.frame_rate)
#     voice_with_intro = intro + raw_voice

#     tmp_vo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     voice_with_intro.export(tmp_vo.name, format="wav")
#     voice_for_mix = tmp_vo.name

#     # IMPORTANT: don't retime voice to full music length, so we can keep a music-only outro
#     duration_ms_final = mixr.mix(
#         voice_for_mix,
#         music_path,
#         out_path,
#         duck_db=10.0,
#         sync_mode="no_retime_trim_pad",
#         ffmpeg_bin=c.FFMPEG_BIN,
#     )

#     # persist + respond
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )


# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out


# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }



# #------------------------------------------------------------------------------------------------
# # THE BEST CODE
# from pathlib import Path
# import os
# import re
# import tempfile

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from pydub import AudioSegment

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..utils.text import finalize_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# MUSIC_INTRO_MS = 6000   # ~6s music-only intro before voice comes in
# TAIL_MARGIN_MS = 1500   # keep ~1.5s of music-only tail after VO ends


# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()


# # ---------- helpers ----------

# def _estimate_target_words(music_ms: int, wps: float = 2.0) -> int:
#     """
#     Estimate target word count for the SPOKEN portion only.
#     We assume a slightly slower average WPS to keep delivery clear.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))


# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     return abs(ms - target) <= int(target * tol)


# def _word_count(txt: str) -> int:
#     return len((txt or "").strip().split())


# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = (txt or "").strip().split()
#     return " ".join(w[-n:]) if len(w) > n else (txt or "").strip()


# def _sentence_safe(text: str) -> str:
#     """
#     Make sure the text ends at a sentence boundary if possible.
#     If no '.', '!' or '?' exists, returns the text as-is.
#     """
#     text = (text or "").strip()
#     if not text:
#         return text

#     last_dot = text.rfind(".")
#     last_ex = text.rfind("!")
#     last_q = text.rfind("?")
#     last_punct = max(last_dot, last_ex, last_q)

#     if last_punct != -1:
#         return text[: last_punct + 1].strip()
#     return text


# def _trim_tail_words_by_count(txt: str, drop_words: int) -> str:
#     """
#     Trim approximately `drop_words` from the end, then snap to a clean sentence.
#     This avoids ugly endings like 'There are whispers of'.
#     """
#     if drop_words <= 0:
#         return (txt or "").strip()

#     words = (txt or "").strip().split()
#     if not words:
#         return ""

#     if len(words) <= drop_words:
#         # keep at least a tiny tail, then sentence-safe it
#         base = " ".join(words[: max(1, len(words) - 5)])
#         out = _sentence_safe(base)
#         if not out.endswith((".", "!", "?")):
#             out = out.rstrip() + "."
#         return out

#     kept = words[: len(words) - drop_words]
#     base = " ".join(kept).strip()
#     out = _sentence_safe(base)
#     if not out.endswith((".", "!", "?")):
#         out = out.rstrip() + "."
#     return out


# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
#     return (
#         f"{head_short}\n"
#         "Continue the SAME single spoken narration, matching the same reflective voice and style, "
#         "WITHOUT repeating ideas or sentences.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions except the literal token [pause] where a slightly longer silence makes sense.\n"
#         "No summaries. Keep cadence natural. End decisively.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )


# def _trim_script_to_ratio(txt: str, ratio: float) -> str:
#     """
#     When we truncate the VO audio to fit inside the music, trim the script
#     to roughly the same proportion and make sure it ends on a clean line.
#     """
#     txt = (txt or "").strip()
#     if not txt or ratio >= 0.999:
#         # nothing to do
#         return _sentence_safe(txt)

#     words = txt.split()
#     if not words:
#         return ""

#     # proportional keep, with a bit of safety margin
#     keep = int(len(words) * ratio) - 3
#     keep = max(30, min(keep, len(words)))  # keep at least some content

#     trimmed = " ".join(words[:keep]).strip()
#     trimmed = _sentence_safe(trimmed)

#     if not trimmed.endswith((".", "!", "?")):
#         trimmed = trimmed.rstrip() + "."

#     return trimmed


# # ---------- routes ----------

# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # recent history (avoid repeats; remember last voice)
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # music + voice selection
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)
#     track_id, music_path, chosen_folder, music_file = ti
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # base music timing
#     music_ms = duration_ms(load_audio(music_path))

#     # Spoken portion target is shorter than full music (intro + tail).
#     spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
#     target_words = min(_estimate_target_words(spoken_target_ms, wps=2.0), 1200)

#     # PHASE 1: base script
#     jdict = x.model_dump()
#     jdict["music_ms"] = music_ms
#     jdict["spoken_target_ms"] = spoken_target_ms
#     jdict["intro_ms"] = MUSIC_INTRO_MS

#     prompt_txt = pr.build(jdict, target_words=target_words)
#     script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

#     # PHASE 2: if too short, extend once or twice to get near target
#     max_extend_rounds = 2
#     round_i = 0
#     while _word_count(script) < int(0.95 * target_words) and round_i < max_extend_rounds:
#         need = target_words - _word_count(script)
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()
#         round_i += 1

#     # PHASE 3: adaptive, time-aware correction with smoothed WPS
#     max_corrections = 4
#     attempt = 0
#     best_script = script
#     best_tts_path = None
#     ema_wps = 2.0  # start slightly slower; update from observed

#     while True:
#         script_for_tts = finalize_script(best_script)

#         tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         wc = _word_count(script_for_tts)
#         observed_wps = wc / max(1.0, tts_ms / 1000.0)
#         ema_wps = 0.7 * ema_wps + 0.3 * observed_wps

#         print(
#             f"[Journey] music={music_ms}ms, spoken_target={spoken_target_ms}ms, "
#             f"tts={tts_ms}ms, words={wc}, wps_obs={observed_wps:.2f}, "
#             f"wps_ema={ema_wps:.2f}, try={attempt+1}"
#         )

#         if _within(tts_ms, spoken_target_ms, tol=0.04) or attempt >= max_corrections:
#             best_script, best_tts_path = script_for_tts, tts_tmp_wav
#             break

#         delta_ms = spoken_target_ms - tts_ms
#         delta_words = int(abs(delta_ms) / 1000.0 * ema_wps)
#         delta_words = max(30, min(delta_words, 200))

#         if delta_ms > 0:
#             # Too short → extend
#             tail = _last_n_words(script_for_tts, 40)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=delta_words)
#             addition = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#             if addition:
#                 best_script = (script_for_tts + " " + addition).strip()
#         else:
#             # Too long → trim tail
#             trimmed = _trim_tail_words_by_count(script_for_tts, delta_words)
#             best_script = trimmed

#         attempt += 1

#     # PHASE 4: build VO with a music-only intro, then mix
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)

#     # Load final TTS and enforce "voice ends before music" with a small music-only tail.
#     raw_voice = load_audio(best_tts_path).set_frame_rate(44100).set_channels(2)

#     # Max allowed spoken duration inside the track (leave some tail for music-only)
#     max_spoken_ms = max(
#         1000,
#         music_ms - MUSIC_INTRO_MS - TAIL_MARGIN_MS,
#     )
#     if max_spoken_ms < 1000:
#         max_spoken_ms = 1000

#     original_voice_ms = len(raw_voice)

#     if original_voice_ms > max_spoken_ms:
#         # Trim the audio AND trim the script proportionally, so
#         # script_text actually matches what you hear.
#         ratio = max_spoken_ms / float(original_voice_ms)
#         raw_voice = raw_voice[:max_spoken_ms]
#         best_script = _trim_script_to_ratio(best_script, ratio)
#     else:
#         # Still snap ending to a clean sentence so it doesn't sound cut
#         best_script = _sentence_safe(best_script)
#         if not best_script.endswith((".", "!", "?")):
#             best_script = best_script.rstrip() + "."

#     # prepend silence to create the intro Felix wants
#     intro = AudioSegment.silent(duration=MUSIC_INTRO_MS, frame_rate=raw_voice.frame_rate)
#     voice_with_intro = intro + raw_voice

#     tmp_vo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     voice_with_intro.export(tmp_vo.name, format="wav")
#     voice_for_mix = tmp_vo.name

#     # IMPORTANT: don't retime voice to full music length, so we can keep a music-only outro
#     duration_ms_final = mixr.mix(
#         voice_for_mix,
#         music_path,
#         out_path,
#         duck_db=10.0,
#         sync_mode="no_retime_trim_pad",
#         ffmpeg_bin=c.FFMPEG_BIN,
#     )

#     # persist + respond
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )


# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out


# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }
# --------------------------------------------------------------------------------------------
# from pathlib import Path
# import os
# import re
# import tempfile

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from pydub import AudioSegment

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..utils.text import finalize_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# MUSIC_INTRO_MS = 6000   # ~6s music-only intro before voice comes in
# TAIL_MARGIN_MS = 1500   # keep ~1.5s of music-only tail after VO ends


# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()


# # ---------- helpers ----------

# def _estimate_target_words(music_ms: int, wps: float = 1.7) -> int:
#     """
#     Estimate target word count for the SPOKEN portion only.
#     We assume a slightly slower average WPS to keep delivery clear and less dense.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))


# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     return abs(ms - target) <= int(target * tol)


# def _word_count(txt: str) -> int:
#     return len((txt or "").strip().split())


# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = (txt or "").strip().split()
#     return " ".join(w[-n:]) if len(w) > n else (txt or "").strip()


# def _sentence_safe(text: str) -> str:
#     """
#     Make sure the text ends at a sentence boundary if possible.
#     If no '.', '!' or '?' exists, returns the text as-is.
#     """
#     text = (text or "").strip()
#     if not text:
#         return text

#     last_dot = text.rfind(".")
#     last_ex = text.rfind("!")
#     last_q = text.rfind("?")
#     last_punct = max(last_dot, last_ex, last_q)

#     if last_punct != -1:
#         return text[: last_punct + 1].strip()
#     return text


# def _trim_tail_words_by_count(txt: str, drop_words: int) -> str:
#     """
#     Trim approximately `drop_words` from the end, then snap to a clean sentence.
#     This avoids ugly endings like 'There are whispers of'.
#     """
#     if drop_words <= 0:
#         return (txt or "").strip()

#     words = (txt or "").strip().split()
#     if not words:
#         return ""

#     if len(words) <= drop_words:
#         # keep at least a tiny tail, then sentence-safe it
#         base = " ".join(words[: max(1, len(words) - 5)])
#         out = _sentence_safe(base)
#         if not out.endswith((".", "!", "?")):
#             out = out.rstrip() + "."
#         return out

#     kept = words[: len(words) - drop_words]
#     base = " ".join(kept).strip()
#     out = _sentence_safe(base)
#     if not out.endswith((".", "!", "?")):
#         out = out.rstrip() + "."
#     return out


# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     """
#     Build a continuation prompt that strictly enforces:
#     - same unnamed character
#     - same day and setting
#     - no second story or restart.
#     """
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
#     return (
#         f"{head_short}\n"
#         "Continue the SAME single spoken narration about the SAME unnamed person, "
#         "in the SAME day and setting.\n"
#         "Do NOT restart the story, do NOT introduce a new character name, "
#         "and do NOT describe a new morning, a new apartment, or a second beginning.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions except the literal token [pause] where a slightly longer silence makes sense.\n"
#         "No summaries. Keep cadence natural. End decisively with a clear emotional landing.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )


# def _trim_script_to_ratio(txt: str, ratio: float) -> str:
#     """
#     When we truncate the VO audio to fit inside the music, trim the script
#     to roughly the same proportion and make sure it ends on a clean line.
#     """
#     txt = (txt or "").strip()
#     if not txt or ratio >= 0.999:
#         # nothing to do
#         return _sentence_safe(txt)

#     words = txt.split()
#     if not words:
#         return ""

#     # proportional keep, with a bit of safety margin
#     keep = int(len(words) * ratio) - 3
#     keep = max(30, min(keep, len(words)))  # keep at least some content

#     trimmed = " ".join(words[:keep]).strip()
#     trimmed = _sentence_safe(trimmed)

#     if not trimmed.endswith((".", "!", "?")):
#         trimmed = trimmed.rstrip() + "."

#     return trimmed


# # ---------- routes ----------

# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # recent history (avoid repeats; remember last voice)
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # music + voice selection
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)
#     track_id, music_path, chosen_folder, music_file = ti
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # base music timing
#     music_ms = duration_ms(load_audio(music_path))

#     # Spoken portion target is shorter than full music (intro + tail).
#     spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
#     # Use a slightly slower assumed WPS so we don't over-fill the track with words
#     target_words = min(_estimate_target_words(spoken_target_ms, wps=1.7), 1200)

#     # PHASE 1: base script
#     jdict = x.model_dump()
#     jdict["music_ms"] = music_ms
#     jdict["spoken_target_ms"] = spoken_target_ms
#     jdict["intro_ms"] = MUSIC_INTRO_MS

#     prompt_txt = pr.build(jdict, target_words=target_words)
#     script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

#     # PHASE 2: if too short, extend at most once to get near target
#     max_extend_rounds = 1
#     round_i = 0
#     while _word_count(script) < int(0.9 * target_words) and round_i < max_extend_rounds:
#         need = target_words - _word_count(script)
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()
#         round_i += 1

#     # PHASE 3: adaptive, time-aware correction with smoothed WPS
#     max_corrections = 4
#     attempt = 0
#     best_script = script
#     best_tts_path = None
#     ema_wps = 2.0  # start slightly slower; update from observed

#     while True:
#         script_for_tts = finalize_script(best_script)

#         tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         wc = _word_count(script_for_tts)
#         observed_wps = wc / max(1.0, tts_ms / 1000.0)
#         ema_wps = 0.7 * ema_wps + 0.3 * observed_wps

#         print(
#             f"[Journey] music={music_ms}ms, spoken_target={spoken_target_ms}ms, "
#             f"tts={tts_ms}ms, words={wc}, wps_obs={observed_wps:.2f}, "
#             f"wps_ema={ema_wps:.2f}, try={attempt+1}"
#         )

#         if _within(tts_ms, spoken_target_ms, tol=0.04) or attempt >= max_corrections:
#             best_script, best_tts_path = script_for_tts, tts_tmp_wav
#             break

#         delta_ms = spoken_target_ms - tts_ms
#         delta_words = int(abs(delta_ms) / 1000.0 * ema_wps)
#         delta_words = max(30, min(delta_words, 200))

#         if delta_ms > 0:
#             # Too short → extend
#             tail = _last_n_words(script_for_tts, 40)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=delta_words)
#             addition = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#             if addition:
#                 best_script = (script_for_tts + " " + addition).strip()
#         else:
#             # Too long → trim tail
#             trimmed = _trim_tail_words_by_count(script_for_tts, delta_words)
#             best_script = trimmed

#         attempt += 1

#     # PHASE 4: build VO with a music-only intro, then mix
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)

#     # Load final TTS and enforce "voice ends before music" with a small music-only tail.
#     raw_voice = load_audio(best_tts_path).set_frame_rate(44100).set_channels(2)

#     # Max allowed spoken duration inside the track (leave some tail for music-only)
#     max_spoken_ms = max(
#         1000,
#         music_ms - MUSIC_INTRO_MS - TAIL_MARGIN_MS,
#     )
#     if max_spoken_ms < 1000:
#         max_spoken_ms = 1000

#     original_voice_ms = len(raw_voice)

#     if original_voice_ms > max_spoken_ms:
#         # Trim the audio AND trim the script proportionally, so
#         # script_text actually matches what you hear.
#         ratio = max_spoken_ms / float(original_voice_ms)
#         raw_voice = raw_voice[:max_spoken_ms]
#         best_script = _trim_script_to_ratio(best_script, ratio)
#     else:
#         # Still snap ending to a clean sentence so it doesn't sound cut
#         best_script = _sentence_safe(best_script)
#         if not best_script.endswith((".", "!", "?")):
#             best_script = best_script.rstrip() + "."

#     # prepend silence to create the intro Felix wants
#     intro = AudioSegment.silent(duration=MUSIC_INTRO_MS, frame_rate=raw_voice.frame_rate)
#     voice_with_intro = intro + raw_voice

#     tmp_vo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     voice_with_intro.export(tmp_vo.name, format="wav")
#     voice_for_mix = tmp_vo.name

#     # IMPORTANT: don't retime voice to full music length, so we can keep a music-only outro
#     duration_ms_final = mixr.mix(
#         voice_for_mix,
#         music_path,
#         out_path,
#         duck_db=10.0,
#         sync_mode="no_retime_trim_pad",
#         ffmpeg_bin=c.FFMPEG_BIN,
#     )

#     # persist + respond
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )


# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out


# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }




# from pathlib import Path
# import os
# import re
# import tempfile

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from pydub import AudioSegment

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..utils.text import finalize_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# MUSIC_INTRO_MS = 6000   # ~6s music-only intro before voice comes in
# TAIL_MARGIN_MS = 1500   # keep ~1.5s of music-only tail after VO ends


# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()


# # ---------- helpers ----------

# def _estimate_target_words(music_ms: int, wps: float = 1.7) -> int:
#     """
#     Estimate target word count for the SPOKEN portion only.
#     We assume a slightly slower average WPS to keep delivery clear and less dense.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))


# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     return abs(ms - target) <= int(target * tol)


# def _word_count(txt: str) -> int:
#     return len((txt or "").strip().split())


# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = (txt or "").strip().split()
#     return " ".join(w[-n:]) if len(w) > n else (txt or "").strip()


# def _sentence_safe(text: str) -> str:
#     """
#     Make sure the text ends at a sentence boundary if possible.
#     If no '.', '!' or '?' exists, returns the text as-is.
#     """
#     text = (text or "").strip()
#     if not text:
#         return text

#     last_dot = text.rfind(".")
#     last_ex = text.rfind("!")
#     last_q = text.rfind("?")
#     last_punct = max(last_dot, last_ex, last_q)

#     if last_punct != -1:
#         return text[: last_punct + 1].strip()
#     return text


# def _trim_tail_words_by_count(txt: str, drop_words: int) -> str:
#     """
#     Trim approximately `drop_words` from the end, then snap to a clean sentence.
#     This avoids ugly endings like 'There are whispers of'.
#     """
#     if drop_words <= 0:
#         return (txt or "").strip()

#     words = (txt or "").strip().split()
#     if not words:
#         return ""

#     if len(words) <= drop_words:
#         # keep at least a tiny tail, then sentence-safe it
#         base = " ".join(words[: max(1, len(words) - 5)])
#         out = _sentence_safe(base)
#         if not out.endswith((".", "!", "?")):
#             out = out.rstrip() + "."
#         return out

#     kept = words[: len(words) - drop_words]
#     base = " ".join(kept).strip()
#     out = _sentence_safe(base)
#     if not out.endswith((".", "!", "?")):
#         out = out.rstrip() + "."
#     return out


# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     """
#     Build a continuation prompt that strictly enforces:
#     - same unnamed character
#     - same day and setting
#     - no second story or restart.
#     We reuse the same emotional arc by passing arc_name through base_json.
#     """
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
#     return (
#         f"{head_short}\n"
#         "Continue the SAME single spoken narration about the SAME unnamed person, "
#         "in the SAME day and setting.\n"
#         "Do NOT restart the story, do NOT introduce a new character name, "
#         "and do NOT describe a new morning, a new apartment, or a second beginning.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions except the literal token [pause] where a slightly longer silence makes sense.\n"
#         "No summaries. Keep cadence natural. End decisively with a clear emotional landing.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )


# def _trim_script_to_ratio(txt: str, ratio: float) -> str:
#     """
#     When we truncate the VO audio to fit inside the music, trim the script
#     to roughly the same proportion and make sure it ends on a clean line.
#     """
#     txt = (txt or "").strip()
#     if not txt or ratio >= 0.999:
#         # nothing to do
#         return _sentence_safe(txt)

#     words = txt.split()
#     if not words:
#         return ""

#     # proportional keep, with a bit of safety margin
#     keep = int(len(words) * ratio) - 3
#     keep = max(30, min(keep, len(words)))  # keep at least some content

#     trimmed = " ".join(words[:keep]).strip()
#     trimmed = _sentence_safe(trimmed)

#     if not trimmed.endswith((".", "!", "?")):
#         trimmed = trimmed.rstrip() + "."

#     return trimmed


# # ---------- routes ----------

# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # recent history (avoid repeats; remember last voice)
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # music + voice selection
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)
#     track_id, music_path, chosen_folder, music_file = ti
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # base music timing
#     music_ms = duration_ms(load_audio(music_path))

#     # Spoken portion target is shorter than full music (intro + tail).
#     spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
#     # Use a slightly slower assumed WPS so we don't over-fill the track with words
#     target_words = min(_estimate_target_words(spoken_target_ms, wps=1.7), 1200)

#     # PHASE 1: base script
#     jdict = x.model_dump()
#     jdict["music_ms"] = music_ms
#     jdict["spoken_target_ms"] = spoken_target_ms
#     jdict["intro_ms"] = MUSIC_INTRO_MS

#     # NEW: choose an emotional arc once, based on intake + context (Reagan et al. style).
#     arc_name = pr.choose_arc(jdict)
#     jdict["arc_name"] = arc_name

#     prompt_txt = pr.build(jdict, target_words=target_words)
#     script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

#     # PHASE 2: if too short, extend at most once to get near target
#     max_extend_rounds = 1
#     round_i = 0
#     while _word_count(script) < int(0.9 * target_words) and round_i < max_extend_rounds:
#         need = target_words - _word_count(script)
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()
#         round_i += 1

#     # PHASE 3: adaptive, time-aware correction with smoothed WPS
#     max_corrections = 4
#     attempt = 0
#     best_script = script
#     best_tts_path = None
#     ema_wps = 2.0  # start slightly slower; update from observed

#     while True:
#         script_for_tts = finalize_script(best_script)

#         tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         wc = _word_count(script_for_tts)
#         observed_wps = wc / max(1.0, tts_ms / 1000.0)
#         ema_wps = 0.7 * ema_wps + 0.3 * observed_wps

#         print(
#             f"[Journey] music={music_ms}ms, spoken_target={spoken_target_ms}ms, "
#             f"tts={tts_ms}ms, words={wc}, wps_obs={observed_wps:.2f}, "
#             f"wps_ema={ema_wps:.2f}, try={attempt+1}"
#         )

#         if _within(tts_ms, spoken_target_ms, tol=0.04) or attempt >= max_corrections:
#             best_script, best_tts_path = script_for_tts, tts_tmp_wav
#             break

#         delta_ms = spoken_target_ms - tts_ms
#         delta_words = int(abs(delta_ms) / 1000.0 * ema_wps)
#         delta_words = max(30, min(delta_words, 200))

#         if delta_ms > 0:
#             # Too short → extend
#             tail = _last_n_words(script_for_tts, 40)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=delta_words)
#             addition = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#             if addition:
#                 best_script = (script_for_tts + " " + addition).strip()
#         else:
#             # Too long → trim tail
#             trimmed = _trim_tail_words_by_count(script_for_tts, delta_words)
#             best_script = trimmed

#         attempt += 1

#     # PHASE 4: build VO with a music-only intro, then mix
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)

#     # Load final TTS and enforce "voice ends before music" with a small music-only tail.
#     raw_voice = load_audio(best_tts_path).set_frame_rate(44100).set_channels(2)

#     # Max allowed spoken duration inside the track (leave some tail for music-only)
#     max_spoken_ms = max(
#         1000,
#         music_ms - MUSIC_INTRO_MS - TAIL_MARGIN_MS,
#     )
#     if max_spoken_ms < 1000:
#         max_spoken_ms = 1000

#     original_voice_ms = len(raw_voice)

#     if original_voice_ms > max_spoken_ms:
#         # Trim the audio AND trim the script proportionally, so
#         # script_text actually matches what you hear.
#         ratio = max_spoken_ms / float(original_voice_ms)
#         raw_voice = raw_voice[:max_spoken_ms]
#         best_script = _trim_script_to_ratio(best_script, ratio)
#     else:
#         # Still snap ending to a clean sentence so it doesn't sound cut
#         best_script = _sentence_safe(best_script)
#         if not best_script.endswith((".", "!", "?")):
#             best_script = best_script.rstrip() + "."

#     # prepend silence to create the intro Felix wants
#     intro = AudioSegment.silent(duration=MUSIC_INTRO_MS, frame_rate=raw_voice.frame_rate)
#     voice_with_intro = intro + raw_voice

#     tmp_vo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     voice_with_intro.export(tmp_vo.name, format="wav")
#     voice_for_mix = tmp_vo.name

#     # IMPORTANT: don't retime voice to full music length, so we can keep a music-only outro
#     duration_ms_final = mixr.mix(
#         voice_for_mix,
#         music_path,
#         out_path,
#         duck_db=10.0,
#         sync_mode="no_retime_trim_pad",
#         ffmpeg_bin=c.FFMPEG_BIN,
#     )

#     # persist + respond
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )


# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out


# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }

# from pathlib import Path
# import os
# import re
# import tempfile

# from fastapi import APIRouter, Depends, HTTPException
# from sqlalchemy.orm import Session
# from pydub import AudioSegment

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..utils.text import finalize_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# MUSIC_INTRO_MS = 6000   # ~6s music-only intro before voice comes in
# TAIL_MARGIN_MS = 1500   # (no longer used for trimming; kept for future tuning if needed)


# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()


# # ---------- helpers ----------

# def _estimate_target_words(music_ms: int, wps: float = 1.7) -> int:
#     """
#     Estimate target word count for the SPOKEN portion only.
#     We assume a slightly slower average WPS to keep delivery clear and less dense.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))


# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     return abs(ms - target) <= int(target * tol)


# def _word_count(txt: str) -> int:
#     return len((txt or "").strip().split())


# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = (txt or "").strip().split()
#     return " ".join(w[-n:]) if len(w) > n else (txt or "").strip()


# def _sentence_safe(text: str) -> str:
#     """
#     Make sure the text ends at a sentence boundary if possible.
#     If no '.', '!' or '?' exists, returns the text as-is.
#     """
#     text = (text or "").strip()
#     if not text:
#         return text

#     last_dot = text.rfind(".")
#     last_ex = text.rfind("!")
#     last_q = text.rfind("?")
#     last_punct = max(last_dot, last_ex, last_q)

#     if last_punct != -1:
#         return text[: last_punct + 1].strip()
#     return text


# def _trim_tail_words_by_count(txt: str, drop_words: int) -> str:
#     """
#     Trim approximately `drop_words` from the end, then snap to a clean sentence.
#     This avoids ugly endings like 'There are whispers of'.
#     """
#     if drop_words <= 0:
#         return (txt or "").strip()

#     words = (txt or "").strip().split()
#     if not words:
#         return ""

#     if len(words) <= drop_words:
#         # keep at least a tiny tail, then sentence-safe it
#         base = " ".join(words[: max(1, len(words) - 5)])
#         out = _sentence_safe(base)
#         if not out.endswith((".", "!", "?")):
#             out = out.rstrip() + "."
#         return out

#     kept = words[: len(words) - drop_words]
#     base = " ".join(kept).strip()
#     out = _sentence_safe(base)
#     if not out.endswith((".", "!", "?")):
#         out = out.rstrip() + "."
#     return out


# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     """
#     Build a continuation prompt that strictly enforces:
#     - same unnamed character
#     - same day and setting
#     - no second story or restart.
#     We reuse the same emotional arc by passing arc_name through base_json.
#     """
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
#     return (
#         f"{head_short}\n"
#         "Continue the SAME single spoken narration about the SAME unnamed person, "
#         "in the SAME day and setting.\n"
#         "Do NOT restart the story, do NOT introduce a new character name, "
#         "and do NOT describe a new morning, a new apartment, or a second beginning.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions except the literal token [pause] where a slightly longer silence makes sense.\n"
#         "No summaries. Keep cadence natural. End decisively with a clear emotional landing.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )


# def _trim_script_to_ratio(txt: str, ratio: float) -> str:
#     """
#     When we truncate the VO audio, trim the script to roughly the same proportion
#     and make sure it ends on a clean line. (Not used in the new "voice as master"
#     flow but kept for future safety / experimentation.)
#     """
#     txt = (txt or "").strip()
#     if not txt or ratio >= 0.999:
#         # nothing to do
#         return _sentence_safe(txt)

#     words = txt.split()
#     if not words:
#         return ""

#     # proportional keep, with a bit of safety margin
#     keep = int(len(words) * ratio) - 3
#     keep = max(30, min(keep, len(words)))  # keep at least some content

#     trimmed = " ".join(words[:keep]).strip()
#     trimmed = _sentence_safe(trimmed)

#     if not trimmed.endswith((".", "!", "?")):
#         trimmed = trimmed.rstrip() + "."

#     return trimmed


# # ---------- routes ----------

# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # recent history (avoid repeats; remember last voice)
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # music + voice selection
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)
#     track_id, music_path, chosen_folder, music_file = ti
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # base music timing (for initial target estimation only)
#     music_ms = duration_ms(load_audio(music_path))

#     # Spoken portion target is shorter than full music (intro + tail),
#     # but final master length will be voice-driven.
#     spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
#     # Use a slightly slower assumed WPS so we don't over-fill the track with words
#     target_words = min(_estimate_target_words(spoken_target_ms, wps=1.7), 1200)

#     # PHASE 1: base script
#     jdict = x.model_dump()
#     jdict["music_ms"] = music_ms
#     jdict["spoken_target_ms"] = spoken_target_ms
#     jdict["intro_ms"] = MUSIC_INTRO_MS

#     # choose an emotional arc once, based on intake + context
#     arc_name = pr.choose_arc(jdict)
#     jdict["arc_name"] = arc_name

#     prompt_txt = pr.build(jdict, target_words=target_words)
#     script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

#     # PHASE 2: if too short, extend at most once to get near target
#     max_extend_rounds = 1
#     round_i = 0
#     while _word_count(script) < int(0.9 * target_words) and round_i < max_extend_rounds:
#         need = target_words - _word_count(script)
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()
#         round_i += 1

#     # PHASE 3: adaptive, time-aware correction with smoothed WPS
#     max_corrections = 4
#     attempt = 0
#     best_script = script
#     best_tts_path = None
#     ema_wps = 2.0  # start slightly slower; update from observed

#     while True:
#         script_for_tts = finalize_script(best_script)

#         tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         wc = _word_count(script_for_tts)
#         observed_wps = wc / max(1.0, tts_ms / 1000.0)
#         ema_wps = 0.7 * ema_wps + 0.3 * observed_wps

#         print(
#             f"[Journey] music={music_ms}ms, spoken_target={spoken_target_ms}ms, "
#             f"tts={tts_ms}ms, words={wc}, wps_obs={observed_wps:.2f}, "
#             f"wps_ema={ema_wps:.2f}, try={attempt+1}"
#         )

#         if _within(tts_ms, spoken_target_ms, tol=0.04) or attempt >= max_corrections:
#             best_script, best_tts_path = script_for_tts, tts_tmp_wav
#             break

#         delta_ms = spoken_target_ms - tts_ms
#         delta_words = int(abs(delta_ms) / 1000.0 * ema_wps)
#         delta_words = max(30, min(delta_words, 200))

#         if delta_ms > 0:
#             # Too short → extend
#             tail = _last_n_words(script_for_tts, 40)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=delta_words)
#             addition = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#             if addition:
#                 best_script = (script_for_tts + " " + addition).strip()
#         else:
#             # Too long → trim tail
#             trimmed = _trim_tail_words_by_count(script_for_tts, delta_words)
#             best_script = trimmed

#         attempt += 1

#     # PHASE 4: build VO with a music-only intro, then mix (VOICE = master length)
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)

#     # Load final TTS (this is the version we tuned in PHASE 3)
#     raw_voice = load_audio(best_tts_path).set_frame_rate(44100).set_channels(2)

#     # Make sure the script text ends on a clean sentence so it matches what we hear.
#     best_script = _sentence_safe(best_script)
#     if not best_script.endswith((".", "!", "?")):
#         best_script = best_script.rstrip() + "."

#     # prepend silence to create the intro Felix wants
#     intro = AudioSegment.silent(duration=MUSIC_INTRO_MS, frame_rate=raw_voice.frame_rate)
#     voice_with_intro = intro + raw_voice

#     tmp_vo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     voice_with_intro.export(tmp_vo.name, format="wav")
#     voice_for_mix = tmp_vo.name

#     # IMPORTANT: use voice as the master timeline.
#     # Music is retimed to VO length so when music stops, speech also stops.
#     duration_ms_final = mixr.mix(
#         voice_for_mix,
#         music_path,
#         out_path,
#         duck_db=10.0,
#         sync_mode="retime_music_to_voice",
#         ffmpeg_bin=c.FFMPEG_BIN,
#     )

#     # persist + respond
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )


# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out


# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }

# from pathlib import Path
# import os
# import re
# import tempfile

# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session
# from pydub import AudioSegment

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..services import narrative as narrative_service
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..utils.text import finalize_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# MUSIC_INTRO_MS = 6000   # ~6s music-only intro before voice comes in
# TAIL_MARGIN_MS = 1500   # (no longer used for trimming; kept for future tuning if needed)


# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()


# # ---------- helpers ----------

# def _estimate_target_words(music_ms: int, wps: float = 1.7) -> int:
#     """
#     Estimate target word count for the SPOKEN portion only.
#     We assume a slightly slower average WPS to keep delivery clear and less dense.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))


# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     return abs(ms - target) <= int(target * tol)


# def _word_count(txt: str) -> int:
#     return len((txt or "").strip().split())


# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = (txt or "").strip().split()
#     return " ".join(w[-n:]) if len(w) > n else (txt or "").strip()


# def _sentence_safe(text: str) -> str:
#     """
#     Make sure the text ends at a sentence boundary if possible.
#     If no '.', '!' or '?' exists, returns the text as-is.
#     """
#     text = (text or "").strip()
#     if not text:
#         return text

#     last_dot = text.rfind(".")
#     last_ex = text.rfind("!")
#     last_q = text.rfind("?")
#     last_punct = max(last_dot, last_ex, last_q)

#     if last_punct != -1:
#         return text[: last_punct + 1].strip()
#     return text


# def _trim_tail_words_by_count(txt: str, drop_words: int) -> str:
#     """
#     Trim approximately `drop_words` from the end, then snap to a clean sentence.
#     This avoids ugly endings like 'There are whispers of'.
#     """
#     if drop_words <= 0:
#         return (txt or "").strip()

#     words = (txt or "").strip().split()
#     if not words:
#         return ""

#     if len(words) <= drop_words:
#         # keep at least a tiny tail, then sentence-safe it
#         base = " ".join(words[: max(1, len(words) - 5)])
#         out = _sentence_safe(base)
#         if not out.endswith((".", "!", "?")):
#             out = out.rstrip() + "."
#         return out

#     kept = words[: len(words) - drop_words]
#     base = " ".join(kept).strip()
#     out = _sentence_safe(base)
#     if not out.endswith((".", "!", "?")):
#         out = out.rstrip() + "."
#     return out


# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     """
#     Build a continuation prompt that strictly enforces:
#     - same unnamed character
#     - same day and setting
#     - no second story or restart.
#     We reuse the same emotional arc by passing arc_name through base_json.
#     """
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
#     return (
#         f"{head_short}\n"
#         "Continue the SAME single spoken narration about the SAME unnamed person, "
#         "in the SAME day and setting.\n"
#         "Do NOT restart the story, do NOT introduce a new character name, "
#         "and do NOT describe a new morning, a new apartment, or a second beginning.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions except the literal token [pause] where a slightly longer silence makes sense.\n"
#         "No summaries. Keep cadence natural. End decisively with a clear emotional landing.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )


# def _trim_script_to_ratio(txt: str, ratio: float) -> str:
#     """
#     When we truncate the VO audio, trim the script to roughly the same proportion
#     and make sure it ends on a clean line. (Not used in the new "voice as master"
#     flow but kept for future safety / experimentation.)
#     """
#     txt = (txt or "").strip()
#     if not txt or ratio >= 0.999:
#         # nothing to do
#         return _sentence_safe(txt)

#     words = txt.split()
#     if not words:
#         return ""

#     # proportional keep, with a bit of safety margin
#     keep = int(len(words) * ratio) - 3
#     keep = max(30, min(keep, len(words)))  # keep at least some content

#     trimmed = " ".join(words[:keep]).strip()
#     trimmed = _sentence_safe(trimmed)

#     if not trimmed.endswith((".", "!", "?")):
#         trimmed = trimmed.rstrip() + "."

#     return trimmed


# # ---------- routes ----------

# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     idx = sel.load_index()

#     # recent history (avoid repeats; remember last voice)
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # music + voice selection
#     ti = None
#     if getattr(x, "journey_day", None):
#         ti = sel.pick_track_by_day(idx, x.journey_day)
#     if ti is None:
#         folders = sel.choose_folder(x.feeling, x.schema_choice)
#         ti = sel.pick_track(idx, folders, recent_track_ids)
#     track_id, music_path, chosen_folder, music_file = ti
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # base music timing (for initial target estimation only)
#     music_ms = duration_ms(load_audio(music_path))

#     # Spoken portion target is shorter than full music (intro + tail),
#     # but final master length will be voice-driven.
#     spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
#     # Use a slightly slower assumed WPS so we don't over-fill the track with words
#     target_words = min(_estimate_target_words(spoken_target_ms, wps=1.7), 1200)

#     # PHASE 1: base script
#     jdict = x.model_dump()
#     jdict["music_ms"] = music_ms
#     jdict["spoken_target_ms"] = spoken_target_ms
#     jdict["intro_ms"] = MUSIC_INTRO_MS

#     # choose an emotional arc once, based on intake + context
#     arc_name = pr.choose_arc(jdict)
#     jdict["arc_name"] = arc_name

#     prompt_txt = pr.build(jdict, target_words=target_words)
#     script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

#     # PHASE 2: if too short, extend at most once to get near target
#     max_extend_rounds = 1
#     round_i = 0
#     while _word_count(script) < int(0.9 * target_words) and round_i < max_extend_rounds:
#         need = target_words - _word_count(script)
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()
#         round_i += 1

#     # PHASE 3: adaptive, time-aware correction with smoothed WPS
#     max_corrections = 4
#     attempt = 0
#     best_script = script
#     best_tts_path = None
#     ema_wps = 2.0  # start slightly slower; update from observed

#     while True:
#         script_for_tts = finalize_script(best_script)

#         tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         wc = _word_count(script_for_tts)
#         observed_wps = wc / max(1.0, tts_ms / 1000.0)
#         ema_wps = 0.7 * ema_wps + 0.3 * observed_wps

#         print(
#             f"[Journey] music={music_ms}ms, spoken_target={spoken_target_ms}ms, "
#             f"tts={tts_ms}ms, words={wc}, wps_obs={observed_wps:.2f}, "
#             f"wps_ema={ema_wps:.2f}, try={attempt+1}"
#         )

#         if _within(tts_ms, spoken_target_ms, tol=0.04) or attempt >= max_corrections:
#             best_script, best_tts_path = script_for_tts, tts_tmp_wav
#             break

#         delta_ms = spoken_target_ms - tts_ms
#         delta_words = int(abs(delta_ms) / 1000.0 * ema_wps)
#         delta_words = max(30, min(delta_words, 200))

#         if delta_ms > 0:
#             # Too short → extend
#             tail = _last_n_words(script_for_tts, 40)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=delta_words)
#             addition = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#             if addition:
#                 best_script = (script_for_tts + " " + addition).strip()
#         else:
#             # Too long → trim tail
#             trimmed = _trim_tail_words_by_count(script_for_tts, delta_words)
#             best_script = trimmed

#         attempt += 1

#     # PHASE 4: build VO with a music-only intro, then mix (VOICE = master length)
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)

#     # Load final TTS (this is the version we tuned in PHASE 3)
#     raw_voice = load_audio(best_tts_path).set_frame_rate(44100).set_channels(2)

#     # Make sure the script text ends on a clean sentence so it matches what we hear.
#     best_script = _sentence_safe(best_script)
#     if not best_script.endswith((".", "!", "?")):
#         best_script = best_script.rstrip() + "."

#     # prepend silence to create the intro Felix wants
#     intro = AudioSegment.silent(duration=MUSIC_INTRO_MS, frame_rate=raw_voice.frame_rate)
#     voice_with_intro = intro + raw_voice

#     tmp_vo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     voice_with_intro.export(tmp_vo.name, format="wav")
#     voice_for_mix = tmp_vo.name

#     # IMPORTANT: use voice as the master timeline.
#     # Music is retimed to VO length so when music stops, speech also stops.
#     duration_ms_final = mixr.mix(
#         voice_for_mix,
#         music_path,
#         out_path,
#         duck_db=10.0,
#         sync_mode="retime_music_to_voice",
#         ffmpeg_bin=c.FFMPEG_BIN,
#     )

#     # persist + respond
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=x.feeling,
#         schema_hint=x.schema_choice or "",
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=getattr(x, "journey_day", None),
#     )


# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out


# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }


# @r.get("/api/journey/state")
# def journey_state(
#     user_hash: str | None = Query(
#         None,
#         description="Optional user hash; if omitted, state is computed as 'ready' by default.",
#     ),
#     q: Session = Depends(db),
# ):
#     """
#     Simple cooldown-based state for the Journey button ("locked / charging" vs "ready").
#     Frontend can call this to grey out the button if the last session was too recent.
#     """
#     return narrative_service.compute_journey_state(q, user_hash)


# from pathlib import Path
# import os
# import re
# import tempfile

# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session
# from pydub import AudioSegment

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts, Activities, ActivitySessions, Users  # added Users/Activities refs for fallback
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..services import narrative as narrative_service
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..utils.text import finalize_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# MUSIC_INTRO_MS = 6000   # ~6s music-only intro before voice comes in
# TAIL_MARGIN_MS = 1500   # (no longer used for trimming; kept for future tuning if needed)


# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()


# # ---------- helpers ----------

# def _estimate_target_words(music_ms: int, wps: float = 1.7) -> int:
#     """
#     Estimate target word count for the SPOKEN portion only.
#     We assume a slightly slower average WPS to keep delivery clear and less dense.
#     """
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))


# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     return abs(ms - target) <= int(target * tol)


# def _word_count(txt: str) -> int:
#     return len((txt or "").strip().split())


# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = (txt or "").strip().split()
#     return " ".join(w[-n:]) if len(w) > n else (txt or "").strip()


# def _sentence_safe(text: str) -> str:
#     """
#     Make sure the text ends at a sentence boundary if possible.
#     If no '.', '!' or '?' exists, returns the text as-is.
#     """
#     text = (text or "").strip()
#     if not text:
#         return text

#     last_dot = text.rfind(".")
#     last_ex = text.rfind("!")
#     last_q = text.rfind("?")
#     last_punct = max(last_dot, last_ex, last_q)

#     if last_punct != -1:
#         return text[: last_punct + 1].strip()
#     return text


# def _trim_tail_words_by_count(txt: str, drop_words: int) -> str:
#     """
#     Trim approximately `drop_words` from the end, then snap to a clean sentence.
#     This avoids ugly endings like 'There are whispers of'.
#     """
#     if drop_words <= 0:
#         return (txt or "").strip()

#     words = (txt or "").strip().split()
#     if not words:
#         return ""

#     if len(words) <= drop_words:
#         # keep at least a tiny tail, then sentence-safe it
#         base = " ".join(words[: max(1, len(words) - 5)])
#         out = _sentence_safe(base)
#         if not out.endswith((".", "!", "?")):
#             out = out.rstrip() + "."
#         return out

#     kept = words[: len(words) - drop_words]
#     base = " ".join(kept).strip()
#     out = _sentence_safe(base)
#     if not out.endswith((".", "!", "?")):
#         out = out.rstrip() + "."
#     return out


# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     """
#     Build a continuation prompt that strictly enforces:
#     - same unnamed character
#     - same day and setting
#     - no second story or restart.
#     We reuse the same emotional arc by passing arc_name through base_json.
#     """
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
#     return (
#         f"{head_short}\n"
#         "Continue the SAME single spoken narration about the SAME unnamed person, "
#         "in the SAME day and setting.\n"
#         "Do NOT restart the story, do NOT introduce a new character name, "
#         "and do NOT describe a new morning, a new apartment, or a second beginning.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions except the literal token [pause] where a slightly longer silence makes sense.\n"
#         "No summaries. Keep cadence natural. End decisively with a clear emotional landing.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )


# def _trim_script_to_ratio(txt: str, ratio: float) -> str:
#     """
#     When we truncate the VO audio, trim the script to roughly the same proportion
#     and make sure it ends on a clean line. (Not used in the new "voice as master"
#     flow but kept for future safety / experimentation.)
#     """
#     txt = (txt or "").strip()
#     if not txt or ratio >= 0.999:
#       # nothing to do
#       return _sentence_safe(txt)

#     words = txt.split()
#     if not words:
#       return ""

#     # proportional keep, with a bit of safety margin
#     keep = int(len(words) * ratio) - 3
#     keep = max(30, min(keep, len(words)))  # keep at least some content

#     trimmed = " ".join(words[:keep]).strip()
#     trimmed = _sentence_safe(trimmed)

#     if not trimmed.endswith((".", "!", "?")):
#       trimmed = trimmed.rstrip() + "."

#     return trimmed


# def _fallback_from_history(q: Session, user_hash: str | None) -> dict:
#   """
#   Gather best-effort fallback context from user's history (Day-1 / last known).
#   Returns dict keys that match IntakeIn fields partially: feeling, schema_choice,
#   postal_code, goal_today, place, journey_day.
#   """
#   out = {
#       "feeling": None,
#       "schema_choice": None,
#       "postal_code": None,
#       "goal_today": None,
#       "place": None,
#       "journey_day": None,
#   }
#   if not user_hash:
#     return out

#   # last session (mood, schema, voice, etc.)
#   last_sess = (
#       q.query(Sessions)
#       .filter(Sessions.user_hash == user_hash)
#       .order_by(Sessions.created_at.desc())
#       .first()
#   )
#   if last_sess:
#     out["feeling"] = last_sess.mood or out["feeling"]
#     out["schema_choice"] = last_sess.schema_hint or out["schema_choice"]

#   # user profile (postal_code if present)
#   try:
#     u = q.query(Users).filter(Users.user_hash == user_hash).first()
#     if u and getattr(u, "postal_code", None):
#       out["postal_code"] = getattr(u, "postal_code")
#     if u and getattr(u, "journey_day", None):
#       out["journey_day"] = getattr(u, "journey_day")
#   except Exception:
#     pass

#   # last committed/started activity -> use title/place as soft goal/place
#   try:
#     asess = (
#         q.query(ActivitySessions)
#         .filter(ActivitySessions.user_hash == user_hash)
#         .order_by(ActivitySessions.started_at.desc())
#         .first()
#     )
#     if asess:
#       act = q.query(Activities).filter(Activities.id == asess.activity_id).first()
#       if act:
#         out["goal_today"] = getattr(act, "title", None) or out["goal_today"]
#         out["place"] = getattr(act, "location_label", None) or out["place"]
#   except Exception:
#     pass

#   return out


# # ---------- routes ----------

# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     # --- Fallback enrichment: if mini-checkin omitted values, pull Day-1 / last-known ---
#     fb = _fallback_from_history(q, getattr(x, "user_hash", None))

#     # produce an "effective" context using explicit > fallback > default
#     def eff(val, fallback, default):
#         if val is None or (isinstance(val, str) and val.strip() == ""):
#             return fallback if (fallback is not None and str(fallback).strip() != "") else default
#         return val

#     effective = {
#         "feeling": eff(getattr(x, "feeling", None), fb.get("feeling"), "mixed"),
#         "schema_choice": eff(getattr(x, "schema_choice", None), fb.get("schema_choice"), "default"),
#         "postal_code": eff(getattr(x, "postal_code", None), fb.get("postal_code"), ""),
#         "goal_today": eff(getattr(x, "goal_today", None), fb.get("goal_today"), "show up for the day"),
#         "place": eff(getattr(x, "place", None), fb.get("place"), None),
#         "journey_day": getattr(x, "journey_day", None) or fb.get("journey_day", None),
#     }

#     idx = sel.load_index()

#     # recent history (avoid repeats; remember last voice)
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # music + voice selection
#     ti = None
#     if getattr(x, "journey_day", None) or effective["journey_day"]:
#         ti = sel.pick_track_by_day(idx, getattr(x, "journey_day", None) or effective["journey_day"])
#     if ti is None:
#         folders = sel.choose_folder(effective["feeling"], effective["schema_choice"])
#         ti = sel.pick_track(idx, folders, recent_track_ids)
#     track_id, music_path, chosen_folder, music_file = ti
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # base music timing (for initial target estimation only)
#     music_ms = duration_ms(load_audio(music_path))

#     # Spoken portion target is shorter than full music (intro + tail),
#     # but final master length will be voice-driven.
#     spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
#     target_words = min(_estimate_target_words(spoken_target_ms, wps=1.7), 1200)

#     # PHASE 1: base script
#     jdict = x.model_dump()
#     jdict["music_ms"] = music_ms
#     jdict["spoken_target_ms"] = spoken_target_ms
#     jdict["intro_ms"] = MUSIC_INTRO_MS

#     # ensure effective context is used for prompt generation
#     jdict["feeling"] = effective["feeling"]
#     jdict["schema_choice"] = effective["schema_choice"]
#     jdict["postal_code"] = effective["postal_code"]
#     jdict["goal_today"] = effective["goal_today"]
#     jdict["place"] = effective["place"]

#     # choose an emotional arc once, based on intake + context
#     arc_name = pr.choose_arc(jdict)
#     jdict["arc_name"] = arc_name

#     prompt_txt = pr.build(jdict, target_words=target_words)
#     script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

#     # PHASE 2: if too short, extend at most once to get near target
#     max_extend_rounds = 1
#     round_i = 0
#     while _word_count(script) < int(0.9 * target_words) and round_i < max_extend_rounds:
#         need = target_words - _word_count(script)
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()
#         round_i += 1

#     # PHASE 3: adaptive, time-aware correction with smoothed WPS
#     max_corrections = 4
#     attempt = 0
#     best_script = script
#     best_tts_path = None
#     ema_wps = 2.0  # start slightly slower; update from observed

#     while True:
#         script_for_tts = finalize_script(best_script)

#         tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         wc = _word_count(script_for_tts)
#         observed_wps = wc / max(1.0, tts_ms / 1000.0)
#         ema_wps = 0.7 * ema_wps + 0.3 * observed_wps

#         print(
#             f"[Journey] music={music_ms}ms, spoken_target={spoken_target_ms}ms, "
#             f"tts={tts_ms}ms, words={wc}, wps_obs={observed_wps:.2f}, "
#             f"wps_ema={ema_wps:.2f}, try={attempt+1}"
#         )

#         if _within(tts_ms, spoken_target_ms, tol=0.04) or attempt >= max_corrections:
#             best_script, best_tts_path = script_for_tts, tts_tmp_wav
#             break

#         delta_ms = spoken_target_ms - tts_ms
#         delta_words = int(abs(delta_ms) / 1000.0 * ema_wps)
#         delta_words = max(30, min(delta_words, 200))

#         if delta_ms > 0:
#             # Too short → extend
#             tail = _last_n_words(script_for_tts, 40)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=delta_words)
#             addition = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#             if addition:
#                 best_script = (script_for_tts + " " + addition).strip()
#         else:
#             # Too long → trim tail
#             trimmed = _trim_tail_words_by_count(script_for_tts, delta_words)
#             best_script = trimmed

#         attempt += 1

#     # PHASE 4: build VO with a music-only intro, then mix (VOICE = master length)
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)

#     # Load final TTS (this is the version we tuned in PHASE 3)
#     raw_voice = load_audio(best_tts_path).set_frame_rate(44100).set_channels(2)

#     # Make sure the script text ends on a clean sentence so it matches what we hear.
#     best_script = _sentence_safe(best_script)
#     if not best_script.endswith((".", "!", "?")):
#         best_script = best_script.rstrip() + "."

#     # prepend silence to create the intro Felix wants
#     intro = AudioSegment.silent(duration=MUSIC_INTRO_MS, frame_rate=raw_voice.frame_rate)
#     voice_with_intro = intro + raw_voice

#     tmp_vo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     voice_with_intro.export(tmp_vo.name, format="wav")
#     voice_for_mix = tmp_vo.name

#     # IMPORTANT: use voice as the master timeline.
#     # Music is retimed to VO length so when music stops, speech also stops.
#     duration_ms_final = mixr.mix(
#         voice_for_mix,
#         music_path,
#         out_path,
#         duck_db=10.0,
#         sync_mode="retime_music_to_voice",
#         ffmpeg_bin=c.FFMPEG_BIN,
#     )

#     # persist + respond (store the "effective" mood/schema so future Day-2 can fallback)
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=effective["feeling"],
#         schema_hint=effective["schema_choice"],
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=effective["journey_day"],
#     )


# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out


# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }


# @r.get("/api/journey/state")
# def journey_state(
#     user_hash: str | None = Query(
#         None,
#         description="Optional user hash; if omitted, state is computed as 'ready' by default.",
#     ),
#     q: Session = Depends(db),
# ):
#     """
#     Simple cooldown-based state for the Journey button ("locked / charging" vs "ready").
#     Frontend can call this to grey out the button if the last session was too recent.
#     """
#     return narrative_service.compute_journey_state(q, user_hash)



# from pathlib import Path
# import os
# import tempfile

# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session
# from pydub import AudioSegment

# from ..schemas import IntakeIn, GenerateOut
# from ..db import SessionLocal
# from ..models import Sessions, Scripts, Activities, ActivitySessions, Users
# from ..services import prompt as pr
# from ..services import llm
# from ..services import selector as sel
# from ..services import tts as tts
# from ..services import mix as mixr
# from ..services import store as st
# from ..services import narrative as narrative_service
# from ..utils.hash import sid
# from ..utils.audio import clean_script, load_audio, duration_ms
# from ..utils.text import finalize_script
# from ..core.config import cfg  # cfg is an object (already instantiated)

# r = APIRouter()

# MUSIC_INTRO_MS = 6000   # ~6s music-only intro before voice comes in


# def db():
#     q = SessionLocal()
#     try:
#         yield q
#     finally:
#         q.close()


# # ---------- helpers ----------

# def _estimate_target_words(music_ms: int, wps: float = 1.7) -> int:
#     seconds = max(1, music_ms // 1000)
#     return max(120, int(seconds * wps))


# def _within(ms: int, target: int, tol: float = 0.03) -> bool:
#     return abs(ms - target) <= int(target * tol)


# def _word_count(txt: str) -> int:
#     return len((txt or "").strip().split())


# def _last_n_words(txt: str, n: int = 35) -> str:
#     w = (txt or "").strip().split()
#     return " ".join(w[-n:]) if len(w) > n else (txt or "").strip()


# def _sentence_safe(text: str) -> str:
#     text = (text or "").strip()
#     if not text:
#         return text
#     last_dot = text.rfind(".")
#     last_ex = text.rfind("!")
#     last_q = text.rfind("?")
#     last_punct = max(last_dot, last_ex, last_q)
#     if last_punct != -1:
#         return text[: last_punct + 1].strip()
#     return text


# def _trim_tail_words_by_count(txt: str, drop_words: int) -> str:
#     if drop_words <= 0:
#         return (txt or "").strip()
#     words = (txt or "").strip().split()
#     if not words:
#         return ""
#     if len(words) <= drop_words:
#         base = " ".join(words[: max(1, len(words) - 5)])
#         out = _sentence_safe(base)
#         if not out.endswith((".", "!", "?")):
#             out = out.rstrip() + "."
#         return out
#     kept = words[: len(words) - drop_words]
#     base = " ".join(kept).strip()
#     out = _sentence_safe(base)
#     if not out.endswith((".", "!", "?")):
#         out = out.rstrip() + "."
#     return out


# def _build_continue_prompt(base_json: dict, last_tail: str, need_more: int) -> str:
#     head = pr.build(base_json, target_words=None)
#     head_lines = head.splitlines()
#     head_short = "\n".join(head_lines[:10]) if len(head_lines) > 10 else head
#     return (
#         f"{head_short}\n"
#         "Continue the SAME single spoken narration about the SAME unnamed person, "
#         "in the SAME day and setting.\n"
#         "Do NOT restart the story, do NOT introduce a new character name, "
#         "and do NOT describe a new morning, a new apartment, or a second beginning.\n"
#         f"Add approximately {need_more} new words.\n"
#         "No stage directions except the literal token [pause] where a slightly longer silence makes sense.\n"
#         "No summaries. Keep cadence natural. End decisively with a clear emotional landing.\n"
#         f"Pick up seamlessly from this tail: \"{last_tail}\""
#     )


# def _fallback_from_history(q: Session, user_hash: str | None) -> dict:
#     """
#     Gather best-effort fallback context from user's history (Day-1 / last known).
#     """
#     out = {
#         "feeling": None,
#         "schema_choice": None,
#         "postal_code": None,
#         "goal_today": None,
#         "place": None,
#         "journey_day": None,
#     }
#     if not user_hash:
#         return out

#     last_sess = (
#         q.query(Sessions)
#         .filter(Sessions.user_hash == user_hash)
#         .order_by(Sessions.created_at.desc())
#         .first()
#     )
#     if last_sess:
#         out["feeling"] = last_sess.mood or out["feeling"]
#         out["schema_choice"] = last_sess.schema_hint or out["schema_choice"]

#     try:
#         u = q.query(Users).filter(Users.user_hash == user_hash).first()
#         if u and getattr(u, "postal_code", None):
#             out["postal_code"] = getattr(u, "postal_code")
#         if u and getattr(u, "journey_day", None):
#             out["journey_day"] = getattr(u, "journey_day")
#     except Exception:
#         pass

#     try:
#         asess = (
#             q.query(ActivitySessions)
#             .filter(ActivitySessions.user_hash == user_hash)
#             .order_by(ActivitySessions.started_at.desc())
#             .first()
#         )
#         if asess:
#             act = q.query(Activities).filter(Activities.id == asess.activity_id).first()
#             if act:
#                 out["goal_today"] = getattr(act, "title", None) or out["goal_today"]
#                 out["place"] = getattr(act, "location_label", None) or out["place"]
#     except Exception:
#         pass

#     return out


# # ---------- routes ----------

# @r.post("/api/journey/generate", response_model=GenerateOut)
# def generate(x: IntakeIn, q: Session = Depends(db)):
#     c = cfg
#     st.ensure_dir(c.OUT_DIR)

#     # --- Fallback enrichment: if mini-checkin omitted values, pull Day-1 / last-known ---
#     fb = _fallback_from_history(q, getattr(x, "user_hash", None))

#     # explicit > fallback > default (protects prompt even if frontend missed a field)
#     def eff(val, fallback, default):
#         if val is None or (isinstance(val, str) and val.strip() == ""):
#             return fallback if (fallback is not None and str(fallback).strip() != "") else default
#         return val

#     effective = {
#         "feeling": eff(getattr(x, "feeling", None), fb.get("feeling"), "mixed"),
#         "schema_choice": eff(getattr(x, "schema_choice", None), fb.get("schema_choice"), "default"),
#         "postal_code": eff(getattr(x, "postal_code", None), fb.get("postal_code"), ""),
#         "goal_today": eff(getattr(x, "goal_today", None), fb.get("goal_today"), "show up for the day"),
#         "place": eff(getattr(x, "place", None), fb.get("place"), None),
#         "journey_day": getattr(x, "journey_day", None) or fb.get("journey_day", None),
#     }

#     idx = sel.load_index()

#     # recent history (avoid repeats; remember last voice)
#     recent_track_ids: list[str] = []
#     last_voice = None
#     srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
#     for s in srows:
#         if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
#             if s.track_id:
#                 recent_track_ids.append(s.track_id)
#             if not last_voice and s.voice_id:
#                 last_voice = s.voice_id

#     # music + voice selection
#     ti = None
#     if getattr(x, "journey_day", None) or effective["journey_day"]:
#         ti = sel.pick_track_by_day(idx, getattr(x, "journey_day", None) or effective["journey_day"])
#     if ti is None:
#         folders = sel.choose_folder(effective["feeling"], effective["schema_choice"])
#         ti = sel.pick_track(idx, folders, recent_track_ids)
#     track_id, music_path, chosen_folder, music_file = ti
#     voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

#     # base music timing
#     music_ms = duration_ms(load_audio(music_path))
#     spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
#     target_words = min(_estimate_target_words(spoken_target_ms, wps=1.7), 1200)

#     # PHASE 1: base script
#     jdict = x.model_dump()
#     jdict["music_ms"] = music_ms
#     jdict["spoken_target_ms"] = spoken_target_ms
#     jdict["intro_ms"] = MUSIC_INTRO_MS

#     # ensure effective context is used for prompt generation
#     jdict["feeling"] = effective["feeling"]
#     jdict["schema_choice"] = effective["schema_choice"]
#     jdict["postal_code"] = effective["postal_code"]
#     jdict["goal_today"] = effective["goal_today"]
#     jdict["place"] = effective["place"]

#     # choose an emotional arc once
#     arc_name = pr.choose_arc(jdict)
#     jdict["arc_name"] = arc_name

#     prompt_txt = pr.build(jdict, target_words=target_words)
#     script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

#     # PHASE 2: extend once if short
#     if _word_count(script) < int(0.9 * target_words):
#         need = max(30, target_words - _word_count(script))
#         tail = _last_n_words(script, 40)
#         cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
#         more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#         if more and more not in script:
#             script = (script + " " + more).strip()

#     # PHASE 3: adaptive correction
#     max_corrections = 4
#     attempt = 0
#     best_script = script
#     best_tts_path = None
#     ema_wps = 2.0

#     while True:
#         script_for_tts = finalize_script(best_script)

#         tts_tmp_wav = tts.synth(script_for_tts, voice_id, c.ELEVENLABS_API_KEY)
#         tts_ms = duration_ms(load_audio(tts_tmp_wav))
#         wc = _word_count(script_for_tts)
#         observed_wps = wc / max(1.0, tts_ms / 1000.0)
#         ema_wps = 0.7 * ema_wps + 0.3 * observed_wps

#         if _within(tts_ms, spoken_target_ms, tol=0.04) or attempt >= max_corrections:
#             best_script, best_tts_path = script_for_tts, tts_tmp_wav
#             break

#         delta_ms = spoken_target_ms - tts_ms
#         delta_words = int(abs(delta_ms) / 1000.0 * ema_wps)
#         delta_words = max(30, min(delta_words, 200))

#         if delta_ms > 0:
#             # extend
#             tail = _last_n_words(script_for_tts, 40)
#             cont_prompt = _build_continue_prompt(jdict, tail, need_more=delta_words)
#             addition = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
#             if addition:
#                 best_script = (script_for_tts + " " + addition).strip()
#         else:
#             # trim
#             best_script = _trim_tail_words_by_count(script_for_tts, delta_words)

#         attempt += 1

#     # PHASE 4: build VO with intro, then mix (voice = master)
#     session_id = sid()
#     out_path = st.out_file(c.OUT_DIR, session_id)

#     raw_voice = load_audio(best_tts_path).set_frame_rate(44100).set_channels(2)

#     best_script = _sentence_safe(best_script)
#     if not best_script.endswith((".", "!", "?")):
#         best_script = best_script.rstrip() + "."

#     intro = AudioSegment.silent(duration=MUSIC_INTRO_MS, frame_rate=raw_voice.frame_rate)
#     voice_with_intro = intro + raw_voice

#     tmp_vo = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     voice_with_intro.export(tmp_vo.name, format="wav")
#     voice_for_mix = tmp_vo.name

#     duration_ms_final = mixr.mix(
#         voice_for_mix,
#         music_path,
#         out_path,
#         duck_db=10.0,
#         sync_mode="retime_music_to_voice",
#         ffmpeg_bin=c.FFMPEG_BIN,
#     )

#     # persist + respond
#     public_url = st.public_url(c.PUBLIC_BASE_URL, Path(out_path).name)
#     excerpt = best_script[:600] + ("..." if len(best_script) > 600 else "")

#     row = Sessions(
#         id=session_id,
#         user_hash=x.user_hash or "",
#         track_id=track_id,
#         voice_id=voice_id,
#         audio_path=Path(out_path).name,
#         mood=effective["feeling"],
#         schema_hint=effective["schema_choice"],
#     )
#     q.add(row)
#     q.add(Scripts(session_id=session_id, script_text=best_script))
#     q.commit()

#     return GenerateOut(
#         session_id=session_id,
#         audio_url=public_url,
#         duration_ms=duration_ms_final,
#         script_excerpt=excerpt,
#         script_text=best_script,
#         track_id=track_id,
#         voice_id=voice_id,
#         music_folder=chosen_folder,
#         music_file=music_file,
#         journey_day=effective["journey_day"],
#     )


# @r.get("/api/journey/recent")
# def recent(limit: int = 10, user_hash: str | None = None, q: Session = Depends(db)):
#     c = cfg
#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}

#     s = q.query(Sessions)
#     if user_hash:
#         s = s.filter(Sessions.user_hash == user_hash)
#     rows = s.order_by(Sessions.created_at.desc()).limit(limit).all()

#     out = []
#     for z in rows:
#         url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#         relpath = id2path.get(z.track_id, "")
#         music_file = os.path.basename(relpath) if relpath else ""
#         music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""
#         out.append({
#             "session_id": z.id,
#             "audio_url": url,
#             "track_id": z.track_id,
#             "voice_id": z.voice_id,
#             "mood": z.mood,
#             "schema_hint": z.schema_hint,
#             "music_folder": music_folder,
#             "music_file": music_file,
#             "created_at": z.created_at.isoformat(),
#         })
#     return out


# @r.get("/api/journey/session/{sid}")
# def get_session(sid: str, q: Session = Depends(db)):
#     c = cfg
#     z = q.query(Sessions).filter(Sessions.id == sid).first()
#     if not z:
#         raise HTTPException(status_code=404, detail="session not found")

#     idx = sel.load_index()
#     id2path = {row["id"]: row["path"] for row in idx["tracks"]}
#     relpath = id2path.get(z.track_id, "")
#     music_file = os.path.basename(relpath) if relpath else ""
#     music_folder = os.path.dirname(relpath).replace("\\", "/").split("/")[-1] if relpath else ""

#     url = st.public_url(c.PUBLIC_BASE_URL, z.audio_path)
#     return {
#         "session_id": z.id,
#         "audio_url": url,
#         "track_id": z.track_id,
#         "voice_id": z.voice_id,
#         "mood": z.mood,
#         "schema_hint": z.schema_hint,
#         "music_folder": music_folder,
#         "music_file": music_file,
#         "created_at": z.created_at.isoformat(),
#     }


# @r.get("/api/journey/state")
# def journey_state(
#     user_hash: str | None = Query(
#         None,
#         description="Optional user hash; if omitted, state is computed as 'ready' by default.",
#     ),
#     q: Session = Depends(db),
# ):
#     return narrative_service.compute_journey_state(q, user_hash)



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
from ..core.config import cfg  # cfg is an object (already instantiated)

r = APIRouter()

MUSIC_INTRO_MS = 6000   # ~6s music-only intro before voice comes in


def db():
    q = SessionLocal()
    try:
        yield q
    finally:
        q.close()


# ---------- helpers ----------

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
    Gather best-effort fallback context from user's history (Day-1 / last known).
    """
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


# ---------- routes ----------

@r.post("/api/journey/generate", response_model=GenerateOut)
def generate(x: IntakeIn, q: Session = Depends(db)):
    c = cfg
    st.ensure_dir(c.OUT_DIR)

    # --- Fallback enrichment: if mini-checkin omitted values, pull Day-1 / last-known ---
    fb = _fallback_from_history(q, getattr(x, "user_hash", None))

    # explicit > fallback > default (protects prompt even if frontend missed a field)
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

    # recent history (avoid repeats; remember last voice)
    recent_track_ids: list[str] = []
    last_voice = None
    srows = q.query(Sessions).order_by(Sessions.created_at.desc()).limit(20).all()
    for s in srows:
        if s.user_hash and x.user_hash and s.user_hash == x.user_hash:
            if s.track_id:
                recent_track_ids.append(s.track_id)
            if not last_voice and s.voice_id:
                last_voice = s.voice_id

    # music + voice selection
    ti = None
    if getattr(x, "journey_day", None) or effective["journey_day"]:
        ti = sel.pick_track_by_day(idx, getattr(x, "journey_day", None) or effective["journey_day"])
    if ti is None:
        folders = sel.choose_folder(effective["feeling"], effective["schema_choice"])
        ti = sel.pick_track(idx, folders, recent_track_ids)
    track_id, music_path, chosen_folder, music_file = ti
    voice_id = sel.pick_voice(chosen_folder, c, recent_voice=last_voice)

    # base music timing
    music_ms = duration_ms(load_audio(music_path))
    spoken_target_ms = max(int(music_ms - MUSIC_INTRO_MS), int(0.75 * music_ms))
    target_words = min(_estimate_target_words(spoken_target_ms, wps=1.7), 1200)

    # PHASE 1: base script
    jdict = x.model_dump()
    jdict["music_ms"] = music_ms
    jdict["spoken_target_ms"] = spoken_target_ms
    jdict["intro_ms"] = MUSIC_INTRO_MS

    # ensure effective context is used for prompt generation
    jdict["feeling"] = effective["feeling"]
    jdict["schema_choice"] = effective["schema_choice"]
    jdict["postal_code"] = effective["postal_code"]
    jdict["goal_today"] = effective["goal_today"]
    jdict["place"] = effective["place"]

    # choose an emotional arc once
    arc_name = pr.choose_arc(jdict)
    jdict["arc_name"] = arc_name

    prompt_txt = pr.build(jdict, target_words=target_words)
    script = clean_script(llm.generate_text(prompt_txt, c.OPENAI_API_KEY))

    # PHASE 2: extend once if short
    if _word_count(script) < int(0.9 * target_words):
        need = max(30, target_words - _word_count(script))
        tail = _last_n_words(script, 40)
        cont_prompt = _build_continue_prompt(jdict, tail, need_more=need)
        more = clean_script(llm.generate_text(cont_prompt, c.OPENAI_API_KEY))
        if more and more not in script:
            script = (script + " " + more).strip()

    # PHASE 3: adaptive correction
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

    # PHASE 4: build VO with intro, then mix (voice = master)
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

    # persist + respond
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

    # NEW: persist a mini-checkin snapshot for the user (so it shows on Profile)
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
