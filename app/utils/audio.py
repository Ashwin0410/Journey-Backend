# app/utils/audio.py
from __future__ import annotations
import re
from pathlib import Path
from typing import Tuple
from pydub import AudioSegment


_STAGE_DIR_RE = re.compile(
    r"^\s*(?:\[.*?\]|\(.*?\)|soft\s+instrumental\s+music\s+(?:begins|starts|fades)|background\s+music.*)$",
    re.IGNORECASE,
)

def clean_script(s: str) -> str:
    lines = []
    for raw in s.splitlines():
        t = raw.strip()
        if not t:
            continue
        if t.startswith("[") and t.endswith("]"):
            continue
        if t.startswith("(") and t.endswith(")"):
            continue
        if _STAGE_DIR_RE.search(t):
            continue
        lines.append(t)
    text = " ".join(lines)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def load_audio(path: str | Path) -> AudioSegment:
    p = str(path)
    
    return AudioSegment.from_file(p)

def normalize_dbfs(seg: AudioSegment, target_dbfs: float = -1.0) -> AudioSegment:
    change = target_dbfs - seg.dBFS
    return seg.apply_gain(change)

def loop_to(seg: AudioSegment, target_ms: int) -> AudioSegment:
    if len(seg) >= target_ms:
        return seg[:target_ms]
    reps = target_ms // len(seg) + 1
    out = seg * reps
    return out[:target_ms]

def make_stereo(seg: AudioSegment) -> AudioSegment:
    
    if seg.channels == 2:
        return seg
    return seg.set_channels(2)

def export_mp3(seg: AudioSegment, out_path: str | Path, bitrate: str = "192k") -> None:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    seg.export(str(out_path), format="mp3", bitrate=bitrate)

def duration_ms(seg: AudioSegment) -> int:
    return int(len(seg))
