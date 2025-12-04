# # # app/services/selector.py
# # import json
# # import os
# # import random
# # from pathlib import Path
# # from typing import List, Tuple


# # def load_index() -> dict:
# #     p = Path(__file__).resolve().parents[1] / "assets" / "chillsdb_index.json"
# #     if not p.exists():
# #         raise RuntimeError("ChillsDB index not found. Run scripts/build_chillsdb_index.py")
# #     with open(p, "r", encoding="utf-8") as f:
# #         return json.load(f)


# # def choose_folder(mood: str, schema: str) -> List[str]:
# #     """Return a ranked list of internal music folders based on schema first, mood second."""
# #     mood = (mood or "").lower().strip()
# #     schema = (schema or "").lower().strip()

# #     # 1) Schema-first mapping (internal folder names; not shown to users)
# #     if schema in {"failure", "subjugation"}:
# #         return ["1. inception"]
# #     if schema in {"unseen", "defectiveness", "abandonment"}:
# #         return ["2. interstellar"]
# #     if schema in {"overthinking", "rumination", "self-criticism"}:
# #         return ["3. think too much"]

# #     # 2) Mood-based fallback if schema didn't match
# #     anxious_like = {"anxious", "sad", "heavy", "lonely", "restless", "stressed", "overthinking"}
# #     calm_like    = {"calm", "hopeful", "reflective", "light", "peaceful"}
# #     driven_like  = {"excited", "energized", "determined", "motivated", "confident"}

# #     if mood in anxious_like:
# #         return ["3. think too much"]
# #     if mood in calm_like:
# #         return ["2. interstellar"]
# #     if mood in driven_like:
# #         return ["1. inception"]

# #     # 3) Default
# #     return ["2. interstellar"]


# # def pick_track(idx: dict, folders: List[str], recent_ids: List[str]) -> Tuple[str, str, str, str]:
# #     """
# #     Choose a track not in recent_ids, filtered by desired folders.
# #     Returns: (track_id, absolute_music_path, folder_name, music_filename)
# #     """
# #     recent = set(recent_ids or [])
# #     candidates = [t for t in idx["tracks"] if t.get("folder") in folders and t.get("id") not in recent]
# #     if not candidates:
# #         candidates = [t for t in idx["tracks"] if t.get("folder") in folders]
# #     if not candidates:
# #         candidates = idx["tracks"]

# #     t = random.choice(candidates)
# #     abs_path = os.path.join(idx["root"], t["path"])
# #     return t["id"], abs_path, t["folder"], os.path.basename(t["path"])


# # def pick_voice(folder: str, cfg) -> str:
# #     """Map internal folder to voice id."""
# #     if folder.startswith("1."):
# #         return cfg.VOICE_INCEPTION_PRIMARY
# #     if folder.startswith("2."):
# #         return cfg.VOICE_INTERSTELLAR_PRIMARY
# #     return cfg.VOICE_THINK_PRIMARY
# # app/services/selector.py
# import json
# import os
# import random
# from pathlib import Path
# from typing import List, Tuple, Optional


# def load_index() -> dict:
#     p = Path(__file__).resolve().parents[1] / "assets" / "chillsdb_index.json"
#     if not p.exists():
#         raise RuntimeError("ChillsDB index not found. Run scripts/build_chillsdb_index.py")
#     with open(p, "r", encoding="utf-8") as f:
#         return json.load(f)


# def choose_folder(mood: str, schema: str) -> List[str]:
#     """Return a single desired folder based on schema first, mood second."""
#     mood = (mood or "").lower().strip()
#     schema = (schema or "").lower().strip()

#     # 1) Schema-first mapping (internal folder names; not shown to users)
#     if schema in {"failure", "subjugation"}:
#         return ["1. inception"]
#     if schema in {"unseen", "defectiveness", "abandonment"}:
#         return ["2. interstellar"]
#     if schema in {"overthinking", "rumination", "self-criticism"}:
#         return ["3. think too much"]

#     # 2) Mood-based fallback if schema didn't match
#     anxious_like = {"anxious", "sad", "heavy", "lonely", "restless", "stressed", "overthinking", "tense"}
#     calm_like    = {"calm", "hopeful", "reflective", "light", "peaceful"}
#     driven_like  = {"excited", "energized", "determined", "motivated", "confident"}

#     if mood in anxious_like:
#         return ["3. think too much"]
#     if mood in calm_like:
#         return ["2. interstellar"]
#     if mood in driven_like:
#         return ["1. inception"]

#     # 3) Default
#     return ["2. interstellar"]


