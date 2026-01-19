from __future__ import annotations

import json
import math
import uuid
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


# =============================================================================
# CHANGE 5: ALL ACTIVITIES ARE NOW PLACE-BASED
# =============================================================================


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
    # NEW: Intake weekly plan fields
    life_area: Optional[str] = None,
    life_focus: Optional[str] = None,
    week_actions: Optional[List[str]] = None,
    # CHANGE 2: Direct GPS coordinates for location refresh
    gps_lat: Optional[float] = None,
    gps_lng: Optional[float] = None,
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
    
    # NEW: Add intake weekly plan context
    if life_area:
        context_bits.append(f"life area focus this week: {life_area}")
    if life_focus:
        context_bits.append(f"specific focus within that area: {life_focus}")
    if week_actions and len(week_actions) > 0:
        actions_str = "; ".join(week_actions[:5])  # Limit to 5 actions
        context_bits.append(f"user's committed actions this week: {actions_str}")
    
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
    nearby_restaurants: List[PlaceDetail] = []
    nearby_museums: List[PlaceDetail] = []
    nearby_spas: List[PlaceDetail] = []

    coords: Optional[Tuple[float, float]] = None
    
    # CHANGE 2: Prefer direct GPS coordinates over postal code geocoding
    if gps_lat is not None and gps_lng is not None:
        coords = (gps_lat, gps_lng)
        print(f"[activity] Using direct GPS coordinates: {coords}")
    elif postal_code:
        coords = _geocode_postal_code(postal_code)

    if coords:
        lat, lng = coords

        # CHANGE 5: Fetch more place types to ensure ALL activities can be place-based
        nearby_parks = _nearby_places(lat, lng, "park", max_results=5)
        nearby_cafes = _nearby_places(lat, lng, "cafe", max_results=5)
        nearby_attractions = _nearby_places(lat, lng, "tourist_attraction", max_results=5)
        nearby_malls = _nearby_places(lat, lng, "shopping_mall", max_results=5)
        nearby_theatres = _nearby_places(lat, lng, "movie_theater", max_results=5)
        nearby_libraries = _nearby_places(lat, lng, "library", max_results=5)
        nearby_gyms = _nearby_places(lat, lng, "gym", max_results=5)
        nearby_restaurants = _nearby_places(lat, lng, "restaurant", max_results=5)
        nearby_museums = _nearby_places(lat, lng, "museum", max_results=5)
        nearby_spas = _nearby_places(lat, lng, "spa", max_results=5)

        # Extract names for LLM prompt
        park_names = _get_place_names(nearby_parks)
        cafe_names = _get_place_names(nearby_cafes)
        attraction_names = _get_place_names(nearby_attractions)
        mall_names = _get_place_names(nearby_malls)
        theatre_names = _get_place_names(nearby_theatres)
        library_names = _get_place_names(nearby_libraries)
        gym_names = _get_place_names(nearby_gyms)
        restaurant_names = _get_place_names(nearby_restaurants)
        museum_names = _get_place_names(nearby_museums)
        spa_names = _get_place_names(nearby_spas)

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
        if restaurant_names:
            context_bits.append("nearby_restaurants: " + ", ".join(restaurant_names))
        if museum_names:
            context_bits.append("nearby_museums: " + ", ".join(museum_names))
        if spa_names:
            context_bits.append("nearby_spas: " + ", ".join(spa_names))

    # Combine all places for coordinate lookup later
    all_nearby_places: List[PlaceDetail] = (
        nearby_parks
        + nearby_cafes
        + nearby_attractions
        + nearby_malls
        + nearby_theatres
        + nearby_libraries
        + nearby_gyms
        + nearby_restaurants
        + nearby_museums
        + nearby_spas
    )

    print(
        f"[activity] nearby counts – parks={len(nearby_parks)}, cafes={len(nearby_cafes)}, "
        f"attractions={len(nearby_attractions)}, malls={len(nearby_malls)}, "
        f"theatres={len(nearby_theatres)}, libraries={len(nearby_libraries)}, gyms={len(nearby_gyms)}, "
        f"restaurants={len(nearby_restaurants)}, museums={len(nearby_museums)}, spas={len(nearby_spas)}"
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

    # NEW: Build weekly plan hint for the system message
    weekly_plan_hint = ""
    if life_area or life_focus or (week_actions and len(week_actions) > 0):
        weekly_plan_hint = (
            "\n\nUSER'S WEEKLY COMMITMENT:\n"
            "The user has set specific intentions for this week. "
            "Design activities that support or are variations of their commitments:\n"
        )
        if life_area:
            weekly_plan_hint += f"- Life area they're focusing on: '{life_area}'\n"
        if life_focus:
            weekly_plan_hint += f"- Specific focus: '{life_focus}'\n"
        if week_actions and len(week_actions) > 0:
            weekly_plan_hint += "- Actions they committed to:\n"
            for action in week_actions[:5]:  # Limit to 5
                weekly_plan_hint += f"  • {action}\n"
        weekly_plan_hint += (
            "Generate activities that align with these commitments. "
            "ALL activities should be at real nearby places that support their goals.\n"
        )

    # =============================================================================
    # CHANGE 5: Updated system message - ALL 6 activities must be PLACE-BASED
    # FIX: Added fallback instructions when no nearby places are available
    # =============================================================================
    
    # Check if we have nearby places
    has_nearby_places = len(all_nearby_places) > 0
    
    if has_nearby_places:
        place_instruction = (
            "CRITICAL: ALL 6 activities MUST use a real place from the nearby_* lists.\n"
            "You MUST use the exact name from the provided nearby_* lists.\n"
            "Do NOT invent or tweak place names.\n"
            "Do NOT suggest 'at home' or 'anywhere comfortable' - every activity needs a real location.\n\n"
        )
    else:
        # FIX: When no GPS/location is available, use generic but specific place types
        place_instruction = (
            "IMPORTANT: No specific nearby places were provided, but ALL activities MUST still be place-based.\n"
            "Use SPECIFIC generic place names like:\n"
            "- 'the nearest park' or 'a local park'\n"
            "- 'a nearby cafe' or 'the local coffee shop'\n"
            "- 'the neighborhood library'\n"
            "- 'a local restaurant'\n"
            "- 'the nearest gym or fitness center'\n"
            "- 'a nearby shopping area'\n"
            "Do NOT use vague terms like 'anywhere comfortable' or 'at home'.\n"
            "Each activity MUST specify a type of place to visit.\n\n"
        )
    
    system_msg = (
        "You are a behavioural activation coach designing very small, realistic, "
        "real-world activities for a mental health app.\n"
        "Each activity must be:\n"
        "- concrete and doable in 5–30 minutes\n"
        "- safe and gentle (no extreme exercise, no unsafe locations)\n"
        "- described in simple language\n"
        "- AT A REAL PLACE (not at home)\n\n"
        f"{place_instruction}"
        "MATCH PLACE TYPE TO THE ACTIVITY GOAL:\n"
        "- Movement / steps / walk / exercise -> prefer parks or gyms\n"
        "- Connection / talking / social -> prefer cafes or restaurants\n"
        "- Relaxation / recharging / entertainment -> prefer malls, theatres, spas, or attractions\n"
        "- Focus / work / study / reading -> prefer libraries or quiet cafes\n"
        "- Culture / inspiration / learning -> prefer museums or attractions\n"
        "- Self-care / wellness -> prefer spas, gyms, or parks\n\n"
        "Vary the place types across all 6 activities for diversity.\n"
        "Use BA flavours like Movement, Connection, Creative, Grounding, or Self-compassion.\n"
        f"{chills_hint}"
        f"{weekly_plan_hint}"
    )

    # =============================================================================
    # CHANGE 5: Updated user message - ALL 6 activities are PLACE-BASED
    # =============================================================================
    user_msg = (
        f"User context: {context_text}\n\n"
        "Generate EXACTLY 6 PLACE-BASED activities.\n"
        "EVERY activity MUST be at a real place (park, cafe, library, gym, etc.) - NOT at home.\n"
        "Use different place types across the 6 activities for variety.\n\n"
        "Return ONLY JSON in this exact format (no extra commentary):\n"
        "{\n"
        '  \"activities\": [\n'
        "    {\n"
        '      \"title\": \"short name\",\n'
        '      \"description\": \"2–3 sentence description of what to do at this specific place\",\n'
        '      \"life_area\": \"Movement | Connection | Creative | Grounding | Self-compassion | Work | Body\",\n'
        '      \"effort_level\": \"low | medium | high\",\n'
        '      \"reward_type\": \"calm | connection | mastery | movement | other\",\n'
        '      \"default_duration_min\": 5,\n'
        '      \"location_label\": \"EXACT place name from nearby lists OR specific place type like the nearest park - REQUIRED\",\n'
        '      \"tags\": [\"+ PlaceBased\", \"BA flavour like Movement/Connection\"]\n'
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

    # CHANGE 5: All activities are now PlaceBased - enforce tag on all
    for idx, item in enumerate(items):
        tags = item.get("tags") or []
        if not any("+ PlaceBased" in str(t) for t in tags):
            tags.append("+ PlaceBased")
        item["tags"] = tags

    activities: List[schemas.ActivityBase] = []

    for idx, item in enumerate(items):
        try:
            title = (item.get("title") or "").strip() or "Small step"
            description = (item.get("description") or "").strip() or "Take a small helpful step."
            life_area_item = item.get("life_area", "Meaning")
            effort_level = item.get("effort_level", "low")
            reward_type = item.get("reward_type")
            default_duration_min = item.get("default_duration_min") or 10
            tags = item.get("tags") or []
            location_label = item.get("location_label")

            # FIX Issue #2: Improved fallback for location_label with coordinates
            lat: Optional[float] = None
            lng: Optional[float] = None
            place_id: Optional[str] = None
            
            # First, try to find coordinates for the LLM-generated location_label
            if location_label and all_nearby_places:
                place_detail = _find_place_by_name(location_label, all_nearby_places)
                if place_detail:
                    lat = place_detail["lat"]
                    lng = place_detail["lng"]
                    place_id = place_detail["place_id"]
                    # Use the exact name from the place detail for consistency
                    location_label = place_detail["name"]
                    print(f"[activity] Matched location '{location_label}' -> lat={lat}, lng={lng}")
            
            # FIX Issue #2: If no location or no match, use the first available place WITH coordinates
            if not location_label or (lat is None and all_nearby_places):
                if all_nearby_places:
                    # Use different places for different activities to add variety
                    place_idx = idx % len(all_nearby_places)
                    fallback_place = all_nearby_places[place_idx]
                    location_label = fallback_place["name"]
                    lat = fallback_place["lat"]
                    lng = fallback_place["lng"]
                    place_id = fallback_place["place_id"]
                    print(f"[activity] Using fallback location '{location_label}' -> lat={lat}, lng={lng}")
                elif gps_lat is not None and gps_lng is not None:
                    # No nearby places but have GPS - keep the LLM-generated location label
                    # and use GPS coords so map can at least show approximate area
                    lat = gps_lat
                    lng = gps_lng
                    if not location_label or location_label.lower() in ["nearby", "anywhere", "anywhere comfortable", "at home"]:
                        # FIX: Replace generic labels with specific place types
                        place_types = ["the nearest park", "a local cafe", "the neighborhood library", 
                                      "a nearby restaurant", "a local gym", "a nearby shopping area"]
                        location_label = place_types[idx % len(place_types)]
                    print(f"[activity] No nearby places, using GPS coords with label '{location_label}' -> lat={lat}, lng={lng}")
                else:
                    # FIX: No GPS and no nearby places - use specific place type labels (not generic)
                    place_types = ["the nearest park", "a local cafe", "the neighborhood library", 
                                  "a nearby restaurant", "a local gym", "a nearby shopping area"]
                    if not location_label or location_label.lower() in ["nearby", "anywhere", "anywhere comfortable", "at home"]:
                        location_label = place_types[idx % len(place_types)]
                    print(f"[activity] No location data, using generic place type: '{location_label}'")

            act = schemas.ActivityBase(
                title=title,
                description=description,
                life_area=life_area_item,
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


# =============================================================================
# UPDATED: Store generated activities with action tracking metadata
# =============================================================================


def _store_generated_activities(
    db: Session,
    *,
    activities: List[schemas.ActivityBase],
    user_hash: Optional[str] = None,
    # NEW: Action tracking fields
    action_intention: Optional[str] = None,
    source_type: Optional[str] = None,  # "action_intention", "place_based", "therapist", "system"
    video_session_id: Optional[str] = None,
) -> List[models.Activities]:
    """
    Store generated activities in the database.
    
    BUG FIX (Change 7): Now accepts user_hash to scope activities to individual users.
    Without this, activities were stored globally and shared across all users.
    
    NEW: Now accepts action tracking metadata:
    - action_intention: The user's stated action text (e.g., "Call my mom")
    - source_type: How this activity was generated
    - video_session_id: Links back to the video session that triggered this
    
    FIX Issue #3: If no user_hash provided, do NOT store to database.
    This prevents anonymous/unidentified activity generation from polluting the global pool.
    """
    # FIX Issue #3: Require user_hash to store activities
    if not user_hash:
        print("[activity] WARNING: No user_hash provided - activities will NOT be stored to database")
        return []
    
    now = datetime.utcnow()
    rows: List[models.Activities] = []

    for a in activities:
        row = models.Activities(
            user_hash=user_hash,  # BUG FIX: Store user_hash with activity
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
            # NEW: Action tracking fields
            action_intention=action_intention,
            source_type=source_type,
            video_session_id=video_session_id,
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
        description=act.description or "",  # FIX: Ensure description is never None
        life_area=act.life_area,
        effort_level=act.effort_level,
        reward_type=act.reward_type,
        default_duration_min=act.default_duration_min,
        location_label=act.location_label,
        tags=tags,
        user_hash=act.user_hash,  # BUG FIX: Include user_hash in output
        lat=act.lat,
        lng=act.lng,
        place_id=act.place_id,
    )


def _therapist_activity_to_out(ta: models.TherapistSuggestedActivities) -> schemas.ActivityRecommendationOut:
    """
    Convert a TherapistSuggestedActivities record to ActivityRecommendationOut.
    Uses negative ID to distinguish from regular activities.
    """
    tags = ["+ TherapistSuggested"]
    if ta.category:
        tags.append(ta.category)
    
    # Use negative ID (based on therapist activity ID) to avoid collision with regular activities
    # This allows the frontend to identify therapist activities
    virtual_id = -ta.id
    
    return schemas.ActivityRecommendationOut(
        id=virtual_id,
        title=ta.title,
        description=ta.description or "",  # FIX: Ensure description is never None
        life_area=ta.category or "General",
        effort_level=ta.barrier_level.lower() if ta.barrier_level else "low",
        reward_type="other",
        default_duration_min=ta.duration_minutes or 15,
        location_label="as suggested by therapist",
        tags=tags,
        user_hash=None,  # Therapist activities don't have user_hash directly
        lat=None,
        lng=None,
        place_id=None,
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
    
    Also includes intake weekly plan data (life_area, life_focus, week_actions).
    
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
        # NEW: Intake weekly plan fields
        "life_area": None,
        "life_focus": None,
        "week_actions": [],
    }
    if not user_hash:
        return out

    # First, try to get chills-based context from last session's feedback
    # This now also includes intake data (life_area, life_focus, week_actions)
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
        # NEW: Get intake weekly plan data
        out["life_area"] = chills_ctx.get("life_area")
        out["life_focus"] = chills_ctx.get("life_focus")
        out["week_actions"] = chills_ctx.get("week_actions", [])
        return out

    # Even without chills context, still get intake weekly plan data
    out["life_area"] = chills_ctx.get("life_area")
    out["life_focus"] = chills_ctx.get("life_focus")
    out["week_actions"] = chills_ctx.get("week_actions", [])
    out["postal_code"] = chills_ctx.get("postal_code")

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


def _get_therapist_suggested_activities_for_patient(
    db: Session, user_hash: str
) -> List[models.TherapistSuggestedActivities]:
    """
    Get enabled therapist-suggested activities for a SPECIFIC patient only.
    
    CHANGE #4: Fixed to only return activities assigned to this specific patient,
    not activities from other patients or global activities.
    
    Returns the raw TherapistSuggestedActivities records (not converted to Activities).
    """
    if not user_hash:
        return []
    
    try:
        # Find the user by user_hash
        user = db.query(models.Users).filter(models.Users.user_hash == user_hash).first()
        if not user:
            print(f"[activity] No user found for user_hash: {user_hash}")
            return []
        
        # Find active therapist-patient link for this specific patient
        therapist_link = (
            db.query(models.TherapistPatients)
            .filter(
                models.TherapistPatients.patient_user_id == user.id,
                models.TherapistPatients.status == "active",
            )
            .first()
        )
        if not therapist_link:
            print(f"[activity] No active therapist link for user_id: {user.id}")
            return []
        
        # CHANGE #4: Get enabled therapist-suggested activities for THIS SPECIFIC PATIENT ONLY
        # Filter by patient_user_id to ensure activities are only for this patient
        therapist_activities = (
            db.query(models.TherapistSuggestedActivities)
            .filter(
                models.TherapistSuggestedActivities.patient_user_id == user.id,
                models.TherapistSuggestedActivities.is_enabled == True,
            )
            .order_by(models.TherapistSuggestedActivities.created_at.desc())
            .all()
        )
        
        if therapist_activities:
            print(f"[activity] Found {len(therapist_activities)} therapist activities for patient user_id: {user.id}")
        
        return therapist_activities
    
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


# =============================================================================
# FIX Issue #2: Added /today endpoint as alias for getting today's recommended activity
# =============================================================================

@r.get(
    "/today",
    response_model=schemas.ActivityTodayOut,
    summary="Get today's recommended activity for the user.",
)
def get_today_activity(
    user_hash: str = Query(..., description="User hash"),
    gps_lat: Optional[float] = Query(None, description="GPS latitude for location-based activities"),
    gps_lng: Optional[float] = Query(None, description="GPS longitude for location-based activities"),
    db: Session = Depends(get_db),
):
    """
    Get today's recommended activity for the user.
    
    This endpoint first checks for an existing current activity (suggested/started).
    If none exists, it generates a new recommendation.
    
    Returns activity with full location data (location_label, lat, lng, place_id).
    """
    # First, check if user has a current activity
    current_act = _get_current_activity(db, user_hash=user_hash)
    
    if current_act:
        # Return the current activity
        activity_out = _to_activity_out(current_act)
        print(f"[activity] /today returning current activity: {activity_out.title}, location={activity_out.location_label}, lat={activity_out.lat}, lng={activity_out.lng}")
        return schemas.ActivityTodayOut(
            activity=activity_out,
            is_new=False,
        )
    
    # No current activity - generate a new recommendation
    # Get context from user history
    fb = _fallback_context_from_history(db, user_hash)
    
    print(f"[activity] /today generating new activity with gps_lat={gps_lat}, gps_lng={gps_lng}")
    
    generated = _generate_activities_via_llm(
        mood=fb.get("mood"),
        schema_hint=fb.get("schema_hint"),
        postal_code=fb.get("postal_code"),
        goal_today=fb.get("goal_today"),
        place=fb.get("place"),
        count=1,  # Only need 1 for today
        emotion_word=fb.get("emotion_word"),
        chills_detail=fb.get("chills_detail"),
        last_insight=fb.get("last_insight"),
        chills_level=fb.get("chills_level"),
        life_area=fb.get("life_area"),
        life_focus=fb.get("life_focus"),
        week_actions=fb.get("week_actions", []),
        gps_lat=gps_lat,
        gps_lng=gps_lng,
    )
    
    if not generated:
        raise HTTPException(status_code=404, detail="Could not generate activity")
    
    # Store and commit the activity
    rows = _store_generated_activities(
        db, 
        activities=generated[:1], 
        user_hash=user_hash,
        source_type="system",
    )
    
    if not rows:
        raise HTTPException(status_code=500, detail="Failed to store activity")
    
    # Commit as the user's current activity
    _commit_activity(db, user_hash=user_hash, activity_id=rows[0].id)
    
    activity_out = _to_activity_out(rows[0])
    print(f"[activity] /today generated new activity: {activity_out.title}, location={activity_out.location_label}, lat={activity_out.lat}, lng={activity_out.lng}")
    
    return schemas.ActivityTodayOut(
        activity=activity_out,
        is_new=True,
    )


@r.post(
    "/commit",
    summary="Persist a specific activity as the user's current recommendation.",
)
def commit_activity(
    payload: schemas.ActivityCommitIn,
    db: Session = Depends(get_db),
):
    activity_id = payload.activity_id
    
    # CHANGE #4: Handle negative IDs (therapist activities)
    # Negative IDs are virtual IDs for therapist-suggested activities
    if activity_id < 0:
        # This is a therapist activity - we need to create a real Activity from it
        therapist_activity_id = -activity_id
        
        ta = (
            db.query(models.TherapistSuggestedActivities)
            .filter(
                models.TherapistSuggestedActivities.id == therapist_activity_id,
                models.TherapistSuggestedActivities.is_enabled == True,
            )
            .first()
        )
        if not ta:
            raise HTTPException(status_code=404, detail="Therapist activity not found")
        
        # Create a real Activity from the therapist suggestion for this commit
        # BUG FIX (Change 7): Include user_hash when creating activity from therapist suggestion
        tags = ["+ TherapistSuggested"]
        if ta.category:
            tags.append(ta.category)
        
        now = datetime.utcnow()
        new_activity = models.Activities(
            user_hash=payload.user_hash,  # BUG FIX: Scope to this user
            title=ta.title,
            description=ta.description or "",  # FIX: Ensure description is never None
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
            source_type="therapist",
        )
        db.add(new_activity)
        db.commit()
        db.refresh(new_activity)
        
        activity_id = new_activity.id
    else:
        # Regular activity - verify it exists
        act = (
            db.query(models.Activities)
            .filter(models.Activities.id == activity_id, models.Activities.is_active == True)
            .first()
        )
        if not act:
            raise HTTPException(status_code=404, detail="Activity not found")
    
    _commit_activity(db, user_hash=payload.user_hash, activity_id=activity_id)
    return {"ok": True}


# =============================================================================
# CHANGE 2: Added gps_lat and gps_lng parameters for location refresh
# =============================================================================

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
    user_hash: str = Query(..., description="User hash - REQUIRED for proper activity isolation"),
    life_area: Optional[str] = Query(None, description="Preferred life area filter, e.g., 'Connection'"),
    mood: Optional[str] = Query(None, description="Current mood (from intake)"),
    schema_hint: Optional[str] = Query(None, description="Schema / story (from intake)"),
    postal_code: Optional[str] = Query(None, description="Location text (postcode, city, etc.)"),
    goal_today: Optional[str] = Query(None, description="User's stated goal for today"),
    place: Optional[str] = Query(None, description="Environment: indoors / outdoors / nature etc."),
    # CHANGE 2: New GPS coordinate parameters for location refresh
    gps_lat: Optional[float] = Query(None, description="GPS latitude for location-based refresh"),
    gps_lng: Optional[float] = Query(None, description="GPS longitude for location-based refresh"),
    limit: int = Query(6, ge=1, le=20, description="Maximum number of activities to return"),
    commit_first: bool = Query(False, description="If true, persist the top pick as user's current activity"),
    db: Session = Depends(get_db),
):
    # =============================================================================
    # BUG FIX: user_hash is now REQUIRED - no activities without user identification
    # =============================================================================

    # Chills-based fields for personalization
    emotion_word: Optional[str] = None
    chills_detail: Optional[str] = None
    last_insight: Optional[str] = None
    chills_level: Optional[str] = None
    # NEW: Intake weekly plan fields
    intake_life_area: Optional[str] = None
    intake_life_focus: Optional[str] = None
    week_actions: Optional[List[str]] = None

    # Get context from user history (user_hash is always present now)
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
    # NEW: Get intake weekly plan fields
    intake_life_area = fb.get("life_area")
    intake_life_focus = fb.get("life_focus")
    week_actions = fb.get("week_actions", [])

    print(f"[activity] /recommendation called with postal_code='{postal_code}', user_hash='{user_hash}', life_area='{intake_life_area}', life_focus='{intake_life_focus}', gps_lat={gps_lat}, gps_lng={gps_lng}")

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
        # NEW: Pass intake weekly plan fields
        life_area=intake_life_area,
        life_focus=intake_life_focus,
        week_actions=week_actions,
        # CHANGE 2: Pass GPS coordinates for location refresh
        gps_lat=gps_lat,
        gps_lng=gps_lng,
    )

    # BUG FIX (Change 7): Pass user_hash when storing activities
    rows = _store_generated_activities(
        db, 
        activities=generated, 
        user_hash=user_hash,
        source_type="system",
    )

    # CHANGE #4: Get therapist-suggested activities for THIS SPECIFIC PATIENT ONLY
    # These are returned directly without creating global Activity rows
    therapist_activities = _get_therapist_suggested_activities_for_patient(db, user_hash)
    therapist_activity_outs: List[schemas.ActivityRecommendationOut] = []
    if therapist_activities:
        print(f"[activity] Adding {len(therapist_activities)} therapist-suggested activities for patient")
        therapist_activity_outs = [_therapist_activity_to_out(ta) for ta in therapist_activities]

    # =============================================================================
    # FIX Issue #3: If no rows stored (no user_hash), convert generated activities directly
    # =============================================================================
    if not rows and generated:
        # Convert generated ActivityBase objects to ActivityRecommendationOut
        # Use negative temporary IDs since they're not stored
        recs: List[schemas.ActivityRecommendationOut] = []
        for idx, act in enumerate(generated[:limit]):
            recs.append(schemas.ActivityRecommendationOut(
                id=-(idx + 1000),  # Temporary negative ID for unsaved activities
                title=act.title,
                description=act.description or "",
                life_area=act.life_area,
                effort_level=act.effort_level,
                reward_type=act.reward_type,
                default_duration_min=act.default_duration_min,
                location_label=act.location_label,
                tags=act.tags or [],
                user_hash=None,
                lat=act.lat,
                lng=act.lng,
                place_id=act.place_id,
            ))
        recs.extend(therapist_activity_outs)
        return schemas.ActivityRecommendationListOut(activities=recs)

    # Filter LLM activities by life_area if specified (query param takes precedence)
    if life_area:
        filtered = [
            r_
            for r_ in rows
            if (r_.life_area or "").lower() == life_area.lower()
        ]
        candidates = filtered or rows
    else:
        candidates = rows

    if not candidates and not therapist_activity_outs:
        raise HTTPException(status_code=404, detail="No activities available")

    # Sort LLM activities by created_at
    llm_sorted = sorted(
        candidates,
        key=lambda x: x.created_at or datetime.utcnow(),
        reverse=True,
    )[:limit]

    # Convert to output format
    recs: List[schemas.ActivityRecommendationOut] = [_to_activity_out(a) for a in llm_sorted]
    
    # CHANGE #4: Add therapist activities at the end (they're patient-specific)
    recs.extend(therapist_activity_outs)

    if commit_first and recs:
        try:
            first_activity_id = recs[0].id
            # Only commit if it's a positive ID (regular activity)
            # Therapist activities (negative IDs) will be converted when committed
            if first_activity_id > 0:
                _commit_activity(db, user_hash=user_hash, activity_id=first_activity_id)
        except Exception as e:
            print(f"[activity] commit_first failed: {e}")

    return schemas.ActivityRecommendationListOut(activities=recs)


# =============================================================================
# FIX Issue #1: Added limit parameter to /library endpoint
# FIX Issue #3: User isolation with fallback to global activities
# =============================================================================

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
    user_hash: str = Query(..., description="User hash - REQUIRED to filter activities"),
    limit: int = Query(6, ge=1, le=20, description="Maximum number of activities to return"),
    db: Session = Depends(get_db),
):
    """
    Return the latest active activities for the user plus any therapist-suggested activities.
    
    BUG FIX: user_hash is now REQUIRED and activities are STRICTLY filtered to this user only.
    
    Previously, activities with user_hash=NULL were returned to ALL users, causing
    one user's activities to appear for other users.
    
    Now:
    - Returns ONLY activities with matching user_hash
    - If user has no activities, returns empty list (frontend should trigger generation)
    - Therapist activities are still included (they're patient-specific)
    """
    # =============================================================================
    # BUG FIX: STRICT user_hash filter - no NULL fallback
    # =============================================================================
    acts = (
        db.query(models.Activities)
        .filter(
            models.Activities.is_active == True,
            models.Activities.user_hash == user_hash,  # STRICT: Only this user's activities
        )
        .order_by(models.Activities.created_at.desc())
        .limit(limit)
        .all()
    )
    
    print(f"[activity] /library returning {len(acts)} activities for user_hash={user_hash}, limit={limit}")

    out: List[schemas.ActivityOut] = []
    
    # CHANGE #4: Add therapist-suggested activities for THIS SPECIFIC PATIENT ONLY
    # These are returned with virtual (negative) IDs to distinguish them
    if user_hash:
        therapist_activities = _get_therapist_suggested_activities_for_patient(db, user_hash)
        for ta in therapist_activities:
            tags = ["+ TherapistSuggested"]
            if ta.category:
                tags.append(ta.category)
            
            # Use negative ID to distinguish from regular activities
            virtual_id = -ta.id
            
            # FIX: Ensure description is never None to prevent Pydantic validation error
            out.append(
                schemas.ActivityOut(
                    id=virtual_id,
                    title=ta.title or "Therapist Activity",
                    description=ta.description or "",  # FIX: Default to empty string if None
                    life_area=ta.category or "General",
                    effort_level=ta.barrier_level.lower() if ta.barrier_level else "low",
                    reward_type="other",
                    default_duration_min=ta.duration_minutes or 15,
                    location_label="as suggested by therapist",
                    tags=tags,
                    user_hash=None,
                    lat=None,
                    lng=None,
                    place_id=None,
                )
            )
        if therapist_activities:
            print(f"[activity] Library: Added {len(therapist_activities)} therapist activities for user {user_hash}")

    # Then add user's activities (or global fallback activities)
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
                title=a.title or "Activity",
                description=a.description or "",  # FIX: Ensure description is never None
                life_area=a.life_area,
                effort_level=a.effort_level,
                reward_type=a.reward_type,
                default_duration_min=a.default_duration_min,
                location_label=a.location_label,
                tags=tags,
                user_hash=a.user_hash,  # BUG FIX: Include user_hash in output
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
    activity_id = payload.activity_id
    
    # CHANGE #4: Handle negative IDs (therapist activities)
    if activity_id < 0:
        # This is a therapist activity - create a real Activity from it first
        therapist_activity_id = -activity_id
        
        ta = (
            db.query(models.TherapistSuggestedActivities)
            .filter(
                models.TherapistSuggestedActivities.id == therapist_activity_id,
                models.TherapistSuggestedActivities.is_enabled == True,
            )
            .first()
        )
        if not ta:
            raise HTTPException(status_code=404, detail="Therapist activity not found")
        
        # Create a real Activity from the therapist suggestion
        # BUG FIX (Change 7): Include user_hash when creating activity
        tags = ["+ TherapistSuggested"]
        if ta.category:
            tags.append(ta.category)
        
        now = datetime.utcnow()
        new_activity = models.Activities(
            user_hash=payload.user_hash,  # BUG FIX: Scope to this user
            title=ta.title,
            description=ta.description or "",  # FIX: Ensure description is never None
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
            source_type="therapist",
        )
        db.add(new_activity)
        db.commit()
        db.refresh(new_activity)
        
        activity_id = new_activity.id
    else:
        # Regular activity - verify it exists
        act = (
            db.query(models.Activities)
            .filter(
                models.Activities.id == activity_id,
                models.Activities.is_active == True,
            )
            .first()
        )
        if not act:
            raise HTTPException(status_code=404, detail="Activity not found")

    row = models.ActivitySessions(
        user_hash=payload.user_hash,
        activity_id=activity_id,
        session_id=payload.session_id,
        status="started",
        started_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {"ok": True, "activity_session_id": row.id}


# =============================================================================
# FIX Issue #3b & #5: Enhanced /complete endpoint
# - Properly marks activity as completed
# - Returns next_activity for frontend to display after completion
# =============================================================================

@r.post("/complete", summary="Complete Activity")
def complete_activity(
    payload: schemas.ActivityStartIn,
    db: Session = Depends(get_db),
):
    activity_id = payload.activity_id
    
    # CHANGE #4: Handle negative IDs (therapist activities)
    # For completion, we need to find the ActivitySession that was already started
    # The activity_id in the session would have been converted to a real ID when started
    if activity_id < 0:
        # Therapist activity - but by now it should have been converted to a real activity when started
        # Try to find a session with this user that matches a recently created therapist activity
        therapist_activity_id = -activity_id
        
        ta = (
            db.query(models.TherapistSuggestedActivities)
            .filter(models.TherapistSuggestedActivities.id == therapist_activity_id)
            .first()
        )
        if ta:
            # Look for an Activity with matching title/description that was started by this user
            matching_activity = (
                db.query(models.Activities)
                .filter(
                    models.Activities.title == ta.title,
                    models.Activities.description == ta.description,
                    models.Activities.user_hash == payload.user_hash,  # BUG FIX (Change 7): Filter by user
                    models.Activities.is_active == True,
                )
                .order_by(models.Activities.created_at.desc())
                .first()
            )
            if matching_activity:
                activity_id = matching_activity.id

    session_row = (
        db.query(models.ActivitySessions)
        .filter(
            models.ActivitySessions.activity_id == activity_id,
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

    # =============================================================================
    # FIX Issue #5: Generate and return next activity after completion
    # =============================================================================
    next_activity_out = None
    try:
        # Get context from user history for generating next activity
        fb = _fallback_context_from_history(db, payload.user_hash)
        
        # Generate a new activity
        generated = _generate_activities_via_llm(
            mood=fb.get("mood"),
            schema_hint=fb.get("schema_hint"),
            postal_code=fb.get("postal_code"),
            goal_today=fb.get("goal_today"),
            place=fb.get("place"),
            count=1,
            emotion_word=fb.get("emotion_word"),
            chills_detail=fb.get("chills_detail"),
            last_insight=fb.get("last_insight"),
            chills_level=fb.get("chills_level"),
            life_area=fb.get("life_area"),
            life_focus=fb.get("life_focus"),
            week_actions=fb.get("week_actions", []),
        )
        
        if generated:
            # Store the new activity
            rows = _store_generated_activities(
                db, 
                activities=generated[:1], 
                user_hash=payload.user_hash,
                source_type="system",
            )
            if rows:
                # Commit as the user's new current activity
                _commit_activity(db, user_hash=payload.user_hash, activity_id=rows[0].id)
                next_activity_out = _to_activity_out(rows[0])
                print(f"[activity] /complete: Generated next activity '{next_activity_out.title}' for user {payload.user_hash}")
    except Exception as e:
        print(f"[activity] /complete: Failed to generate next activity: {e}")
        # Don't fail the completion if next activity generation fails

    return {
        "ok": True,
        "completed_activity_id": activity_id,
        "next_activity": next_activity_out.model_dump() if next_activity_out else None,
    }


# =============================================================================
# FIX Issue #2: /swap endpoint now properly sets new activity as current
# =============================================================================

@r.post("/swap", summary="Swap Activity")
def swap_activity(
    payload: schemas.ActivitySwapIn,
    db: Session = Depends(get_db),
):
    activity_id = payload.activity_id
    
    # CHANGE #4: Handle negative IDs (therapist activities)
    if activity_id < 0:
        # This is a therapist activity - create a real Activity from it first
        therapist_activity_id = -activity_id
        
        ta = (
            db.query(models.TherapistSuggestedActivities)
            .filter(
                models.TherapistSuggestedActivities.id == therapist_activity_id,
                models.TherapistSuggestedActivities.is_enabled == True,
            )
            .first()
        )
        if not ta:
            raise HTTPException(status_code=404, detail="Therapist activity not found")
        
        # Create a real Activity from the therapist suggestion
        # BUG FIX (Change 7): Include user_hash when creating activity
        tags = ["+ TherapistSuggested"]
        if ta.category:
            tags.append(ta.category)
        
        now = datetime.utcnow()
        new_activity = models.Activities(
            user_hash=payload.user_hash,  # BUG FIX: Scope to this user
            title=ta.title,
            description=ta.description or "",  # FIX: Ensure description is never None
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
            source_type="therapist",
        )
        db.add(new_activity)
        db.commit()
        db.refresh(new_activity)
        
        act = new_activity
    else:
        # Regular activity
        act = (
            db.query(models.Activities)
            .filter(
                models.Activities.id == activity_id,
                models.Activities.is_active == True,
            )
            .first()
        )
        if not act:
            raise HTTPException(status_code=404, detail="Activity not found")

    # =============================================================================
    # FIX Issue #2: Mark old current activity as "swapped_out" first
    # =============================================================================
    existing_current_sessions = (
        db.query(models.ActivitySessions)
        .filter(
            models.ActivitySessions.user_hash == payload.user_hash,
            models.ActivitySessions.status.in_(["suggested", "started"]),
        )
        .all()
    )
    
    for old_session in existing_current_sessions:
        old_session.status = "swapped_out"
        print(f"[activity] Marked old activity session {old_session.id} as swapped_out")

    # =============================================================================
    # FIX Issue #2: Create new session with status "suggested" (not "swapped")
    # This ensures the new activity becomes the current activity
    # =============================================================================
    row = models.ActivitySessions(
        user_hash=payload.user_hash,
        activity_id=act.id,
        status="suggested",  # FIX: Use "suggested" so _get_current_activity() picks it up
        started_at=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    db.add(row)
    db.commit()

    print(f"[activity] Swapped to activity {act.id} '{act.title}' for user {payload.user_hash}")

    return {
        "ok": True,
        "activity": _to_activity_out(act),
    }


# =============================================================================
# Issue #8: GET single activity by ID - for timeline activity completion
# =============================================================================


# =============================================================================
# NEW: Generate activities from post-video action
# This endpoint uses the user's stated action intention from the video experience
# =============================================================================


def _get_action_from_post_video_response(db: Session, user_hash: str, session_id: Optional[str] = None) -> Optional[str]:
    """
    Get the user's action intention from their most recent PostVideoResponse.
    
    Priority:
    1. action_custom (if provided)
    2. action_selected (if not "Other")
    
    Args:
        db: Database session
        user_hash: User hash
        session_id: Optional specific session ID to get action from
    
    Returns:
        Action text to use for activity generation, or None
    """
    try:
        query = db.query(models.PostVideoResponse)
        
        if session_id:
            # Get response for specific session
            response = query.filter(models.PostVideoResponse.session_id == session_id).first()
        else:
            # Get most recent response for this user
            # Join with Sessions to filter by user_hash
            response = (
                query.join(models.Sessions, models.PostVideoResponse.session_id == models.Sessions.id)
                .filter(models.Sessions.user_hash == user_hash)
                .order_by(models.PostVideoResponse.created_at.desc())
                .first()
            )
        
        if not response:
            return None
        
        # Priority: action_custom > action_selected
        if response.action_custom:
            return response.action_custom.strip()
        
        if response.action_selected and response.action_selected.lower() != "other":
            return response.action_selected.strip()
        
        return None
        
    except Exception as e:
        print(f"[activity] Error getting action from post-video response: {e}")
        return None


def _generate_activities_from_action(
    db: Session,
    *,
    user_hash: str,
    action_today: str,
    postal_code: Optional[str] = None,
    gps_lat: Optional[float] = None,
    gps_lng: Optional[float] = None,
    count: int = 6,
) -> List[schemas.ActivityBase]:
    """
    Generate activities based on the user's stated action intention.
    
    This is a specialized version of _generate_activities_via_llm that
    focuses on the user's action_today as the primary input.
    
    Args:
        db: Database session
        user_hash: User hash
        action_today: The user's stated action from post-video response
        postal_code: Optional location hint
        gps_lat: Optional GPS latitude
        gps_lng: Optional GPS longitude
        count: Number of activities to generate
    
    Returns:
        List of generated ActivityBase objects
    """
    # Get additional context from user history
    fb = _fallback_context_from_history(db, user_hash)
    
    # Use the action_today as the primary goal
    return _generate_activities_via_llm(
        mood=fb.get("mood"),
        schema_hint=fb.get("schema_hint"),
        postal_code=postal_code or fb.get("postal_code"),
        goal_today=action_today,  # Use the action as the goal
        place=fb.get("place"),
        count=count,
        emotion_word=fb.get("emotion_word"),
        chills_detail=fb.get("chills_detail"),
        last_insight=fb.get("last_insight"),
        chills_level=fb.get("chills_level"),
        life_area=fb.get("life_area"),
        life_focus=fb.get("life_focus"),
        week_actions=fb.get("week_actions", []),
        gps_lat=gps_lat,
        gps_lng=gps_lng,
    )


@r.post(
    "/from-action",
    response_model=schemas.ActivityRecommendationListOut,
    summary="Generate activities from post-video action",
)
def generate_from_action(
    payload: schemas.ActivityFromActionIn,
    db: Session = Depends(get_db),
):
    """
    Generate 6 place-based BA activities based on the user's action intention.
    
    All 6 activities are:
    - Behavioural Activation (BA) activities - variations of the user's action
    - Place-based - each at a real nearby location from Google Maps
    
    Example: If action is "Call my mom":
    1. "Call mom while walking at Central Park" - at park
    2. "Voice message to mom from Starbucks" - at cafe  
    3. "Video call mom from the library" - at library
    4. "Quick check-in call at the gym" - at gym
    5. "Walk and talk with mom at Riverside Park" - at park
    6. "Call mom over coffee at Blue Bottle" - at cafe
    
    This endpoint is called after the user completes the video watching flow
    and has entered their action intention.
    
    Request:
        - user_hash: Required
        - action_today: The user's stated action intention
        - session_id: Optional - video session ID for linking
        - value_selected: Optional - the value that resonated
    
    Returns:
        List of 6 place-based BA activities tailored to the user's action
    """
    user_hash = payload.user_hash
    action_today = payload.action_today
    session_id = getattr(payload, 'session_id', None)
    gps_lat = getattr(payload, 'gps_lat', None)
    gps_lng = getattr(payload, 'gps_lng', None)
    
    if not user_hash:
        raise HTTPException(status_code=400, detail="user_hash is required")
    
    if not action_today:
        raise HTTPException(status_code=400, detail="action_today is required")
    
    print(f"[activity] /from-action called for user {user_hash}, action='{action_today}', session={session_id}, gps=({gps_lat}, {gps_lng})")
    
    # Get postal code from user if not provided via GPS
    postal_code = None
    if gps_lat is None or gps_lng is None:
        try:
            user = db.query(models.Users).filter(models.Users.user_hash == user_hash).first()
            if user and getattr(user, 'postal_code', None):
                postal_code = user.postal_code
                print(f"[activity] Using postal_code from user profile: {postal_code}")
        except Exception:
            pass
    
    # Generate session ID for linking activities to this video session
    video_session_id = session_id or str(uuid.uuid4())
    
    # Generate 6 place-based BA activities using existing LLM + Google Maps logic
    generated = _generate_activities_from_action(
        db,
        user_hash=user_hash,
        action_today=action_today,
        postal_code=postal_code,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        count=6,
    )
    
    if not generated:
        raise HTTPException(status_code=500, detail="Failed to generate activities")
    
    # Store activities with action tracking metadata
    rows = _store_generated_activities(
        db, 
        activities=generated, 
        user_hash=user_hash,
        action_intention=action_today,
        source_type="action_intention",
        video_session_id=video_session_id,
    )
    
    # Convert to output format
    if rows:
        recs: List[schemas.ActivityRecommendationOut] = [_to_activity_out(a) for a in rows]
    else:
        # Fallback if storage failed
        recs = []
        for idx, act in enumerate(generated):
            recs.append(schemas.ActivityRecommendationOut(
                id=-(idx + 2000),
                title=act.title,
                description=act.description or "",
                life_area=act.life_area,
                effort_level=act.effort_level,
                reward_type=act.reward_type,
                default_duration_min=act.default_duration_min,
                location_label=act.location_label,
                tags=act.tags or [],
                user_hash=None,
                lat=act.lat,
                lng=act.lng,
                place_id=act.place_id,
            ))
    
    print(f"[activity] Generated {len(recs)} place-based BA activities for action '{action_today}'")
    
    # Get therapist activities if any
    therapist_activities = _get_therapist_suggested_activities_for_patient(db, user_hash)
    if therapist_activities:
        therapist_outs = [_therapist_activity_to_out(ta) for ta in therapist_activities]
        recs.extend(therapist_outs)
    
    # Commit the first activity as the user's current activity
    if rows and user_hash:
        try:
            _commit_activity(db, user_hash=user_hash, activity_id=rows[0].id)
            print(f"[activity] Committed first activity '{rows[0].title}' for user {user_hash}")
        except Exception as e:
            print(f"[activity] Failed to commit first activity: {e}")
    
    return schemas.ActivityRecommendationListOut(activities=recs)


@r.get(
    "/action-for-session/{session_id}",
    summary="Get action from post-video response for a session",
)
def get_action_for_session(
    session_id: str,
    db: Session = Depends(get_db),
):
    """
    Get the action text from a session's post-video response.
    
    This is useful for debugging or for the frontend to confirm
    what action was captured.
    """
    response = (
        db.query(models.PostVideoResponse)
        .filter(models.PostVideoResponse.session_id == session_id)
        .first()
    )
    
    if not response:
        return {
            "has_action": False,
            "action": None,
            "source": None,
            "session_id": session_id,
        }
    
    # Get the action
    action = None
    source = None
    
    if response.action_custom:
        action = response.action_custom.strip()
        source = "custom"
    elif response.action_selected and response.action_selected.lower() != "other":
        action = response.action_selected.strip()
        source = "selected"
    
    return {
        "has_action": action is not None,
        "action": action,
        "source": source,
        "session_id": session_id,
        "action_selected": response.action_selected,
        "action_custom": response.action_custom,
    }


@r.get(
    "/by-session/{video_session_id}",
    response_model=schemas.ActivityRecommendationListOut,
    summary="Get activities generated from a specific video session",
)
def get_activities_by_session(
    video_session_id: str,
    user_hash: str = Query(..., description="User hash for security"),
    db: Session = Depends(get_db),
):
    """
    Get all activities that were generated from a specific video session.
    
    This is useful for the frontend to retrieve the activities that were
    generated after watching a video, without regenerating them.
    """
    activities = (
        db.query(models.Activities)
        .filter(
            models.Activities.video_session_id == video_session_id,
            models.Activities.user_hash == user_hash,
            models.Activities.is_active == True,
        )
        .order_by(models.Activities.created_at.asc())
        .all()
    )
    
    if not activities:
        return schemas.ActivityRecommendationListOut(activities=[])
    
    recs = [_to_activity_out(a) for a in activities]
    return schemas.ActivityRecommendationListOut(activities=recs)


@r.get(
    "/{activity_id}",
    response_model=schemas.ActivityOut,
    summary="Get a single activity by ID",
)
def get_activity_by_id(
    activity_id: int,
    db: Session = Depends(get_db),
):
    """
    Get a single activity by its ID.
    
    Issue #8: This endpoint is used by the frontend (journal.js) to fetch
    activity details when adding activity completion to the timeline.
    
    Note: This endpoint must be defined AFTER all other specific routes
    (like /current, /today, /library, etc.) to avoid path conflicts.
    """
    # Handle negative IDs (therapist activities)
    if activity_id < 0:
        therapist_activity_id = -activity_id
        ta = (
            db.query(models.TherapistSuggestedActivities)
            .filter(models.TherapistSuggestedActivities.id == therapist_activity_id)
            .first()
        )
        if not ta:
            raise HTTPException(status_code=404, detail="Activity not found")
        
        # Return therapist activity as ActivityOut
        tags = ["+ TherapistSuggested"]
        if ta.category:
            tags.append(ta.category)
        
        return schemas.ActivityOut(
            id=activity_id,  # Keep the negative ID
            title=ta.title or "Therapist Activity",
            description=ta.description or "",
            life_area=ta.category or "General",
            effort_level=ta.barrier_level.lower() if ta.barrier_level else "low",
            reward_type="other",
            default_duration_min=ta.duration_minutes or 15,
            location_label="as suggested by therapist",
            tags=tags,
            user_hash=None,
            lat=None,
            lng=None,
            place_id=None,
        )
    
    # Regular activity
    activity = (
        db.query(models.Activities)
        .filter(models.Activities.id == activity_id)
        .first()
    )
    
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    
    # Convert to output format
    tags: List[str] = []
    if activity.tags_json:
        try:
            tags = json.loads(activity.tags_json)
        except Exception:
            tags = []
    
    return schemas.ActivityOut(
        id=activity.id,
        title=activity.title or "Activity",
        description=activity.description or "",
        life_area=activity.life_area,
        effort_level=activity.effort_level,
        reward_type=activity.reward_type,
        default_duration_min=activity.default_duration_min,
        location_label=activity.location_label,
        tags=tags,
        user_hash=activity.user_hash,
        lat=activity.lat,
        lng=activity.lng,
        place_id=activity.place_id,
    )
