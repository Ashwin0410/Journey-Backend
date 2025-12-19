from __future__ import annotations

import json
import math
from datetime import datetime
from typing import List, Optional, Tuple, Dict

import requests
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app import models, schemas
from app.core.config import cfg as c
from app.services import narrative as narrative_service



from openai import OpenAI

client = OpenAI(api_key=c.OPENAI_API_KEY)
OPENAI_ACTIVITY_MODEL = "gpt-4.1-mini"

r = APIRouter(prefix="/api/journey/activity", tags=["journey-activity"])




def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




def _geocode_postal_code(location: str) -> Optional[Tuple[float, float]]:
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
    R = 6371000  # meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c_ = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c_


# Type alias for place details
PlaceDetail = Dict[str, any]  # {"name": str, "lat": float, "lng": float, "place_id": str}


def _nearby_places(
    lat: float,
    lng: float,
    place_type: str,
    radius_m: int = 1200,
    max_results: int = 5,
) -> List[PlaceDetail]:
    """
    Returns list of place details with name, lat, lng, and place_id.
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
    places: List[PlaceDetail] = []

    for r_ in results:
        if len(places) >= max_results:
            break

        name = r_.get("name")
        loc = (r_.get("geometry") or {}).get("location") or {}
        lat2 = loc.get("lat")
        lng2 = loc.get("lng")
        place_id = r_.get("place_id")

        if not name or lat2 is None or lng2 is None:
            continue

        dist = _distance_meters(lat, lng, float(lat2), float(lng2))
        if dist > radius_m:
            continue

        places.append({
            "name": name.strip(),
            "lat": float(lat2),
            "lng": float(lng2),
            "place_id": place_id or "",
        })

    return places


def _get_place_names(places: List[PlaceDetail]) -> List[str]:
    """Extract just the names from place details for LLM prompt."""
    return [p["name"] for p in places]


def _find_place_by_name(name: str, all_places: List[PlaceDetail]) -> Optional[PlaceDetail]:
    """
    Find a place by name (case-insensitive, partial match).
    Returns the place details if found, None otherwise.
    """
    if not name or not all_places:
        return None
    
    name_lower = name.lower().strip()
    
    # First try exact match
    for p in all_places:
        if p["name"].lower().strip() == name_lower:
            return p
    
    # Then try partial match (place name contains the search term or vice versa)
    for p in all_places:
        p_name_lower = p["name"].lower().strip()
        if name_lower in p_name_lower or p_name_lower in name_lower:
            return p
    
    return None




def _generate_activities_via_llm(
    *,
    mood: Optional[str],
    schema_hint: Optional[str],
    postal_code: Optional[str],
    goal_today: Optional[str],
    place: Optional[str],
    count: int = 6,
    # Chills-based personalization fields
    emotion_word: Optional[str] = None,
    chills_detail: Optional[str] = None,
    last_insight: Optional[str] = None,
    chills_level: Optional[str] = None,
) -> List[schemas.ActivityBase]:

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
    
    # Add chills-based context for better personalization
    if emotion_word:
        context_bits.append(f"emotion that resonated in last session: {emotion_word}")
    if chills_detail:
        context_bits.append(f"what triggered emotional response: {chills_detail}")
    if last_insight:
        insight_short = last_insight[:100] + "..." if len(last_insight) > 100 else last_insight
        context_bits.append(f"user's recent reflection: {insight_short}")


    # Store full place details (with coordinates) not just names
    nearby_parks: List[PlaceDetail] = []
    nearby_cafes: List[PlaceDetail] = []
    nearby_attractions: List[PlaceDetail] = []
    nearby_malls: List[PlaceDetail] = []
    nearby_theatres: List[PlaceDetail] = []
    nearby_libraries: List[PlaceDetail] = []
    nearby_gyms: List[PlaceDetail] = []

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

        # Extract names for LLM prompt
        park_names = _get_place_names(nearby_parks)
        cafe_names = _get_place_names(nearby_cafes)
        attraction_names = _get_place_names(nearby_attractions)
        mall_names = _get_place_names(nearby_malls)
        theatre_names = _get_place_names(nearby_theatres)
        library_names = _get_place_names(nearby_libraries)
        gym_names = _get_place_names(nearby_gyms)

        if park_names:
            context_bits.append("nearby_parks: " + ", ".join(park_names))
        if cafe_names:
            context_bits.append("nearby_cafes: " + ", ".join(cafe_names))
        if attraction_names:
            context_bits.append("nearby_attractions: " + ", ".join(attraction_names))
        if mall_names:
            context_bits.append("nearby_malls: " + ", ".join(mall_names))
        if theatre_names:
            context_bits.append("nearby_theatres: " + ", ".join(theatre_names))
        if library_names:
            context_bits.append("nearby_libraries: " + ", ".join(library_names))
        if gym_names:
            context_bits.append("nearby_gyms: " + ", ".join(gym_names))

    # Combine all places for coordinate lookup later
    all_nearby_places: List[PlaceDetail] = (
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

    # Build chills-based personalization hint for the system message
    chills_hint = ""
    if emotion_word or chills_detail or last_insight:
        chills_hint = (
            "\n\nPERSONALIZATION FROM LAST SESSION:\n"
            "The user had an emotional response in their last journey session. "
            "Design activities that build on what resonated with them:\n"
        )
        if emotion_word:
            chills_hint += f"- They felt '{emotion_word}' strongly\n"
        if chills_detail:
            chills_hint += f"- What triggered it: '{chills_detail}'\n"
        if last_insight:
            insight_short = last_insight[:150] + "..." if len(last_insight) > 150 else last_insight
            chills_hint += f"- Their reflection: '{insight_short}'\n"
        chills_hint += (
            "Use this context to suggest activities that continue or deepen "
            "the emotional thread they connected with.\n"
        )
        if chills_level == "high":
            chills_hint += "They responded strongly - suggest activities that build on this momentum.\n"
        elif chills_level == "medium":
            chills_hint += "They noticed subtle shifts - suggest gentle activities that continue this exploration.\n"

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
        f"{chills_hint}"
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

            # Try to find coordinates for this location
            lat: Optional[float] = None
            lng: Optional[float] = None
            place_id: Optional[str] = None
            
            # Look up place details if location_label matches a nearby place
            place_detail = _find_place_by_name(location_label, all_nearby_places)
            if place_detail:
                lat = place_detail["lat"]
                lng = place_detail["lng"]
                place_id = place_detail["place_id"]

            act = schemas.ActivityBase(
                title=title,
                description=description,
                life_area=life_area,
                effort_level=effort_level,
                reward_type=reward_type,
                default_duration_min=default_duration_min,
                location_label=location_label,
                tags=tags,
                lat=lat,
                lng=lng,
                place_id=place_id,
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
            lat=a.lat,
            lng=a.lng,
            place_id=a.place_id,
        )
        db.add(row)
        rows.append(row)

    db.commit()
    for r_obj in rows:
        db.refresh(r_obj)

    return rows



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
        lat=act.lat,
        lng=act.lng,
        place_id=act.place_id,
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
    Get context for activity generation from user history.
    
    For Day 2+ users: Uses chills-based context from last session's feedback
    (emotion_word, session_insight, chills_detail) instead of mini check-in.
    
    Falls back to session/activity history if no feedback available.
    """
    out = {
        "postal_code": None,
        "schema_hint": None,
        "mood": None,
        "goal_today": None,
        "place": None,
        # Chills-based fields
        "emotion_word": None,
        "chills_detail": None,
        "last_insight": None,
        "chills_level": None,
    }
    if not user_hash:
        return out

    # First, try to get chills-based context from last session's feedback
    chills_ctx = narrative_service.get_chills_context_for_generation(db, user_hash)
    
    # If we have chills context with meaningful data, use it
    if chills_ctx.get("feeling") or chills_ctx.get("last_insight") or chills_ctx.get("emotion_word"):
        out["mood"] = chills_ctx.get("feeling")
        out["schema_hint"] = chills_ctx.get("schema_choice")
        out["postal_code"] = chills_ctx.get("postal_code")
        out["goal_today"] = chills_ctx.get("goal_today")
        out["place"] = chills_ctx.get("place")
        out["emotion_word"] = chills_ctx.get("emotion_word")
        out["chills_detail"] = chills_ctx.get("chills_detail")
        out["last_insight"] = chills_ctx.get("last_insight")
        out["chills_level"] = chills_ctx.get("chills_level")
        return out

    # Fallback to old behavior if no chills context
    try:
        # user profile postal_code if present
        u = db.query(models.Users).filter(models.Users.user_hash == user_hash).first()
        if u and getattr(u, "postal_code", None):
            out["postal_code"] = getattr(u, "postal_code")
    except Exception:
        pass


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


