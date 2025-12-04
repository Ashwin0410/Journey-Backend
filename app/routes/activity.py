# app/routes/activity.py

# from __future__ import annotations

# import json
# from datetime import datetime
# from typing import List, Optional, Tuple

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session

# from app.db import SessionLocal
# from app import models, schemas
# from app.core.config import cfg as c

# # ---------------- OpenAI setup ----------------

# from openai import OpenAI

# # use the same OPENAI_API_KEY as your script generator
# client = OpenAI(api_key=c.OPENAI_API_KEY)
# OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

# r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])


# # ---------------- DB dependency ----------------

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---------------- Google Maps helpers ----------------

# def _geocode_postal_code(postal_code: str) -> Optional[Tuple[float, float]]:
#     """
#     postal_code -> (lat, lng) using Google Geocoding.
#     Returns None on any error so we can gracefully fall back.
#     """
#     if not c.GOOGLE_MAPS_API_KEY or not postal_code:
#         return None

#     url = "https://maps.googleapis.com/maps/api/geocode/json"
#     params = {"address": postal_code, "key": c.GOOGLE_MAPS_API_KEY}

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#         if data.get("status") != "OK":
#             return None
#         loc = data["results"][0]["geometry"]["location"]
#         return float(loc["lat"]), float(loc["lng"])
#     except Exception:
#         return None


# def _nearby_parks(
#     lat: float,
#     lng: float,
#     radius_m: int = 2500,
#     max_results: int = 5,
# ) -> List[str]:
#     """
#     Use Google Places to find nearby parks by name.
#     Returns a list of place names like ["Sefton Park", "Otterspool Promenade", ...]
#     """
#     if not c.GOOGLE_MAPS_API_KEY:
#         return []

#     url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
#     params = {
#         "location": f"{lat},{lng}",
#         "radius": radius_m,
#         "type": "park",
#         "key": c.GOOGLE_MAPS_API_KEY,
#     }

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#     except Exception:
#         return []

#     results = data.get("results") or []
#     names: List[str] = []
#     for r_ in results[:max_results]:
#         name = r_.get("name")
#         if name:
#             names.append(name.strip())
#     return names


# # ---------------- OpenAI helper ----------------

# def _generate_activities_via_llm(
#     *,
#     mood: Optional[str],
#     schema_hint: Optional[str],
#     postal_code: Optional[str],
#     goal_today: Optional[str],
#     place: Optional[str],
#     count: int = 5,
# ) -> List[schemas.ActivityBase]:
#     """
#     Call OpenAI to generate a small set of concrete BA activities.
#     If possible, we include real nearby parks based on postal_code.
#     """

#     # --- build context text ---
#     context_bits: List[str] = []
#     if mood:
#         context_bits.append(f"current mood: {mood}")
#     if schema_hint:
#         context_bits.append(f"schema or core story: {schema_hint}")
#     if goal_today:
#         context_bits.append(f"today's goal: {goal_today}")
#     if place:
#         context_bits.append(f"preferred environment: {place}")
#     if postal_code:
#         context_bits.append(f"postal code: {postal_code}")

#     coords: Optional[Tuple[float, float]] = None
#     if postal_code:
#         coords = _geocode_postal_code(postal_code)

#     if coords:
#         lat, lng = coords
#         parks = _nearby_parks(lat, lng)
#         if parks:
#             context_bits.append("nearby_parks: " + ", ".join(parks))

#     context_text = "; ".join(context_bits) or "no extra context provided"

#     system_msg = (
#         "You are a behavioural activation coach designing very small, realistic, "
#         "real-world activities for a mental health app.\n"
#         "Each activity must be:\n"
#         "- concrete and doable in 5–30 minutes\n"
#         "- safe and gentle (no extreme exercise, no unsafe locations)\n"
#         "- described in simple language\n"
#         "- when you reference their area, prefer actual nearby places given to you, "
#         "such as specific parks or promenades.\n\n"
#         "Life areas can be: Social, Body, Work, Meaning, Self-compassion.\n"
#         "Effort level: 'low', 'medium', or 'high'.\n"
#         "Reward type: 'calm', 'connection', 'mastery', 'movement', or similar.\n"
#     )

#     user_msg = (
#         f"User context: {context_text}\n\n"
#         f"Generate {count} candidate activities that could help this person take "
#         f"a small step in a valued direction.\n\n"
#         "If you received a list of nearby_parks, explicitly use one or two of them "
#         "by name in the activities (e.g., 'Walk one lap around Sefton Park').\n\n"
#         "Return ONLY JSON in this exact format (no extra commentary):\n"
#         "{\n"
#         '  \"activities\": [\n'
#         "    {\n"
#         '      \"title\": \"short name\",\n'
#         '      \"description\": \"2–3 sentence description of what to do\",\n'
#         '      \"life_area\": \"Social | Body | Work | Meaning | Self-compassion\",\n'
#         '      \"effort_level\": \"low | medium | high\",\n'
#         '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
#         '      \"default_duration_min\": 5,\n'
#         '      \"location_label\": \"Sefton Park / nearby promenade / indoors / etc.\",\n'
#         '      \"tags\": [\"+ Social\", \"+ Body\"]\n'
#         "    }\n"
#         "  ]\n"
#         "}"
#     )

#     # Use new v1 chat completions client
#     try:
#         resp = client.chat.completions.create(
#             model=OPENAI_ACTIVITY_MODEL,
#             messages=[
#                 {"role": "system", "content": system_msg},
#                 {"role": "user", "content": user_msg},
#             ],
#             temperature=0.7,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")

#     # Parse JSON from model output
#     try:
#         content = resp.choices[0].message.content
#         data = json.loads(content)
#         items = data.get("activities") or []
#     except json.JSONDecodeError:
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to parse OpenAI JSON for activities",
#         )

#     activities: List[schemas.ActivityBase] = []
#     for item in items:
#         try:
#             act = schemas.ActivityBase(
#                 title=(item.get("title") or "").strip() or "Small step",
#                 description=(item.get("description") or "").strip()
#                 or "Take a small helpful step.",
#                 life_area=item.get("life_area", "Meaning"),
#                 effort_level=item.get("effort_level", "low"),
#                 reward_type=item.get("reward_type"),
#                 default_duration_min=item.get("default_duration_min") or 10,
#                 location_label=item.get("location_label"),
#                 tags=item.get("tags") or [],
#             )
#             activities.append(act)
#         except Exception:
#             continue

#     if not activities:
#         raise HTTPException(status_code=500, detail="OpenAI returned no valid activities")

#     return activities


# # --------- Store generated activities in DB (no global cache) ---------


# def _store_generated_activities(
#     db: Session,
#     *,
#     activities: List[schemas.ActivityBase],
# ) -> List[models.Activities]:
#     """
#     Persist a batch of generated activities.
#     We do NOT reuse previous batches for new recommendations – each call
#     can create its own activities tied to that moment / context.
#     """
#     now = datetime.utcnow()
#     rows: List[models.Activities] = []

#     for a in activities:
#         row = models.Activities(
#             title=a.title,
#             description=a.description,
#             life_area=a.life_area,
#             effort_level=a.effort_level,
#             reward_type=a.reward_type,
#             default_duration_min=a.default_duration_min,
#             location_label=a.location_label,
#             tags_json=json.dumps(a.tags or []),
#             is_active=True,
#             created_at=now,
#         )
#         db.add(row)
#         rows.append(row)

#     db.commit()
#     for r_obj in rows:
#         db.refresh(r_obj)

#     return rows


# # ---------------- Public endpoints ----------------

# @r.get(
#     "/recommendation",
#     response_model=schemas.ActivityRecommendationOut,
#     summary="Get Recommendation",
# )
# def get_recommendation(
#     user_hash: Optional[str] = Query(None, description="Optional user hash"),
#     life_area: Optional[str] = Query(None, description="Preferred life area, e.g., 'Social'"),
#     mood: Optional[str] = Query(None, description="Current mood (from intake)"),
#     schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
#     postal_code: Optional[str] = Query(None, description="Postal code, e.g., L18 2QA"),
#     goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
#     place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return one LLM-generated BA activity, tailored to *this* request.
#     We always generate a fresh batch with OpenAI for this context,
#     then store them in the DB for logging / later inspection.
#     """

#     generated = _generate_activities_via_llm(
#         mood=mood,
#         schema_hint=schema_hint,
#         postal_code=postal_code,
#         goal_today=goal_today,
#         place=place,
#         count=5,
#     )

#     rows = _store_generated_activities(db, activities=generated)

#     # Optional life_area filter over this batch only
#     if life_area:
#         filtered = [
#             r_
#             for r_ in rows
#             if (r_.life_area or "").lower() == life_area.lower()
#         ]
#         candidates = filtered or rows
#     else:
#         candidates = rows

#     if not candidates:
#         raise HTTPException(status_code=404, detail="No activities available")

#     # pick the most recent row from this batch
#     act = sorted(
#         candidates,
#         key=lambda x: x.created_at or datetime.utcnow(),
#         reverse=True,
#     )[0]

#     tags: List[str] = []
#     if act.tags_json:
#         try:
#             tags = json.loads(act.tags_json)
#         except Exception:
#             tags = []

#     return schemas.ActivityRecommendationOut(
#         id=act.id,
#         title=act.title,
#         description=act.description,
#         life_area=act.life_area,
#         effort_level=act.effort_level,
#         reward_type=act.reward_type,
#         default_duration_min=act.default_duration_min,
#         location_label=act.location_label,
#         tags=tags,
#     )


# @r.get(
#     "/library",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library",
# )
# def get_library(
#     db: Session = Depends(get_db),
# ):
#     """
#     Return the full activity library.
#     This is basically all activities that have ever been generated and stored.
#     """

#     acts = (
#         db.query(models.Activities)
#         .filter(models.Activities.is_active == True)
#         .order_by(models.Activities.created_at.desc())
#         .all()
#     )

#     out: List[schemas.ActivityOut] = []
#     for a in acts:
#         tags: List[str] = []
#         if a.tags_json:
#             try:
#                 tags = json.loads(a.tags_json)
#             except Exception:
#                 tags = []
#         out.append(
#             schemas.ActivityOut(
#                 id=a.id,
#                 title=a.title,
#                 description=a.description,
#                 life_area=a.life_area,
#                 effort_level=a.effort_level,
#                 reward_type=a.reward_type,
#                 default_duration_min=a.default_duration_min,
#                 location_label=a.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityListOut(activities=out)


# @r.post(
#     "/start",
#     summary="Start Activity",
# )
# def start_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=act.id,
#         session_id=payload.session_id,
#         status="started",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()

#     return {"ok": True}


# @r.post(
#     "/swap",
#     summary="Swap Activity",
# )
# def swap_activity(
#     payload: schemas.ActivitySwapIn,
#     db: Session = Depends(get_db),
# ):
#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=payload.activity_id,
#         status="swapped",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     return {"ok": True}

# app/routes/activity.py

# from __future__ import annotations

# import json
# from datetime import datetime
# from typing import List, Optional, Tuple

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session

# from app.db import SessionLocal
# from app import models, schemas
# from app.core.config import cfg as c

# # ---------------- OpenAI setup ----------------

# from openai import OpenAI

# # use the same OPENAI_API_KEY as your script generator
# client = OpenAI(api_key=c.OPENAI_API_KEY)
# OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

# r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])


# # ---------------- DB dependency ----------------

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---------------- Google Maps helpers ----------------

# def _geocode_postal_code(postal_code: str) -> Optional[Tuple[float, float]]:
#     """
#     postal_code -> (lat, lng) using Google Geocoding.
#     Returns None on any error so we can gracefully fall back.
#     """
#     if not c.GOOGLE_MAPS_API_KEY or not postal_code:
#         return None

#     url = "https://maps.googleapis.com/maps/api/geocode/json"
#     params = {"address": postal_code, "key": c.GOOGLE_MAPS_API_KEY}

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#         if data.get("status") != "OK":
#             return None
#         loc = data["results"][0]["geometry"]["location"]
#         return float(loc["lat"]), float(loc["lng"])
#     except Exception:
#         return None


# def _nearby_parks(
#     lat: float,
#     lng: float,
#     radius_m: int = 2500,
#     max_results: int = 5,
# ) -> List[str]:
#     """
#     Use Google Places to find nearby parks by name.
#     Returns a list of place names like ["Sefton Park", "Otterspool Promenade", ...]
#     """
#     if not c.GOOGLE_MAPS_API_KEY:
#         return []

#     url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
#     params = {
#         "location": f"{lat},{lng}",
#         "radius": radius_m,
#         "type": "park",
#         "key": c.GOOGLE_MAPS_API_KEY,
#     }

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#     except Exception:
#         return []

#     results = data.get("results") or []
#     names: List[str] = []
#     for r_ in results[:max_results]:
#         name = r_.get("name")
#         if name:
#             names.append(name.strip())
#     return names


# # ---------------- OpenAI helper ----------------

# def _generate_activities_via_llm(
#     *,
#     mood: Optional[str],
#     schema_hint: Optional[str],
#     postal_code: Optional[str],
#     goal_today: Optional[str],
#     place: Optional[str],
#     count: int = 3,
# ) -> List[schemas.ActivityBase]:
#     """
#     Call OpenAI to generate a small set of concrete BA activities.
#     If possible, we include real nearby parks based on postal_code.
#     """

#     # --- build context text ---
#     context_bits: List[str] = []
#     if mood:
#         context_bits.append(f"current mood: {mood}")
#     if schema_hint:
#         context_bits.append(f"schema or core story: {schema_hint}")
#     if goal_today:
#         context_bits.append(f"today's goal: {goal_today}")
#     if place:
#         context_bits.append(f"preferred environment: {place}")
#     if postal_code:
#         context_bits.append(f"postal code: {postal_code}")

#     coords: Optional[Tuple[float, float]] = None
#     if postal_code:
#         coords = _geocode_postal_code(postal_code)

#     if coords:
#         lat, lng = coords
#         parks = _nearby_parks(lat, lng)
#         if parks:
#             context_bits.append("nearby_parks: " + ", ".join(parks))

#     context_text = "; ".join(context_bits) or "no extra context provided"

#     system_msg = (
#         "You are a behavioural activation coach designing very small, realistic, "
#         "real-world activities for a mental health app.\n"
#         "Each activity must be:\n"
#         "- concrete and doable in 5–30 minutes\n"
#         "- safe and gentle (no extreme exercise, no unsafe locations)\n"
#         "- described in simple language\n"
#         "- when you reference their area, prefer actual nearby places given to you, "
#         "such as specific parks or promenades.\n"
#         "- Do NOT invent place names like 'Sefton Park' unless they appear explicitly "
#         "in the nearby_parks list.\n\n"
#         "Life areas can be: Social, Body, Work, Meaning, Self-compassion.\n"
#         "Effort level: 'low', 'medium', or 'high'.\n"
#         "Reward type: 'calm', 'connection', 'mastery', 'movement', or similar.\n"
#     )

#     user_msg = (
#         f"User context: {context_text}\n\n"
#         f"Generate EXACTLY {count} candidate activities that could help this person take "
#         f"a small step in a valued direction.\n\n"
#         "If you received a list of nearby_parks, explicitly use them:\n"
#         "- Prefer different nearby places for different activities when possible.\n\n"
#         "Return ONLY JSON in this exact format (no extra commentary):\n"
#         "{\n"
#         '  \"activities\": [\n'
#         "    {\n"
#         '      \"title\": \"short name\",\n'
#         '      \"description\": \"2–3 sentence description of what to do\",\n'
#         '      \"life_area\": \"Social | Body | Work | Meaning | Self-compassion\",\n'
#         '      \"effort_level\": \"low | medium | high\",\n'
#         '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
#         '      \"default_duration_min\": 5,\n'
#         '      \"location_label\": \"Specific local place / nearby promenade / indoors / etc.\",\n'
#         '      \"tags\": [\"+ Social\", \"+ Body\"]\n'
#         "    }\n"
#         "  ]\n"
#         "}"
#     )

#     # Use new v1 chat completions client
#     try:
#         resp = client.chat.completions.create(
#             model=OPENAI_ACTIVITY_MODEL,
#             messages=[
#                 {"role": "system", "content": system_msg},
#                 {"role": "user", "content": user_msg},
#             ],
#             temperature=0.7,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")

#     # Parse JSON from model output
#     try:
#         content = resp.choices[0].message.content
#         data = json.loads(content)
#         items = data.get("activities") or []
#     except json.JSONDecodeError:
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to parse OpenAI JSON for activities",
#         )

#     activities: List[schemas.ActivityBase] = []
#     for item in items:
#         try:
#             act = schemas.ActivityBase(
#                 title=(item.get("title") or "").strip() or "Small step",
#                 description=(item.get("description") or "").strip()
#                 or "Take a small helpful step.",
#                 life_area=item.get("life_area", "Meaning"),
#                 effort_level=item.get("effort_level", "low"),
#                 reward_type=item.get("reward_type"),
#                 default_duration_min=item.get("default_duration_min") or 10,
#                 location_label=item.get("location_label"),
#                 tags=item.get("tags") or [],
#             )
#             activities.append(act)
#         except Exception:
#             continue

#     if not activities:
#         raise HTTPException(status_code=500, detail="OpenAI returned no valid activities")

#     return activities


# # --------- Store generated activities in DB (no global cache) ---------


# def _store_generated_activities(
#     db: Session,
#     *,
#     activities: List[schemas.ActivityBase],
# ) -> List[models.Activities]:
#     """
#     Persist a batch of generated activities.
#     We do NOT reuse previous batches for new recommendations – each call
#     can create its own activities tied to that moment / context.
#     """
#     now = datetime.utcnow()
#     rows: List[models.Activities] = []

#     for a in activities:
#         row = models.Activities(
#             title=a.title,
#             description=a.description,
#             life_area=a.life_area,
#             effort_level=a.effort_level,
#             reward_type=a.reward_type,
#             default_duration_min=a.default_duration_min,
#             location_label=a.location_label,
#             tags_json=json.dumps(a.tags or []),
#             is_active=True,
#             created_at=now,
#         )
#         db.add(row)
#         rows.append(row)

#     db.commit()
#     for r_obj in rows:
#         db.refresh(r_obj)

#     return rows


# # ---------------- Public endpoints ----------------

# @r.get(
#     "/recommendation",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation",
# )
# def get_recommendation(
#     user_hash: Optional[str] = Query(None, description="Optional user hash"),
#     life_area: Optional[str] = Query(None, description="Preferred life area, e.g., 'Social'"),
#     mood: Optional[str] = Query(None, description="Current mood (from intake)"),
#     schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
#     postal_code: Optional[str] = Query(None, description="Postal code, e.g., L18 2QA"),
#     goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
#     place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return THREE LLM-generated BA activities, tailored to *this* request.
#     We always generate a fresh batch with OpenAI for this context,
#     then store them in the DB for logging / later inspection.
#     """

#     generated = _generate_activities_via_llm(
#         mood=mood,
#         schema_hint=schema_hint,
#         postal_code=postal_code,
#         goal_today=goal_today,
#         place=place,
#         count=3,
#     )

#     rows = _store_generated_activities(db, activities=generated)

#     # Optional life_area filter over this batch only
#     if life_area:
#         filtered = [
#             r_
#             for r_ in rows
#             if (r_.life_area or "").lower() == life_area.lower()
#         ]
#         candidates = filtered or rows
#     else:
#         candidates = rows

#     if not candidates:
#         raise HTTPException(status_code=404, detail="No activities available")

#     # Take up to 3 from this batch (they already correspond to this location/goal)
#     selected = sorted(
#         candidates,
#         key=lambda x: x.created_at or datetime.utcnow(),
#         reverse=True,
#     )[:3]

#     recs: List[schemas.ActivityRecommendationOut] = []
#     for act in selected:
#         tags: List[str] = []
#         if act.tags_json:
#             try:
#                 tags = json.loads(act.tags_json)
#             except Exception:
#                 tags = []
#         recs.append(
#             schemas.ActivityRecommendationOut(
#                 id=act.id,
#                 title=act.title,
#                 description=act.description,
#                 life_area=act.life_area,
#                 effort_level=act.effort_level,
#                 reward_type=act.reward_type,
#                 default_duration_min=act.default_duration_min,
#                 location_label=act.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityRecommendationListOut(activities=recs)


# @r.get(
#     "/library",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library",
# )
# def get_library(
#     db: Session = Depends(get_db),
# ):
#     """
#     Return the full activity library.
#     This is basically all activities that have ever been generated and stored.
#     """

#     acts = (
#         db.query(models.Activities)
#         .filter(models.Activities.is_active == True)
#         .order_by(models.Activities.created_at.desc())
#         .all()
#     )

#     out: List[schemas.ActivityOut] = []
#     for a in acts:
#         tags: List[str] = []
#         if a.tags_json:
#             try:
#                 tags = json.loads(a.tags_json)
#             except Exception:
#                 tags = []
#         out.append(
#             schemas.ActivityOut(
#                 id=a.id,
#                 title=a.title,
#                 description=a.description,
#                 life_area=a.life_area,
#                 effort_level=a.effort_level,
#                 reward_type=a.reward_type,
#                 default_duration_min=a.default_duration_min,
#                 location_label=a.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityListOut(activities=out)


# @r.post(
#     "/start",
#     summary="Start Activity",
# )
# def start_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=act.id,
#         session_id=payload.session_id,
#         status="started",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()

#     return {"ok": True}


# @r.post(
#     "/swap",
#     summary="Swap Activity",
# )
# def swap_activity(
#     payload: schemas.ActivitySwapIn,
#     db: Session = Depends(get_db),
# ):
#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=payload.activity_id,
#         status="swapped",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     return {"ok": True}

# app/routes/activity.py

# from __future__ import annotations

# import json
# from datetime import datetime
# from typing import List, Optional, Tuple

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session

# from app.db import SessionLocal
# from app import models, schemas
# from app.core.config import cfg as c

# # ---------------- OpenAI setup ----------------

# from openai import OpenAI

# # use the same OPENAI_API_KEY as your script generator
# client = OpenAI(api_key=c.OPENAI_API_KEY)
# OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

# r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])


# # ---------------- DB dependency ----------------

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---------------- Google Maps helpers ----------------

# def _geocode_postal_code(postal_code: str) -> Optional[Tuple[float, float]]:
#     """
#     postal_code -> (lat, lng) using Google Geocoding.
#     Returns None on any error so we can gracefully fall back.
#     """
#     if not c.GOOGLE_MAPS_API_KEY or not postal_code:
#         return None

#     url = "https://maps.googleapis.com/maps/api/geocode/json"
#     params = {"address": postal_code, "key": c.GOOGLE_MAPS_API_KEY}

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#         if data.get("status") != "OK":
#             return None
#         loc = data["results"][0]["geometry"]["location"]
#         return float(loc["lat"]), float(loc["lng"])
#     except Exception:
#         return None


# def _nearby_places(
#     lat: float,
#     lng: float,
#     place_type: str,
#     radius_m: int = 2500,
#     max_results: int = 5,
# ) -> List[str]:
#     """
#     Generic helper: look up nearby places of a given type.
#     """
#     if not c.GOOGLE_MAPS_API_KEY:
#         return []

#     url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
#     params = {
#         "location": f"{lat},{lng}",
#         "radius": radius_m,
#         "type": place_type,
#         "key": c.GOOGLE_MAPS_API_KEY,
#     }

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#     except Exception:
#         return []

#     results = data.get("results") or []
#     names: List[str] = []
#     for r_ in results[:max_results]:
#         name = r_.get("name")
#         if name:
#             names.append(name.strip())
#     return names


# # ---------------- OpenAI helper ----------------

# def _generate_activities_via_llm(
#     *,
#     mood: Optional[str],
#     schema_hint: Optional[str],
#     postal_code: Optional[str],
#     goal_today: Optional[str],
#     place: Optional[str],
#     count: int = 6,
# ) -> List[schemas.ActivityBase]:
#     """
#     Call OpenAI to generate a small set of concrete BA activities.

