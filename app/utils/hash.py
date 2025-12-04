import hashlib, uuid, datetime as dt

def sid():
    return uuid.uuid4().hex[:12]

def md(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()[:12]

def stamp(fmt="%Y%m%d_%H%M%S"):
    return dt.datetime.utcnow().strftime(fmt)
