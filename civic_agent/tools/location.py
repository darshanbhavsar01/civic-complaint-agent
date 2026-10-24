"""Location tools: EXIF GPS, Maps Geocoding (forward + reverse), ward resolution."""
from __future__ import annotations

import os
from pathlib import Path

import httpx

import geo
from store import get_store

UPLOADS = Path(__file__).resolve().parents[2] / "uploads"
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

_LOCALITY_TYPES = (
    "sublocality_level_1",
    "sublocality",
    "neighborhood",
    "locality",
    "administrative_area_level_2",
)


def _maps_key() -> str:
    return (os.getenv("MAPS_SERVER_KEY") or os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()


def _localities(result: dict) -> list[str]:
    """Pull locality-ish names out of a Geocoding API result, most specific first."""
    names: list[str] = []
    for comp in result.get("address_components", []):
        types = comp.get("types", [])
        for want in _LOCALITY_TYPES:
            if want in types and comp.get("long_name") not in names:
                names.append(comp["long_name"])
    return names


def _call_geocode(params: dict) -> dict:
    key = _maps_key()
    if not key:
        return {"status": "error", "message": "Geocoding is not configured (MAPS_SERVER_KEY missing)."}
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(GEOCODE_URL, params={**params, "key": key})
            resp.raise_for_status()
            body = resp.json()
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "message": f"Could not reach the Geocoding API: {exc}"}

    if body.get("status") != "OK" or not body.get("results"):
        return {
            "status": "error",
            "message": f"Geocoding returned {body.get('status', 'no results')}.",
        }
    return {"status": "success", "results": body["results"]}


def get_photo_location(image_id: str) -> dict:
    """Read GPS coordinates from an uploaded photo's EXIF metadata.

    Try this before asking the user where they are. Many photos (especially
    from WhatsApp or a browser) have the EXIF stripped, so found=false is
    normal - fall back to the browser location in the user's message, or ask
    for an area name and use geocode_area.

    Args:
        image_id: Filename returned by the upload endpoint.

    Returns:
        dict with status "success" and either {found: true, lat, lng} or
        {found: false, reason}.
    """
    path = UPLOADS / Path(image_id).name
    if not path.exists():
        return {"status": "error", "message": f"No uploaded image named {path.name}."}

    try:
        from PIL import ExifTags, Image

        with Image.open(path) as img:
            exif = img.getexif()
            gps_ifd = exif.get_ifd(ExifTags.IFD.GPSInfo) if exif else None
    except Exception as exc:  # noqa: BLE001
        return {"status": "success", "found": False, "reason": f"Could not read EXIF: {exc}"}

    if not gps_ifd:
        return {"status": "success", "found": False, "reason": "The photo has no GPS metadata."}

    tags = {ExifTags.GPSTAGS.get(k, k): v for k, v in gps_ifd.items()}
    lat = geo.exif_to_decimal(tags.get("GPSLatitude"), tags.get("GPSLatitudeRef", "N"))
    lng = geo.exif_to_decimal(tags.get("GPSLongitude"), tags.get("GPSLongitudeRef", "E"))
    if lat is None or lng is None:
        return {"status": "success", "found": False, "reason": "GPS tags present but unreadable."}

    return {
        "status": "success",
        "found": True,
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "source": "exif",
    }