# def pick_track(idx: dict, folders: List[str], recent_ids: List[str]) -> Tuple[str, str, str, str]:
#     """
#     Choose a track not in recent_ids, filtered by desired folders.
#     Returns: (track_id, absolute_music_path, folder_name, music_filename)
#     """
#     recent = set(recent_ids or [])
#     candidates = [t for t in idx["tracks"] if t.get("folder") in folders and t.get("id") not in recent]
#     if not candidates:
#         candidates = [t for t in idx["tracks"] if t.get("folder") in folders]
#     if not candidates:
#         candidates = idx["tracks"]

#     t = random.choice(candidates)
#     abs_path = os.path.join(idx["root"], t["path"])
#     return t["id"], abs_path, t["folder"], os.path.basename(t["path"])


# def pick_voice(folder: str, cfg, recent_voice: Optional[str] = None) -> str:
#     """
#     Map internal folder to a rotating voice set.
#     Avoids immediately repeating the same voice for the same user when possible.
#     """
#     f = (folder or "").strip().lower()

#     def _clean_pool(xs):
#         return [v for v in xs if v]  # drop None/empty

#     if f.startswith("1."):  # inception
#         pool = _clean_pool([
#             cfg.VOICE_INCEPTION_PRIMARY,
#             cfg.VOICE_INCEPTION_SECONDARY,
#             cfg.VOICE_JJ,
#             cfg.VOICE_SEVAN,
#         ])
#     elif f.startswith("2."):  # interstellar
#         pool = _clean_pool([
#             cfg.VOICE_INTERSTELLAR_PRIMARY,
#             cfg.VOICE_INTERSTELLAR_SECONDARY,
#             cfg.VOICE_JJ,
#             cfg.VOICE_SEVAN,
#         ])
#     else:  # think too much
#         pool = _clean_pool([
#             cfg.VOICE_THINK_PRIMARY,
#             cfg.VOICE_THINK_SECONDARY,
#         ])

#     # Avoid immediate repeat if possible
#     if recent_voice and recent_voice in pool and len(pool) > 1:
#         pool = [v for v in pool if v != recent_voice]

#     # Fallback: if pool somehow empty, prefer THINK primary
#     return random.choice(pool) if pool else (cfg.VOICE_THINK_PRIMARY or cfg.VOICE_INCEPTION_PRIMARY or "")
# app/services/selector.py
# import json
# import os
# import random
# from pathlib import Path
# from typing import List, Tuple, Optional

# # Day -> ordered list of preferred music basenames (match your index "path" basenames)
# DAY_TO_TRACK_FILES = {
#     1: ["Audiosocket_29004628_Fullscore_Heroes of World War II"],
#     2: ["Audiosocket_130059644_Inod_Epic Tragedy"],
#     3: [
#         "Audiosocket_29006482_Fullscore_Freedom",
#         "Audiosocket_29332810_Matthew Raetzel_Cult",
#     ],
#     4: ["Audiosocket_29265256_Wolfram Gruss_Le Voie Petit.mp3"],
#     5: [
#         "Audiosocket_42825406_Paul Werner_Rise From The Shadows",
#         "Audiosocket_29154472_In The Nursery_Itn 5",
#     ],
# }


# def load_index() -> dict:
#     p = Path(__file__).resolve().parents[1] / "assets" / "chillsdb_index.json"
#     if not p.exists():
#         raise RuntimeError("ChillsDB index not found. Run scripts/build_chillsdb_index.py")
#     with open(p, "r", encoding="utf-8") as f:
#         return json.load(f)


# def choose_folder(mood: str, schema: str) -> List[str]:
#     mood = (mood or "").lower().strip()
#     schema = (schema or "").lower().strip()

#     if schema in {"failure", "subjugation"}:
#         return ["1. inception"]
#     if schema in {"unseen", "defectiveness", "abandonment"}:
#         return ["2. interstellar"]
#     if schema in {"overthinking", "rumination", "self-criticism"}:
#         return ["3. think too much"]

#     anxious_like = {"anxious", "sad", "heavy", "lonely", "restless", "stressed", "overthinking", "tense"}
#     calm_like    = {"calm", "hopeful", "reflective", "light", "peaceful"}
#     driven_like  = {"excited", "energized", "determined", "motivated", "confident"}

#     if mood in anxious_like:
#         return ["3. think too much"]
#     if mood in calm_like:
#         return ["2. interstellar"]
#     if mood in driven_like:
#         return ["1. inception"]
#     return ["2. interstellar"]