#     We ask for EXACTLY 6:
#     - First 3: place-based activities using real nearby place names
#       (parks / cafes / attractions).
#     - Last 3: goal-based BA activities like "Coffee with Maya",
#       "Call Mom", "Morning Pages", linked to the therapy goal.
#     """

#     # --- build context text ---
#     context_bits: List[str] = []
#     if mood:
#         context_bits.append(f"current mood: {mood}")
#     if schema_hint:
#         context_bits.append(f"schema or core story: {schema_hint}")
#     if goal_today:
#         context_bits.append(f"today's goal: {goal_today}")
#     if place:
#         context_bits.append(f"preferred environment: {place}")
#     if postal_code:
#         context_bits.append(f"postal code: {postal_code}")

#     nearby_parks: List[str] = []
#     nearby_cafes: List[str] = []
#     nearby_attractions: List[str] = []

#     coords: Optional[Tuple[float, float]] = None
#     if postal_code:
#         coords = _geocode_postal_code(postal_code)

#     if coords:
#         lat, lng = coords
#         nearby_parks = _nearby_places(lat, lng, "park", max_results=5)
#         nearby_cafes = _nearby_places(lat, lng, "cafe", max_results=5)
#         nearby_attractions = _nearby_places(lat, lng, "tourist_attraction", max_results=5)

#         if nearby_parks:
#             context_bits.append("nearby_parks: " + ", ".join(nearby_parks))
#         if nearby_cafes:
#             context_bits.append("nearby_cafes: " + ", ".join(nearby_cafes))
#         if nearby_attractions:
#             context_bits.append("nearby_attractions: " + ", ".join(nearby_attractions))

#     context_text = "; ".join(context_bits) or "no extra context provided"

#     system_msg = (
#         "You are a behavioural activation coach designing very small, realistic, "
#         "real-world activities for a mental health app.\n"
#         "Each activity must be:\n"
#         "- concrete and doable in 5–30 minutes\n"
#         "- safe and gentle (no extreme exercise, no unsafe locations)\n"
#         "- described in simple language\n"
#         "- If you reference a place (park, cafe, attraction), you MUST use the exact "
#         "name from the provided nearby_parks / nearby_cafes / nearby_attractions lists.\n"
#         "- Do NOT invent or tweak place names (e.g., do not say 'Durham Riverside' "
#         "unless that exact string is in the nearby lists).\n\n"
#         "You can use BA flavours like Movement, Connection, Creative, Grounding, "
#         "or Self-compassion. Use tags to encode this.\n"
#     )

#     user_msg = (
#         f"User context: {context_text}\n\n"
#         "Generate EXACTLY 6 activities in this order:\n"
#         "1–3: PLACE-BASED activities that use real nearby places from the lists. "
#         "Mark them with a '+ PlaceBased' tag.\n"
#         "4–6: GOAL-BASED BA activities (like 'Coffee with Maya', 'Call Mom', "
#         "'Morning Pages', 'Farmers Market Visit'). These can be at home, on the phone, "
#         "or generic. Mark them with a '+ GoalBased' tag.\n\n"
#         "For GOAL-BASED items, also include a tag of the form "
#         "'Supports: <short phrase>' explaining how it supports their goal.\n\n"
#         "Return ONLY JSON in this exact format (no extra commentary):\n"
#         "{\n"
#         '  \"activities\": [\n'
#         "    {\n"
#         '      \"title\": \"short name\",\n'
#         '      \"description\": \"2–3 sentence description of what to do\",\n'
#         '      \"life_area\": \"Movement | Connection | Creative | Grounding | Self-compassion | Work\",\n'
#         '      \"effort_level\": \"low | medium | high\",\n'
#         '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
#         '      \"default_duration_min\": 5,\n'
#         '      \"location_label\": \"Exact place name from nearby lists, or \'at home\' / \'anywhere comfortable\' for goal-based items\",\n'
#         '      \"tags\": [\"+ PlaceBased or + GoalBased\", \"BA flavour like Movement/Connection\", \"Supports: ... for goal-based\"]\n'
#         "    }\n"
#         "  ]\n"
#         "}"
#     )

#     # Use new v1 chat completions client
#     try:
#         resp = client.chat.completions.create(
#             model=OPENAI_ACTIVITY_MODEL,
#             messages=[
#                 {"role": "system", "content": system_msg},
#                 {"role": "user", "content": user_msg},
#             ],
#             temperature=0.7,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")

#     # Parse JSON from model output
#     try:
#         content = resp.choices[0].message.content
#         data = json.loads(content)
#         items = data.get("activities") or []
#     except json.JSONDecodeError:
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to parse OpenAI JSON for activities",
#         )

#     activities: List[schemas.ActivityBase] = []
#     for item in items:
#         try:
#             act = schemas.ActivityBase(
#                 title=(item.get("title") or "").strip() or "Small step",
#                 description=(item.get("description") or "").strip()
#                 or "Take a small helpful step.",
#                 life_area=item.get("life_area", "Meaning"),
#                 effort_level=item.get("effort_level", "low"),
#                 reward_type=item.get("reward_type"),
#                 default_duration_min=item.get("default_duration_min") or 10,
#                 location_label=item.get("location_label"),
#                 tags=item.get("tags") or [],
#             )
#             activities.append(act)
#         except Exception:
#             continue

#     if not activities:
#         raise HTTPException(status_code=500, detail="OpenAI returned no valid activities")

#     return activities


# # --------- Store generated activities in DB (no global cache) ---------


# def _store_generated_activities(
#     db: Session,
#     *,
#     activities: List[schemas.ActivityBase],
# ) -> List[models.Activities]:
#     """
#     Persist a batch of generated activities.
#     We do NOT reuse previous batches for new recommendations – each call
#     can create its own activities tied to that moment / context.
#     """
#     now = datetime.utcnow()
#     rows: List[models.Activities] = []

#     for a in activities:
#         row = models.Activities(
#             title=a.title,
#             description=a.description,
#             life_area=a.life_area,
#             effort_level=a.effort_level,
#             reward_type=a.reward_type,
#             default_duration_min=a.default_duration_min,
#             location_label=a.location_label,
#             tags_json=json.dumps(a.tags or []),
#             is_active=True,
#             created_at=now,
#         )
#         db.add(row)
#         rows.append(row)

#     db.commit()
#     for r_obj in rows:
#         db.refresh(r_obj)

#     return rows


# # ---------------- Public endpoints ----------------

# @r.get(
#     "/recommendation",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation",
# )
# def get_recommendation(
#     user_hash: Optional[str] = Query(None, description="Optional user hash"),
#     life_area: Optional[str] = Query(None, description="Preferred life area filter, e.g., 'Connection'"),
#     mood: Optional[str] = Query(None, description="Current mood (from intake)"),
#     schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
#     postal_code: Optional[str] = Query(None, description="Postal code, e.g., L18 2QA"),
#     goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
#     place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return SIX LLM-generated BA activities, tailored to *this* request.

#     - 3 place-based (with '+ PlaceBased' tag, using exact nearby place names).
#     - 3 goal-based BA actions (with '+ GoalBased' tag and 'Supports: ...' tag).
#     """

#     generated = _generate_activities_via_llm(
#         mood=mood,
#         schema_hint=schema_hint,
#         postal_code=postal_code,
#         goal_today=goal_today,
#         place=place,
#         count=6,
#     )

#     rows = _store_generated_activities(db, activities=generated)

#     # Optional life_area filter over this batch only (e.g. 'Connection', 'Movement')
#     if life_area:
#         filtered = [
#             r_
#             for r_ in rows
#             if (r_.life_area or "").lower() == life_area.lower()
#         ]
#         candidates = filtered or rows
#     else:
#         candidates = rows

#     if not candidates:
#         raise HTTPException(status_code=404, detail="No activities available")

#     # For now just return the whole batch for this request (up to 6)
#     selected = sorted(
#         candidates,
#         key=lambda x: x.created_at or datetime.utcnow(),
#         reverse=True,
#     )[:6]

#     recs: List[schemas.ActivityRecommendationOut] = []
#     for act in selected:
#         tags: List[str] = []
#         if act.tags_json:
#             try:
#                 tags = json.loads(act.tags_json)
#             except Exception:
#                 tags = []
#         recs.append(
#             schemas.ActivityRecommendationOut(
#                 id=act.id,
#                 title=act.title,
#                 description=act.description,
#                 life_area=act.life_area,
#                 effort_level=act.effort_level,
#                 reward_type=act.reward_type,
#                 default_duration_min=act.default_duration_min,
#                 location_label=act.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityRecommendationListOut(activities=recs)


# @r.get(
#     "/library",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library",
# )
# def get_library(
#     db: Session = Depends(get_db),
# ):
#     """
#     Return the full activity library.
#     This is basically all activities that have ever been generated and stored.
#     """

#     acts = (
#         db.query(models.Activities)
#         .filter(models.Activities.is_active == True)
#         .order_by(models.Activities.created_at.desc())
#         .all()
#     )

#     out: List[schemas.ActivityOut] = []
#     for a in acts:
#         tags: List[str] = []
#         if a.tags_json:
#             try:
#                 tags = json.loads(a.tags_json)
#             except Exception:
#                 tags = []
#         out.append(
#             schemas.ActivityOut(
#                 id=a.id,
#                 title=a.title,
#                 description=a.description,
#                 life_area=a.life_area,
#                 effort_level=a.effort_level,
#                 reward_type=a.reward_type,
#                 default_duration_min=a.default_duration_min,
#                 location_label=a.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityListOut(activities=out)


# @r.post(
#     "/start",
#     summary="Start Activity",
# )
# def start_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=act.id,
#         session_id=payload.session_id,
#         status="started",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()

#     return {"ok": True}


# @r.post(
#     "/swap",
#     summary="Swap Activity",
# )
# def swap_activity(
#     payload: schemas.ActivitySwapIn,
#     db: Session = Depends(get_db),
# ):
#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=payload.activity_id,
#         status="swapped",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     return {"ok": True}

# from __future__ import annotations

# import json
# import math
# from datetime import datetime
# from typing import List, Optional, Tuple

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session

# from app.db import SessionLocal
# from app import models, schemas
# from app.core.config import cfg as c

# # ---------------- OpenAI setup ----------------

# from openai import OpenAI

# # use the same OPENAI_API_KEY as your script generator
# client = OpenAI(api_key=c.OPENAI_API_KEY)
# OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

# r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])


# # ---------------- DB dependency ----------------

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---------------- Google Maps helpers ----------------

# def _geocode_postal_code(postal_code: str) -> Optional[Tuple[float, float]]:
#     """
#     postal_code -> (lat, lng) using Google Geocoding.
#     Returns None on any error so we can gracefully fall back.
#     """
#     if not c.GOOGLE_MAPS_API_KEY or not postal_code:
#         return None

#     url = "https://maps.googleapis.com/maps/api/geocode/json"
#     params = {"address": postal_code, "key": c.GOOGLE_MAPS_API_KEY}

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#         if data.get("status") != "OK":
#             return None
#         loc = data["results"][0]["geometry"]["location"]
#         return float(loc["lat"]), float(loc["lng"])
#     except Exception:
#         return None


# def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
#     """
#     Haversine distance between two lat/lng points in meters.
#     """
#     R = 6371000  # Earth radius in meters
#     phi1 = math.radians(lat1)
#     phi2 = math.radians(lat2)
#     dphi = math.radians(lat2 - lat1)
#     dlambda = math.radians(lng2 - lng1)

#     a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
#     c_ = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
#     return R * c_


# def _nearby_places(
#     lat: float,
#     lng: float,
#     place_type: str,
#     radius_m: int = 1200,
#     max_results: int = 5,
# ) -> List[str]:
#     """
#     Generic helper: look up nearby places of a given type.

#     We explicitly enforce that returned places are within `radius_m`
#     of the reference point, to keep recommendations VERY close to
#     the user's postal code.
#     """
#     if not c.GOOGLE_MAPS_API_KEY:
#         return []

#     url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
#     params = {
#         "location": f"{lat},{lng}",
#         "radius": radius_m,  # ask Google for a tight circle
#         "type": place_type,
#         "key": c.GOOGLE_MAPS_API_KEY,
#     }

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#     except Exception:
#         return []

#     results = data.get("results") or []
#     names: List[str] = []

#     for r_ in results:
#         if len(names) >= max_results:
#             break

#         name = r_.get("name")
#         loc = (r_.get("geometry") or {}).get("location") or {}
#         lat2 = loc.get("lat")
#         lng2 = loc.get("lng")

#         if not name or lat2 is None or lng2 is None:
#             continue

#         # Enforce "very close" – cut off anything outside radius_m.
#         dist = _distance_meters(lat, lng, float(lat2), float(lng2))
#         if dist > radius_m:
#             continue

#         names.append(name.strip())

#     return names


# # ---------------- OpenAI helper ----------------

# def _generate_activities_via_llm(
#     *,
#     mood: Optional[str],
#     schema_hint: Optional[str],
#     postal_code: Optional[str],
#     goal_today: Optional[str],
#     place: Optional[str],
#     count: int = 6,
# ) -> List[schemas.ActivityBase]:
#     """
#     Call OpenAI to generate a small set of concrete BA activities.

#     We ask for EXACTLY 6:
#     - First 3: place-based activities using real nearby place names
#       (parks / cafes / attractions).
#     - Last 3: goal-based BA activities like "Coffee with Maya",
#       "Call Mom", "Morning Pages", linked to the therapy goal.
#     """

#     # --- build context text ---
#     context_bits: List[str] = []
#     if mood:
#         context_bits.append(f"current mood: {mood}")
#     if schema_hint:
#         context_bits.append(f"schema or core story: {schema_hint}")
#     if goal_today:
#         context_bits.append(f"today's goal: {goal_today}")
#     if place:
#         context_bits.append(f"preferred environment: {place}")
#     if postal_code:
#         context_bits.append(f"postal code: {postal_code}")

#     nearby_parks: List[str] = []
#     nearby_cafes: List[str] = []
#     nearby_attractions: List[str] = []

#     coords: Optional[Tuple[float, float]] = None
#     if postal_code:
#         coords = _geocode_postal_code(postal_code)

#     if coords:
#         lat, lng = coords
#         nearby_parks = _nearby_places(lat, lng, "park", max_results=5)
#         nearby_cafes = _nearby_places(lat, lng, "cafe", max_results=5)
#         nearby_attractions = _nearby_places(lat, lng, "tourist_attraction", max_results=5)

#         if nearby_parks:
#             context_bits.append("nearby_parks: " + ", ".join(nearby_parks))
#         if nearby_cafes:
#             context_bits.append("nearby_cafes: " + ", ".join(nearby_cafes))
#         if nearby_attractions:
#             context_bits.append("nearby_attractions: " + ", ".join(nearby_attractions))

#     context_text = "; ".join(context_bits) or "no extra context provided"

#     system_msg = (
#         "You are a behavioural activation coach designing very small, realistic, "
#         "real-world activities for a mental health app.\n"
#         "Each activity must be:\n"
#         "- concrete and doable in 5–30 minutes\n"
#         "- safe and gentle (no extreme exercise, no unsafe locations)\n"
#         "- described in simple language\n"
#         "- If you reference a place (park, cafe, attraction), you MUST use the exact "
#         "name from the provided nearby_parks / nearby_cafes / nearby_attractions lists.\n"
#         "- Do NOT invent or tweak place names (e.g., do not say 'Durham Riverside' "
#         "unless that exact string is in the nearby lists).\n\n"
#         "You can use BA flavours like Movement, Connection, Creative, Grounding, "
#         "or Self-compassion. Use tags to encode this.\n"
#     )

#     user_msg = (
#         f"User context: {context_text}\n\n"
#         "Generate EXACTLY 6 activities in this order:\n"
#         "1–3: PLACE-BASED activities that use real nearby places from the lists. "
#         "Mark them with a '+ PlaceBased' tag.\n"
#         "4–6: GOAL-BASED BA activities (like 'Coffee with Maya', 'Call Mom', "
#         "'Morning Pages', 'Farmers Market Visit'). These can be at home, on the phone, "
#         "or generic. Mark them with a '+ GoalBased' tag.\n\n"
#         "For GOAL-BASED items, also include a tag of the form "
#         "'Supports: <short phrase>' explaining how it supports their goal.\n\n"
#         "Return ONLY JSON in this exact format (no extra commentary):\n"
#         "{\n"
#         '  \"activities\": [\n'
#         "    {\n"
#         '      \"title\": \"short name\",\n'
#         '      \"description\": \"2–3 sentence description of what to do\",\n'
#         '      \"life_area\": \"Movement | Connection | Creative | Grounding | Self-compassion | Work\",\n'
#         '      \"effort_level\": \"low | medium | high\",\n'
#         '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
#         '      \"default_duration_min\": 5,\n'
#         '      \"location_label\": \"Exact place name from nearby lists, or \'at home\' / \'anywhere comfortable\' for goal-based items\",\n'
#         '      \"tags\": [\"+ PlaceBased or + GoalBased\", \"BA flavour like Movement/Connection\", \"Supports: ... for goal-based\"]\n'
#         "    }\n"
#         "  ]\n"
#         "}"
#     )

#     # Use new v1 chat completions client
#     try:
#         resp = client.chat.completions.create(
#             model=OPENAI_ACTIVITY_MODEL,
#             messages=[
#                 {"role": "system", "content": system_msg},
#                 {"role": "user", "content": user_msg},
#             ],
#             temperature=0.7,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")

#     # Parse JSON from model output
#     try:
#         content = resp.choices[0].message.content
#         data = json.loads(content)
#         items = data.get("activities") or []
#     except json.JSONDecodeError:
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to parse OpenAI JSON for activities",
#         )

#     activities: List[schemas.ActivityBase] = []
#     for item in items:
#         try:
#             act = schemas.ActivityBase(
#                 title=(item.get("title") or "").strip() or "Small step",
#                 description=(item.get("description") or "").strip()
#                 or "Take a small helpful step.",
#                 life_area=item.get("life_area", "Meaning"),
#                 effort_level=item.get("effort_level", "low"),
#                 reward_type=item.get("reward_type"),
#                 default_duration_min=item.get("default_duration_min") or 10,
#                 location_label=item.get("location_label"),
#                 tags=item.get("tags") or [],
#             )
#             activities.append(act)
#         except Exception:
#             continue

#     if not activities:
#         raise HTTPException(status_code=500, detail="OpenAI returned no valid activities")

#     return activities


# # --------- Store generated activities in DB (no global cache) ---------


# def _store_generated_activities(
#     db: Session,
#     *,
#     activities: List[schemas.ActivityBase],
# ) -> List[models.Activities]:
#     """
#     Persist a batch of generated activities.
#     We do NOT reuse previous batches for new recommendations – each call
#     can create its own activities tied to that moment / context.
#     """
#     now = datetime.utcnow()
#     rows: List[models.Activities] = []

#     for a in activities:
#         row = models.Activities(
#             title=a.title,
#             description=a.description,
#             life_area=a.life_area,
#             effort_level=a.effort_level,
#             reward_type=a.reward_type,
#             default_duration_min=a.default_duration_min,
#             location_label=a.location_label,
#             tags_json=json.dumps(a.tags or []),
#             is_active=True,
#             created_at=now,
#         )
#         db.add(row)
#         rows.append(row)

#     db.commit()
#     for r_obj in rows:
#         db.refresh(r_obj)

#     return rows


# # ---------------- Public endpoints ----------------

# @r.get(
#     "/recommendation",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation",
# )
# def get_recommendation(
#     user_hash: Optional[str] = Query(None, description="Optional user hash"),
#     life_area: Optional[str] = Query(None, description="Preferred life area filter, e.g., 'Connection'"),
#     mood: Optional[str] = Query(None, description="Current mood (from intake)"),
#     schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
#     postal_code: Optional[str] = Query(None, description="Postal code, e.g., L18 2QA"),
#     goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
#     place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return SIX LLM-generated BA activities, tailored to *this* request.

#     - 3 place-based (with '+ PlaceBased' tag, using exact nearby place names).
#     - 3 goal-based BA actions (with '+ GoalBased' tag and 'Supports: ...' tag).
#     """

#     generated = _generate_activities_via_llm(
#         mood=mood,
#         schema_hint=schema_hint,
#         postal_code=postal_code,
#         goal_today=goal_today,
#         place=place,
#         count=6,
#     )

#     rows = _store_generated_activities(db, activities=generated)

#     # Optional life_area filter over this batch only (e.g. 'Connection', 'Movement')
#     if life_area:
#         filtered = [
#             r_
#             for r_ in rows
#             if (r_.life_area or "").lower() == life_area.lower()
#         ]
#         candidates = filtered or rows
#     else:
#         candidates = rows

#     if not candidates:
#         raise HTTPException(status_code=404, detail="No activities available")

#     # For now just return the whole batch for this request (up to 6)
#     selected = sorted(
#         candidates,
#         key=lambda x: x.created_at or datetime.utcnow(),
#         reverse=True,
#     )[:6]

#     recs: List[schemas.ActivityRecommendationOut] = []
#     for act in selected:
#         tags: List[str] = []
#         if act.tags_json:
#             try:
#                 tags = json.loads(act.tags_json)
#             except Exception:
#                 tags = []
#         recs.append(
#             schemas.ActivityRecommendationOut(
#                 id=act.id,
#                 title=act.title,
#                 description=act.description,
#                 life_area=act.life_area,
#                 effort_level=act.effort_level,
#                 reward_type=act.reward_type,
#                 default_duration_min=act.default_duration_min,
#                 location_label=act.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityRecommendationListOut(activities=recs)


# @r.get(
#     "/library",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library",
# )
# def get_library(
#     db: Session = Depends(get_db),
# ):
#     """
#     Return the full activity library.
#     This is basically all activities that have ever been generated and stored.
#     """

#     acts = (
#         db.query(models.Activities)
#         .filter(models.Activities.is_active == True)
#         .order_by(models.Activities.created_at.desc())
#         .all()
#     )

#     out: List[schemas.ActivityOut] = []
#     for a in acts:
#         tags: List[str] = []
#         if a.tags_json:
#             try:
#                 tags = json.loads(a.tags_json)
#             except Exception:
#                 tags = []
#         out.append(
#             schemas.ActivityOut(
#                 id=a.id,
#                 title=a.title,
#                 description=a.description,
#                 life_area=a.life_area,
#                 effort_level=a.effort_level,
#                 reward_type=a.reward_type,
#                 default_duration_min=a.default_duration_min,
#                 location_label=a.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityListOut(activities=out)


# @r.post(
#     "/start",
#     summary="Start Activity",
# )
# def start_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=act.id,
#         session_id=payload.session_id,
#         status="started",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()

#     return {"ok": True}


# @r.post(
#     "/swap",
#     summary="Swap Activity",
# )
# def swap_activity(
#     payload: schemas.ActivitySwapIn,
#     db: Session = Depends(get_db),
# ):
#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=payload.activity_id,
#         status="swapped",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     return {"ok": True}

# from __future__ import annotations

# import json
# import math
# from datetime import datetime
# from typing import List, Optional, Tuple

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session

# from app.db import SessionLocal
# from app import models, schemas
# from app.core.config import cfg as c

# # ---------------- OpenAI setup ----------------

# from openai import OpenAI

# # use the same OPENAI_API_KEY as your script generator
# client = OpenAI(api_key=c.OPENAI_API_KEY)
# OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

# r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])


# # ---------------- DB dependency ----------------

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---------------- Google Maps helpers ----------------

# def _geocode_postal_code(postal_code: str) -> Optional[Tuple[float, float]]:
#     """
#     postal_code -> (lat, lng) using Google Geocoding.
#     Returns None on any error so we can gracefully fall back.
#     """
#     if not c.GOOGLE_MAPS_API_KEY or not postal_code:
#         return None

