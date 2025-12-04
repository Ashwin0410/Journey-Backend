# import requests, tempfile

# def synth(text: str, voice_id: str, key: str) -> str:
#     u = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
#     h = {"xi-api-key": key, "accept":"audio/mpeg","Content-Type":"application/json"}
#     j = {"text": text.replace("[pause]",". ").replace("[breath]"," "), "model_id":"eleven_multilingual_v2", "voice_settings":{"stability":0.5,"similarity_boost":0.7,"style":0.3,"use_speaker_boost":True}}
#     r = requests.post(u, headers=h, json=j, stream=True, timeout=180)
#     r.raise_for_status()
#     f = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
#     for c in r.iter_content(16384):
#         if c: f.write(c)
#     f.flush(); f.close()
#     return f.name


#-------------------------------------------------------------------------------------------------


# import io
# import re
# import tempfile
# from typing import List

# import requests
# from pydub import AudioSegment

# # Split on sentence boundaries so each chunk stays under ElevenLabs' input cap
# _SENTENCE_SPLIT_RE = re.compile(r'(?<=[\.\!\?])\s+')
# _PAUSE_TOKEN = "[pause]"
# _PAUSE_SENTINEL = "<<<PAUSE>>>"

# def _split_text_into_chunks(text: str, max_chars: int = 4600) -> List[str]:
#     """
#     Split the script into <= max_chars chunks on sentence boundaries.
#     Long single sentences are hard-split if needed.
#     """
#     text = text.strip()
#     if len(text) <= max_chars:
#         return [text]

#     sentences = _SENTENCE_SPLIT_RE.split(text)
#     chunks: List[str] = []
#     cur: List[str] = []
#     cur_len = 0

#     for s in sentences:
#         s = s.strip()
#         if not s:
#             continue
#         add_len = len(s) + (1 if cur_len > 0 else 0)
#         if cur_len + add_len <= max_chars:
#             cur.append(s)
#             cur_len += add_len
#         else:
#             if cur:
#                 chunks.append(" ".join(cur))
#             if len(s) > max_chars:
#                 # Hard-split extremely long sentences
#                 for i in range(0, len(s), max_chars):
#                     chunks.append(s[i:i + max_chars])
#                 cur, cur_len = [], 0
#             else:
#                 cur, cur_len = [s], len(s)

#     if cur:
#         chunks.append(" ".join(cur))
#     return chunks


# def _synth_chunk(text: str, voice_id: str, key: str) -> AudioSegment:
#     """
#     Synthesize a single chunk and return it as a pydub AudioSegment.
#     """
#     url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
#     headers = {
#         "xi-api-key": key,
#         "accept": "audio/mpeg",
#         "Content-Type": "application/json"
#     }
#     payload = {
#         # [pause]/[breath] are stripped or pre-processed BEFORE this stage.
#         "text": text,
#         "model_id": "eleven_multilingual_v2",
#         "voice_settings": {
#             "stability": 0.5,
#             "similarity_boost": 0.7,
#             "style": 0.3,
#             "use_speaker_boost": True
#         }
#     }
#     r = requests.post(url, headers=headers, json=payload, stream=True, timeout=180)
#     r.raise_for_status()
#     buf = io.BytesIO()
#     for c in r.iter_content(16384):
#         if c:
#             buf.write(c)
#     buf.seek(0)
#     return AudioSegment.from_file(buf, format="mp3")


# def synth(text: str, voice_id: str, key: str, max_chars: int = 4600) -> str:
#     """
#     Chunk long scripts, synth each chunk, stitch, and return a temp WAV path.

#     We treat "[pause]" as a request for a slightly longer-than-normal silence
#     by inserting explicit silent gaps between blocks.
#     """
#     raw = (text or "").strip()
#     if not raw:
#         # Return a 1s silent WAV if something odd happens
#         silent = AudioSegment.silent(duration=1000, frame_rate=44100)
#         f = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#         silent.export(f.name, format="wav")
#         return f.name

#     # Convert [breath] to nothing (small prosody change is fine)
#     raw = raw.replace("[breath]", " ")

#     # Mark pauses with a sentinel so we can split and inject silence
#     raw = raw.replace(_PAUSE_TOKEN, f" {_PAUSE_SENTINEL} ")

#     blocks = [b.strip() for b in raw.split(_PAUSE_SENTINEL) if b.strip()]
#     if not blocks:
#         silent = AudioSegment.silent(duration=1000, frame_rate=44100)
#         f = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#         silent.export(f.name, format="wav")
#         return f.name

#     segs: List[AudioSegment] = []
#     PAUSE_MS = 900  # ~0.9s of silence for [pause]

