"""
External Event Integration Service (Issue #5)

Fetches events from Eventbrite (and future: Luma, Partiful) and caches
them in the external_events table for use in activity recommendations.

Events are cached for 24 hours to avoid hitting external APIs on every request.
Stale events are refreshed automatically when requested.

Currently supported:
- Eventbrite (public API with token)

Future (no public API yet):
- Luma
- Partiful
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import requests
from sqlalchemy.orm import Session

from app.core.config import cfg as c

logger = logging.getLogger(__name__)

# Cache duration: events older than this are re-fetched
CACHE_HOURS = 24

# Eventbrite API base
EVENTBRITE_API_BASE = "https://www.eventbriteapi.com/v3"

# Category mapping: Eventbrite category IDs to human-readable names
# https://www.eventbrite.com/platform/api#/reference/categories
EVENTBRITE_CATEGORIES = {
    "103": "music",
    "104": "film",
    "105": "arts",
    "108": "sports",
    "109": "wellness",
    "110": "food",
    "111": "charity",
    "112": "community",
    "113": "fashion",
    "115": "health",
    "116": "hobbies",
    "199": "other",
}

# Categories most relevant to ReWire's BA activities
REWIRE_RELEVANT_CATEGORIES = [
    "109",  # Health & Wellness
    "115",  # Health
    "105",  # Performing & Visual Arts
    "103",  # Music
    "112",  # Community & Culture
    "110",  # Food & Drink
    "108",  # Sports & Fitness
    "116",  # Hobbies & Special Interest
]


def fetch_nearby_events(
    *,
    lat: float,
    lng: float,
    radius_km: int = 10,
    limit: int = 6,
    db_session: Optional[Session] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch nearby events, using cache when available.
    
    Args:
        lat: User's latitude
        lng: User's longitude
        radius_km: Search radius in kilometers
        limit: Maximum events to return
        db_session: SQLAlchemy session for cache read/write
        
    Returns:
        List of event dicts with keys: id, name, description, url, venue_name,
        address, lat, lng, start_time, end_time, category, is_free, price_text, source
    """
    # Try cache first
    if db_session:
        cached = _get_cached_events(db_session, lat, lng, radius_km, limit)
        if cached:
            logger.info(f"[events] Returning {len(cached)} cached events")
            return cached
    
    # Fetch fresh from Eventbrite
    events = _fetch_eventbrite(lat, lng, radius_km, limit)
    
    # Cache the results
    if db_session and events:
        _cache_events(db_session, events)
    
    return events[:limit]


def _get_cached_events(
    db: Session,
    lat: float,
    lng: float,
    radius_km: int,
    limit: int,
) -> List[Dict[str, Any]]:
    """Check cache for recent events near the given coordinates."""
    try:
        from app.models import ExternalEvent
        
        cutoff = datetime.utcnow() - timedelta(hours=CACHE_HOURS)
        now = datetime.utcnow()
        
        # Simple bounding box filter (rough approximation)
        # 1 degree latitude ~ 111 km
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * max(0.1, abs(lat) * 0.0174533))  # cos(lat) approximation
        
        rows = (
            db.query(ExternalEvent)
            .filter(
                ExternalEvent.fetched_at >= cutoff,
                ExternalEvent.start_time >= now,  # Only future events
                ExternalEvent.lat.isnot(None),
                ExternalEvent.lng.isnot(None),
                ExternalEvent.lat >= lat - lat_delta,
                ExternalEvent.lat <= lat + lat_delta,
                ExternalEvent.lng >= lng - lng_delta,
                ExternalEvent.lng <= lng + lng_delta,
            )
            .order_by(ExternalEvent.start_time.asc())
            .limit(limit)
            .all()
        )
        
        if not rows:
            return []
        
        return [_row_to_dict(r) for r in rows]
        
    except Exception as e:
        logger.warning(f"[events] Cache read error (non-fatal): {e}")
        return []


def _row_to_dict(row) -> Dict[str, Any]:
    """Convert ExternalEvent DB row to dict."""
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "url": row.url,
        "image_url": row.image_url,
        "venue_name": row.venue_name,
        "address": row.address,
        "city": row.city,
        "lat": row.lat,
        "lng": row.lng,
        "start_time": row.start_time.isoformat() if row.start_time else None,
        "end_time": row.end_time.isoformat() if row.end_time else None,
        "category": row.category,
        "is_free": row.is_free,
        "price_text": row.price_text,
        "source": row.source,
    }


def _cache_events(db: Session, events: List[Dict[str, Any]]) -> None:
    """Cache fetched events in the database."""
    try:
        from app.models import ExternalEvent
        
        expires = datetime.utcnow() + timedelta(hours=CACHE_HOURS)
        
        for ev in events:
            # Check if already cached (by source + external_id)
            existing = (
                db.query(ExternalEvent)
                .filter(
                    ExternalEvent.source == ev.get("source", "eventbrite"),
                    ExternalEvent.external_id == str(ev.get("external_id", "")),
                )
                .first()
            )
            
            if existing:
                # Update cache timestamp
                existing.fetched_at = datetime.utcnow()
                existing.expires_at = expires
                # Update fields that might have changed
                existing.name = ev.get("name", existing.name)
                existing.start_time = _parse_dt(ev.get("start_time"))
                existing.end_time = _parse_dt(ev.get("end_time"))
            else:
                # Insert new
                row = ExternalEvent(
                    source=ev.get("source", "eventbrite"),
                    external_id=str(ev.get("external_id", "")),
                    name=ev.get("name", "Event"),
                    description=(ev.get("description") or "")[:1000],
                    url=ev.get("url", ""),
                    image_url=ev.get("image_url"),
                    venue_name=ev.get("venue_name"),
                    address=ev.get("address"),
                    city=ev.get("city"),
                    lat=ev.get("lat"),
                    lng=ev.get("lng"),
                    start_time=_parse_dt(ev.get("start_time")),
                    end_time=_parse_dt(ev.get("end_time")),
                    category=ev.get("category"),
                    is_free=ev.get("is_free", False),
                    price_text=ev.get("price_text"),
                    expires_at=expires,
                )
                db.add(row)
        
        db.commit()
        logger.info(f"[events] Cached {len(events)} events")
        
    except Exception as e:
        logger.warning(f"[events] Cache write error (non-fatal): {e}")
        try:
            db.rollback()
        except Exception:
            pass