#     url = "https://maps.googleapis.com/maps/api/geocode/json"
#     params = {"address": postal_code, "key": c.GOOGLE_MAPS_API_KEY}

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#         if data.get("status") != "OK":
#             return None
#         loc = data["results"][0]["geometry"]["location"]
#         return float(loc["lat"]), float(loc["lng"])
#     except Exception:
#         return None


# def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
#     """
#     Haversine distance between two lat/lng points in meters.
#     """
#     R = 6371000  # Earth radius in meters
#     phi1 = math.radians(lat1)
#     phi2 = math.radians(lat2)
#     dphi = math.radians(lat2 - lat1)
#     dlambda = math.radians(lng2 - lng1)

#     a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
#     c_ = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
#     return R * c_


# def _nearby_places(
#     lat: float,
#     lng: float,
#     place_type: str,
#     radius_m: int = 1200,
#     max_results: int = 5,
# ) -> List[str]:
#     """
#     Generic helper: look up nearby places of a given type.

#     We explicitly enforce that returned places are within `radius_m`
#     of the reference point, to keep recommendations VERY close to
#     the user's postal code.
#     """
#     if not c.GOOGLE_MAPS_API_KEY:
#         return []

#     url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
#     params = {
#         "location": f"{lat},{lng}",
#         "radius": radius_m,  # ask Google for a tight circle
#         "type": place_type,
#         "key": c.GOOGLE_MAPS_API_KEY,
#     }

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#     except Exception:
#         return []

#     results = data.get("results") or []
#     names: List[str] = []

#     for r_ in results:
#         if len(names) >= max_results:
#             break

#         name = r_.get("name")
#         loc = (r_.get("geometry") or {}).get("location") or {}
#         lat2 = loc.get("lat")
#         lng2 = loc.get("lng")

#         if not name or lat2 is None or lng2 is None:
#             continue

#         # Enforce "very close" – cut off anything outside radius_m.
#         dist = _distance_meters(lat, lng, float(lat2), float(lng2))
#         if dist > radius_m:
#             continue

#         names.append(name.strip())

#     return names


# # ---------------- OpenAI helper ----------------

# def _generate_activities_via_llm(
#     *,
#     mood: Optional[str],
#     schema_hint: Optional[str],
#     postal_code: Optional[str],
#     goal_today: Optional[str],
#     place: Optional[str],
#     count: int = 6,
# ) -> List[schemas.ActivityBase]:
#     """
#     Call OpenAI to generate a small set of concrete BA activities.

#     We ask for EXACTLY 6:
#     - First 3: place-based activities using real nearby place names
#       (parks / cafes / malls / theatres / libraries / gyms / attractions).
#     - Last 3: goal-based BA activities like "Coffee with Maya",
#       "Call Mom", "Morning Pages", linked to the therapy goal.
#     """

#     # --- build context text ---
#     context_bits: List[str] = []
#     if mood:
#         context_bits.append(f"current mood: {mood}")
#     if schema_hint:
#         context_bits.append(f"schema or core story: {schema_hint}")
#     if goal_today:
#         context_bits.append(f"today's goal: {goal_today}")
#     if place:
#         context_bits.append(f"preferred environment: {place}")
#     if postal_code:
#         context_bits.append(f"postal code: {postal_code}")

#     nearby_parks: List[str] = []
#     nearby_cafes: List[str] = []
#     nearby_attractions: List[str] = []
#     nearby_malls: List[str] = []
#     nearby_theatres: List[str] = []
#     nearby_libraries: List[str] = []
#     nearby_gyms: List[str] = []

#     coords: Optional[Tuple[float, float]] = None
#     if postal_code:
#         coords = _geocode_postal_code(postal_code)

#     if coords:
#         lat, lng = coords

#         # Movement / nature
#         nearby_parks = _nearby_places(lat, lng, "park", max_results=5)
#         # Social / talk / coffee
#         nearby_cafes = _nearby_places(lat, lng, "cafe", max_results=5)
#         # Entertainment / sightseeing
#         nearby_attractions = _nearby_places(lat, lng, "tourist_attraction", max_results=5)
#         nearby_malls = _nearby_places(lat, lng, "shopping_mall", max_results=5)
#         nearby_theatres = _nearby_places(lat, lng, "movie_theater", max_results=5)
#         # Quiet focus / learning
#         nearby_libraries = _nearby_places(lat, lng, "library", max_results=5)
#         # Movement in non-nature spaces
#         nearby_gyms = _nearby_places(lat, lng, "gym", max_results=5)

#         if nearby_parks:
#             context_bits.append("nearby_parks: " + ", ".join(nearby_parks))
#         if nearby_cafes:
#             context_bits.append("nearby_cafes: " + ", ".join(nearby_cafes))
#         if nearby_attractions:
#             context_bits.append("nearby_attractions: " + ", ".join(nearby_attractions))
#         if nearby_malls:
#             context_bits.append("nearby_malls: " + ", ".join(nearby_malls))
#         if nearby_theatres:
#             context_bits.append("nearby_theatres: " + ", ".join(nearby_theatres))
#         if nearby_libraries:
#             context_bits.append("nearby_libraries: " + ", ".join(nearby_libraries))
#         if nearby_gyms:
#             context_bits.append("nearby_gyms: " + ", ".join(nearby_gyms))

#     context_text = "; ".join(context_bits) or "no extra context provided"

#     system_msg = (
#         "You are a behavioural activation coach designing very small, realistic, "
#         "real-world activities for a mental health app.\n"
#         "Each activity must be:\n"
#         "- concrete and doable in 5–30 minutes\n"
#         "- safe and gentle (no extreme exercise, no unsafe locations)\n"
#         "- described in simple language\n"
#         "- If you reference a place (park, cafe, mall, theatre, library, attraction, gym), "
#         "you MUST use the exact name from the provided nearby_* lists.\n"
#         "- Do NOT invent or tweak place names (e.g., do not say 'Durham Riverside' "
#         "unless that exact string is in the nearby lists).\n\n"
#         "MATCH PLACE TYPE TO THE USER'S GOAL:\n"
#         "- Goals about movement / steps / walk / exercise -> prefer parks or gyms.\n"
#         "- Goals about talking, connection, not feeling alone -> prefer cafes or other social spaces.\n"
#         "- Goals about chilling, recharging, entertainment -> prefer malls, theatres, or gentle attractions.\n"
#         "- Goals about focus, work, study, reading -> prefer libraries or quiet cafes.\n"
#         "Avoid suggesting only walks in parks unless that clearly matches the goal.\n"
#         "Where possible, vary the place types across the 3 place-based activities.\n\n"
#         "You can use BA flavours like Movement, Connection, Creative, Grounding, "
#         "or Self-compassion. Use tags to encode this.\n"
#     )

#     user_msg = (
#         f"User context: {context_text}\n\n"
#         "Generate EXACTLY 6 activities in this order:\n"
#         "1–3: PLACE-BASED activities that use real nearby places from the lists. "
#         "Choose the type of place that best fits the user's goal and mood "
#         "(e.g., cafe for talking to someone, mall/theatre for chill, park/gym for movement, "
#         "library for focused work). Mark them with a '+ PlaceBased' tag.\n"
#         "4–6: GOAL-BASED BA activities (like 'Coffee with Maya', 'Call Mom', "
#         "'Morning Pages', 'Farmers Market Visit'). These can be at home, on the phone, "
#         "or generic. Mark them with a '+ GoalBased' tag.\n\n"
#         "For GOAL-BASED items, also include a tag of the form "
#         "'Supports: <short phrase>' explaining how it supports their goal.\n\n"
#         "Return ONLY JSON in this exact format (no extra commentary):\n"
#         "{\n"
#         '  \"activities\": [\n'
#         "    {\n"
#         '      \"title\": \"short name\",\n'
#         '      \"description\": \"2–3 sentence description of what to do\",\n'
#         '      \"life_area\": \"Movement | Connection | Creative | Grounding | Self-compassion | Work\",\n'
#         '      \"effort_level\": \"low | medium | high\",\n'
#         '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
#         '      \"default_duration_min\": 5,\n'
#         '      \"location_label\": \"Exact place name from nearby lists, or \'at home\' / \'anywhere comfortable\' for goal-based items\",\n'
#         '      \"tags\": [\"+ PlaceBased or + GoalBased\", \"BA flavour like Movement/Connection\", \"Supports: ... for goal-based\"]\n'
#         "    }\n"
#         "  ]\n"
#         "}"
#     )

#     # Use new v1 chat completions client
#     try:
#         resp = client.chat.completions.create(
#             model=OPENAI_ACTIVITY_MODEL,
#             messages=[
#                 {"role": "system", "content": system_msg},
#                 {"role": "user", "content": user_msg},
#             ],
#             temperature=0.7,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")

#     # Parse JSON from model output
#     try:
#         content = resp.choices[0].message.content
#         data = json.loads(content)
#         items = data.get("activities") or []
#     except json.JSONDecodeError:
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to parse OpenAI JSON for activities",
#         )

#     activities: List[schemas.ActivityBase] = []
#     for item in items:
#         try:
#             act = schemas.ActivityBase(
#                 title=(item.get("title") or "").strip() or "Small step",
#                 description=(item.get("description") or "").strip()
#                 or "Take a small helpful step.",
#                 life_area=item.get("life_area", "Meaning"),
#                 effort_level=item.get("effort_level", "low"),
#                 reward_type=item.get("reward_type"),
#                 default_duration_min=item.get("default_duration_min") or 10,
#                 location_label=item.get("location_label"),
#                 tags=item.get("tags") or [],
#             )
#             activities.append(act)
#         except Exception:
#             continue

#     if not activities:
#         raise HTTPException(status_code=500, detail="OpenAI returned no valid activities")

#     return activities


# # --------- Store generated activities in DB (no global cache) ---------


# def _store_generated_activities(
#     db: Session,
#     *,
#     activities: List[schemas.ActivityBase],
# ) -> List[models.Activities]:
#     """
#     Persist a batch of generated activities.
#     We do NOT reuse previous batches for new recommendations – each call
#     can create its own activities tied to that moment / context.
#     """
#     now = datetime.utcnow()
#     rows: List[models.Activities] = []

#     for a in activities:
#         row = models.Activities(
#             title=a.title,
#             description=a.description,
#             life_area=a.life_area,
#             effort_level=a.effort_level,
#             reward_type=a.reward_type,
#             default_duration_min=a.default_duration_min,
#             location_label=a.location_label,
#             tags_json=json.dumps(a.tags or []),
#             is_active=True,
#             created_at=now,
#         )
#         db.add(row)
#         rows.append(row)

#     db.commit()
#     for r_obj in rows:
#         db.refresh(r_obj)

#     return rows


# # ---------------- Public endpoints ----------------

# @r.get(
#     "/recommendation",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation",
# )
# def get_recommendation(
#     user_hash: Optional[str] = Query(None, description="Optional user hash"),
#     life_area: Optional[str] = Query(None, description="Preferred life area filter, e.g., 'Connection'"),
#     mood: Optional[str] = Query(None, description="Current mood (from intake)"),
#     schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
#     postal_code: Optional[str] = Query(None, description="Postal code, e.g., L18 2QA"),
#     goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
#     place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return SIX LLM-generated BA activities, tailored to *this* request.

#     - 3 place-based (with '+ PlaceBased' tag, using exact nearby place names).
#     - 3 goal-based BA actions (with '+ GoalBased' tag and 'Supports: ...' tag).
#     """

#     generated = _generate_activities_via_llm(
#         mood=mood,
#         schema_hint=schema_hint,
#         postal_code=postal_code,
#         goal_today=goal_today,
#         place=place,
#         count=6,
#     )

#     rows = _store_generated_activities(db, activities=generated)

#     # Optional life_area filter over this batch only (e.g. 'Connection', 'Movement')
#     if life_area:
#         filtered = [
#             r_
#             for r_ in rows
#             if (r_.life_area or "").lower() == life_area.lower()
#         ]
#         candidates = filtered or rows
#     else:
#         candidates = rows

#     if not candidates:
#         raise HTTPException(status_code=404, detail="No activities available")

#     # For now just return the whole batch for this request (up to 6)
#     selected = sorted(
#         candidates,
#         key=lambda x: x.created_at or datetime.utcnow(),
#         reverse=True,
#     )[:6]

#     recs: List[schemas.ActivityRecommendationOut] = []
#     for act in selected:
#         tags: List[str] = []
#         if act.tags_json:
#             try:
#                 tags = json.loads(act.tags_json)
#             except Exception:
#                 tags = []
#         recs.append(
#             schemas.ActivityRecommendationOut(
#                 id=act.id,
#                 title=act.title,
#                 description=act.description,
#                 life_area=act.life_area,
#                 effort_level=act.effort_level,
#                 reward_type=act.reward_type,
#                 default_duration_min=act.default_duration_min,
#                 location_label=act.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityRecommendationListOut(activities=recs)


# @r.get(
#     "/library",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library",
# )
# def get_library(
#     db: Session = Depends(get_db),
# ):
#     """
#     Return the full activity library.
#     This is basically all activities that have ever been generated and stored.
#     """

#     acts = (
#         db.query(models.Activities)
#         .filter(models.Activities.is_active == True)
#         .order_by(models.Activities.created_at.desc())
#         .all()
#     )

#     out: List[schemas.ActivityOut] = []
#     for a in acts:
#         tags: List[str] = []
#         if a.tags_json:
#             try:
#                 tags = json.loads(a.tags_json)
#             except Exception:
#                 tags = []
#         out.append(
#             schemas.ActivityOut(
#                 id=a.id,
#                 title=a.title,
#                 description=a.description,
#                 life_area=a.life_area,
#                 effort_level=a.effort_level,
#                 reward_type=a.reward_type,
#                 default_duration_min=a.default_duration_min,
#                 location_label=a.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityListOut(activities=out)


# @r.post(
#     "/start",
#     summary="Start Activity",
# )
# def start_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=act.id,
#         session_id=payload.session_id,
#         status="started",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()

#     return {"ok": True}


# @r.post(
#     "/swap",
#     summary="Swap Activity",
# )
# def swap_activity(
#     payload: schemas.ActivitySwapIn,
#     db: Session = Depends(get_db),
# ):
#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=payload.activity_id,
#         status="swapped",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     return {"ok": True}

# from __future__ import annotations

# import json
# import math
# from datetime import datetime
# from typing import List, Optional, Tuple

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session

# from app.db import SessionLocal
# from app import models, schemas
# from app.core.config import cfg as c

# # ---------------- OpenAI setup ----------------

# from openai import OpenAI

# # use the same OPENAI_API_KEY as your script generator
# client = OpenAI(api_key=c.OPENAI_API_KEY)
# OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

# r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])


# # ---------------- DB dependency ----------------

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---------------- Google Maps helpers ----------------

# def _geocode_postal_code(postal_code: str) -> Optional[Tuple[float, float]]:
#     """
#     postal_code -> (lat, lng) using Google Geocoding.
#     Returns None on any error so we can gracefully fall back.
#     """
#     if not c.GOOGLE_MAPS_API_KEY or not postal_code:
#         return None

#     url = "https://maps.googleapis.com/maps/api/geocode/json"
#     params = {"address": postal_code, "key": c.GOOGLE_MAPS_API_KEY}

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#         if data.get("status") != "OK":
#             return None
#         loc = data["results"][0]["geometry"]["location"]
#         return float(loc["lat"]), float(loc["lng"])
#     except Exception:
#         return None


# def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
#     """
#     Haversine distance between two lat/lng points in meters.
#     """
#     R = 6371000  # Earth radius in meters
#     phi1 = math.radians(lat1)
#     phi2 = math.radians(lat2)
#     dphi = math.radians(lat2 - lat1)
#     dlambda = math.radians(lng2 - lng1)

#     a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
#     c_ = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
#     return R * c_


# def _nearby_places(
#     lat: float,
#     lng: float,
#     place_type: str,
#     radius_m: int = 1200,
#     max_results: int = 5,
# ) -> List[str]:
#     """
#     Generic helper: look up nearby places of a given type.

#     We explicitly enforce that returned places are within `radius_m`
#     of the reference point, to keep recommendations VERY close to
#     the user's postal code.
#     """
#     if not c.GOOGLE_MAPS_API_KEY:
#         return []

#     url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
#     params = {
#         "location": f"{lat},{lng}",
#         "radius": radius_m,  # ask Google for a tight circle
#         "type": place_type,
#         "key": c.GOOGLE_MAPS_API_KEY,
#     }

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#     except Exception:
#         return []

#     results = data.get("results") or []
#     names: List[str] = []

#     for r_ in results:
#         if len(names) >= max_results:
#             break

#         name = r_.get("name")
#         loc = (r_.get("geometry") or {}).get("location") or {}
#         lat2 = loc.get("lat")
#         lng2 = loc.get("lng")

#         if not name or lat2 is None or lng2 is None:
#             continue

#         # Enforce "very close" – cut off anything outside radius_m.
#         dist = _distance_meters(lat, lng, float(lat2), float(lng2))
#         if dist > radius_m:
#             continue

#         names.append(name.strip())

#     return names


# # ---------------- OpenAI helper ----------------

# def _generate_activities_via_llm(
#     *,
#     mood: Optional[str],
#     schema_hint: Optional[str],
#     postal_code: Optional[str],
#     goal_today: Optional[str],
#     place: Optional[str],
#     count: int = 6,
# ) -> List[schemas.ActivityBase]:
#     """
#     Call OpenAI to generate a small set of concrete BA activities.

#     We ask for EXACTLY 6:
#     - First 3: place-based activities using real nearby place names
#       (parks / cafes / malls / theatres / libraries / gyms / attractions).
#     - Last 3: goal-based BA activities like "Coffee with Maya",
#       "Call Mom", "Morning Pages", linked to the therapy goal.
#     """

#     # --- build context text ---
#     context_bits: List[str] = []
#     if mood:
#         context_bits.append(f"current mood: {mood}")
#     if schema_hint:
#         context_bits.append(f"schema or core story: {schema_hint}")
#     if goal_today:
#         context_bits.append(f"today's goal: {goal_today}")
#     if place:
#         context_bits.append(f"preferred environment: {place}")
#     if postal_code:
#         context_bits.append(f"postal code: {postal_code}")

#     nearby_parks: List[str] = []
#     nearby_cafes: List[str] = []
#     nearby_attractions: List[str] = []
#     nearby_malls: List[str] = []
#     nearby_theatres: List[str] = []
#     nearby_libraries: List[str] = []
#     nearby_gyms: List[str] = []

#     coords: Optional[Tuple[float, float]] = None
#     if postal_code:
#         coords = _geocode_postal_code(postal_code)

#     if coords:
#         lat, lng = coords

#         # Movement / nature
#         nearby_parks = _nearby_places(lat, lng, "park", max_results=5)
#         # Social / talk / coffee
#         nearby_cafes = _nearby_places(lat, lng, "cafe", max_results=5)
#         # Entertainment / sightseeing
#         nearby_attractions = _nearby_places(lat, lng, "tourist_attraction", max_results=5)
#         nearby_malls = _nearby_places(lat, lng, "shopping_mall", max_results=5)
#         nearby_theatres = _nearby_places(lat, lng, "movie_theater", max_results=5)
#         # Quiet focus / learning
#         nearby_libraries = _nearby_places(lat, lng, "library", max_results=5)
#         # Movement in non-nature spaces
#         nearby_gyms = _nearby_places(lat, lng, "gym", max_results=5)

#         if nearby_parks:
#             context_bits.append("nearby_parks: " + ", ".join(nearby_parks))
#         if nearby_cafes:
#             context_bits.append("nearby_cafes: " + ", ".join(nearby_cafes))
#         if nearby_attractions:
#             context_bits.append("nearby_attractions: " + ", ".join(nearby_attractions))
#         if nearby_malls:
#             context_bits.append("nearby_malls: " + ", ".join(nearby_malls))
#         if nearby_theatres:
#             context_bits.append("nearby_theatres: " + ", ".join(nearby_theatres))
#         if nearby_libraries:
#             context_bits.append("nearby_libraries: " + ", ".join(nearby_libraries))
#         if nearby_gyms:
#             context_bits.append("nearby_gyms: " + ", ".join(nearby_gyms))

#     context_text = "; ".join(context_bits) or "no extra context provided"

#     # We'll also keep a combined list of all place names for backend overriding.
#     all_nearby_places: List[str] = (
#         nearby_parks
#         + nearby_cafes
#         + nearby_attractions
#         + nearby_malls
#         + nearby_theatres
#         + nearby_libraries
#         + nearby_gyms
#     )

#     system_msg = (
#         "You are a behavioural activation coach designing very small, realistic, "
#         "real-world activities for a mental health app.\n"
#         "Each activity must be:\n"
#         "- concrete and doable in 5–30 minutes\n"
#         "- safe and gentle (no extreme exercise, no unsafe locations)\n"
#         "- described in simple language\n"
#         "- If you reference a place (park, cafe, mall, theatre, library, attraction, gym), "
#         "you MUST use the exact name from the provided nearby_* lists.\n"
#         "- Do NOT invent or tweak place names (e.g., do not say 'Durham Riverside' "
#         "unless that exact string is in the nearby lists).\n\n"
#         "MATCH PLACE TYPE TO THE USER'S GOAL:\n"
#         "- Goals about movement / steps / walk / exercise -> prefer parks or gyms.\n"
#         "- Goals about talking, connection, not feeling alone -> prefer cafes or other social spaces.\n"
#         "- Goals about chilling, recharging, entertainment -> prefer malls, theatres, or gentle attractions.\n"
#         "- Goals about focus, work, study, reading -> prefer libraries or quiet cafes.\n"
#         "Avoid suggesting only walks in parks unless that clearly matches the goal.\n"
#         "Where possible, vary the place types across the 3 place-based activities.\n\n"
#         "You can use BA flavours like Movement, Connection, Creative, Grounding, "
#         "or Self-compassion. Use tags to encode this.\n"
#     )

#     user_msg = (
#         f"User context: {context_text}\n\n"
#         "Generate EXACTLY 6 activities in this order:\n"
#         "1–3: PLACE-BASED activities that use real nearby places from the lists. "
#         "Choose the type of place that best fits the user's goal and mood "
#         "(e.g., cafe for talking to someone, mall/theatre for chill, park/gym for movement, "
#         "library for focused work). Mark them with a '+ PlaceBased' tag.\n"
#         "4–6: GOAL-BASED BA activities (like 'Coffee with Maya', 'Call Mom', "
#         "'Morning Pages', 'Farmers Market Visit'). These can be at home, on the phone, "
#         "or generic. Mark them with a '+ GoalBased' tag.\n\n"
#         "For GOAL-BASED items, also include a tag of the form "
#         "'Supports: <short phrase>' explaining how it supports their goal.\n\n"
#         "Return ONLY JSON in this exact format (no extra commentary):\n"
#         "{\n"
#         '  \"activities\": [\n'
#         "    {\n"
#         '      \"title\": \"short name\",\n'
#         '      \"description\": \"2–3 sentence description of what to do\",\n'
#         '      \"life_area\": \"Movement | Connection | Creative | Grounding | Self-compassion | Work\",\n'
#         '      \"effort_level\": \"low | medium | high\",\n'
#         '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
#         '      \"default_duration_min\": 5,\n'
#         '      \"location_label\": \"Exact place name from nearby lists, or \'at home\' / \'anywhere comfortable\' for goal-based items\",\n'
#         '      \"tags\": [\"+ PlaceBased or + GoalBased\", \"BA flavour like Movement/Connection\", \"Supports: ... for goal-based\"]\n'
#         "    }\n"
#         "  ]\n"
#         "}"
#     )

#     # Use new v1 chat completions client
#     try:
#         resp = client.chat.completions.create(
#             model=OPENAI_ACTIVITY_MODEL,
#             messages=[
#                 {"role": "system", "content": system_msg},
#                 {"role": "user", "content": user_msg},
#             ],
#             temperature=0.7,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")

#     # Parse JSON from model output
#     try:
#         content = resp.choices[0].message.content
#         data = json.loads(content)
#         items = data.get("activities") or []
#     except json.JSONDecodeError:
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to parse OpenAI JSON for activities",
#         )