#     for idx, block in enumerate(blocks):
#         parts = _split_text_into_chunks(block, max_chars=max_chars)
#         for p in parts:
#             segs.append(_synth_chunk(p, voice_id, key))
#         if idx < len(blocks) - 1:
#             segs.append(AudioSegment.silent(duration=PAUSE_MS, frame_rate=44100))

#     full = segs[0]
#     for s in segs[1:]:
#         full += s

#     outf = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
#     full.export(outf.name, format="wav")
#     return outf.name
#------------------------------------------------------------------------------------------------
import io
import re
import tempfile
from typing import List

import requests
from pydub import AudioSegment

# Split on sentence boundaries so each chunk stays under ElevenLabs' input cap
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[\.\!\?])\s+')
_PAUSE_TOKEN = "[pause]"
_PAUSE_SENTINEL = "<<<PAUSE>>>"


def _split_text_into_chunks(text: str, max_chars: int = 4600) -> List[str]:
    """
    Split the script into <= max_chars chunks on sentence boundaries.
    Long single sentences are hard-split if needed.
    """
    text = text.strip()
    if len(text) <= max_chars:
        return [text]

    sentences = _SENTENCE_SPLIT_RE.split(text)
    chunks: List[str] = []
    cur: List[str] = []
    cur_len = 0

    for s in sentences:
        s = s.strip()
        if not s:
            continue
        add_len = len(s) + (1 if cur_len > 0 else 0)
        if cur_len + add_len <= max_chars:
            cur.append(s)
            cur_len += add_len
        else:
            if cur:
                chunks.append(" ".join(cur))
            if len(s) > max_chars:
                # Hard-split extremely long sentences
                for i in range(0, len(s), max_chars):
                    chunks.append(s[i:i + max_chars])
                cur, cur_len = [], 0
            else:
                cur, cur_len = [s], len(s)

    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _synth_chunk(text: str, voice_id: str, key: str) -> AudioSegment:
    """
    Synthesize a single chunk and return it as a pydub AudioSegment.
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "xi-api-key": key,
        "accept": "audio/mpeg",
        "Content-Type": "application/json"
    }
    payload = {
        # [pause]/[breath] are stripped or pre-processed BEFORE this stage.
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.7,
            "style": 0.3,
            "use_speaker_boost": True
        }
    }
    r = requests.post(url, headers=headers, json=payload, stream=True, timeout=180)
    r.raise_for_status()
    buf = io.BytesIO()
    for c in r.iter_content(16384):
        if c:
            buf.write(c)
    buf.seek(0)
    return AudioSegment.from_file(buf, format="mp3")


def synth(text: str, voice_id: str, key: str, max_chars: int = 4600) -> str:
    """
    Chunk long scripts, synth each chunk, stitch, and return a temp WAV path.

    We treat "[pause]" as a request for a slightly longer-than-normal silence
    by inserting explicit silent gaps between blocks.

    Additionally, we insert short gaps between synthesized chunks so the flow
    feels less like continuous talking and more like natural phrasing.
    """
    raw = (text or "").strip()
    if not raw:
        # Return a 1s silent WAV if something odd happens
        silent = AudioSegment.silent(duration=1000, frame_rate=44100)
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        silent.export(f.name, format="wav")
        return f.name

    # Convert [breath] to nothing (small prosody change is fine)
    raw = raw.replace("[breath]", " ")

    # Mark pauses with a sentinel so we can split and inject silence
    raw = raw.replace(_PAUSE_TOKEN, f" {_PAUSE_SENTINEL} ")

    blocks = [b.strip() for b in raw.split(_PAUSE_SENTINEL) if b.strip()]
    if not blocks:
        silent = AudioSegment.silent(duration=1000, frame_rate=44100)
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        silent.export(f.name, format="wav")
        return f.name

    segs: List[AudioSegment] = []
    PAUSE_MS = 900          # ~0.9s of silence for [pause]
    CHUNK_GAP_MS = 350      # ~0.35s between chunks for more natural pacing

    for block_idx, block in enumerate(blocks):
        parts = _split_text_into_chunks(block, max_chars=max_chars)
        for j, p in enumerate(parts):
            segs.append(_synth_chunk(p, voice_id, key))
            # Short gap between chunks inside the same block
            if j < len(parts) - 1:
                segs.append(AudioSegment.silent(duration=CHUNK_GAP_MS, frame_rate=44100))

        # Longer pause when the script explicitly used [pause]
        if block_idx < len(blocks) - 1:
            segs.append(AudioSegment.silent(duration=PAUSE_MS, frame_rate=44100))

    full = segs[0]
    for s in segs[1:]:
        full += s

    outf = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    full.export(outf.name, format="wav")
    return outf.name