def _parse_dt(val) -> Optional[datetime]:
    """Parse a datetime string or return None."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    try:
        # ISO format
        return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
    except Exception:
        return None


# =============================================================================
# Eventbrite API
# =============================================================================

def _fetch_eventbrite(
    lat: float,
    lng: float,
    radius_km: int = 10,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """
    Fetch events from Eventbrite's public API.
    
    Uses the /events/search endpoint with location-based filtering.
    """
    if not c.EVENTBRITE_API_TOKEN:
        logger.info("[events] Eventbrite API token not configured, skipping")
        return []
    
    headers = {
        "Authorization": f"Bearer {c.EVENTBRITE_API_TOKEN}",
    }
    
    # Convert radius to miles (Eventbrite uses miles)
    radius_mi = str(round(radius_km * 0.621371, 1)) + "mi"
    
    # Search for events near the coordinates
    params = {
        "location.latitude": str(lat),
        "location.longitude": str(lng),
        "location.within": radius_mi,
        "sort_by": "date",
        "start_date.keyword": "today",
        "expand": "venue",
        "page_size": min(limit * 2, 50),  # Fetch extra to filter
    }
    
    try:
        resp = requests.get(
            f"{EVENTBRITE_API_BASE}/events/search/",
            headers=headers,
            params=params,
            timeout=10,
        )
        
        if resp.status_code == 401:
            logger.error("[events] Eventbrite API: Unauthorized (check token)")
            return []
        
        if resp.status_code == 429:
            logger.warning("[events] Eventbrite API: Rate limited")
            return []
        
        if not resp.ok:
            logger.warning(f"[events] Eventbrite API error: {resp.status_code} {resp.text[:200]}")
            return []
        
        data = resp.json()
        raw_events = data.get("events") or []
        
        logger.info(f"[events] Eventbrite returned {len(raw_events)} events")
        
        events = []
        for raw in raw_events:
            parsed = _parse_eventbrite_event(raw)
            if parsed:
                events.append(parsed)
            if len(events) >= limit:
                break
        
        return events
        
    except requests.Timeout:
        logger.warning("[events] Eventbrite API timeout")
        return []
    except Exception as e:
        logger.error(f"[events] Eventbrite API error: {e}")
        return []


def _parse_eventbrite_event(raw: dict) -> Optional[Dict[str, Any]]:
    """Parse a single Eventbrite event into our standard format."""
    try:
        event_id = raw.get("id", "")
        name_data = raw.get("name") or {}
        name = name_data.get("text") or name_data.get("html") or "Event"
        
        desc_data = raw.get("description") or raw.get("summary") or {}
        if isinstance(desc_data, dict):
            description = desc_data.get("text") or desc_data.get("html") or ""
        else:
            description = str(desc_data)
        
        url = raw.get("url", "")
        
        # Image
        logo = raw.get("logo") or {}
        image_url = logo.get("url") if isinstance(logo, dict) else None
        
        # Venue / location
        venue = raw.get("venue") or {}
        venue_name = venue.get("name")
        address_data = venue.get("address") or {}
        address = address_data.get("localized_address_display") or address_data.get("address_1") or ""
        city = address_data.get("city") or ""
        venue_lat = address_data.get("latitude")
        venue_lng = address_data.get("longitude")
        
        # Parse lat/lng
        lat = float(venue_lat) if venue_lat else None
        lng = float(venue_lng) if venue_lng else None
        
        # Times
        start_data = raw.get("start") or {}
        end_data = raw.get("end") or {}
        start_time = start_data.get("utc") or start_data.get("local")
        end_time = end_data.get("utc") or end_data.get("local")
        
        # Category
        category_id = raw.get("category_id") or ""
        category = EVENTBRITE_CATEGORIES.get(str(category_id), "other")
        
        # Price
        is_free = raw.get("is_free", False)
        price_text = "Free" if is_free else "Paid"
        
        # Skip events without location
        if lat is None or lng is None:
            return None
        
        # Skip events without a name
        if not name or name == "Event":
            return None
        
        return {
            "external_id": str(event_id),
            "name": name[:200],
            "description": description[:1000],
            "url": url,
            "image_url": image_url,
            "venue_name": venue_name,
            "address": address,
            "city": city,
            "lat": lat,
            "lng": lng,
            "start_time": start_time,
            "end_time": end_time,
            "category": category,
            "is_free": is_free,
            "price_text": price_text,
            "source": "eventbrite",
        }
        
    except Exception as e:
        logger.warning(f"[events] Failed to parse Eventbrite event: {e}")
        return None