# def _find_track_by_basenames(idx: dict, names: List[str]) -> Optional[Tuple[str, str, str, str]]:
#     # build basename -> row map (also map without extension)
#     cand = {}
#     for t in idx["tracks"]:
#         bn = os.path.basename(t["path"])
#         cand.setdefault(bn, t)
#         root, _ = os.path.splitext(bn)
#         cand.setdefault(root, t)
#     for name in names:
#         row = cand.get(name)
#         if row:
#             abs_path = os.path.join(idx["root"], row["path"])
#             return row["id"], abs_path, row["folder"], os.path.basename(row["path"])
#     return None


# def pick_track_by_day(idx: dict, day: int) -> Optional[Tuple[str, str, str, str]]:
#     names = DAY_TO_TRACK_FILES.get(day)
#     if not names:
#         return None
#     return _find_track_by_basenames(idx, names)


# def pick_track(idx: dict, folders: List[str], recent_ids: List[str]) -> Tuple[str, str, str, str]:
#     recent = set(recent_ids or [])
#     candidates = [t for t in idx["tracks"] if t.get("folder") in folders and t.get("id") not in recent]
#     if not candidates:
#         candidates = [t for t in idx["tracks"] if t.get("folder") in folders]
#     if not candidates:
#         candidates = idx["tracks"]
#     t = random.choice(candidates)
#     abs_path = os.path.join(idx["root"], t["path"])
#     return t["id"], abs_path, t["folder"], os.path.basename(t["path"])


# def pick_voice(folder: str, cfg, recent_voice: Optional[str] = None) -> str:
#     """
#     Privilege Sevan + Carter globally; then fall back to folder voices.
#     Avoid immediate repeats when possible.
#     """
#     f = (folder or "").strip().lower()

#     def _clean(xs): 
#         return [v for v in xs if v]

#     # privileged voices first (will come from .env or defaults)
#     priority_pool = _clean([
#         getattr(cfg, "VOICE_SEVAN", None),
#         getattr(cfg, "VOICE_CARTER", None),
#     ])

#     if f.startswith("1."):       # inception
#         thematic = _clean([cfg.VOICE_INCEPTION_PRIMARY, cfg.VOICE_INCEPTION_SECONDARY])
#     elif f.startswith("2."):     # interstellar
#         thematic = _clean([cfg.VOICE_INTERSTELLAR_PRIMARY, cfg.VOICE_INTERSTELLAR_SECONDARY])
#     else:                        # think too much
#         thematic = _clean([cfg.VOICE_THINK_PRIMARY, cfg.VOICE_THINK_SECONDARY])

#     pool = _clean(priority_pool + thematic)

#     if recent_voice and recent_voice in pool and len(pool) > 1:
#         pool = [v for v in pool if v != recent_voice]

#     random.shuffle(pool)
#     return pool[0] if pool else (getattr(cfg, "VOICE_SEVAN", None) 
#                                  or getattr(cfg, "VOICE_CARTER", None) 
#                                  or cfg.VOICE_THINK_PRIMARY 
#                                  or "")




# The Previous best Code
# import json
# import os
# import random
# from pathlib import Path
# from typing import List, Tuple, Optional

# # ---------------- Day → specific tracks ----------------

# # Day -> ordered list of preferred music basenames (match your index "path" basenames)
# DAY_TO_TRACK_FILES = {
#     1: ["Audiosocket_29004628_Fullscore_Heroes of World War II"],
#     2: ["Audiosocket_130059644_Inod_Epic Tragedy"],
#     3: [
#         "Audiosocket_29006482_Fullscore_Freedom",
#         "Audiosocket_29332810_Matthew Raetzel_Cult",
#     ],
#     4: ["Audiosocket_29265256_Wolfram Gruss_Le Voie Petit.mp3"],
#     5: [
#         "Audiosocket_42825406_Paul Werner_Rise From The Shadows",
#         "Audiosocket_29154472_In The Nursery_Itn 5",
#     ],
# }

# # ---------------- Music → Voices mapping ----------------
# # Folder names in the index are like:
# #   "1. inception", "2. interstellar", "3. think too much"
# #
# # We normalise that to a key and then map to fixed ElevenLabs voice IDs.