def geocode_area(area_text: str) -> dict:
    """Turn an Ahmedabad area or landmark name into coordinates.

    Use this when the photo has no GPS and the user types where they are,
    e.g. "Kankaria", "near Stadium Circle", "Bodakdev".

    Args:
        area_text: Area, road or landmark name as the user wrote it.

    Returns:
        dict with status "success" and keys lat, lng, formatted_address,
        localities (list of area names, most specific first). On failure:
        status "error" with a message.
    """
    store = get_store()
    query = area_text.strip()
    if not query:
        return {"status": "error", "message": "No area name given."}

    cache_key = "fwd:" + query.lower()
    if (hit := store.geocode_get(cache_key)) is not None:
        return {**hit, "cached": True}

    bounds = store.city["bounds"]
    bias = f"{bounds['sw'][0]},{bounds['sw'][1]}|{bounds['ne'][0]},{bounds['ne'][1]}"
    called = _call_geocode(
        {
            "address": f"{query}, Ahmedabad, Gujarat, India",
            "bounds": bias,
            "region": "in",
            "components": "country:IN|administrative_area:Gujarat",
        }
    )
    if called["status"] != "success":
        return called

    top = called["results"][0]
    loc = top["geometry"]["location"]
    out = {
        "status": "success",
        "lat": round(loc["lat"], 6),
        "lng": round(loc["lng"], 6),
        "formatted_address": top.get("formatted_address", ""),
        "localities": _localities(top),
        "source": "geocode",
    }
    store.geocode_put(cache_key, out)
    return out


def reverse_geocode(lat: float, lng: float) -> dict:
    """Turn coordinates into a street address and area names.

    Use this once you have coordinates, to get the address for the complaint
    and a locality hint for resolve_ward.

    Args:
        lat: Latitude in decimal degrees.
        lng: Longitude in decimal degrees.

    Returns:
        dict with status "success" and keys formatted_address, localities
        (list, most specific first), locality_hint (str). On failure:
        status "error" with a message.
    """
    store = get_store()
    cache_key = f"rev:{round(lat, 4)},{round(lng, 4)}"
    if (hit := store.geocode_get(cache_key)) is not None:
        return {**hit, "cached": True}

    called = _call_geocode({"latlng": f"{lat},{lng}", "region": "in"})
    if called["status"] != "success":
        return called

    top = called["results"][0]
    localities = _localities(top)
    # Widen the hint with localities from the other results - ward names often
    # only appear on a coarser result than the first (street-level) one.
    for extra in called["results"][1:4]:
        for name in _localities(extra):
            if name not in localities:
                localities.append(name)

    out = {
        "status": "success",
        "formatted_address": top.get("formatted_address", ""),
        "localities": localities,
        "locality_hint": ", ".join(localities[:3]),
        "source": "reverse_geocode",
    }
    store.geocode_put(cache_key, out)
    return out


def resolve_ward(lat: float, lng: float, locality_hint: str = "") -> dict:
    """Find which AMC ward a location belongs to.

    Matches the locality hint against known ward area names first (most
    accurate), then falls back to the nearest ward centroid. If the point is
    far outside Ahmedabad it returns an error asking for an area name.

    Args:
        lat: Latitude in decimal degrees.
        lng: Longitude in decimal degrees.
        locality_hint: Area names from reverse_geocode or geocode_area, e.g.
            "Navrangpura, Ahmedabad". Optional but improves accuracy.

    Returns:
        dict with status "success" and keys ward_id, ward_name, zone, method
        ("area_name_match" or "nearest_centroid"), distance_km. On failure:
        status "error" with need="area_name".
    """
    store = get_store()
    wards = store.wards

    if locality_hint:
        ward, score = geo.match_ward_by_name(wards, locality_hint)
        if ward and score >= 82:
            clat, clng = ward["centroid"]
            return {
                "status": "success",
                "ward_id": ward["id"],
                "ward_name": ward["name"],
                "zone": ward["zone"],
                "method": "area_name_match",
                "match_score": score,
                "distance_km": round(geo.haversine_m(lat, lng, clat, clng) / 1000, 2),
            }

    ward, km = geo.nearest_ward(wards, lat, lng)
    if ward and km <= geo.MAX_WARD_CENTROID_KM:
        return {
            "status": "success",
            "ward_id": ward["id"],
            "ward_name": ward["name"],
            "zone": ward["zone"],
            "method": "nearest_centroid",
            "distance_km": round(km, 2),
        }

    return {
        "status": "error",
        "need": "area_name",
        "message": "This location is outside the wards in the mock AMC dataset. "
        "Ask the user for a nearby Ahmedabad area or landmark name.",
    }
