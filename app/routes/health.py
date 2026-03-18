from fastapi import APIRouter

r = APIRouter()

@r.get("/api/health")
def health():
    return {"ok": True}