# MUSIC_TO_VOICES = {
#     # Music 1 – inception
#     "inception": [
#         "qNkzaJoHLLdpvgh5tISm",  # Voice 1
#         "bU2VfAdiOb2Gv2eZWlFq",  # Voice 2
#         "9DY0k6JS3lZaUAIvDlAA",  # JJ
#         "bTEswxYhpv7UDkQg5VRu",  # Sevan
#     ],
#     # Music 2 – interstellar
#     "interstellar": [
#         "qNkzaJoHLLdpvgh5tISm",  # Voice 1
#         "bU2VfAdiOb2Gv2eZWlFq",  # Voice 2
#         "9DY0k6JS3lZaUAIvDlAA",  # JJ
#         "bTEswxYhpv7UDkQg5VRu",  # Sevan
#     ],
#     # Music 3 – think too much
#     "think too much": [
#         "eL7xfWghif0oJwtmX2qs",  # Kelly
#         "Qggl4b0xRMiqOwhPtVWT",  # Clara
#     ],
# }


# def _folder_key(folder: str) -> str:
#     """
#     Normalise folder name like '1. inception' → 'inception',
#     '2. interstellar' → 'interstellar', '3. think too much' → 'think too much'.
#     """
#     f = (folder or "").strip().lower()
#     # split on first space so "1. inception" → ["1.", "inception"]
#     parts = f.split(" ", 1)
#     if len(parts) == 2:
#         return parts[1].strip()
#     return f


# # ---------------- Index helpers ----------------

# def load_index() -> dict:
#     p = Path(__file__).resolve().parents[1] / "assets" / "chillsdb_index.json"
#     if not p.exists():
#         raise RuntimeError("ChillsDB index not found. Run scripts/build_chillsdb_index.py")
#     with open(p, "r", encoding="utf-8") as f:
#         return json.load(f)


# def choose_folder(mood: str, schema: str) -> List[str]:
#     """
#     Map mood + schema to one of the three Journey music folders:
#       - '1. inception'
#       - '2. interstellar'
#       - '3. think too much'
#     """
#     mood = (mood or "").lower().strip()
#     schema = (schema or "").lower().strip()

#     # Schema-driven selection has priority
#     if schema in {"failure", "subjugation"}:
#         return ["1. inception"]
#     if schema in {"unseen", "defectiveness", "abandonment"}:
#         return ["2. interstellar"]
#     if schema in {"overthinking", "rumination", "self-criticism"}:
#         return ["3. think too much"]

#     anxious_like = {
#         "anxious", "sad", "heavy", "lonely",
#         "restless", "stressed", "overthinking", "tense"
#     }
#     calm_like = {"calm", "hopeful", "reflective", "light", "peaceful"}
#     driven_like = {"excited", "energized", "determined", "motivated", "confident"}

#     if mood in anxious_like:
#         return ["3. think too much"]
#     if mood in calm_like:
#         return ["2. interstellar"]
#     if mood in driven_like:
#         return ["1. inception"]

#     # Fallback
#     return ["2. interstellar"]


# def _find_track_by_basenames(idx: dict, names: List[str]) -> Optional[Tuple[str, str, str, str]]:
#     # build basename -> row map (also map without extension)
#     cand = {}
#     for t in idx["tracks"]:
#         bn = os.path.basename(t["path"])
#         cand.setdefault(bn, t)
#         root, _ = os.path.splitext(bn)
#         cand.setdefault(root, t)
#     for name in names:
#         row = cand.get(name)
#         if row:
#             abs_path = os.path.join(idx["root"], row["path"])
#             return row["id"], abs_path, row["folder"], os.path.basename(row["path"])
#     return None


# def pick_track_by_day(idx: dict, day: int) -> Optional[Tuple[str, str, str, str]]:
#     names = DAY_TO_TRACK_FILES.get(day)
#     if not names:
#         return None
#     return _find_track_by_basenames(idx, names)


# def pick_track(idx: dict, folders: List[str], recent_ids: List[str]) -> Tuple[str, str, str, str]:
#     """
#     Pick one track from the requested folders, avoiding recently used IDs when possible.
#     Returns: (track_id, abs_path, folder, basename)
#     """
#     recent = set(recent_ids or [])
#     candidates = [
#         t for t in idx["tracks"]
#         if t.get("folder") in folders and t.get("id") not in recent
#     ]
#     if not candidates:
#         candidates = [t for t in idx["tracks"] if t.get("folder") in folders]
#     if not candidates:
#         candidates = idx["tracks"]

#     t = random.choice(candidates)
#     abs_path = os.path.join(idx["root"], t["path"])
#     return t["id"], abs_path, t["folder"], os.path.basename(t["path"])


# # ---------------- Voice selection ----------------

# def pick_voice(folder: str, cfg, recent_voice: Optional[str] = None) -> str:
#     """
#     Pick a voice based on the chosen music folder.

#     Mapping (hard-coded for now):