#     activities: List[schemas.ActivityBase] = []

#     # Helper: choose a concrete place name based on life_area
#     def pick_place_for_life_area(life_area: str) -> Optional[str]:
#         la = (life_area or "").lower()

#         # Heuristic mapping: pick from the most relevant category first
#         if "movement" in la:
#             candidates = nearby_parks + nearby_gyms
#         elif "connection" in la:
#             candidates = nearby_cafes + nearby_malls + nearby_theatres
#         elif "work" in la:
#             candidates = nearby_libraries + nearby_cafes
#         elif "creative" in la:
#             candidates = nearby_attractions + nearby_malls
#         elif "grounding" in la or "self" in la:
#             candidates = nearby_parks + nearby_attractions
#         else:
#             candidates = all_nearby_places

#         if not candidates:
#             candidates = all_nearby_places

#         return candidates[0] if candidates else None

#     for item in items:
#         try:
#             title = (item.get("title") or "").strip() or "Small step"
#             description = (item.get("description") or "").strip() or "Take a small helpful step."
#             life_area = item.get("life_area", "Meaning")
#             effort_level = item.get("effort_level", "low")
#             reward_type = item.get("reward_type")
#             default_duration_min = item.get("default_duration_min") or 10
#             tags = item.get("tags") or []
#             location_label = item.get("location_label")

#             # --- Backend override: if it's PlaceBased, force a real nearby place name ---
#             is_place_based = any("+ PlaceBased" in str(t) for t in tags)

#             if is_place_based and all_nearby_places:
#                 picked = pick_place_for_life_area(life_area)
#                 if picked:
#                     location_label = picked

#             act = schemas.ActivityBase(
#                 title=title,
#                 description=description,
#                 life_area=life_area,
#                 effort_level=effort_level,
#                 reward_type=reward_type,
#                 default_duration_min=default_duration_min,
#                 location_label=location_label,
#                 tags=tags,
#             )
#             activities.append(act)
#         except Exception:
#             continue

#     if not activities:
#         raise HTTPException(status_code=500, detail="OpenAI returned no valid activities")

#     return activities


# # --------- Store generated activities in DB (no global cache) ---------


# def _store_generated_activities(
#     db: Session,
#     *,
#     activities: List[schemas.ActivityBase],
# ) -> List[models.Activities]:
#     """
#     Persist a batch of generated activities.
#     We do NOT reuse previous batches for new recommendations – each call
#     can create its own activities tied to that moment / context.
#     """
#     now = datetime.utcnow()
#     rows: List[models.Activities] = []

#     for a in activities:
#         row = models.Activities(
#             title=a.title,
#             description=a.description,
#             life_area=a.life_area,
#             effort_level=a.effort_level,
#             reward_type=a.reward_type,
#             default_duration_min=a.default_duration_min,
#             location_label=a.location_label,
#             tags_json=json.dumps(a.tags or []),
#             is_active=True,
#             created_at=now,
#         )
#         db.add(row)
#         rows.append(row)

#     db.commit()
#     for r_obj in rows:
#         db.refresh(r_obj)

#     return rows


# # ---------------- Public endpoints ----------------

# @r.get(
#     "/recommendation",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation",
# )
# def get_recommendation(
#     user_hash: Optional[str] = Query(None, description="Optional user hash"),
#     life_area: Optional[str] = Query(None, description="Preferred life area filter, e.g., 'Connection'"),
#     mood: Optional[str] = Query(None, description="Current mood (from intake)"),
#     schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
#     postal_code: Optional[str] = Query(None, description="Postal code, e.g., L18 2QA"),
#     goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
#     place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return SIX LLM-generated BA activities, tailored to *this* request.

#     - 3 place-based (with '+ PlaceBased' tag, using exact nearby place names).
#     - 3 goal-based BA actions (with '+ GoalBased' tag and 'Supports: ...' tag).
#     """

#     generated = _generate_activities_via_llm(
#         mood=mood,
#         schema_hint=schema_hint,
#         postal_code=postal_code,
#         goal_today=goal_today,
#         place=place,
#         count=6,
#     )

#     rows = _store_generated_activities(db, activities=generated)

#     # Optional life_area filter over this batch only (e.g. 'Connection', 'Movement')
#     if life_area:
#         filtered = [
#             r_
#             for r_ in rows
#             if (r_.life_area or "").lower() == life_area.lower()
#         ]
#         candidates = filtered or rows
#     else:
#         candidates = rows

#     if not candidates:
#         raise HTTPException(status_code=404, detail="No activities available")

#     # For now just return the whole batch for this request (up to 6)
#     selected = sorted(
#         candidates,
#         key=lambda x: x.created_at or datetime.utcnow(),
#         reverse=True,
#     )[:6]

#     recs: List[schemas.ActivityRecommendationOut] = []
#     for act in selected:
#         tags: List[str] = []
#         if act.tags_json:
#             try:
#                 tags = json.loads(act.tags_json)
#             except Exception:
#                 tags = []
#         recs.append(
#             schemas.ActivityRecommendationOut(
#                 id=act.id,
#                 title=act.title,
#                 description=act.description,
#                 life_area=act.life_area,
#                 effort_level=act.effort_level,
#                 reward_type=act.reward_type,
#                 default_duration_min=act.default_duration_min,
#                 location_label=act.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityRecommendationListOut(activities=recs)


# @r.get(
#     "/library",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library",
# )
# def get_library(
#     db: Session = Depends(get_db),
# ):
#     """
#     Return the full activity library.
#     This is basically all activities that have ever been generated and stored.
#     """

#     acts = (
#         db.query(models.Activities)
#         .filter(models.Activities.is_active == True)
#         .order_by(models.Activities.created_at.desc())
#         .all()
#     )

#     out: List[schemas.ActivityOut] = []
#     for a in acts:
#         tags: List[str] = []
#         if a.tags_json:
#             try:
#                 tags = json.loads(a.tags_json)
#             except Exception:
#                 tags = []
#         out.append(
#             schemas.ActivityOut(
#                 id=a.id,
#                 title=a.title,
#                 description=a.description,
#                 life_area=a.life_area,
#                 effort_level=a.effort_level,
#                 reward_type=a.reward_type,
#                 default_duration_min=a.default_duration_min,
#                 location_label=a.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityListOut(activities=out)


# @r.post(
#     "/start",
#     summary="Start Activity",
# )
# def start_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=act.id,
#         session_id=payload.session_id,
#         status="started",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()

#     return {"ok": True}


# @r.post(
#     "/swap",
#     summary="Swap Activity",
# )
# def swap_activity(
#     payload: schemas.ActivitySwapIn,
#     db: Session = Depends(get_db),
# ):
#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=payload.activity_id,
#         status="swapped",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     return {"ok": True}



# from __future__ import annotations

# import json
# import math
# from datetime import datetime
# from typing import List, Optional, Tuple

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session

# from app.db import SessionLocal
# from app import models, schemas
# from app.core.config import cfg as c

# # ---------------- OpenAI setup ----------------

# from openai import OpenAI

# # use the same OPENAI_API_KEY as your script generator
# client = OpenAI(api_key=c.OPENAI_API_KEY)
# OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

# r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])


# # ---------------- DB dependency ----------------

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---------------- Google Maps helpers ----------------

# def _geocode_postal_code(postal_code: str) -> Optional[Tuple[float, float]]:
#     """
#     postal_code -> (lat, lng) using Google Geocoding.
#     Returns None on any error so we can gracefully fall back.
#     """
#     if not c.GOOGLE_MAPS_API_KEY or not postal_code:
#         return None

#     url = "https://maps.googleapis.com/maps/api/geocode/json"
#     params = {"address": postal_code, "key": c.GOOGLE_MAPS_API_KEY}

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#         if data.get("status") != "OK":
#             return None
#         loc = data["results"][0]["geometry"]["location"]
#         return float(loc["lat"]), float(loc["lng"])
#     except Exception:
#         return None


# def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
#     """
#     Haversine distance between two lat/lng points in meters.
#     """
#     R = 6371000  # Earth radius in meters
#     phi1 = math.radians(lat1)
#     phi2 = math.radians(lat2)
#     dphi = math.radians(lat2 - lat1)
#     dlambda = math.radians(lng2 - lng1)

#     a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
#     c_ = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
#     return R * c_


# def _nearby_places(
#     lat: float,
#     lng: float,
#     place_type: str,
#     radius_m: int = 1200,
#     max_results: int = 5,
# ) -> List[str]:
#     """
#     Generic helper: look up nearby places of a given type.

#     We explicitly enforce that returned places are within `radius_m`
#     of the reference point, to keep recommendations VERY close to
#     the user's postal code.
#     """
#     if not c.GOOGLE_MAPS_API_KEY:
#         return []

#     url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
#     params = {
#         "location": f"{lat},{lng}",
#         "radius": radius_m,  # tight circle around the user
#         "type": place_type,
#         "key": c.GOOGLE_MAPS_API_KEY,
#     }

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#     except Exception:
#         return []

#     results = data.get("results") or []
#     names: List[str] = []

#     for r_ in results:
#         if len(names) >= max_results:
#             break

#         name = r_.get("name")
#         loc = (r_.get("geometry") or {}).get("location") or {}
#         lat2 = loc.get("lat")
#         lng2 = loc.get("lng")

#         if not name or lat2 is None or lng2 is None:
#             continue

#         # Enforce "very close" – cut off anything outside radius_m.
#         dist = _distance_meters(lat, lng, float(lat2), float(lng2))
#         if dist > radius_m:
#             continue

#         names.append(name.strip())

#     return names


# # ---------------- OpenAI helper ----------------

# def _generate_activities_via_llm(
#     *,
#     mood: Optional[str],
#     schema_hint: Optional[str],
#     postal_code: Optional[str],
#     goal_today: Optional[str],
#     place: Optional[str],
#     count: int = 6,
# ) -> List[schemas.ActivityBase]:
#     """
#     Call OpenAI to generate a small set of concrete BA activities.

#     We ask for EXACTLY 6:
#     - First 3: place-based activities using real nearby place names
#       (parks / cafes / malls / theatres / libraries / gyms / attractions).
#     - Last 3: goal-based BA activities like "Coffee with Maya",
#       "Call Mom", "Morning Pages", linked to the therapy goal.
#     """

#     # --- build context text ---
#     context_bits: List[str] = []
#     if mood:
#         context_bits.append(f"current mood: {mood}")
#     if schema_hint:
#         context_bits.append(f"schema or core story: {schema_hint}")
#     if goal_today:
#         context_bits.append(f"today's goal: {goal_today}")
#     if place:
#         context_bits.append(f"preferred environment: {place}")
#     if postal_code:
#         context_bits.append(f"postal code: {postal_code}")

#     nearby_parks: List[str] = []
#     nearby_cafes: List[str] = []
#     nearby_attractions: List[str] = []
#     nearby_malls: List[str] = []
#     nearby_theatres: List[str] = []
#     nearby_libraries: List[str] = []
#     nearby_gyms: List[str] = []

#     coords: Optional[Tuple[float, float]] = None
#     if postal_code:
#         coords = _geocode_postal_code(postal_code)

#     if coords:
#         lat, lng = coords

#         # Movement / nature
#         nearby_parks = _nearby_places(lat, lng, "park", max_results=5)
#         # Social / talk / coffee
#         nearby_cafes = _nearby_places(lat, lng, "cafe", max_results=5)
#         # Entertainment / sightseeing
#         nearby_attractions = _nearby_places(lat, lng, "tourist_attraction", max_results=5)
#         nearby_malls = _nearby_places(lat, lng, "shopping_mall", max_results=5)
#         nearby_theatres = _nearby_places(lat, lng, "movie_theater", max_results=5)
#         # Quiet focus / learning
#         nearby_libraries = _nearby_places(lat, lng, "library", max_results=5)
#         # Movement in non-nature spaces
#         nearby_gyms = _nearby_places(lat, lng, "gym", max_results=5)

#         if nearby_parks:
#             context_bits.append("nearby_parks: " + ", ".join(nearby_parks))
#         if nearby_cafes:
#             context_bits.append("nearby_cafes: " + ", ".join(nearby_cafes))
#         if nearby_attractions:
#             context_bits.append("nearby_attractions: " + ", ".join(nearby_attractions))
#         if nearby_malls:
#             context_bits.append("nearby_malls: " + ", ".join(nearby_malls))
#         if nearby_theatres:
#             context_bits.append("nearby_theatres: " + ", ".join(nearby_theatres))
#         if nearby_libraries:
#             context_bits.append("nearby_libraries: " + ", ".join(nearby_libraries))
#         if nearby_gyms:
#             context_bits.append("nearby_gyms: " + ", ".join(nearby_gyms))

#     context_text = "; ".join(context_bits) or "no extra context provided"

#     # Combined list of all place names for backend overriding.
#     all_nearby_places: List[str] = (
#         nearby_parks
#         + nearby_cafes
#         + nearby_attractions
#         + nearby_malls
#         + nearby_theatres
#         + nearby_libraries
#         + nearby_gyms
#     )

#     system_msg = (
#         "You are a behavioural activation coach designing very small, realistic, "
#         "real-world activities for a mental health app.\n"
#         "Each activity must be:\n"
#         "- concrete and doable in 5–30 minutes\n"
#         "- safe and gentle (no extreme exercise, no unsafe locations)\n"
#         "- described in simple language\n"
#         "- If you reference a place (park, cafe, mall, theatre, library, attraction, gym), "
#         "you MUST use the exact name from the provided nearby_* lists.\n"
#         "- Do NOT invent or tweak place names (e.g., do not say 'Durham Riverside' "
#         "unless that exact string is in the nearby lists).\n\n"
#         "MATCH PLACE TYPE TO THE USER'S GOAL:\n"
#         "- Goals about movement / steps / walk / exercise -> prefer parks or gyms.\n"
#         "- Goals about talking, connection, not feeling alone -> prefer cafes or other social spaces.\n"
#         "- Goals about chilling, recharging, entertainment -> prefer malls, theatres, or gentle attractions.\n"
#         "- Goals about focus, work, study, reading -> prefer libraries or quiet cafes.\n"
#         "Avoid suggesting only walks in parks unless that clearly matches the goal.\n"
#         "Where possible, vary the place types across the 3 place-based activities.\n\n"
#         "You can use BA flavours like Movement, Connection, Creative, Grounding, "
#         "or Self-compassion. Use tags to encode this.\n"
#     )

#     user_msg = (
#         f"User context: {context_text}\n\n"
#         "Generate EXACTLY 6 activities in this order:\n"
#         "1–3: PLACE-BASED activities that use real nearby places from the lists. "
#         "Choose the type of place that best fits the user's goal and mood "
#         "(e.g., cafe for talking to someone, mall/theatre for chill, park/gym for movement, "
#         "library for focused work). Mark them with a '+ PlaceBased' tag.\n"
#         "4–6: GOAL-BASED BA activities (like 'Coffee with Maya', 'Call Mom', "
#         "'Morning Pages', 'Farmers Market Visit'). These can be at home, on the phone, "
#         "or generic. Mark them with a '+ GoalBased' tag.\n\n"
#         "For GOAL-BASED items, also include a tag of the form "
#         "'Supports: <short phrase>' explaining how it supports their goal.\n\n"
#         "Return ONLY JSON in this exact format (no extra commentary):\n"
#         "{\n"
#         '  \"activities\": [\n'
#         "    {\n"
#         '      \"title\": \"short name\",\n'
#         '      \"description\": \"2–3 sentence description of what to do\",\n'
#         '      \"life_area\": \"Movement | Connection | Creative | Grounding | Self-compassion | Work | Body\",\n'
#         '      \"effort_level\": \"low | medium | high\",\n'
#         '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
#         '      \"default_duration_min\": 5,\n'
#         '      \"location_label\": \"Exact place name from nearby lists, or \'at home\' / \'anywhere comfortable\' for goal-based items\",\n'
#         '      \"tags\": [\"+ PlaceBased or + GoalBased\", \"BA flavour like Movement/Connection\", \"Supports: ... for goal-based\"]\n'
#         "    }\n"
#         "  ]\n"
#         "}"
#     )

#     # Use new v1 chat completions client
#     try:
#         resp = client.chat.completions.create(
#             model=OPENAI_ACTIVITY_MODEL,
#             messages=[
#                 {"role": "system", "content": system_msg},
#                 {"role": "user", "content": user_msg},
#             ],
#             temperature=0.7,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")

#     # Parse JSON from model output
#     try:
#         content = resp.choices[0].message.content
#         data = json.loads(content)
#         items = data.get("activities") or []
#     except json.JSONDecodeError:
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to parse OpenAI JSON for activities",
#         )

#     # ---- FORCE TAGS FOR FIRST 3 / LAST 3 ----
#     for idx, item in enumerate(items):
#         tags = item.get("tags") or []
#         # First 3: must be PlaceBased
#         if idx < 3 and not any("+ PlaceBased" in str(t) for t in tags):
#             tags.append("+ PlaceBased")
#         # Last 3: must be GoalBased
#         if idx >= 3 and not any("+ GoalBased" in str(t) for t in tags):
#             tags.append("+ GoalBased")
#         item["tags"] = tags

#     activities: List[schemas.ActivityBase] = []

#     # Helper: choose a concrete place name based on life_area
#     def pick_place_for_life_area(life_area: str) -> Optional[str]:
#         la = (life_area or "").lower()

#         # Heuristic mapping: pick from the most relevant category first
#         if any(word in la for word in ["movement", "body", "exercise"]):
#             candidates = nearby_parks + nearby_gyms
#         elif any(word in la for word in ["connection", "social", "talk"]):
#             candidates = nearby_cafes + nearby_malls + nearby_theatres
#         elif any(word in la for word in ["work", "focus", "study"]):
#             candidates = nearby_libraries + nearby_cafes
#         elif any(word in la for word in ["creative", "art", "play"]):
#             candidates = nearby_attractions + nearby_malls
#         elif any(word in la for word in ["grounding", "calm", "self"]):
#             candidates = nearby_parks + nearby_attractions
#         else:
#             candidates = all_nearby_places

#         if not candidates:
#             candidates = all_nearby_places

#         return candidates[0] if candidates else None

#     for item in items:
#         try:
#             title = (item.get("title") or "").strip() or "Small step"
#             description = (item.get("description") or "").strip() or "Take a small helpful step."
#             life_area = item.get("life_area", "Meaning")
#             effort_level = item.get("effort_level", "low")
#             reward_type = item.get("reward_type")
#             default_duration_min = item.get("default_duration_min") or 10
#             tags = item.get("tags") or []
#             location_label = item.get("location_label")

#             # --- Backend override: if it's PlaceBased, force a real nearby place name ---
#             is_place_based = any("+ PlaceBased" in str(t) for t in tags)

#             if is_place_based and all_nearby_places:
#                 picked = pick_place_for_life_area(life_area)
#                 if picked:
#                     location_label = picked

#             act = schemas.ActivityBase(
#                 title=title,
#                 description=description,
#                 life_area=life_area,
#                 effort_level=effort_level,
#                 reward_type=reward_type,
#                 default_duration_min=default_duration_min,
#                 location_label=location_label,
#                 tags=tags,
#             )
#             activities.append(act)
#         except Exception:
#             continue

#     if not activities:
#         raise HTTPException(status_code=500, detail="OpenAI returned no valid activities")

#     return activities


# # --------- Store generated activities in DB (no global cache) ---------


# def _store_generated_activities(
#     db: Session,
#     *,
#     activities: List[schemas.ActivityBase],
# ) -> List[models.Activities]:
#     """
#     Persist a batch of generated activities.
#     We do NOT reuse previous batches for new recommendations – each call
#     can create its own activities tied to that moment / context.
#     """
#     now = datetime.utcnow()
#     rows: List[models.Activities] = []

#     for a in activities:
#         row = models.Activities(
#             title=a.title,
#             description=a.description,
#             life_area=a.life_area,
#             effort_level=a.effort_level,
#             reward_type=a.reward_type,
#             default_duration_min=a.default_duration_min,
#             location_label=a.location_label,
#             tags_json=json.dumps(a.tags or []),
#             is_active=True,
#             created_at=now,
#         )
#         db.add(row)
#         rows.append(row)

#     db.commit()
#     for r_obj in rows:
#         db.refresh(r_obj)

#     return rows


# # ---------------- Public endpoints ----------------

# @r.get(
#     "/recommendation",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation",
# )
# @r.get(
#     "/recommend",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation (alias)",
#     include_in_schema=False,
# )
# def get_recommendation(
#     user_hash: Optional[str] = Query(None, description="Optional user hash"),
#     life_area: Optional[str] = Query(None, description="Preferred life area filter, e.g., 'Connection'"),
#     mood: Optional[str] = Query(None, description="Current mood (from intake)"),
#     schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
#     postal_code: Optional[str] = Query(None, description="Postal code, e.g., L18 2QA"),
#     goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
#     place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
#     limit: int = Query(6, ge=1, le=20, description="Maximum number of activities to return"),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return up to `limit` LLM-generated BA activities, tailored to *this* request.

#     - 3 place-based (with '+ PlaceBased' tag, using exact nearby place names).
#     - 3 goal-based BA actions (with '+ GoalBased' tag and 'Supports: ...' tag).
#     """

#     generated = _generate_activities_via_llm(
#         mood=mood,
#         schema_hint=schema_hint,
#         postal_code=postal_code,
#         goal_today=goal_today,
#         place=place,
#         count=6,
#     )

#     rows = _store_generated_activities(db, activities=generated)

#     # Optional life_area filter over this batch only (e.g. 'Connection', 'Movement')
#     if life_area:
#         filtered = [
#             r_
#             for r_ in rows
#             if (r_.life_area or "").lower() == life_area.lower()
#         ]
#         candidates = filtered or rows
#     else:
#         candidates = rows

#     if not candidates:
#         raise HTTPException(status_code=404, detail="No activities available")

#     # Return up to `limit` from this batch
#     selected = sorted(
#         candidates,
#         key=lambda x: x.created_at or datetime.utcnow(),
#         reverse=True,
#     )[:limit]

#     recs: List[schemas.ActivityRecommendationOut] = []
#     for act in selected:
#         tags: List[str] = []
#         if act.tags_json:
#             try:
#                 tags = json.loads(act.tags_json)
#             except Exception:
#                 tags = []
#         recs.append(
#             schemas.ActivityRecommendationOut(
#                 id=act.id,
#                 title=act.title,
#                 description=act.description,
#                 life_area=act.life_area,
#                 effort_level=act.effort_level,
#                 reward_type=act.reward_type,
#                 default_duration_min=act.default_duration_min,
#                 location_label=act.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityRecommendationListOut(activities=recs)


# @r.get(
#     "/library",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library",
# )
# @r.get(
#     "/list",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library (alias)",
#     include_in_schema=False,
# )
# def get_library(
#     db: Session = Depends(get_db),
# ):
#     """
#     Return the full activity library.
#     This is basically all activities that have ever been generated and stored.
#     """

#     acts = (
#         db.query(models.Activities)
#         .filter(models.Activities.is_active == True)
#         .order_by(models.Activities.created_at.desc())
#         .all()
#     )

#     out: List[schemas.ActivityOut] = []
#     for a in acts:
#         tags: List[str] = []
#         if a.tags_json:
#             try:
#                 tags = json.loads(a.tags_json)
#             except Exception:
#                 tags = []
#         out.append(
#             schemas.ActivityOut(
#                 id=a.id,
#                 title=a.title,
#                 description=a.description,
#                 life_area=a.life_area,
#                 effort_level=a.effort_level,
#                 reward_type=a.reward_type,
#                 default_duration_min=a.default_duration_min,
#                 location_label=a.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityListOut(activities=out)


# @r.post(
#     "/start",
#     summary="Start Activity",
# )
# def start_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=act.id,
#         session_id=payload.session_id,
#         status="started",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     db.refresh(row)

#     # Frontend hook can use this id as activitySessionId
#     return {"ok": True, "activity_session_id": row.id}


