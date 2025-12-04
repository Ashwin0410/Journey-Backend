# ChillsTV Journey Backend

## Run

1. Put ChillsDB folders inside `./chillsdb/`:
   - `1. inception/`
   - `2. interstellar/`
   - `3. think too much/`
2. `pip install -r requirements.txt`
3. `python scripts/build_chillsdb_index.py`
4. `bash start.sh`
5. Open http://localhost:8000/api/health

## Key Endpoints

- `POST /api/journey/generate`
- `POST /api/journey/feedback`
- `GET  /api/health`
- Static audio: `/public/<filename>.mp3`

## Deploy

- Set `PUBLIC_BASE_URL` to your API domain (e.g., https://api.chillstv.com) and keep ALLOWED_ORIGINS with `http(s)://www.chillstv.com`.