#       - '1. inception'     → Voice1, Voice2, JJ, Sevan
#       - '2. interstellar'  → Voice1, Voice2, JJ, Sevan
#       - '3. think too much'→ Kelly, Clara

#     We avoid immediate repeats using `recent_voice` when possible.
#     """
#     key = _folder_key(folder)

#     # Get the configured pool for this music; default to interstellar pool if unknown
#     voices = MUSIC_TO_VOICES.get(key) or MUSIC_TO_VOICES.get("interstellar", [])

#     # If nothing configured at all (extreme edge case), fall back to any non-empty VOICE_* in cfg
#     if not voices:
#         fallback = [
#             getattr(cfg, "VOICE_INCEPTION_PRIMARY", None),
#             getattr(cfg, "VOICE_INCEPTION_SECONDARY", None),
#             getattr(cfg, "VOICE_INTERSTELLAR_PRIMARY", None),
#             getattr(cfg, "VOICE_INTERSTELLAR_SECONDARY", None),
#             getattr(cfg, "VOICE_THINK_PRIMARY", None),
#             getattr(cfg, "VOICE_THINK_SECONDARY", None),
#         ]
#         voices = [v for v in fallback if v]

#     if not voices:
#         # Really hard fallback – better than returning an empty string
#         return ""

#     # Avoid immediate repeat if possible
#     if recent_voice in voices and len(voices) > 1:
#         pool = [v for v in voices if v != recent_voice]
#     else:
#         pool = voices[:]

#     return random.choice(pool)




import json
import os
import random
from pathlib import Path
from typing import List, Tuple, Optional

# ---------------- Day → specific tracks ----------------

# Day -> ordered list of preferred music basenames (match your index "path" basenames)
#    ❗ Basenames only: SAME text as in chillsdb folder, extension optional.
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

# ---------------- Music → Voices mapping ----------------
# Folder names in the index are like:
#   "1. inception", "2. interstellar", "3. think too much"
#
# We normalise that to a key and then map to fixed ElevenLabs voice IDs.

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
    """
    Normalise folder name like '1. inception' → 'inception',
    '2. interstellar' → 'interstellar', '3. think too much' → 'think too much'.
    """
    f = (folder or "").strip().lower()
    # split on first space so "1. inception" → ["1.", "inception"]
    parts = f.split(" ", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return f


# ---------------- Index helpers ----------------

def load_index() -> dict:
    p = Path(__file__).resolve().parents[1] / "assets" / "chillsdb_index.json"
    if not p.exists():
        raise RuntimeError("ChillsDB index not found. Run scripts/build_chillsdb_index.py")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def choose_folder(mood: str, schema: str) -> List[str]:
    """
    Map mood + schema to one of the three Journey music folders:
      - '1. inception'
      - '2. interstellar'
      - '3. think too much'
    """
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
    # build basename -> row map (also map without extension)
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
    """
    Pick one track from the requested folders, avoiding recently used IDs when possible.
    Returns: (track_id, abs_path, folder, basename)
    """
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


# ---------------- Voice selection ----------------

def pick_voice(folder: str, cfg, recent_voice: Optional[str] = None) -> str:
    """
    Pick a voice based on the chosen music folder.

    Mapping (hard-coded for now):

      - '1. inception'     → Voice1, Voice2, JJ, Sevan
      - '2. interstellar'  → Voice1, Voice2, JJ, Sevan
      - '3. think too much'→ Kelly, Clara

    We avoid immediate repeats using `recent_voice` when possible.
    """
    key = _folder_key(folder)

    # Get the configured pool for this music; default to interstellar pool if unknown
    voices = MUSIC_TO_VOICES.get(key) or MUSIC_TO_VOICES.get("interstellar", [])

    # If nothing configured at all (extreme edge case), fall back to any non-empty VOICE_* in cfg
    if not voices:
        fallback = [
            getattr(cfg, "VOICE_INCEPTION_PRIMARY", None),
            getattr(cfg, "VOICE_INCEPTION_SECONDARY", None),
            getattr(cfg, "VOICE_INTERSTELLAR_PRIMARY", None),
            getattr(cfg, "VOICE_INTERSTELLAR_SECONDARY", None),
            getattr(cfg, "VOICE_THINK_PRIMARY", None),
            getattr(cfg, "VOICE_THINK_SECONDARY", None),
        ]
        voices = [v for v in fallback if v]

    if not voices:
        # Really hard fallback – better than returning an empty string
        return ""

    # Avoid immediate repeat if possible
    if recent_voice in voices and len(voices) > 1:
        pool = [v for v in voices if v != recent_voice]
    else:
        pool = voices[:]

    return random.choice(pool)