def _get_therapist_suggested_activities(db: Session, user_hash: str) -> List[models.Activities]:
    """
    Get enabled therapist-suggested activities for a patient.
    
    Looks up the patient by user_hash, finds their therapist link,
    then fetches enabled activities from TherapistSuggestedActivities.
    These are converted to Activities model format for consistency.
    """
    if not user_hash:
        return []
    
    try:
        # Find the user by user_hash
        user = db.query(models.Users).filter(models.Users.user_hash == user_hash).first()
        if not user:
            return []
        
        # Find therapist-patient link
        therapist_link = (
            db.query(models.TherapistPatients)
            .filter(
                models.TherapistPatients.patient_user_id == user.id,
                models.TherapistPatients.status == "active",
            )
            .first()
        )
        if not therapist_link:
            return []
        
        # Get enabled therapist-suggested activities for this patient
        therapist_activities = (
            db.query(models.TherapistSuggestedActivities)
            .filter(
                models.TherapistSuggestedActivities.patient_user_id == user.id,
                models.TherapistSuggestedActivities.is_enabled == True,
            )
            .order_by(models.TherapistSuggestedActivities.created_at.desc())
            .all()
        )
        
        if not therapist_activities:
            return []
        
        # Convert to Activities format and store in DB so they work with existing flow
        now = datetime.utcnow()
        activity_rows: List[models.Activities] = []
        
        for ta in therapist_activities:
            # Check if this therapist activity was already converted to an Activity
            # by looking for matching title + description created recently
            existing = (
                db.query(models.Activities)
                .filter(
                    models.Activities.title == ta.title,
                    models.Activities.description == ta.description,
                    models.Activities.is_active == True,
                )
                .order_by(models.Activities.created_at.desc())
                .first()
            )
            
            if existing:
                # Use existing activity
                activity_rows.append(existing)
            else:
                # Create new Activity from therapist suggestion
                tags = ["+ TherapistSuggested"]
                if ta.category:
                    tags.append(ta.category)
                
                new_activity = models.Activities(
                    title=ta.title,
                    description=ta.description,
                    life_area=ta.category or "General",
                    effort_level=ta.barrier_level.lower() if ta.barrier_level else "low",
                    reward_type="other",
                    default_duration_min=ta.duration_minutes or 15,
                    location_label="as suggested by therapist",
                    tags_json=json.dumps(tags),
                    is_active=True,
                    created_at=now,
                    lat=None,
                    lng=None,
                    place_id=None,
                )
                db.add(new_activity)
                activity_rows.append(new_activity)
        
        if activity_rows:
            db.commit()
            for row in activity_rows:
                db.refresh(row)
        
        return activity_rows
    
    except Exception as e:
        print(f"[activity] Error getting therapist suggested activities: {e}")
        return []




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

    # Chills-based fields for personalization
    emotion_word: Optional[str] = None
    chills_detail: Optional[str] = None
    last_insight: Optional[str] = None
    chills_level: Optional[str] = None

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
        # Get chills-based fields
        emotion_word = fb.get("emotion_word")
        chills_detail = fb.get("chills_detail")
        last_insight = fb.get("last_insight")
        chills_level = fb.get("chills_level")

    print(f"[activity] /recommendation called with postal_code='{postal_code}'")

    generated = _generate_activities_via_llm(
        mood=mood,
        schema_hint=schema_hint,
        postal_code=postal_code,
        goal_today=goal_today,
        place=place,
        count=6,
        # Pass chills-based fields for personalization
        emotion_word=emotion_word,
        chills_detail=chills_detail,
        last_insight=last_insight,
        chills_level=chills_level,
    )

    rows = _store_generated_activities(db, activities=generated)

    # Get therapist-suggested activities and add them to the list
    therapist_rows: List[models.Activities] = []
    if user_hash:
        therapist_rows = _get_therapist_suggested_activities(db, user_hash)
        if therapist_rows:
            print(f"[activity] Adding {len(therapist_rows)} therapist-suggested activities")

    # Combine: LLM activities + therapist activities
    all_rows = rows + therapist_rows

    if life_area:
        filtered = [
            r_
            for r_ in all_rows
            if (r_.life_area or "").lower() == life_area.lower()
        ]
        candidates = filtered or all_rows
    else:
        candidates = all_rows

    if not candidates:
        raise HTTPException(status_code=404, detail="No activities available")

    # Sort by created_at, but keep therapist activities at the end
    # First: LLM activities sorted by created_at desc
    # Then: Therapist activities sorted by created_at desc
    llm_candidates = [c for c in candidates if c not in therapist_rows]
    therapist_candidates = [c for c in candidates if c in therapist_rows]
    
    llm_sorted = sorted(
        llm_candidates,
        key=lambda x: x.created_at or datetime.utcnow(),
        reverse=True,
    )[:limit]
    
    therapist_sorted = sorted(
        therapist_candidates,
        key=lambda x: x.created_at or datetime.utcnow(),
        reverse=True,
    )
    
    # Combine: LLM first (up to limit), then all therapist activities
    selected = llm_sorted + therapist_sorted


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
    user_hash: Optional[str] = Query(None, description="User hash to include therapist-suggested activities"),
    db: Session = Depends(get_db),
):
    """
    Return the latest 6 active activities plus any therapist-suggested activities for the user.
    """
    # Get latest 6 app activities
    acts = (
        db.query(models.Activities)
        .filter(models.Activities.is_active == True)
        .order_by(models.Activities.created_at.desc())
        .limit(6)
        .all()
    )

    out: List[schemas.ActivityOut] = []
    
    # First, add therapist-suggested activities if user_hash is provided
    if user_hash:
        therapist_activities = _get_therapist_suggested_activities(db, user_hash)
        for a in therapist_activities:
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
                    lat=a.lat,
                    lng=a.lng,
                    place_id=a.place_id,
                )
            )
        if therapist_activities:
            print(f"[activity] Library: Added {len(therapist_activities)} therapist activities for user {user_hash}")

    # Then add app activities
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
                lat=a.lat,
                lng=a.lng,
                place_id=a.place_id,
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
