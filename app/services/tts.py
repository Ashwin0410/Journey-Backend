import io
import re
import tempfile
from typing import List

import requests
from pydub import AudioSegment


_SENTENCE_SPLIT_RE = re.compile(r'(?<=[\.\!\?])\s+')
_PAUSE_TOKEN = "[pause]"
_PAUSE_SENTINEL = "<<<PAUSE>>>"


def _split_text_into_chunks(text: str, max_chars: int = 4600) -> List[str]:
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
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
    headers = {
        "xi-api-key": key,
        "accept": "audio/mpeg",
        "Content-Type": "application/json"
    }
    payload = {

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
    raw = (text or "").strip()
    if not raw:
        # Return a 1s silent WAV if something odd happens
        silent = AudioSegment.silent(duration=1000, frame_rate=44100)
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        silent.export(f.name, format="wav")
        return f.name


    raw = raw.replace("[breath]", " ")


    raw = raw.replace(_PAUSE_TOKEN, f" {_PAUSE_SENTINEL} ")

    blocks = [b.strip() for b in raw.split(_PAUSE_SENTINEL) if b.strip()]
    if not blocks:
        silent = AudioSegment.silent(duration=1000, frame_rate=44100)
        f = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        silent.export(f.name, format="wav")
        return f.name

    segs: List[AudioSegment] = []
    PAUSE_MS = 900  
    CHUNK_GAP_MS = 350

    for block_idx, block in enumerate(blocks):
        parts = _split_text_into_chunks(block, max_chars=max_chars)
        for j, p in enumerate(parts):
            segs.append(_synth_chunk(p, voice_id, key))
           
            if j < len(parts) - 1:
                segs.append(AudioSegment.silent(duration=CHUNK_GAP_MS, frame_rate=44100))

        
        if block_idx < len(blocks) - 1:
            segs.append(AudioSegment.silent(duration=PAUSE_MS, frame_rate=44100))

    full = segs[0]
    for s in segs[1:]:
        full += s

    outf = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    full.export(outf.name, format="wav")
    return outf.name
