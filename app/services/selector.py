import json
import os
import random
from pathlib import Path
from typing import List, Tuple, Optional


DAY_TO_TRACK_FILES = {
    # Day 1: Felix wants Freedom as the very first experience
    1: ["Audiosocket_29006482_Fullscore_Freedom"],

    # Day 2: epic, heavier arc
    2: ["Audiosocket_130059644_Inod_Epic Tragedy"],

    # Day 3: lighter heroic / rising
    3: ["Audiosocket_29004628_Fullscore_Heroes of World War II"],

    # Day 4: more reflective, cinematic
    4: ["Audiosocket_29265256_Wolfram Gruss_Le Voie Petit"],

    # Day 5: big trailer-style rise
    5: ["Audiosocket_29649772_Pat Andrews_The Battle for Freedom Trailer"],
}


MUSIC_TO_VOICES = {
    # Music 1 – inception
    "inception": [
        "qNkzaJoHLLdpvgh5tISm",  # Voice 1
        "bU2VfAdiOb2Gv2eZWlFq",  # Voice 2
        "9DY0k6JS3lZaUAIvDlAA",  # JJ
        "bTEswxYhpv7UDkQg5VRu",  # Sevan
    ],
    # Music 2 – interstellar
    "interstellar": [
        "qNkzaJoHLLdpvgh5tISm",  # Voice 1
        "bU2VfAdiOb2Gv2eZWlFq",  # Voice 2
        "9DY0k6JS3lZaUAIvDlAA",  # JJ
        "bTEswxYhpv7UDkQg5VRu",  # Sevan
    ],
    # Music 3 – think too much
    "think too much": [
        "eL7xfWghif0oJwtmX2qs",  # Kelly
        "Qggl4b0xRMiqOwhPtVWT",  # Clara
    ],
}


def _folder_key(folder: str) -> str:
    f = (folder or "").strip().lower()
    # split on first space so "1. inception" → ["1.", "inception"]
    parts = f.split(" ", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return f


def load_index() -> dict:
    p = Path(__file__).resolve().parents[1] / "assets" / "chillsdb_index.json"
    if not p.exists():
        raise RuntimeError("ChillsDB index not found. Run scripts/build_chillsdb_index.py")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def choose_folder(mood: str, schema: str) -> List[str]:
    mood = (mood or "").lower().strip()
    schema = (schema or "").lower().strip()

    # Schema-driven selection has priority
    if schema in {"failure", "subjugation"}:
        return ["1. inception"]
    if schema in {"unseen", "defectiveness", "abandonment"}:
        return ["2. interstellar"]
    if schema in {"overthinking", "rumination", "self-criticism"}:
        return ["3. think too much"]

    anxious_like = {
        "anxious", "sad", "heavy", "lonely",
        "restless", "stressed", "overthinking", "tense"
    }
    calm_like = {"calm", "hopeful", "reflective", "light", "peaceful"}
    driven_like = {"excited", "energized", "determined", "motivated", "confident"}

    if mood in anxious_like:
        return ["3. think too much"]
    if mood in calm_like:
        return ["2. interstellar"]
    if mood in driven_like:
        return ["1. inception"]

    # Fallback
    return ["2. interstellar"]


def _find_track_by_basenames(idx: dict, names: List[str]) -> Optional[Tuple[str, str, str, str]]:
    cand = {}
    for t in idx["tracks"]:
        bn = os.path.basename(t["path"])
        cand.setdefault(bn, t)
        root, _ = os.path.splitext(bn)
        cand.setdefault(root, t)
    for name in names:
        row = cand.get(name)
        if row:
            abs_path = os.path.join(idx["root"], row["path"])
            return row["id"], abs_path, row["folder"], os.path.basename(row["path"])
    return None


def pick_track_by_day(idx: dict, day: int) -> Optional[Tuple[str, str, str, str]]:
    names = DAY_TO_TRACK_FILES.get(day)
    if not names:
        return None
    return _find_track_by_basenames(idx, names)


def pick_track(idx: dict, folders: List[str], recent_ids: List[str]) -> Tuple[str, str, str, str]:
    recent = set(recent_ids or [])
    candidates = [
        t for t in idx["tracks"]
        if t.get("folder") in folders and t.get("id") not in recent
    ]
    if not candidates:
        candidates = [t for t in idx["tracks"] if t.get("folder") in folders]
    if not candidates:
        candidates = idx["tracks"]

    t = random.choice(candidates)
    abs_path = os.path.join(idx["root"], t["path"])
    return t["id"], abs_path, t["folder"], os.path.basename(t["path"])


def pick_voice(folder: str, cfg, recent_voice: Optional[str] = None) -> str:
    key = _folder_key(folder)

    # Base pool for this music; default to interstellar pool if unknown
    voices = MUSIC_TO_VOICES.get(key) or MUSIC_TO_VOICES.get("interstellar", [])

    # 🔒 Hard-ban JJ so it’s never selected
    voices = [v for v in voices if v != "9DY0k6JS3lZaUAIvDlAA"]

    # If nothing left, fall back to configured voices (also filter JJ)
    if not voices:
        fallback = [
            getattr(cfg, "VOICE_INCEPTION_PRIMARY", None),
            getattr(cfg, "VOICE_INCEPTION_SECONDARY", None),
            getattr(cfg, "VOICE_INTERSTELLAR_PRIMARY", None),
            getattr(cfg, "VOICE_INTERSTELLAR_SECONDARY", None),
            getattr(cfg, "VOICE_THINK_PRIMARY", None),
            getattr(cfg, "VOICE_THINK_SECONDARY", None),
        ]
        voices = [v for v in fallback if v and v != "9DY0k6JS3lZaUAIvDlAA"]

    if not voices:
        # Final safety fallback
        return ""

    # Avoid immediate repeat if possible
    if recent_voice in voices and len(voices) > 1:
        pool = [v for v in voices if v != recent_voice]
    else:
        pool = voices[:]

    return random.choice(pool)
