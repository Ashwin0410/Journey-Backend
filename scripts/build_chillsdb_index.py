import os, json, hashlib
from pathlib import Path

root = os.environ.get("CHILL_ROOT", "./chillsdb")
out = Path(__file__).resolve().parents[1] / "app" / "assets" / "chillsdb_index.json"
p = Path(root)

if not p.exists():
    raise SystemExit(f"ChillsDB not found at {p}. Put your three folders under ./chillsdb")

tracks = []
for mp3 in p.rglob("*.mp3"):
    rel = mp3.relative_to(p).as_posix()
    folder = rel.split("/")[0] if "/" in rel else "root"
    tid = hashlib.md5(rel.encode()).hexdigest()[:12]
    tracks.append({"id": tid, "path": rel, "folder": folder})

out.parent.mkdir(parents=True, exist_ok=True)
with open(out, "w", encoding="utf-8") as f:
    json.dump({"root": str(p), "tracks": tracks}, f, ensure_ascii=False, indent=2)

print(f"Indexed {len(tracks)} tracks → {out}")