# @r.post(
#     "/swap",
#     summary="Swap Activity",
# )
# def swap_activity(
#     payload: schemas.ActivitySwapIn,
#     db: Session = Depends(get_db),
# ):
#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=payload.activity_id,
#         status="swapped",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     return {"ok": True}




# from __future__ import annotations

# import json
# import math
# from datetime import datetime
# from typing import List, Optional, Tuple

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session

# from app.db import SessionLocal
# from app import models, schemas
# from app.core.config import cfg as c

# # ---------------- OpenAI setup ----------------

# from openai import OpenAI

# # use the same OPENAI_API_KEY as your script generator
# client = OpenAI(api_key=c.OPENAI_API_KEY)
# OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

# r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])


# # ---------------- DB dependency ----------------

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---------------- Google Maps helpers ----------------

# def _geocode_postal_code(postal_code: str) -> Optional[Tuple[float, float]]:
#     """
#     postal_code -> (lat, lng) using Google Geocoding.
#     Returns None on any error so we can gracefully fall back.
#     """
#     if not c.GOOGLE_MAPS_API_KEY or not postal_code:
#         return None

#     url = "https://maps.googleapis.com/maps/api/geocode/json"
#     params = {"address": postal_code, "key": c.GOOGLE_MAPS_API_KEY}

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#         if data.get("status") != "OK":
#             return None
#         loc = data["results"][0]["geometry"]["location"]
#         return float(loc["lat"]), float(loc["lng"])
#     except Exception:
#         return None


# def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
#     """
#     Haversine distance between two lat/lng points in meters.
#     """
#     R = 6371000  # Earth radius in meters
#     phi1 = math.radians(lat1)
#     phi2 = math.radians(lat2)
#     dphi = math.radians(lat2 - lat1)
#     dlambda = math.radians(lng2 - lng1)

#     a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
#     c_ = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
#     return R * c_


# def _nearby_places(
#     lat: float,
#     lng: float,
#     place_type: str,
#     radius_m: int = 1200,
#     max_results: int = 5,
# ) -> List[str]:
#     """
#     Generic helper: look up nearby places of a given type.

#     We explicitly enforce that returned places are within `radius_m`
#     of the reference point, to keep recommendations VERY close to
#     the user's postal code.
#     """
#     if not c.GOOGLE_MAPS_API_KEY:
#         return []

#     url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
#     params = {
#         "location": f"{lat},{lng}",
#         "radius": radius_m,  # tight circle around the user
#         "type": place_type,
#         "key": c.GOOGLE_MAPS_API_KEY,
#     }

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#     except Exception:
#         return []

#     results = data.get("results") or []
#     names: List[str] = []

#     for r_ in results:
#         if len(names) >= max_results:
#             break

#         name = r_.get("name")
#         loc = (r_.get("geometry") or {}).get("location") or {}
#         lat2 = loc.get("lat")
#         lng2 = loc.get("lng")

#         if not name or lat2 is None or lng2 is None:
#             continue

#         # Enforce "very close" – cut off anything outside radius_m.
#         dist = _distance_meters(lat, lng, float(lat2), float(lng2))
#         if dist > radius_m:
#             continue

#         names.append(name.strip())

#     return names


# # ---------------- OpenAI helper ----------------

# def _generate_activities_via_llm(
#     *,
#     mood: Optional[str],
#     schema_hint: Optional[str],
#     postal_code: Optional[str],
#     goal_today: Optional[str],
#     place: Optional[str],
#     count: int = 6,
# ) -> List[schemas.ActivityBase]:
#     """
#     Call OpenAI to generate a small set of concrete BA activities.

#     We ask for EXACTLY 6:
#     - First 3: place-based activities using real nearby place names
#       (parks / cafes / malls / theatres / libraries / gyms / attractions).
#     - Last 3: goal-based BA activities like "Coffee with Maya",
#       "Call Mom", "Morning Pages", linked to the therapy goal.
#     """

#     # --- build context text ---
#     context_bits: List[str] = []
#     if mood:
#         context_bits.append(f"current mood: {mood}")
#     if schema_hint:
#         context_bits.append(f"schema or core story: {schema_hint}")
#     if goal_today:
#         context_bits.append(f"today's goal: {goal_today}")
#     if place:
#         context_bits.append(f"preferred environment: {place}")
#     if postal_code:
#         context_bits.append(f"postal code: {postal_code}")

#     nearby_parks: List[str] = []
#     nearby_cafes: List[str] = []
#     nearby_attractions: List[str] = []
#     nearby_malls: List[str] = []
#     nearby_theatres: List[str] = []
#     nearby_libraries: List[str] = []
#     nearby_gyms: List[str] = []

#     coords: Optional[Tuple[float, float]] = None
#     if postal_code:
#         coords = _geocode_postal_code(postal_code)

#     if coords:
#         lat, lng = coords

#         # Movement / nature
#         nearby_parks = _nearby_places(lat, lng, "park", max_results=5)
#         # Social / talk / coffee
#         nearby_cafes = _nearby_places(lat, lng, "cafe", max_results=5)
#         # Entertainment / sightseeing
#         nearby_attractions = _nearby_places(lat, lng, "tourist_attraction", max_results=5)
#         nearby_malls = _nearby_places(lat, lng, "shopping_mall", max_results=5)
#         nearby_theatres = _nearby_places(lat, lng, "movie_theater", max_results=5)
#         # Quiet focus / learning
#         nearby_libraries = _nearby_places(lat, lng, "library", max_results=5)
#         # Movement in non-nature spaces
#         nearby_gyms = _nearby_places(lat, lng, "gym", max_results=5)

#         if nearby_parks:
#             context_bits.append("nearby_parks: " + ", ".join(nearby_parks))
#         if nearby_cafes:
#             context_bits.append("nearby_cafes: " + ", ".join(nearby_cafes))
#         if nearby_attractions:
#             context_bits.append("nearby_attractions: " + ", ".join(nearby_attractions))
#         if nearby_malls:
#             context_bits.append("nearby_malls: " + ", ".join(nearby_malls))
#         if nearby_theatres:
#             context_bits.append("nearby_theatres: " + ", ".join(nearby_theatres))
#         if nearby_libraries:
#             context_bits.append("nearby_libraries: " + ", ".join(nearby_libraries))
#         if nearby_gyms:
#             context_bits.append("nearby_gyms: " + ", ".join(nearby_gyms))

#     context_text = "; ".join(context_bits) or "no extra context provided"

#     # Combined list of all place names for backend overriding.
#     all_nearby_places: List[str] = (
#         nearby_parks
#         + nearby_cafes
#         + nearby_attractions
#         + nearby_malls
#         + nearby_theatres
#         + nearby_libraries
#         + nearby_gyms
#     )

#     system_msg = (
#         "You are a behavioural activation coach designing very small, realistic, "
#         "real-world activities for a mental health app.\n"
#         "Each activity must be:\n"
#         "- concrete and doable in 5–30 minutes\n"
#         "- safe and gentle (no extreme exercise, no unsafe locations)\n"
#         "- described in simple language\n"
#         "- If you reference a place (park, cafe, mall, theatre, library, attraction, gym), "
#         "you MUST use the exact name from the provided nearby_* lists.\n"
#         "- Do NOT invent or tweak place names (e.g., do not say 'Durham Riverside' "
#         "unless that exact string is in the nearby lists).\n\n"
#         "MATCH PLACE TYPE TO THE USER'S GOAL:\n"
#         "- Goals about movement / steps / walk / exercise -> prefer parks or gyms.\n"
#         "- Goals about talking, connection, not feeling alone -> prefer cafes or other social spaces.\n"
#         "- Goals about chilling, recharging, entertainment -> prefer malls, theatres, or gentle attractions.\n"
#         "- Goals about focus, work, study, reading -> prefer libraries or quiet cafes.\n"
#         "Avoid suggesting only walks in parks unless that clearly matches the goal.\n"
#         "Where possible, vary the place types across the 3 place-based activities.\n\n"
#         "You can use BA flavours like Movement, Connection, Creative, Grounding, "
#         "or Self-compassion. Use tags to encode this.\n"
#     )

#     user_msg = (
#         f"User context: {context_text}\n\n"
#         "Generate EXACTLY 6 activities in this order:\n"
#         "1–3: PLACE-BASED activities that use real nearby places from the lists. "
#         "Choose the type of place that best fits the user's goal and mood "
#         "(e.g., cafe for talking to someone, mall/theatre for chill, park/gym for movement, "
#         "library for focused work). Mark them with a '+ PlaceBased' tag.\n"
#         "4–6: GOAL-BASED BA activities (like 'Coffee with Maya', 'Call Mom', "
#         "'Morning Pages', 'Farmers Market Visit'). These can be at home, on the phone, "
#         "or generic. Mark them with a '+ GoalBased' tag.\n\n"
#         "For GOAL-BASED items, also include a tag of the form "
#         "'Supports: <short phrase>' explaining how it supports their goal.\n\n"
#         "Return ONLY JSON in this exact format (no extra commentary):\n"
#         "{\n"
#         '  \"activities\": [\n'
#         "    {\n"
#         '      \"title\": \"short name\",\n'
#         '      \"description\": \"2–3 sentence description of what to do\",\n'
#         '      \"life_area\": \"Movement | Connection | Creative | Grounding | Self-compassion | Work | Body\",\n'
#         '      \"effort_level\": \"low | medium | high\",\n'
#         '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
#         '      \"default_duration_min\": 5,\n'
#         '      \"location_label\": \"Exact place name from nearby lists, or \'at home\' / \'anywhere comfortable\' for goal-based items\",\n'
#         '      \"tags\": [\"+ PlaceBased or + GoalBased\", \"BA flavour like Movement/Connection\", \"Supports: ... for goal-based\"]\n'
#         "    }\n"
#         "  ]\n"
#         "}"
#     )

#     # Use new v1 chat completions client
#     try:
#         resp = client.chat.completions.create(
#             model=OPENAI_ACTIVITY_MODEL,
#             messages=[
#                 {"role": "system", "content": system_msg},
#                 {"role": "user", "content": user_msg},
#             ],
#             temperature=0.7,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")

#     # Parse JSON from model output
#     try:
#         content = resp.choices[0].message.content
#         data = json.loads(content)
#         items = data.get("activities") or []
#     except json.JSONDecodeError:
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to parse OpenAI JSON for activities",
#         )

#     # ---- FORCE TAGS FOR FIRST 3 / LAST 3 ----
#     for idx, item in enumerate(items):
#         tags = item.get("tags") or []
#         # First 3: must be PlaceBased
#         if idx < 3 and not any("+ PlaceBased" in str(t) for t in tags):
#             tags.append("+ PlaceBased")
#         # Last 3: must be GoalBased
#         if idx >= 3 and not any("+ GoalBased" in str(t) for t in tags):
#             tags.append("+ GoalBased")
#         item["tags"] = tags

#     activities: List[schemas.ActivityBase] = []

#     # Helper: choose a concrete place name based on life_area
#     def pick_place_for_life_area(life_area: str) -> Optional[str]:
#         la = (life_area or "").lower()

#         # Heuristic mapping: pick from the most relevant category first
#         if any(word in la for word in ["movement", "body", "exercise"]):
#             candidates = nearby_parks + nearby_gyms
#         elif any(word in la for word in ["connection", "social", "talk"]):
#             candidates = nearby_cafes + nearby_malls + nearby_theatres
#         elif any(word in la for word in ["work", "focus", "study"]):
#             candidates = nearby_libraries + nearby_cafes
#         elif any(word in la for word in ["creative", "art", "play"]):
#             candidates = nearby_attractions + nearby_malls
#         elif any(word in la for word in ["grounding", "calm", "self"]):
#             candidates = nearby_parks + nearby_attractions
#         else:
#             candidates = all_nearby_places

#         if not candidates:
#             candidates = all_nearby_places

#         return candidates[0] if candidates else None

#     for item in items:
#         try:
#             title = (item.get("title") or "").strip() or "Small step"
#             description = (item.get("description") or "").strip() or "Take a small helpful step."
#             life_area = item.get("life_area", "Meaning")
#             effort_level = item.get("effort_level", "low")
#             reward_type = item.get("reward_type")
#             default_duration_min = item.get("default_duration_min") or 10
#             tags = item.get("tags") or []
#             location_label = item.get("location_label")

#             # --- Backend override: if it's PlaceBased, force a real nearby place name ---
#             is_place_based = any("+ PlaceBased" in str(t) for t in tags)

#             if is_place_based and all_nearby_places:
#                 picked = pick_place_for_life_area(life_area)
#                 if picked:
#                     location_label = picked

#             act = schemas.ActivityBase(
#                 title=title,
#                 description=description,
#                 life_area=life_area,
#                 effort_level=effort_level,
#                 reward_type=reward_type,
#                 default_duration_min=default_duration_min,
#                 location_label=location_label,
#                 tags=tags,
#             )
#             activities.append(act)
#         except Exception:
#             continue

#     if not activities:
#         raise HTTPException(status_code=500, detail="OpenAI returned no valid activities")

#     return activities


# # --------- Store generated activities in DB (no global cache) ---------


# def _store_generated_activities(
#     db: Session,
#     *,
#     activities: List[schemas.ActivityBase],
# ) -> List[models.Activities]:
#     """
#     Persist a batch of generated activities.
#     We do NOT reuse previous batches for new recommendations – each call
#     can create its own activities tied to that moment / context.
#     """
#     now = datetime.utcnow()
#     rows: List[models.Activities] = []

#     for a in activities:
#         row = models.Activities(
#             title=a.title,
#             description=a.description,
#             life_area=a.life_area,
#             effort_level=a.effort_level,
#             reward_type=a.reward_type,
#             default_duration_min=a.default_duration_min,
#             location_label=a.location_label,
#             tags_json=json.dumps(a.tags or []),
#             is_active=True,
#             created_at=now,
#         )
#         db.add(row)
#         rows.append(row)

#     db.commit()
#     for r_obj in rows:
#         db.refresh(r_obj)

#     return rows


# # ---------------- Public endpoints ----------------

# @r.get(
#     "/recommendation",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation",
# )
# @r.get(
#     "/recommend",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation (alias)",
#     include_in_schema=False,
# )
# def get_recommendation(
#     user_hash: Optional[str] = Query(None, description="Optional user hash"),
#     life_area: Optional[str] = Query(None, description="Preferred life area filter, e.g., 'Connection'"),
#     mood: Optional[str] = Query(None, description="Current mood (from intake)"),
#     schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
#     postal_code: Optional[str] = Query(None, description="Postal code, e.g., L18 2QA"),
#     goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
#     place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
#     limit: int = Query(6, ge=1, le=20, description="Maximum number of activities to return"),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return up to `limit` LLM-generated BA activities, tailored to *this* request.

#     - 3 place-based (with '+ PlaceBased' tag, using exact nearby place names).
#     - 3 goal-based BA actions (with '+ GoalBased' tag and 'Supports: ...' tag).
#     """

#     generated = _generate_activities_via_llm(
#         mood=mood,
#         schema_hint=schema_hint,
#         postal_code=postal_code,
#         goal_today=goal_today,
#         place=place,
#         count=6,
#     )

#     rows = _store_generated_activities(db, activities=generated)

#     # Optional life_area filter over this batch only (e.g. 'Connection', 'Movement')
#     if life_area:
#         filtered = [
#             r_
#             for r_ in rows
#             if (r_.life_area or "").lower() == life_area.lower()
#         ]
#         candidates = filtered or rows
#     else:
#         candidates = rows

#     if not candidates:
#         raise HTTPException(status_code=404, detail="No activities available")

#     # Return up to `limit` from this batch
#     selected = sorted(
#         candidates,
#         key=lambda x: x.created_at or datetime.utcnow(),
#         reverse=True,
#     )[:limit]

#     recs: List[schemas.ActivityRecommendationOut] = []
#     for act in selected:
#         tags: List[str] = []
#         if act.tags_json:
#             try:
#                 tags = json.loads(act.tags_json)
#             except Exception:
#                 tags = []
#         recs.append(
#             schemas.ActivityRecommendationOut(
#                 id=act.id,
#                 title=act.title,
#                 description=act.description,
#                 life_area=act.life_area,
#                 effort_level=act.effort_level,
#                 reward_type=act.reward_type,
#                 default_duration_min=act.default_duration_min,
#                 location_label=act.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityRecommendationListOut(activities=recs)


# @r.get(
#     "/library",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library",
# )
# @r.get(
#     "/list",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library (alias)",
#     include_in_schema=False,
# )
# def get_library(
#     db: Session = Depends(get_db),
# ):
#     """
#     Return the full activity library.
#     This is basically all activities that have ever been generated and stored.
#     """

#     acts = (
#         db.query(models.Activities)
#         .filter(models.Activities.is_active == True)
#         .order_by(models.Activities.created_at.desc())
#         .all()
#     )

#     out: List[schemas.ActivityOut] = []
#     for a in acts:
#         tags: List[str] = []
#         if a.tags_json:
#             try:
#                 tags = json.loads(a.tags_json)
#             except Exception:
#                 tags = []
#         out.append(
#             schemas.ActivityOut(
#                 id=a.id,
#                 title=a.title,
#                 description=a.description,
#                 life_area=a.life_area,
#                 effort_level=a.effort_level,
#                 reward_type=a.reward_type,
#                 default_duration_min=a.default_duration_min,
#                 location_label=a.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityListOut(activities=out)


# @r.post(
#     "/start",
#     summary="Start Activity",
# )
# def start_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=act.id,
#         session_id=payload.session_id,
#         status="started",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     db.refresh(row)

#     # Frontend hook can use this id as activitySessionId
#     return {"ok": True, "activity_session_id": row.id}


# @r.post(
#     "/swap",
#     summary="Swap Activity",
# )
# def swap_activity(
#     payload: schemas.ActivitySwapIn,
#     db: Session = Depends(get_db),
# ):
#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=payload.activity_id,
#         status="swapped",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     return {"ok": True}















# from __future__ import annotations

# import json
# import math
# from datetime import datetime
# from typing import List, Optional, Tuple

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session

# from app.db import SessionLocal
# from app import models, schemas
# from app.core.config import cfg as c

# # ---------------- OpenAI setup ----------------

# from openai import OpenAI

# # use the same OPENAI_API_KEY as your script generator
# client = OpenAI(api_key=c.OPENAI_API_KEY)
# OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

# r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])


# # ---------------- DB dependency ----------------

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---------------- Google Maps helpers ----------------

# def _geocode_postal_code(postal_code: str) -> Optional[Tuple[float, float]]:
#     """
#     postal_code -> (lat, lng) using Google Geocoding.
#     Returns None on any error so we can gracefully fall back.
#     """
#     if not c.GOOGLE_MAPS_API_KEY or not postal_code:
#         return None

#     url = "https://maps.googleapis.com/maps/api/geocode/json"
#     params = {"address": postal_code, "key": c.GOOGLE_MAPS_API_KEY}

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#         if data.get("status") != "OK":
#             return None
#         loc = data["results"][0]["geometry"]["location"]
#         return float(loc["lat"]), float(loc["lng"])
#     except Exception:
#         return None


# def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
#     """
#     Haversine distance between two lat/lng points in meters.
#     """
#     R = 6371000  # Earth radius in meters
#     phi1 = math.radians(lat1)
#     phi2 = math.radians(lat2)
#     dphi = math.radians(lat2 - lat1)
#     dlambda = math.radians(lng2 - lng1)

#     a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
#     c_ = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
#     return R * c_


# def _nearby_places(
#     lat: float,
#     lng: float,
#     place_type: str,
#     radius_m: int = 1200,
#     max_results: int = 5,
# ) -> List[str]:
#     """
#     Generic helper: look up nearby places of a given type.

#     We explicitly enforce that returned places are within `radius_m`
#     of the reference point, to keep recommendations VERY close to
#     the user's postal code.
#     """
#     if not c.GOOGLE_MAPS_API_KEY:
#         return []

#     url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
#     params = {
#         "location": f"{lat},{lng}",
#         "radius": radius_m,  # tight circle around the user
#         "type": place_type,
#         "key": c.GOOGLE_MAPS_API_KEY,
#     }

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#     except Exception:
#         return []

#     results = data.get("results") or []
#     names: List[str] = []

#     for r_ in results:
#         if len(names) >= max_results:
#             break

#         name = r_.get("name")
#         loc = (r_.get("geometry") or {}).get("location") or {}
#         lat2 = loc.get("lat")
#         lng2 = loc.get("lng")

#         if not name or lat2 is None or lng2 is None:
#             continue

#         # Enforce "very close" – cut off anything outside radius_m.
#         dist = _distance_meters(lat, lng, float(lat2), float(lng2))
#         if dist > radius_m:
#             continue

#         names.append(name.strip())

#     return names


# # ---------------- OpenAI helper ----------------

# def _generate_activities_via_llm(
#     *,
#     mood: Optional[str],
#     schema_hint: Optional[str],
#     postal_code: Optional[str],
#     goal_today: Optional[str],
#     place: Optional[str],
#     count: int = 6,
# ) -> List[schemas.ActivityBase]:
#     """
#     Call OpenAI to generate a small set of concrete BA activities.

#     We ask for EXACTLY `count` (default 6):
#     - First 3: place-based activities using real nearby place names
#       (parks / cafes / malls / theatres / libraries / gyms / attractions).
#     - Last 3: goal-based BA activities like "Coffee with Maya",
#       "Call Mom", "Morning Pages", linked to the therapy goal.
#     """

#     # --- build context text ---
#     context_bits: List[str] = []
#     if mood:
#         context_bits.append(f"current mood: {mood}")
#     if schema_hint:
#         context_bits.append(f"schema or core story: {schema_hint}")
#     if goal_today:
#         context_bits.append(f"today's goal: {goal_today}")
#     if place:
#         context_bits.append(f"preferred environment: {place}")
#     if postal_code:
#         context_bits.append(f"postal code: {postal_code}")

#     nearby_parks: List[str] = []
#     nearby_cafes: List[str] = []
#     nearby_attractions: List[str] = []
#     nearby_malls: List[str] = []
#     nearby_theatres: List[str] = []
#     nearby_libraries: List[str] = []
#     nearby_gyms: List[str] = []

#     coords: Optional[Tuple[float, float]] = None
#     if postal_code:
#         coords = _geocode_postal_code(postal_code)

#     if coords:
#         lat, lng = coords

#         # Movement / nature
#         nearby_parks = _nearby_places(lat, lng, "park", max_results=5)
#         # Social / talk / coffee
#         nearby_cafes = _nearby_places(lat, lng, "cafe", max_results=5)
#         # Entertainment / sightseeing
#         nearby_attractions = _nearby_places(lat, lng, "tourist_attraction", max_results=5)
#         nearby_malls = _nearby_places(lat, lng, "shopping_mall", max_results=5)
#         nearby_theatres = _nearby_places(lat, lng, "movie_theater", max_results=5)
#         # Quiet focus / learning
#         nearby_libraries = _nearby_places(lat, lng, "library", max_results=5)
#         # Movement in non-nature spaces
#         nearby_gyms = _nearby_places(lat, lng, "gym", max_results=5)

#         if nearby_parks:
#             context_bits.append("nearby_parks: " + ", ".join(nearby_parks))
#         if nearby_cafes:
#             context_bits.append("nearby_cafes: " + ", ".join(nearby_cafes))
#         if nearby_attractions:
#             context_bits.append("nearby_attractions: " + ", ".join(nearby_attractions))
#         if nearby_malls:
#             context_bits.append("nearby_malls: " + ", ".join(nearby_malls))
#         if nearby_theatres:
#             context_bits.append("nearby_theatres: " + ", ".join(nearby_theatres))
#         if nearby_libraries:
#             context_bits.append("nearby_libraries: " + ", ".join(nearby_libraries))
#         if nearby_gyms:
#             context_bits.append("nearby_gyms: " + ", ".join(nearby_gyms))

