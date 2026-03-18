from fastapi import APIRouter
import requests

r = APIRouter()

@r.get("/api/health")
def health():
    return {"ok": True}


@r.get("/api/health/maps-diagnostic")
def maps_diagnostic():
    """
    Diagnostic endpoint to test Google Maps API key.
    Hit this in your browser:
    https://journey-backend-yzhw.onrender.com/api/health/maps-diagnostic
    
    DELETE THIS ENDPOINT after debugging is done.
    """
    from app.core.config import cfg as c
    
    key = c.GOOGLE_MAPS_API_KEY
    results = {
        "key_present": bool(key),
        "key_preview": (key[:10] + "..." + key[-4:]) if key else None,
        "geocoding_test": None,
        "places_test": None,
    }
    
    if not key:
        results["error"] = "GOOGLE_MAPS_API_KEY is not set"
        return results
    
    # Test 1: Geocoding API — convert "Liverpool, UK" to coordinates
    try:
        geo_url = "https://maps.googleapis.com/maps/api/geocode/json"
        geo_resp = requests.get(geo_url, params={"address": "Liverpool, UK", "key": key}, timeout=10)
        geo_data = geo_resp.json()
        
        results["geocoding_test"] = {
            "status": geo_data.get("status"),
            "error_message": geo_data.get("error_message"),
            "http_status": geo_resp.status_code,
        }
        
        if geo_data.get("status") == "OK" and geo_data.get("results"):
            loc = geo_data["results"][0]["geometry"]["location"]
            lat, lng = loc["lat"], loc["lng"]
            results["geocoding_test"]["lat"] = lat
            results["geocoding_test"]["lng"] = lng
            
            # Test 2: Places API — find cafes near Liverpool
            try:
                places_url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
                places_resp = requests.get(places_url, params={
                    "location": f"{lat},{lng}",
                    "radius": 1200,
                    "type": "cafe",
                    "key": key,
                }, timeout=10)
                places_data = places_resp.json()
                
                place_names = []
                for p in (places_data.get("results") or [])[:5]:
                    place_names.append(p.get("name"))
                
                results["places_test"] = {
                    "status": places_data.get("status"),
                    "error_message": places_data.get("error_message"),
                    "http_status": places_resp.status_code,
                    "places_found": len(places_data.get("results") or []),
                    "sample_places": place_names,
                }
            except Exception as e:
                results["places_test"] = {"error": str(e)}
        
    except Exception as e:
        results["geocoding_test"] = {"error": str(e)}
    
    return results
