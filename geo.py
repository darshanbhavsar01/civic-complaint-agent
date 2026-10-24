"""Geometry + ward resolution helpers. No network calls here."""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

from rapidfuzz import fuzz

IST = timezone(timedelta(hours=5, minutes=30))

DUPLICATE_RADIUS_M = 150.0
MAX_WARD_CENTROID_KM = 4.0


def now_ist() -> datetime:
    """Current time in Indian Standard Time."""
    return datetime.now(IST)


def iso_ist(dt: datetime) -> str:
    """Format a datetime as an IST ISO-8601 string."""
    return dt.astimezone(IST).isoformat(timespec="seconds")


def parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 string, assuming IST when no offset is present."""
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance between two WGS84 points, in metres."""
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _norm(text: str) -> str:
    """Lowercase, strip punctuation and common filler words for name matching."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(
        r"\b(road|rd|cross|char|rasta|circle|chowk|society|soc|nagar|area|ahmedabad|"
        r"gujarat|india|near|opp|opposite)\b",
        " ",
        text,
    )
    return re.sub(r"\s+", " ", text).strip()


def match_ward_by_name(wards: list[dict], locality_hint: str) -> tuple[dict | None, int]:
    """Best ward match for a locality string. Returns (ward, score 0-100)."""
    hint = _norm(locality_hint)
    if not hint:
        return None, 0
    best: dict | None = None
    best_score = 0
    for ward in wards:
        candidates = [ward["name"], *ward.get("areas", [])]
        for cand in candidates:
            c = _norm(cand)
            if not c:
                continue
            # substring hit is a strong signal ("stadium circle, navrangpura" -> "stadium")
            if c in hint or hint in c:
                score = 95
            else:
                score = int(max(fuzz.token_set_ratio(c, hint), fuzz.partial_ratio(c, hint)))
            if score > best_score:
                best, best_score = ward, score
    return best, best_score


def nearest_ward(wards: list[dict], lat: float, lng: float) -> tuple[dict | None, float]:
    """Nearest ward by centroid. Returns (ward, distance_km)."""
    best: dict | None = None
    best_m = float("inf")
    for ward in wards:
        clat, clng = ward["centroid"]
        d = haversine_m(lat, lng, clat, clng)
        if d < best_m:
            best, best_m = ward, d
    return best, best_m / 1000.0


def priority_for(severity: int, supporters: int = 1) -> str:
    """Map severity + supporter count onto a priority label.

    Extra supporters raise the priority: the second person to report a spot
    pushes it up one band, the fourth pushes it up another.
    """
    bump = 0
    if supporters >= 2:
        bump = 1
    if supporters >= 4:
        bump = 2
    score = int(severity) + bump
    if score >= 5:
        return "Critical"
    if score >= 4:
        return "High"
    if score >= 3:
        return "Medium"
    return "Low"


def exif_to_decimal(dms, ref: str) -> float | None:
    """Convert EXIF (degrees, minutes, seconds) + hemisphere ref to a signed float."""
    try:
        deg, minute, sec = (float(x) for x in dms)
    except (TypeError, ValueError):
        return None
    value = deg + minute / 60.0 + sec / 3600.0
    if str(ref).upper().strip() in ("S", "W"):
        value = -value
    return value