#     context_text = "; ".join(context_bits) or "no extra context provided"

#     # Combined list of all place names for backend overriding.
#     all_nearby_places: List[str] = (
#         nearby_parks
#         + nearby_cafes
#         + nearby_attractions
#         + nearby_malls
#         + nearby_theatres
#         + nearby_libraries
#         + nearby_gyms
#     )

#     system_msg = (
#         "You are a behavioural activation coach designing very small, realistic, "
#         "real-world activities for a mental health app.\n"
#         "Each activity must be:\n"
#         "- concrete and doable in 5–30 minutes\n"
#         "- safe and gentle (no extreme exercise, no unsafe locations)\n"
#         "- described in simple language\n"
#         "- If you reference a place (park, cafe, mall, theatre, library, attraction, gym), "
#         "you MUST use the exact name from the provided nearby_* lists.\n"
#         "- Do NOT invent or tweak place names.\n\n"
#         "MATCH PLACE TYPE TO THE USER'S GOAL:\n"
#         "- Goals about movement / steps / walk / exercise -> prefer parks or gyms.\n"
#         "- Goals about talking, connection, not feeling alone -> prefer cafes or other social spaces.\n"
#         "- Goals about chilling, recharging, entertainment -> prefer malls, theatres, or gentle attractions.\n"
#         "- Goals about focus, work, study, reading -> prefer libraries or quiet cafes.\n"
#         "Where possible, vary the place types across the 3 place-based activities.\n\n"
#         "You can use BA flavours like Movement, Connection, Creative, Grounding, "
#         "or Self-compassion. Use tags to encode this.\n"
#     )

#     user_msg = (
#         f"User context: {context_text}\n\n"
#         "Generate EXACTLY 6 activities in this order:\n"
#         "1–3: PLACE-BASED activities that use real nearby places from the lists. "
#         "Mark them with a '+ PlaceBased' tag.\n"
#         "4–6: GOAL-BASED BA activities (like 'Coffee with Maya', 'Call Mom', "
#         "'Morning Pages'). Mark them with a '+ GoalBased' tag.\n\n"
#         "For GOAL-BASED items, also include a tag of the form "
#         "'Supports: <short phrase>' explaining how it supports their goal.\n\n"
#         "Return ONLY JSON in this exact format (no extra commentary):\n"
#         "{\n"
#         '  \"activities\": [\n'
#         "    {\n"
#         '      \"title\": \"short name\",\n'
#         '      \"description\": \"2–3 sentence description of what to do\",\n'
#         '      \"life_area\": \"Movement | Connection | Creative | Grounding | Self-compassion | Work | Body\",\n'
#         '      \"effort_level\": \"low | medium | high\",\n'
#         '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
#         '      \"default_duration_min\": 5,\n'
#         '      \"location_label\": \"Exact place name from nearby lists, or \'at home\' / \'anywhere comfortable\' for goal-based items\",\n'
#         '      \"tags\": [\"+ PlaceBased or + GoalBased\", \"BA flavour like Movement/Connection\", \"Supports: ... for goal-based\"]\n'
#         "    }\n"
#         "  ]\n"
#         "}"
#     )

#     # Use new v1 chat completions client
#     try:
#         resp = client.chat.completions.create(
#             model=OPENAI_ACTIVITY_MODEL,
#             messages=[
#                 {"role": "system", "content": system_msg},
#                 {"role": "user", "content": user_msg},
#             ],
#             temperature=0.7,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")

#     # Parse JSON from model output
#     try:
#         content = resp.choices[0].message.content
#         data = json.loads(content)
#         items = data.get("activities") or []
#     except json.JSONDecodeError:
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to parse OpenAI JSON for activities",
#         )

#     # Enforce max count (6) – if model gives more, cut.
#     if len(items) > count:
#         items = items[:count]

#     # ---- FORCE TAGS FOR FIRST 3 / LAST 3 ----
#     for idx, item in enumerate(items):
#         tags = item.get("tags") or []
#         # First 3 are always treated as place-based in our logic if we have real places.
#         if idx < 3 and not any("+ PlaceBased" in str(t) for t in tags):
#             tags.append("+ PlaceBased")
#         if idx >= 3 and not any("+ GoalBased" in str(t) for t in tags):
#             tags.append("+ GoalBased")
#         item["tags"] = tags

#     # If we have NO real nearby places at all, downgrade everything to goal-based
#     # so we never show fake place names.
#     if not all_nearby_places:
#         for item in items:
#             tags = [t for t in (item.get("tags") or []) if "+ PlaceBased" not in str(t)]
#             if not any("+ GoalBased" in str(t) for t in tags):
#                 tags.append("+ GoalBased")
#             item["tags"] = tags

#     activities: List[schemas.ActivityBase] = []

#     # Helper: choose a concrete place name based on life_area
#     def pick_place_for_life_area(life_area: str) -> Optional[str]:
#         la = (life_area or "").lower()

#         # Heuristic mapping: pick from the most relevant category first
#         if any(word in la for word in ["movement", "body", "exercise"]):
#             candidates = nearby_parks + nearby_gyms
#         elif any(word in la for word in ["connection", "social", "talk"]):
#             candidates = nearby_cafes + nearby_malls + nearby_theatres
#         elif any(word in la for word in ["work", "focus", "study"]):
#             candidates = nearby_libraries + nearby_cafes
#         elif any(word in la for word in ["creative", "art", "play"]):
#             candidates = nearby_attractions + nearby_malls
#         elif any(word in la for word in ["grounding", "calm", "self"]):
#             candidates = nearby_parks + nearby_attractions
#         else:
#             candidates = all_nearby_places

#         if not candidates:
#             candidates = all_nearby_places

#         return candidates[0] if candidates else None

#     for idx, item in enumerate(items):
#         try:
#             title = (item.get("title") or "").strip() or "Small step"
#             description = (item.get("description") or "").strip() or "Take a small helpful step."
#             life_area = item.get("life_area", "Meaning")
#             effort_level = item.get("effort_level", "low")
#             reward_type = item.get("reward_type")
#             default_duration_min = item.get("default_duration_min") or 10
#             tags = item.get("tags") or []
#             location_label = item.get("location_label")

#             # First 3: if we actually have nearby places, force them to use REAL place names.
#             if idx < 3 and all_nearby_places:
#                 picked = pick_place_for_life_area(life_area)
#                 if picked:
#                     location_label = picked
#                 else:
#                     # Fallback: still force a real place from the combined list
#                     location_label = all_nearby_places[0]

#             # If we *still* don't have a location for goal-based / no-places,
#             # keep it generic rather than a hallucinated place.
#             if not all_nearby_places and not location_label:
#                 location_label = "at home"

#             act = schemas.ActivityBase(
#                 title=title,
#                 description=description,
#                 life_area=life_area,
#                 effort_level=effort_level,
#                 reward_type=reward_type,
#                 default_duration_min=default_duration_min,
#                 location_label=location_label,
#                 tags=tags,
#             )
#             activities.append(act)
#         except Exception:
#             continue

#     if not activities:
#         raise HTTPException(status_code=500, detail="OpenAI returned no valid activities")

#     return activities


# # --------- Store generated activities in DB (no global cache) ---------


# def _store_generated_activities(
#     db: Session,
#     *,
#     activities: List[schemas.ActivityBase],
# ) -> List[models.Activities]:
#     """
#     Persist a batch of generated activities.
#     We do NOT reuse previous batches for new recommendations – each call
#     can create its own activities tied to that moment / context.
#     """
#     now = datetime.utcnow()
#     rows: List[models.Activities] = []

#     for a in activities:
#         row = models.Activities(
#             title=a.title,
#             description=a.description,
#             life_area=a.life_area,
#             effort_level=a.effort_level,
#             reward_type=a.reward_type,
#             default_duration_min=a.default_duration_min,
#             location_label=a.location_label,
#             tags_json=json.dumps(a.tags or []),
#             is_active=True,
#             created_at=now,
#         )
#         db.add(row)
#         rows.append(row)

#     db.commit()
#     for r_obj in rows:
#         db.refresh(r_obj)

#     return rows


# # ---------------- Public endpoints ----------------

# @r.get(
#     "/recommendation",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation",
# )
# @r.get(
#     "/recommend",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation (alias)",
#     include_in_schema=False,
# )
# def get_recommendation(
#     user_hash: Optional[str] = Query(None, description="Optional user hash"),
#     life_area: Optional[str] = Query(None, description="Preferred life area filter, e.g., 'Connection'"),
#     mood: Optional[str] = Query(None, description="Current mood (from intake)"),
#     schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
#     postal_code: Optional[str] = Query(None, description="Postal code, e.g., L18 2QA"),
#     goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
#     place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
#     limit: int = Query(6, ge=1, le=20, description="Maximum number of activities to return"),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return up to `limit` LLM-generated BA activities, tailored to *this* request.

#     - 3 place-based (with '+ PlaceBased' tag, using exact nearby place names) when possible.
#     - 3 goal-based BA actions (with '+ GoalBased' tag and 'Supports: ...' tag).
#     """

#     generated = _generate_activities_via_llm(
#         mood=mood,
#         schema_hint=schema_hint,
#         postal_code=postal_code,
#         goal_today=goal_today,
#         place=place,
#         count=6,
#     )

#     rows = _store_generated_activities(db, activities=generated)

#     # Optional life_area filter over this batch only (e.g. 'Connection', 'Movement')
#     if life_area:
#         filtered = [
#             r_
#             for r_ in rows
#             if (r_.life_area or "").lower() == life_area.lower()
#         ]
#         candidates = filtered or rows
#     else:
#         candidates = rows

#     if not candidates:
#         raise HTTPException(status_code=404, detail="No activities available")

#     # Return up to `limit` from this batch – newest first
#     selected = sorted(
#         candidates,
#         key=lambda x: x.created_at or datetime.utcnow(),
#         reverse=True,
#     )[:limit]

#     recs: List[schemas.ActivityRecommendationOut] = []
#     for act in selected:
#         tags: List[str] = []
#         if act.tags_json:
#             try:
#                 tags = json.loads(act.tags_json)
#             except Exception:
#                 tags = []
#         recs.append(
#             schemas.ActivityRecommendationOut(
#                 id=act.id,
#                 title=act.title,
#                 description=act.description,
#                 life_area=act.life_area,
#                 effort_level=act.effort_level,
#                 reward_type=act.reward_type,
#                 default_duration_min=act.default_duration_min,
#                 location_label=act.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityRecommendationListOut(activities=recs)


# @r.get(
#     "/library",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library",
# )
# @r.get(
#     "/list",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library (alias)",
#     include_in_schema=False,
# )
# def get_library(
#     db: Session = Depends(get_db),
# ):
#     """
#     Return the latest 6 active activities.
#     This keeps the library tight: 3 real-place + 3 BA items from recent batches.
#     """

#     acts = (
#         db.query(models.Activities)
#         .filter(models.Activities.is_active == True)
#         .order_by(models.Activities.created_at.desc())
#         .limit(6)
#         .all()
#     )

#     out: List[schemas.ActivityOut] = []
#     for a in acts:
#         tags: List[str] = []
#         if a.tags_json:
#             try:
#                 tags = json.loads(a.tags_json)
#             except Exception:
#                 tags = []
#         out.append(
#             schemas.ActivityOut(
#                 id=a.id,
#                 title=a.title,
#                 description=a.description,
#                 life_area=a.life_area,
#                 effort_level=a.effort_level,
#                 reward_type=a.reward_type,
#                 default_duration_min=a.default_duration_min,
#                 location_label=a.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityListOut(activities=out)


# @r.post("/start", summary="Start Activity")
# def start_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=act.id,
#         session_id=payload.session_id,
#         status="started",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     db.refresh(row)

#     # Frontend hook can use this id as activitySessionId
#     return {"ok": True, "activity_session_id": row.id}


# @r.post("/complete", summary="Complete Activity")
# def complete_activity(
#     payload: schemas.ActivityStartIn,  # same shape: activity_id + user_hash (+session_id optional)
#     db: Session = Depends(get_db),
# ):
#     """
#     Mark the most recent 'started' session for this activity/user as completed.
#     """
#     session_row = (
#         db.query(models.ActivitySessions)
#         .filter(
#             models.ActivitySessions.activity_id == payload.activity_id,
#             models.ActivitySessions.user_hash == payload.user_hash,
#             models.ActivitySessions.status == "started",
#         )
#         .order_by(models.ActivitySessions.started_at.desc())
#         .first()
#     )

#     if not session_row:
#         raise HTTPException(status_code=404, detail="Started activity not found")

#     session_row.status = "completed"
#     session_row.completed_at = datetime.utcnow()
#     db.commit()
#     db.refresh(session_row)

#     return {"ok": True}


# @r.post("/swap", summary="Swap Activity")
# def swap_activity(
#     payload: schemas.ActivitySwapIn,
#     db: Session = Depends(get_db),
# ):
#     """
#     Log a 'swapped' event and return the chosen activity so the frontend
#     can immediately show it on the Today card.
#     """
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=payload.activity_id,
#         status="swapped",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()

#     tags: List[str] = []
#     if act.tags_json:
#         try:
#             tags = json.loads(act.tags_json)
#         except Exception:
#             tags = []

#     return {
#         "ok": True,
#         "activity": {
#             "id": act.id,
#             "title": act.title,
#             "description": act.description,
#             "life_area": act.life_area,
#             "effort_level": act.effort_level,
#             "reward_type": act.reward_type,
#             "default_duration_min": act.default_duration_min,
#             "location_label": act.location_label,
#             "tags": tags,
#         },
#     }








# from __future__ import annotations

# import json
# import math
# from datetime import datetime
# from typing import List, Optional, Tuple

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session

# from app.db import SessionLocal
# from app import models, schemas
# from app.core.config import cfg as c

# # ---------------- OpenAI setup ----------------

# from openai import OpenAI

# client = OpenAI(api_key=c.OPENAI_API_KEY)
# OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

# r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])


# # ---------------- DB dependency ----------------

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---------------- Google Maps helpers ----------------

# def _geocode_postal_code(location: str) -> Optional[Tuple[float, float]]:
#     """
#     location -> (lat, lng) using Google Geocoding.
#     NOTE: `location` can be ANY human-readable string:
#     - full postcode (e.g. 'L18 2QA')
#     - city + country (e.g. 'Liverpool, UK')
#     - neighbourhood (e.g. 'Notting Hill, London')
#     """
#     if not c.GOOGLE_MAPS_API_KEY or not location:
#         return None

#     url = "https://maps.googleapis.com/maps/api/geocode/json"
#     params = {"address": location, "key": c.GOOGLE_MAPS_API_KEY}

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#         if data.get("status") != "OK":
#             print(f"[activity] Geocode status != OK for '{location}': {data.get('status')}")
#             return None
#         loc = data["results"][0]["geometry"]["location"]
#         coords = float(loc["lat"]), float(loc["lng"])
#         print(f"[activity] Geocoded '{location}' -> {coords}")
#         return coords
#     except Exception as e:
#         print(f"[activity] Geocode error for '{location}': {e}")
#         return None


# def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
#     R = 6371000  # Earth radius in meters
#     phi1 = math.radians(lat1)
#     phi2 = math.radians(lat2)
#     dphi = math.radians(lat2 - lat1)
#     dlambda = math.radians(lng2 - lng1)

#     a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
#     c_ = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
#     return R * c_


# def _nearby_places(
#     lat: float,
#     lng: float,
#     place_type: str,
#     radius_m: int = 1200,
#     max_results: int = 5,
# ) -> List[str]:
#     """
#     Look up nearby places of a given type using Google Places.
#     Only keep results strictly within `radius_m` meters.
#     """
#     if not c.GOOGLE_MAPS_API_KEY:
#         return []

#     url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
#     params = {
#         "location": f"{lat},{lng}",
#         "radius": radius_m,
#         "type": place_type,
#         "key": c.GOOGLE_MAPS_API_KEY,
#     }

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#     except Exception as e:
#         print(f"[activity] Places error for type '{place_type}': {e}")
#         return []

#     results = data.get("results") or []
#     names: List[str] = []

#     for r_ in results:
#         if len(names) >= max_results:
#             break

#         name = r_.get("name")
#         loc = (r_.get("geometry") or {}).get("location") or {}
#         lat2 = loc.get("lat")
#         lng2 = loc.get("lng")

#         if not name or lat2 is None or lng2 is None:
#             continue

#         dist = _distance_meters(lat, lng, float(lat2), float(lng2))
#         if dist > radius_m:
#             continue

#         names.append(name.strip())

#     return names


# # ---------------- OpenAI helper ----------------

# def _generate_activities_via_llm(
#     *,
#     mood: Optional[str],
#     schema_hint: Optional[str],
#     postal_code: Optional[str],
#     goal_today: Optional[str],
#     place: Optional[str],
#     count: int = 6,
# ) -> List[schemas.ActivityBase]:
#     """
#     Generate EXACTLY `count` activities:
#     - First 3: place-based activities using REAL Google Places names.
#     - Last 3: goal-based BA activities.
#     """

#     # --- build context text ---
#     context_bits: List[str] = []
#     if mood:
#         context_bits.append(f"current mood: {mood}")
#     if schema_hint:
#         context_bits.append(f"schema or core story: {schema_hint}")
#     if goal_today:
#         context_bits.append(f"today's goal: {goal_today}")
#     if place:
#         context_bits.append(f"preferred environment: {place}")
#     if postal_code:
#         context_bits.append(f"location_hint: {postal_code}")

#     # --- lookup nearby places from Google ---
#     nearby_parks: List[str] = []
#     nearby_cafes: List[str] = []
#     nearby_attractions: List[str] = []
#     nearby_malls: List[str] = []
#     nearby_theatres: List[str] = []
#     nearby_libraries: List[str] = []
#     nearby_gyms: List[str] = []

#     coords: Optional[Tuple[float, float]] = None
#     if postal_code:
#         coords = _geocode_postal_code(postal_code)

#     if coords:
#         lat, lng = coords

#         nearby_parks = _nearby_places(lat, lng, "park", max_results=5)
#         nearby_cafes = _nearby_places(lat, lng, "cafe", max_results=5)
#         nearby_attractions = _nearby_places(lat, lng, "tourist_attraction", max_results=5)
#         nearby_malls = _nearby_places(lat, lng, "shopping_mall", max_results=5)
#         nearby_theatres = _nearby_places(lat, lng, "movie_theater", max_results=5)
#         nearby_libraries = _nearby_places(lat, lng, "library", max_results=5)
#         nearby_gyms = _nearby_places(lat, lng, "gym", max_results=5)

#         if nearby_parks:
#             context_bits.append("nearby_parks: " + ", ".join(nearby_parks))
#         if nearby_cafes:
#             context_bits.append("nearby_cafes: " + ", ".join(nearby_cafes))
#         if nearby_attractions:
#             context_bits.append("nearby_attractions: " + ", ".join(nearby_attractions))
#         if nearby_malls:
#             context_bits.append("nearby_malls: " + ", ".join(nearby_malls))
#         if nearby_theatres:
#             context_bits.append("nearby_theatres: " + ", ".join(nearby_theatres))
#         if nearby_libraries:
#             context_bits.append("nearby_libraries: " + ", ".join(nearby_libraries))
#         if nearby_gyms:
#             context_bits.append("nearby_gyms: " + ", ".join(nearby_gyms))

#     all_nearby_places: List[str] = (
#         nearby_parks
#         + nearby_cafes
#         + nearby_attractions
#         + nearby_malls
#         + nearby_theatres
#         + nearby_libraries
#         + nearby_gyms
#     )

#     print(
#         f"[activity] nearby counts – parks={len(nearby_parks)}, cafes={len(nearby_cafes)}, "
#         f"attractions={len(nearby_attractions)}, malls={len(nearby_malls)}, "
#         f"theatres={len(nearby_theatres)}, libraries={len(nearby_libraries)}, gyms={len(nearby_gyms)}"
#     )

#     context_text = "; ".join(context_bits) or "no extra context provided"

#     system_msg = (
#         "You are a behavioural activation coach designing very small, realistic, "
#         "real-world activities for a mental health app.\n"
#         "Each activity must be:\n"
#         "- concrete and doable in 5–30 minutes\n"
#         "- safe and gentle (no extreme exercise, no unsafe locations)\n"
#         "- described in simple language\n"
#         "- If you reference a place (park, cafe, mall, theatre, library, attraction, gym), "
#         "you MUST use the exact name from the provided nearby_* lists.\n"
#         "- Do NOT invent or tweak place names.\n\n"
#         "MATCH PLACE TYPE TO THE USER'S GOAL:\n"
#         "- Goals about movement / steps / walk / exercise -> prefer parks or gyms.\n"
#         "- Goals about talking, connection, not feeling alone -> prefer cafes or other social spaces.\n"
#         "- Goals about chilling, recharging, entertainment -> prefer malls, theatres, or gentle attractions.\n"
#         "- Goals about focus, work, study, reading -> prefer libraries or quiet cafes.\n"
#         "Where possible, vary the place types across the 3 place-based activities.\n\n"
#         "You can use BA flavours like Movement, Connection, Creative, Grounding, "
#         "or Self-compassion. Use tags to encode this.\n"
#     )

#     user_msg = (
#         f"User context: {context_text}\n\n"
#         "Generate EXACTLY 6 activities in this order:\n"
#         "1–3: PLACE-BASED activities that use real nearby places from the lists. "
#         "Mark them with a '+ PlaceBased' tag.\n"
#         "4–6: GOAL-BASED BA activities (like 'Coffee with Maya', 'Call Mom', "
#         "'Morning Pages'). Mark them with a '+ GoalBased' tag.\n\n"
#         "For GOAL-BASED items, also include a tag of the form "
#         "'Supports: <short phrase>' explaining how it supports their goal.\n\n"
#         "Return ONLY JSON in this exact format (no extra commentary):\n"
#         "{\n"
#         '  \"activities\": [\n'
#         "    {\n"
#         '      \"title\": \"short name\",\n'
#         '      \"description\": \"2–3 sentence description of what to do\",\n'
#         '      \"life_area\": \"Movement | Connection | Creative | Grounding | Self-compassion | Work | Body\",\n'
#         '      \"effort_level\": \"low | medium | high\",\n'
#         '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
#         '      \"default_duration_min\": 5,\n'
#         '      \"location_label\": \"Exact place name from nearby lists, or \'at home\' / \'anywhere comfortable\' for goal-based items\",\n'
#         '      \"tags\": [\"+ PlaceBased or + GoalBased\", \"BA flavour like Movement/Connection\", \"Supports: ... for goal-based\"]\n'
#         "    }\n"
#         "  ]\n"
#         "}"
#     )

#     try:
#         resp = client.chat.completions.create(
#             model=OPENAI_ACTIVITY_MODEL,
#             messages=[
#                 {"role": "system", "content": system_msg},
#                 {"role": "user", "content": user_msg},
#             ],
#             temperature=0.7,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")

#     try:
#         content = resp.choices[0].message.content
#         data = json.loads(content)
#         items = data.get("activities") or []
#     except json.JSONDecodeError:
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to parse OpenAI JSON for activities",
#         )

#     if len(items) > count:
#         items = items[:count]

#     # tag enforcement: first 3 = PlaceBased, last 3 = GoalBased
#     for idx, item in enumerate(items):
#         tags = item.get("tags") or []
#         if idx < 3 and not any("+ PlaceBased" in str(t) for t in tags):
#             tags.append("+ PlaceBased")
#         if idx >= 3 and not any("+ GoalBased" in str(t) for t in tags):
#             tags.append("+ GoalBased")
#         item["tags"] = tags

#     activities: List[schemas.ActivityBase] = []

#     for idx, item in enumerate(items):
#         try:
#             title = (item.get("title") or "").strip() or "Small step"
#             description = (item.get("description") or "").strip() or "Take a small helpful step."
#             life_area = item.get("life_area", "Meaning")
#             effort_level = item.get("effort_level", "low")
#             reward_type = item.get("reward_type")
#             default_duration_min = item.get("default_duration_min") or 10
#             tags = item.get("tags") or []
#             location_label = item.get("location_label")

