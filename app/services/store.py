from pathlib import Path

def public_url(base: str, filename: str) -> str:
    return base.rstrip("/") + "/public/" + filename

def ensure_dir(p: str):
    Path(p).mkdir(parents=True, exist_ok=True)

def out_file(base_dir: str, sid: str) -> str:
    return str(Path(base_dir) / f"journey_{sid}.mp3")