#             # 🔵 HARD RULE: if we actually have Google places, first 3 MUST use them.
#             if all_nearby_places and idx < 3:
#                 # Cycle through list so we don't crash if < 3 places
#                 picked = all_nearby_places[idx % len(all_nearby_places)]
#                 location_label = picked

#             # If we never got any Google places for this user,
#             # avoid hallucinated place names and fall back to generic labels.
#             if not all_nearby_places and not location_label:
#                 if idx < 3:
#                     location_label = "a nearby place that feels safe"
#                 else:
#                     location_label = "at home"

#             act = schemas.ActivityBase(
#                 title=title,
#                 description=description,
#                 life_area=life_area,
#                 effort_level=effort_level,
#                 reward_type=reward_type,
#                 default_duration_min=default_duration_min,
#                 location_label=location_label,
#                 tags=tags,
#             )
#             activities.append(act)
#         except Exception as e:
#             print(f"[activity] Error building ActivityBase: {e}")
#             continue

#     if not activities:
#         raise HTTPException(status_code=500, detail="OpenAI returned no valid activities")

#     return activities


# # --------- Store generated activities in DB ---------


# def _store_generated_activities(
#     db: Session,
#     *,
#     activities: List[schemas.ActivityBase],
# ) -> List[models.Activities]:
#     now = datetime.utcnow()
#     rows: List[models.Activities] = []

#     for a in activities:
#         row = models.Activities(
#             title=a.title,
#             description=a.description,
#             life_area=a.life_area,
#             effort_level=a.effort_level,
#             reward_type=a.reward_type,
#             default_duration_min=a.default_duration_min,
#             location_label=a.location_label,
#             tags_json=json.dumps(a.tags or []),
#             is_active=True,
#             created_at=now,
#         )
#         db.add(row)
#         rows.append(row)

#     db.commit()
#     for r_obj in rows:
#         db.refresh(r_obj)

#     return rows


# # ---------------- Public endpoints ----------------

# @r.get(
#     "/recommendation",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation",
# )
# @r.get(
#     "/recommend",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation (alias)",
#     include_in_schema=False,
# )
# def get_recommendation(
#     user_hash: Optional[str] = Query(None, description="Optional user hash"),
#     life_area: Optional[str] = Query(None, description="Preferred life area filter, e.g., 'Connection'"),
#     mood: Optional[str] = Query(None, description="Current mood (from intake)"),
#     schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
#     postal_code: Optional[str] = Query(None, description="Location text (postcode, city, etc.)"),
#     goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
#     place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
#     limit: int = Query(6, ge=1, le=20, description="Maximum number of activities to return"),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return up to `limit` LLM-generated BA activities, tailored to *this* request.

#     - First 3: place-based (REAL Google Places names when available).
#     - Last 3: goal-based BA actions.
#     """

#     print(f"[activity] /recommendation called with postal_code='{postal_code}'")

#     generated = _generate_activities_via_llm(
#         mood=mood,
#         schema_hint=schema_hint,
#         postal_code=postal_code,
#         goal_today=goal_today,
#         place=place,
#         count=6,
#     )

#     rows = _store_generated_activities(db, activities=generated)

#     if life_area:
#         filtered = [
#             r_
#             for r_ in rows
#             if (r_.life_area or "").lower() == life_area.lower()
#         ]
#         candidates = filtered or rows
#     else:
#         candidates = rows

#     if not candidates:
#         raise HTTPException(status_code=404, detail="No activities available")

#     selected = sorted(
#         candidates,
#         key=lambda x: x.created_at or datetime.utcnow(),
#         reverse=True,
#     )[:limit]

#     recs: List[schemas.ActivityRecommendationOut] = []
#     for act in selected:
#         tags: List[str] = []
#         if act.tags_json:
#             try:
#                 tags = json.loads(act.tags_json)
#             except Exception:
#                 tags = []
#         recs.append(
#             schemas.ActivityRecommendationOut(
#                 id=act.id,
#                 title=act.title,
#                 description=act.description,
#                 life_area=act.life_area,
#                 effort_level=act.effort_level,
#                 reward_type=act.reward_type,
#                 default_duration_min=act.default_duration_min,
#                 location_label=act.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityRecommendationListOut(activities=recs)


# @r.get(
#     "/library",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library",
# )
# @r.get(
#     "/list",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library (alias)",
#     include_in_schema=False,
# )
# def get_library(
#     db: Session = Depends(get_db),
# ):
#     """
#     Return the latest 6 active activities.
#     """
#     acts = (
#         db.query(models.Activities)
#         .filter(models.Activities.is_active == True)
#         .order_by(models.Activities.created_at.desc())
#         .limit(6)
#         .all()
#     )

#     out: List[schemas.ActivityOut] = []
#     for a in acts:
#         tags: List[str] = []
#         if a.tags_json:
#             try:
#                 tags = json.loads(a.tags_json)
#             except Exception:
#                 tags = []
#         out.append(
#             schemas.ActivityOut(
#                 id=a.id,
#                 title=a.title,
#                 description=a.description,
#                 life_area=a.life_area,
#                 effort_level=a.effort_level,
#                 reward_type=a.reward_type,
#                 default_duration_min=a.default_duration_min,
#                 location_label=a.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityListOut(activities=out)


# @r.post("/start", summary="Start Activity")
# def start_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=act.id,
#         session_id=payload.session_id,
#         status="started",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     db.refresh(row)

#     return {"ok": True, "activity_session_id": row.id}


# @r.post("/complete", summary="Complete Activity")
# def complete_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     """
#     Mark the most recent 'started' session for this activity/user as completed.
#     """
#     session_row = (
#         db.query(models.ActivitySessions)
#         .filter(
#             models.ActivitySessions.activity_id == payload.activity_id,
#             models.ActivitySessions.user_hash == payload.user_hash,
#             models.ActivitySessions.status == "started",
#         )
#         .order_by(models.ActivitySessions.started_at.desc())
#         .first()
#     )

#     if not session_row:
#         raise HTTPException(status_code=404, detail="Started activity not found")

#     session_row.status = "completed"
#     session_row.completed_at = datetime.utcnow()
#     db.commit()
#     db.refresh(session_row)

#     return {"ok": True}


# @r.post("/swap", summary="Swap Activity")
# def swap_activity(
#     payload: schemas.ActivitySwapIn,
#     db: Session = Depends(get_db),
# ):
#     """
#     Log a 'swapped' event and return the chosen activity so the frontend
#     can immediately show it on the Today card.
#     """
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=payload.activity_id,
#         status="swapped",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()

#     tags: List[str] = []
#     if act.tags_json:
#         try:
#             tags = json.loads(act.tags_json)
#         except Exception:
#             tags = []

#     return {
#         "ok": True,
#         "activity": {
#             "id": act.id,
#             "title": act.title,
#             "description": act.description,
#             "life_area": act.life_area,
#             "effort_level": act.effort_level,
#             "reward_type": act.reward_type,
#             "default_duration_min": act.default_duration_min,
#             "location_label": act.location_label,
#             "tags": tags,
#         },
#     }






# from __future__ import annotations

# import json
# import math
# from datetime import datetime
# from typing import List, Optional, Tuple

# import requests
# from fastapi import APIRouter, Depends, HTTPException, Query
# from sqlalchemy.orm import Session

# from app.db import SessionLocal
# from app import models, schemas
# from app.core.config import cfg as c

# # ---------------- OpenAI setup ----------------

# from openai import OpenAI

# client = OpenAI(api_key=c.OPENAI_API_KEY)
# OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

# r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])


# # ---------------- DB dependency ----------------

# def get_db():
#     db = SessionLocal()
#     try:
#         yield db
#     finally:
#         db.close()


# # ---------------- Google Maps helpers ----------------

# def _geocode_postal_code(location: str) -> Optional[Tuple[float, float]]:
#     """
#     location -> (lat, lng) using Google Geocoding.
#     NOTE: `location` can be ANY human-readable string:
#     - full postcode (e.g. 'L18 2QA')
#     - city + country (e.g. 'Liverpool, UK')
#     - neighbourhood (e.g. 'Notting Hill, London')
#     """
#     if not c.GOOGLE_MAPS_API_KEY or not location:
#         return None

#     url = "https://maps.googleapis.com/maps/api/geocode/json"
#     params = {"address": location, "key": c.GOOGLE_MAPS_API_KEY}

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#         if data.get("status") != "OK":
#             print(f"[activity] Geocode status != OK for '{location}': {data.get('status')}")
#             return None
#         loc = data["results"][0]["geometry"]["location"]
#         coords = float(loc["lat"]), float(loc["lng"])
#         print(f"[activity] Geocoded '{location}' -> {coords}")
#         return coords
#     except Exception as e:
#         print(f"[activity] Geocode error for '{location}': {e}")
#         return None


# def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
#     R = 6371000  # Earth radius in meters
#     phi1 = math.radians(lat1)
#     phi2 = math.radians(lat2)
#     dphi = math.radians(lat2 - lat1)
#     dlambda = math.radians(lng2 - lng1)

#     a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
#     c_ = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
#     return R * c_


# def _nearby_places(
#     lat: float,
#     lng: float,
#     place_type: str,
#     radius_m: int = 1200,
#     max_results: int = 5,
# ) -> List[str]:
#     """
#     Look up nearby places of a given type using Google Places.
#     Only keep results strictly within `radius_m` meters.
#     """
#     if not c.GOOGLE_MAPS_API_KEY:
#         return []

#     url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
#     params = {
#         "location": f"{lat},{lng}",
#         "radius": radius_m,
#         "type": place_type,
#         "key": c.GOOGLE_MAPS_API_KEY,
#     }

#     try:
#         resp = requests.get(url, params=params, timeout=8)
#         resp.raise_for_status()
#         data = resp.json()
#     except Exception as e:
#         print(f"[activity] Places error for type '{place_type}': {e}")
#         return []

#     results = data.get("results") or []
#     names: List[str] = []

#     for r_ in results:
#         if len(names) >= max_results:
#             break

#         name = r_.get("name")
#         loc = (r_.get("geometry") or {}).get("location") or {}
#         lat2 = loc.get("lat")
#         lng2 = loc.get("lng")

#         if not name or lat2 is None or lng2 is None:
#             continue

#         dist = _distance_meters(lat, lng, float(lat2), float(lng2))
#         if dist > radius_m:
#             continue

#         names.append(name.strip())

#     return names


# # ---------------- OpenAI helper ----------------

# def _generate_activities_via_llm(
#     *,
#     mood: Optional[str],
#     schema_hint: Optional[str],
#     postal_code: Optional[str],
#     goal_today: Optional[str],
#     place: Optional[str],
#     count: int = 6,
# ) -> List[schemas.ActivityBase]:
#     """
#     Generate EXACTLY `count` activities:
#     - First 3: place-based activities using REAL Google Places names.
#     - Last 3: goal-based BA activities.
#     """

#     # --- build context text ---
#     context_bits: List[str] = []
#     if mood:
#         context_bits.append(f"current mood: {mood}")
#     if schema_hint:
#         context_bits.append(f"schema or core story: {schema_hint}")
#     if goal_today:
#         context_bits.append(f"today's goal: {goal_today}")
#     if place:
#         context_bits.append(f"preferred environment: {place}")
#     if postal_code:
#         context_bits.append(f"location_hint: {postal_code}")

#     # --- lookup nearby places from Google ---
#     nearby_parks: List[str] = []
#     nearby_cafes: List[str] = []
#     nearby_attractions: List[str] = []
#     nearby_malls: List[str] = []
#     nearby_theatres: List[str] = []
#     nearby_libraries: List[str] = []
#     nearby_gyms: List[str] = []

#     coords: Optional[Tuple[float, float]] = None
#     if postal_code:
#         coords = _geocode_postal_code(postal_code)

#     if coords:
#         lat, lng = coords

#         nearby_parks = _nearby_places(lat, lng, "park", max_results=5)
#         nearby_cafes = _nearby_places(lat, lng, "cafe", max_results=5)
#         nearby_attractions = _nearby_places(lat, lng, "tourist_attraction", max_results=5)
#         nearby_malls = _nearby_places(lat, lng, "shopping_mall", max_results=5)
#         nearby_theatres = _nearby_places(lat, lng, "movie_theater", max_results=5)
#         nearby_libraries = _nearby_places(lat, lng, "library", max_results=5)
#         nearby_gyms = _nearby_places(lat, lng, "gym", max_results=5)

#         if nearby_parks:
#             context_bits.append("nearby_parks: " + ", ".join(nearby_parks))
#         if nearby_cafes:
#             context_bits.append("nearby_cafes: " + ", ".join(nearby_cafes))
#         if nearby_attractions:
#             context_bits.append("nearby_attractions: " + ", ".join(nearby_attractions))
#         if nearby_malls:
#             context_bits.append("nearby_malls: " + ", ".join(nearby_malls))
#         if nearby_theatres:
#             context_bits.append("nearby_theatres: " + ", ".join(nearby_theatres))
#         if nearby_libraries:
#             context_bits.append("nearby_libraries: " + ", ".join(nearby_libraries))
#         if nearby_gyms:
#             context_bits.append("nearby_gyms: " + ", ".join(nearby_gyms))

#     all_nearby_places: List[str] = (
#         nearby_parks
#         + nearby_cafes
#         + nearby_attractions
#         + nearby_malls
#         + nearby_theatres
#         + nearby_libraries
#         + nearby_gyms
#     )

#     print(
#         f"[activity] nearby counts – parks={len(nearby_parks)}, cafes={len(nearby_cafes)}, "
#         f"attractions={len(nearby_attractions)}, malls={len(nearby_malls)}, "
#         f"theatres={len(nearby_theatres)}, libraries={len(nearby_libraries)}, gyms={len(nearby_gyms)}"
#     )

#     context_text = "; ".join(context_bits) or "no extra context provided"

#     system_msg = (
#         "You are a behavioural activation coach designing very small, realistic, "
#         "real-world activities for a mental health app.\n"
#         "Each activity must be:\n"
#         "- concrete and doable in 5–30 minutes\n"
#         "- safe and gentle (no extreme exercise, no unsafe locations)\n"
#         "- described in simple language\n"
#         "- If you reference a place (park, cafe, mall, theatre, library, attraction, gym), "
#         "you MUST use the exact name from the provided nearby_* lists.\n"
#         "- Do NOT invent or tweak place names.\n\n"
#         "MATCH PLACE TYPE TO THE USER'S GOAL:\n"
#         "- Goals about movement / steps / walk / exercise -> prefer parks or gyms.\n"
#         "- Goals about talking, connection, not feeling alone -> prefer cafes or other social spaces.\n"
#         "- Goals about chilling, recharging, entertainment -> prefer malls, theatres, or gentle attractions.\n"
#         "- Goals about focus, work, study, reading -> prefer libraries or quiet cafes.\n"
#         "Where possible, vary the place types across the 3 place-based activities.\n\n"
#         "You can use BA flavours like Movement, Connection, Creative, Grounding, "
#         "or Self-compassion. Use tags to encode this.\n"
#     )

#     user_msg = (
#         f"User context: {context_text}\n\n"
#         "Generate EXACTLY 6 activities in this order:\n"
#         "1–3: PLACE-BASED activities that use real nearby places from the lists. "
#         "Mark them with a '+ PlaceBased' tag.\n"
#         "4–6: GOAL-BASED BA activities (like 'Coffee with Maya', 'Call Mom', "
#         "'Morning Pages'). Mark them with a '+ GoalBased' tag.\n\n"
#         "For GOAL-BASED items, also include a tag of the form "
#         "'Supports: <short phrase>' explaining how it supports their goal.\n\n"
#         "Return ONLY JSON in this exact format (no extra commentary):\n"
#         "{\n"
#         '  \"activities\": [\n'
#         "    {\n"
#         '      \"title\": \"short name\",\n'
#         '      \"description\": \"2–3 sentence description of what to do\",\n'
#         '      \"life_area\": \"Movement | Connection | Creative | Grounding | Self-compassion | Work | Body\",\n'
#         '      \"effort_level\": \"low | medium | high\",\n'
#         '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
#         '      \"default_duration_min\": 5,\n'
#         '      \"location_label\": \"Exact place name from nearby lists, or \'at home\' / \'anywhere comfortable\' for goal-based items\",\n'
#         '      \"tags\": [\"+ PlaceBased or + GoalBased\", \"BA flavour like Movement/Connection\", \"Supports: ... for goal-based\"]\n'
#         "    }\n"
#         "  ]\n"
#         "}"
#     )

#     try:
#         resp = client.chat.completions.create(
#             model=OPENAI_ACTIVITY_MODEL,
#             messages=[
#                 {"role": "system", "content": system_msg},
#                 {"role": "user", "content": user_msg},
#             ],
#             temperature=0.7,
#         )
#     except Exception as e:
#         raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")

#     try:
#         content = resp.choices[0].message.content
#         data = json.loads(content)
#         items = data.get("activities") or []
#     except json.JSONDecodeError:
#         raise HTTPException(
#             status_code=500,
#             detail="Failed to parse OpenAI JSON for activities",
#         )

#     if len(items) > count:
#         items = items[:count]

#     # tag enforcement: first 3 = PlaceBased, last 3 = GoalBased
#     for idx, item in enumerate(items):
#         tags = item.get("tags") or []
#         if idx < 3 and not any("+ PlaceBased" in str(t) for t in tags):
#             tags.append("+ PlaceBased")
#         if idx >= 3 and not any("+ GoalBased" in str(t) for t in tags):
#             tags.append("+ GoalBased")
#         item["tags"] = tags

#     activities: List[schemas.ActivityBase] = []

#     for idx, item in enumerate(items):
#         try:
#             title = (item.get("title") or "").strip() or "Small step"
#             description = (item.get("description") or "").strip() or "Take a small helpful step."
#             life_area = item.get("life_area", "Meaning")
#             effort_level = item.get("effort_level", "low")
#             reward_type = item.get("reward_type")
#             default_duration_min = item.get("default_duration_min") or 10
#             tags = item.get("tags") or []
#             location_label = item.get("location_label")

#             # 🔵 HARD RULE: if we actually have Google places, first 3 MUST use them.
#             # We already passed nearby_* to the LLM; additionally guard here.
#             # If there ARE places but LLM omitted, force-pick one.
#             # (Keep as-is if provided.)
#             if not location_label:
#                 location_label = "at home"

#             act = schemas.ActivityBase(
#                 title=title,
#                 description=description,
#                 life_area=life_area,
#                 effort_level=effort_level,
#                 reward_type=reward_type,
#                 default_duration_min=default_duration_min,
#                 location_label=location_label,
#                 tags=tags,
#             )
#             activities.append(act)
#         except Exception as e:
#             print(f"[activity] Error building ActivityBase: {e}")
#             continue

#     if not activities:
#         raise HTTPException(status_code=500, detail="OpenAI returned no valid activities")

#     return activities


# # --------- Store generated activities in DB ---------


# def _store_generated_activities(
#     db: Session,
#     *,
#     activities: List[schemas.ActivityBase],
# ) -> List[models.Activities]:
#     now = datetime.utcnow()
#     rows: List[models.Activities] = []

#     for a in activities:
#         row = models.Activities(
#             title=a.title,
#             description=a.description,
#             life_area=a.life_area,
#             effort_level=a.effort_level,
#             reward_type=a.reward_type,
#             default_duration_min=a.default_duration_min,
#             location_label=a.location_label,
#             tags_json=json.dumps(a.tags or []),
#             is_active=True,
#             created_at=now,
#         )
#         db.add(row)
#         rows.append(row)

#     db.commit()
#     for r_obj in rows:
#         db.refresh(r_obj)

#     return rows


# # ---------------- helpers (persist) ----------------

# def _to_activity_out(act: models.Activities) -> schemas.ActivityRecommendationOut:
#     tags: List[str] = []
#     if act.tags_json:
#         try:
#             tags = json.loads(act.tags_json)
#         except Exception:
#             tags = []
#     return schemas.ActivityRecommendationOut(
#         id=act.id,
#         title=act.title,
#         description=act.description,
#         life_area=act.life_area,
#         effort_level=act.effort_level,
#         reward_type=act.reward_type,
#         default_duration_min=act.default_duration_min,
#         location_label=act.location_label,
#         tags=tags,
#     )


# def _commit_activity(db: Session, *, user_hash: str, activity_id: int) -> None:
#     row = models.ActivitySessions(
#         user_hash=user_hash,
#         activity_id=activity_id,
#         status="suggested",
#         started_at=datetime.utcnow(),
#         created_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()


# def _get_current_activity(db: Session, *, user_hash: str) -> Optional[models.Activities]:
#     sess = (
#         db.query(models.ActivitySessions)
#         .filter(
#             models.ActivitySessions.user_hash == user_hash,
#             models.ActivitySessions.status.in_(["suggested", "started"]),
#         )
#         .order_by(models.ActivitySessions.created_at.desc())
#         .first()
#     )
#     if not sess:
#         return None
#     act = (
#         db.query(models.Activities)
#         .filter(models.Activities.id == sess.activity_id, models.Activities.is_active == True)
#         .first()
#     )
#     return act


# # ---------------- Public endpoints ----------------

# @r.get(
#     "/current",
#     response_model=schemas.ActivityCurrentOut,
#     summary="Get the user's current persisted activity (suggested/started).",
# )
# def get_current(
#     user_hash: str = Query(..., description="User hash whose current activity we want"),
#     db: Session = Depends(get_db),
# ):
#     act = _get_current_activity(db, user_hash=user_hash)
#     return schemas.ActivityCurrentOut(activity=_to_activity_out(act) if act else None)


# @r.post(
#     "/commit",
#     summary="Persist a specific activity as the user's current recommendation.",
# )
# def commit_activity(
#     payload: schemas.ActivityCommitIn,
#     db: Session = Depends(get_db),
# ):
#     act = (
#         db.query(models.Activities)
#         .filter(models.Activities.id == payload.activity_id, models.Activities.is_active == True)
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")
#     _commit_activity(db, user_hash=payload.user_hash, activity_id=payload.activity_id)
#     return {"ok": True}


# @r.get(
#     "/recommendation",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation",
# )
# @r.get(
#     "/recommend",
#     response_model=schemas.ActivityRecommendationListOut,
#     summary="Get Recommendation (alias)",
#     include_in_schema=False,
# )
# def get_recommendation(
#     user_hash: Optional[str] = Query(None, description="Optional user hash"),
#     life_area: Optional[str] = Query(None, description="Preferred life area filter, e.g., 'Connection'"),
#     mood: Optional[str] = Query(None, description="Current mood (from intake)"),
#     schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
#     postal_code: Optional[str] = Query(None, description="Location text (postcode, city, etc.)"),
#     goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
#     place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
#     limit: int = Query(6, ge=1, le=20, description="Maximum number of activities to return"),
#     commit_first: bool = Query(False, description="If true (and user_hash present), persist the top pick"),
#     db: Session = Depends(get_db),
# ):
#     """
#     Return up to `limit` LLM-generated BA activities, tailored to *this* request*.
#     Optionally **persist** the first one as the user's current pick
#     when `commit_first=true&user_hash=...`.

#     - First 3: place-based (REAL Google Places names when available).
#     - Last 3: goal-based BA actions.
#     """

#     print(f"[activity] /recommendation called with postal_code='{postal_code}'")

#     generated = _generate_activities_via_llm(
#         mood=mood,
#         schema_hint=schema_hint,
#         postal_code=postal_code,
#         goal_today=goal_today,
#         place=place,
#         count=6,
#     )

#     rows = _store_generated_activities(db, activities=generated)

#     if life_area:
#         filtered = [
#             r_
#             for r_ in rows
#             if (r_.life_area or "").lower() == life_area.lower()
#         ]
#         candidates = filtered or rows
#     else:
#         candidates = rows

#     if not candidates:
#         raise HTTPException(status_code=404, detail="No activities available")

#     selected = sorted(
#         candidates,
#         key=lambda x: x.created_at or datetime.utcnow(),
#         reverse=True,
#     )[:limit]

#     # Optional persistence of the first selected activity
#     if commit_first and user_hash and selected:
#         try:
#             _commit_activity(db, user_hash=user_hash, activity_id=selected[0].id)
#         except Exception as e:
#             print(f"[activity] commit_first failed: {e}")

#     recs: List[schemas.ActivityRecommendationOut] = [_to_activity_out(a) for a in selected]
#     return schemas.ActivityRecommendationListOut(activities=recs)


# @r.get(
#     "/library",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library",
# )
# @r.get(
#     "/list",
#     response_model=schemas.ActivityListOut,
#     summary="Get Activity Library (alias)",
#     include_in_schema=False,
# )
# def get_library(
#     db: Session = Depends(get_db),
# ):
#     """
#     Return the latest 6 active activities.
#     """
#     acts = (
#         db.query(models.Activities)
#         .filter(models.Activities.is_active == True)
#         .order_by(models.Activities.created_at.desc())
#         .limit(6)
#         .all()
#     )

#     out: List[schemas.ActivityOut] = []
#     for a in acts:
#         tags: List[str] = []
#         if a.tags_json:
#             try:
#                 tags = json.loads(a.tags_json)
#             except Exception:
#                 tags = []
#         out.append(
#             schemas.ActivityOut(
#                 id=a.id,
#                 title=a.title,
#                 description=a.description,
#                 life_area=a.life_area,
#                 effort_level=a.effort_level,
#                 reward_type=a.reward_type,
#                 default_duration_min=a.default_duration_min,
#                 location_label=a.location_label,
#                 tags=tags,
#             )
#         )

#     return schemas.ActivityListOut(activities=out)


# @r.post("/start", summary="Start Activity")
# def start_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=act.id,
#         session_id=payload.session_id,
#         status="started",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()
#     db.refresh(row)

#     return {"ok": True, "activity_session_id": row.id}


# @r.post("/complete", summary="Complete Activity")
# def complete_activity(
#     payload: schemas.ActivityStartIn,
#     db: Session = Depends(get_db),
# ):
#     """
#     Mark the most recent 'started' session for this activity/user as completed.
#     """
#     session_row = (
#         db.query(models.ActivitySessions)
#         .filter(
#             models.ActivitySessions.activity_id == payload.activity_id,
#             models.ActivitySessions.user_hash == payload.user_hash,
#             models.ActivitySessions.status == "started",
#         )
#         .order_by(models.ActivitySessions.started_at.desc())
#         .first()
#     )

#     if not session_row:
#         raise HTTPException(status_code=404, detail="Started activity not found")

#     session_row.status = "completed"
#     session_row.completed_at = datetime.utcnow()
#     db.commit()
#     db.refresh(session_row)

#     return {"ok": True}


# @r.post("/swap", summary="Swap Activity")
# def swap_activity(
#     payload: schemas.ActivitySwapIn,
#     db: Session = Depends(get_db),
# ):
#     """
#     Log a 'swapped' event and return the chosen activity so the frontend
#     can immediately show it on the Today card.
#     """
#     act = (
#         db.query(models.Activities)
#         .filter(
#             models.Activities.id == payload.activity_id,
#             models.Activities.is_active == True,
#         )
#         .first()
#     )
#     if not act:
#         raise HTTPException(status_code=404, detail="Activity not found")

#     row = models.ActivitySessions(
#         user_hash=payload.user_hash,
#         activity_id=payload.activity_id,
#         status="swapped",
#         started_at=datetime.utcnow(),
#     )
#     db.add(row)
#     db.commit()

#     return {
#         "ok": True,
#         "activity": _to_activity_out(act),
#     }




from __future__ import annotations

import json
import math
from datetime import datetime
from typing import List, Optional, Tuple

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app import models, schemas
from app.core.config import cfg as c

# ---------------- OpenAI setup ----------------

from openai import OpenAI

client = OpenAI(api_key=c.OPENAI_API_KEY)
OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])


# ---------------- DB dependency ----------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------------- Google Maps helpers ----------------

def _geocode_postal_code(location: str) -> Optional[Tuple[float, float]]:
    """
    location -> (lat, lng) using Google Geocoding.
    NOTE: `location` can be ANY human-readable string:
    - full postcode (e.g. 'L18 2QA')
    - city + country (e.g. 'Liverpool, UK')
    - neighbourhood (e.g. 'Notting Hill, London')
    """
    if not c.GOOGLE_MAPS_API_KEY or not location:
        return None

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    params = {"address": location, "key": c.GOOGLE_MAPS_API_KEY}

    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "OK":
            print(f"[activity] Geocode status != OK for '{location}': {data.get('status')}")
            return None
        loc = data["results"][0]["geometry"]["location"]
        coords = float(loc["lat"]), float(loc["lng"])
        print(f"[activity] Geocoded '{location}' -> {coords}")
        return coords
    except Exception as e:
        print(f"[activity] Geocode error for '{location}': {e}")
        return None


def _distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c_ = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c_


def _nearby_places(
    lat: float,
    lng: float,
    place_type: str,
    radius_m: int = 1200,
    max_results: int = 5,
) -> List[str]:
    """
    Look up nearby places of a given type using Google Places.
    Only keep results strictly within `radius_m` meters.
    """
    if not c.GOOGLE_MAPS_API_KEY:
        return []

    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": radius_m,
        "type": place_type,
        "key": c.GOOGLE_MAPS_API_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[activity] Places error for type '{place_type}': {e}")
        return []

    results = data.get("results") or []
    names: List[str] = []

    for r_ in results:
        if len(names) >= max_results:
            break

        name = r_.get("name")
        loc = (r_.get("geometry") or {}).get("location") or {}
        lat2 = loc.get("lat")
        lng2 = loc.get("lng")

        if not name or lat2 is None or lng2 is None:
            continue

        dist = _distance_meters(lat, lng, float(lat2), float(lng2))
        if dist > radius_m:
            continue

        names.append(name.strip())

    return names


# ---------------- OpenAI helper ----------------

def _generate_activities_via_llm(
    *,
    mood: Optional[str],
    schema_hint: Optional[str],
    postal_code: Optional[str],
    goal_today: Optional[str],
    place: Optional[str],
    count: int = 6,
) -> List[schemas.ActivityBase]:
    """
    Generate EXACTLY `count` activities:
    - First 3: place-based activities using REAL Google Places names.
    - Last 3: goal-based BA activities.
    """

    # --- build context text ---
    context_bits: List[str] = []
    if mood:
        context_bits.append(f"current mood: {mood}")
    if schema_hint:
        context_bits.append(f"schema or core story: {schema_hint}")
    if goal_today:
        context_bits.append(f"today's goal: {goal_today}")
    if place:
        context_bits.append(f"preferred environment: {place}")
    if postal_code:
        context_bits.append(f"location_hint: {postal_code}")

    # --- lookup nearby places from Google ---
    nearby_parks: List[str] = []
    nearby_cafes: List[str] = []
    nearby_attractions: List[str] = []
    nearby_malls: List[str] = []
    nearby_theatres: List[str] = []
    nearby_libraries: List[str] = []
    nearby_gyms: List[str] = []

    coords: Optional[Tuple[float, float]] = None
    if postal_code:
        coords = _geocode_postal_code(postal_code)

    if coords:
        lat, lng = coords

        nearby_parks = _nearby_places(lat, lng, "park", max_results=5)
        nearby_cafes = _nearby_places(lat, lng, "cafe", max_results=5)
        nearby_attractions = _nearby_places(lat, lng, "tourist_attraction", max_results=5)
        nearby_malls = _nearby_places(lat, lng, "shopping_mall", max_results=5)
        nearby_theatres = _nearby_places(lat, lng, "movie_theater", max_results=5)
        nearby_libraries = _nearby_places(lat, lng, "library", max_results=5)
        nearby_gyms = _nearby_places(lat, lng, "gym", max_results=5)

        if nearby_parks:
            context_bits.append("nearby_parks: " + ", ".join(nearby_parks))
        if nearby_cafes:
            context_bits.append("nearby_cafes: " + ", ".join(nearby_cafes))
        if nearby_attractions:
            context_bits.append("nearby_attractions: " + ", ".join(nearby_attractions))
        if nearby_malls:
            context_bits.append("nearby_malls: " + ", ".join(nearby_malls))
        if nearby_theatres:
            context_bits.append("nearby_theatres: " + ", ".join(nearby_theatres))
        if nearby_libraries:
            context_bits.append("nearby_libraries: " + ", ".join(nearby_libraries))
        if nearby_gyms:
            context_bits.append("nearby_gyms: " + ", ".join(nearby_gyms))

    all_nearby_places: List[str] = (
        nearby_parks
        + nearby_cafes
        + nearby_attractions
        + nearby_malls
        + nearby_theatres
        + nearby_libraries
        + nearby_gyms
    )

    print(
        f"[activity] nearby counts – parks={len(nearby_parks)}, cafes={len(nearby_cafes)}, "
        f"attractions={len(nearby_attractions)}, malls={len(nearby_malls)}, "
        f"theatres={len(nearby_theatres)}, libraries={len(nearby_libraries)}, gyms={len(nearby_gyms)}"
    )

    context_text = "; ".join(context_bits) or "no extra context provided"

    system_msg = (
        "You are a behavioural activation coach designing very small, realistic, "
        "real-world activities for a mental health app.\n"
        "Each activity must be:\n"
        "- concrete and doable in 5–30 minutes\n"
        "- safe and gentle (no extreme exercise, no unsafe locations)\n"
        "- described in simple language\n"
        "- If you reference a place (park, cafe, mall, theatre, library, attraction, gym), "
        "you MUST use the exact name from the provided nearby_* lists.\n"
        "- Do NOT invent or tweak place names.\n\n"
        "MATCH PLACE TYPE TO THE USER'S GOAL:\n"
        "- Goals about movement / steps / walk / exercise -> prefer parks or gyms.\n"
        "- Goals about talking, connection, not feeling alone -> prefer cafes or other social spaces.\n"
        "- Goals about chilling, recharging, entertainment -> prefer malls, theatres, or gentle attractions.\n"
        "- Goals about focus, work, study, reading -> prefer libraries or quiet cafes.\n"
        "Where possible, vary the place types across the 3 place-based activities.\n\n"
        "You can use BA flavours like Movement, Connection, Creative, Grounding, "
        "or Self-compassion. Use tags to encode this.\n"
    )

    user_msg = (
        f"User context: {context_text}\n\n"
        "Generate EXACTLY 6 activities in this order:\n"
        "1–3: PLACE-BASED activities that use real nearby places from the lists. "
        "Mark them with a '+ PlaceBased' tag.\n"
        "4–6: GOAL-BASED BA activities (like 'Coffee with Maya', 'Call Mom', "
        "'Morning Pages'). Mark them with a '+ GoalBased' tag.\n\n"
        "For GOAL-BASED items, also include a tag of the form "
        "'Supports: <short phrase>' explaining how it supports their goal.\n\n"
        "Return ONLY JSON in this exact format (no extra commentary):\n"
        "{\n"
        '  \"activities\": [\n'
        "    {\n"
        '      \"title\": \"short name\",\n'
        '      \"description\": \"2–3 sentence description of what to do\",\n'
        '      \"life_area\": \"Movement | Connection | Creative | Grounding | Self-compassion | Work | Body\",\n'
        '      \"effort_level\": \"low | medium | high\",\n'
        '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
        '      \"default_duration_min\": 5,\n'
        '      \"location_label\": \"Exact place name from nearby lists, or \'at home\' / \'anywhere comfortable\' for goal-based items\",\n'
        '      \"tags\": [\"+ PlaceBased or + GoalBased\", \"BA flavour like Movement/Connection\", \"Supports: ... for goal-based\"]\n'
        "    }\n"
        "  ]\n"
        "}"
    )

    try:
        resp = client.chat.completions.create(
            model=OPENAI_ACTIVITY_MODEL,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"OpenAI error: {e}")

    try:
        content = resp.choices[0].message.content
        data = json.loads(content)
        items = data.get("activities") or []
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=500,
            detail="Failed to parse OpenAI JSON for activities",
        )

    if len(items) > count:
        items = items[:count]

    # tag enforcement: first 3 = PlaceBased, last 3 = GoalBased
    for idx, item in enumerate(items):
        tags = item.get("tags") or []
        if idx < 3 and not any("+ PlaceBased" in str(t) for t in tags):
            tags.append("+ PlaceBased")
        if idx >= 3 and not any("+ GoalBased" in str(t) for t in tags):
            tags.append("+ GoalBased")
        item["tags"] = tags

    activities: List[schemas.ActivityBase] = []

    for idx, item in enumerate(items):
        try:
            title = (item.get("title") or "").strip() or "Small step"
            description = (item.get("description") or "").strip() or "Take a small helpful step."
            life_area = item.get("life_area", "Meaning")
            effort_level = item.get("effort_level", "low")
            reward_type = item.get("reward_type")
            default_duration_min = item.get("default_duration_min") or 10
            tags = item.get("tags") or []
            location_label = item.get("location_label")

            if not location_label:
                location_label = "at home"

            act = schemas.ActivityBase(
                title=title,
                description=description,
                life_area=life_area,
                effort_level=effort_level,
                reward_type=reward_type,
                default_duration_min=default_duration_min,
                location_label=location_label,
                tags=tags,
            )
            activities.append(act)
        except Exception as e:
            print(f"[activity] Error building ActivityBase: {e}")
            continue

    if not activities:
        raise HTTPException(status_code=500, detail="OpenAI returned no valid activities")

    return activities


# --------- Store generated activities in DB ---------


def _store_generated_activities(
    db: Session,
    *,
    activities: List[schemas.ActivityBase],
) -> List[models.Activities]:
    now = datetime.utcnow()
    rows: List[models.Activities] = []

    for a in activities:
        row = models.Activities(
            title=a.title,
            description=a.description,
            life_area=a.life_area,
            effort_level=a.effort_level,
            reward_type=a.reward_type,
            default_duration_min=a.default_duration_min,
            location_label=a.location_label,
            tags_json=json.dumps(a.tags or []),
            is_active=True,
            created_at=now,
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for r_obj in rows:
        db.refresh(r_obj)

    return rows


# ---------------- helpers (persist) ----------------

def _to_activity_out(act: models.Activities) -> schemas.ActivityRecommendationOut:
    tags: List[str] = []
    if act.tags_json:
        try:
            tags = json.loads(act.tags_json)
        except Exception:
            tags = []
    return schemas.ActivityRecommendationOut(
        id=act.id,
        title=act.title,
        description=act.description,
        life_area=act.life_area,
        effort_level=act.effort_level,
        reward_type=act.reward_type,
        default_duration_min=act.default_duration_min,
        location_label=act.location_label,
        tags=tags,
    )


def _commit_activity(db: Session, *, user_hash: str, activity_id: int) -> None:
    row = models.ActivitySessions(
        user_hash=user_hash,
        activity_id=activity_id,
        status="suggested",
        started_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()


def _get_current_activity(db: Session, *, user_hash: str) -> Optional[models.Activities]:
    sess = (
        db.query(models.ActivitySessions)
        .filter(
            models.ActivitySessions.user_hash == user_hash,
            models.ActivitySessions.status.in_(["suggested", "started"]),
        )
        .order_by(models.ActivitySessions.created_at.desc())
        .first()
    )
    if not sess:
        return None
    act = (
        db.query(models.Activities)
        .filter(models.Activities.id == sess.activity_id, models.Activities.is_active == True)
        .first()
    )
    return act


def _fallback_context_from_history(db: Session, user_hash: Optional[str]) -> dict:
    """
    When the request omits fields and we have a user_hash, use last-known Day-1 context
    (or most recent session/activity/user profile) to fill gaps.
    """
    out = {
        "postal_code": None,
        "schema_hint": None,
        "mood": None,
        "goal_today": None,
        "place": None,
    }
    if not user_hash:
        return out

    try:
        # user profile postal_code if present
        u = db.query(models.Users).filter(models.Users.user_hash == user_hash).first()
        if u and getattr(u, "postal_code", None):
            out["postal_code"] = getattr(u, "postal_code")
    except Exception:
        pass

    # last journey session for schema/mood
    try:
        s = (
            db.query(models.Sessions)
            .filter(models.Sessions.user_hash == user_hash)
            .order_by(models.Sessions.created_at.desc())
            .first()
        )
        if s:
            out["schema_hint"] = s.schema_hint or out["schema_hint"]
            out["mood"] = s.mood or out["mood"]
    except Exception:
        pass

    # last activity for goal/place if available
    try:
        asess = (
            db.query(models.ActivitySessions)
            .filter(models.ActivitySessions.user_hash == user_hash)
            .order_by(models.ActivitySessions.started_at.desc())
            .first()
        )
        if asess:
            a = db.query(models.Activities).filter(models.Activities.id == asess.activity_id).first()
            if a:
                out["goal_today"] = getattr(a, "title", None) or out["goal_today"]
                out["place"] = getattr(a, "location_label", None) or out["place"]
    except Exception:
        pass

    return out


# ---------------- Public endpoints ----------------

@r.get(
    "/current",
    response_model=schemas.ActivityCurrentOut,
    summary="Get the user's current persisted activity (suggested/started).",
)
def get_current(
    user_hash: str = Query(..., description="User hash whose current activity we want"),
    db: Session = Depends(get_db),
):
    act = _get_current_activity(db, user_hash=user_hash)
    return schemas.ActivityCurrentOut(activity=_to_activity_out(act) if act else None)


@r.post(
    "/commit",
    summary="Persist a specific activity as the user's current recommendation.",
)
def commit_activity(
    payload: schemas.ActivityCommitIn,
    db: Session = Depends(get_db),
):
    act = (
        db.query(models.Activities)
        .filter(models.Activities.id == payload.activity_id, models.Activities.is_active == True)
        .first()
    )
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")
    _commit_activity(db, user_hash=payload.user_hash, activity_id=payload.activity_id)
    return {"ok": True}


@r.get(
    "/recommendation",
    response_model=schemas.ActivityRecommendationListOut,
    summary="Get Recommendation",
)
@r.get(
    "/recommend",
    response_model=schemas.ActivityRecommendationListOut,
    summary="Get Recommendation (alias)",
    include_in_schema=False,
)
def get_recommendation(
    user_hash: Optional[str] = Query(None, description="Optional user hash"),
    life_area: Optional[str] = Query(None, description="Preferred life area filter, e.g., 'Connection'"),
    mood: Optional[str] = Query(None, description="Current mood (from intake)"),
    schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
    postal_code: Optional[str] = Query(None, description="Location text (postcode, city, etc.)"),
    goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
    place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
    limit: int = Query(6, ge=1, le=20, description="Maximum number of activities to return"),
    commit_first: bool = Query(False, description="If true (and user_hash present), persist the top pick"),
    db: Session = Depends(get_db),
):
    """
    Return up to `limit` LLM-generated BA activities, tailored to *this* request*.
    Optionally **persist** the first one as the user's current pick
    when `commit_first=true&user_hash=...`.

    - First 3: place-based (REAL Google Places names when available).
    - Last 3: goal-based BA actions.
    """

    # Fill missing fields from last-known Day-1 context if user_hash is provided
    if user_hash:
        fb = _fallback_context_from_history(db, user_hash)
        def eff(val, fallback):
            if val is None or (isinstance(val, str) and val.strip() == ""):
                return fallback
            return val
        postal_code = eff(postal_code, fb.get("postal_code"))
        schema_hint = eff(schema_hint, fb.get("schema_hint"))
        mood = eff(mood, fb.get("mood"))
        goal_today = eff(goal_today, fb.get("goal_today"))
        place = eff(place, fb.get("place"))

    print(f"[activity] /recommendation called with postal_code='{postal_code}'")

    generated = _generate_activities_via_llm(
        mood=mood,
        schema_hint=schema_hint,
        postal_code=postal_code,
        goal_today=goal_today,
        place=place,
        count=6,
    )

    rows = _store_generated_activities(db, activities=generated)

    if life_area:
        filtered = [
            r_
            for r_ in rows
            if (r_.life_area or "").lower() == life_area.lower()
        ]
        candidates = filtered or rows
    else:
        candidates = rows

    if not candidates:
        raise HTTPException(status_code=404, detail="No activities available")

    selected = sorted(
        candidates,
        key=lambda x: x.created_at or datetime.utcnow(),
        reverse=True,
    )[:limit]

    # Optional persistence of the first selected activity
    if commit_first and user_hash and selected:
        try:
            _commit_activity(db, user_hash=user_hash, activity_id=selected[0].id)
        except Exception as e:
            print(f"[activity] commit_first failed: {e}")

    recs: List[schemas.ActivityRecommendationOut] = [_to_activity_out(a) for a in selected]
    return schemas.ActivityRecommendationListOut(activities=recs)


@r.get(
    "/library",
    response_model=schemas.ActivityListOut,
    summary="Get Activity Library",
)
@r.get(
    "/list",
    response_model=schemas.ActivityListOut,
    summary="Get Activity Library (alias)",
    include_in_schema=False,
)
def get_library(
    db: Session = Depends(get_db),
):
    """
    Return the latest 6 active activities.
    """
    acts = (
        db.query(models.Activities)
        .filter(models.Activities.is_active == True)
        .order_by(models.Activities.created_at.desc())
        .limit(6)
        .all()
    )

    out: List[schemas.ActivityOut] = []
    for a in acts:
        tags: List[str] = []
        if a.tags_json:
            try:
                tags = json.loads(a.tags_json)
            except Exception:
                tags = []
        out.append(
            schemas.ActivityOut(
                id=a.id,
                title=a.title,
                description=a.description,
                life_area=a.life_area,
                effort_level=a.effort_level,
                reward_type=a.reward_type,
                default_duration_min=a.default_duration_min,
                location_label=a.location_label,
                tags=tags,
            )
        )

    return schemas.ActivityListOut(activities=out)


@r.post("/start", summary="Start Activity")
def start_activity(
    payload: schemas.ActivityStartIn,
    db: Session = Depends(get_db),
):
    act = (
        db.query(models.Activities)
        .filter(
            models.Activities.id == payload.activity_id,
            models.Activities.is_active == True,
        )
        .first()
    )
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")

    row = models.ActivitySessions(
        user_hash=payload.user_hash,
        activity_id=act.id,
        session_id=payload.session_id,
        status="started",
        started_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {"ok": True, "activity_session_id": row.id}


@r.post("/complete", summary="Complete Activity")
def complete_activity(
    payload: schemas.ActivityStartIn,
    db: Session = Depends(get_db),
):
    """
    Mark the most recent 'started' session for this activity/user as completed.
    """
    session_row = (
        db.query(models.ActivitySessions)
        .filter(
            models.ActivitySessions.activity_id == payload.activity_id,
            models.ActivitySessions.user_hash == payload.user_hash,
            models.ActivitySessions.status == "started",
        )
        .order_by(models.ActivitySessions.started_at.desc())
        .first()
    )

    if not session_row:
        raise HTTPException(status_code=404, detail="Started activity not found")

    session_row.status = "completed"
    session_row.completed_at = datetime.utcnow()
    db.commit()
    db.refresh(session_row)

    return {"ok": True}


@r.post("/swap", summary="Swap Activity")
def swap_activity(
    payload: schemas.ActivitySwapIn,
    db: Session = Depends(get_db),
):
    """
    Log a 'swapped' event and return the chosen activity so the frontend
    can immediately show it on the Today card.
    """
    act = (
        db.query(models.Activities)
        .filter(
            models.Activities.id == payload.activity_id,
            models.Activities.is_active == True,
        )
        .first()
    )
    if not act:
        raise HTTPException(status_code=404, detail="Activity not found")

    row = models.ActivitySessions(
        user_hash=payload.user_hash,
        activity_id=payload.activity_id,
        status="swapped",
        started_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()

    return {
        "ok": True,
        "activity": _to_activity_out(act),
    }
