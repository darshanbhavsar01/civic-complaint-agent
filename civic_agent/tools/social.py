"""Social draft tool. Template-based and deterministic - drafts only, never posts."""
from __future__ import annotations

import os
from urllib.parse import quote

import geo
from store import get_store

ISSUE_LABEL = {
    "pothole": "Pothole",
    "garbage": "Uncollected garbage",
    "streetlight": "Broken streetlight",
    "waterlogging": "Waterlogging",
    "other": "Civic issue",
}


def _hashtag(name: str) -> str:
    return "#" + "".join(ch for ch in name.title() if ch.isalnum())


def _public_base() -> str:
    return (os.getenv("PUBLIC_BASE_URL", "") or "").rstrip("/")


def draft_social_post(tracking_id: str) -> dict:
    """Draft an X post and an Instagram caption for a filed complaint.

    These are drafts for the user to review. Nothing is posted anywhere -
    never tell the user it has been posted.

    Args:
        tracking_id: Tracking ID returned by create_complaint.

    Returns:
        dict with status "success" and keys x_text, x_chars, x_intent_url,
        instagram_text, hashtags (list), image_url. On failure: status "error".
    """
    store = get_store()
    complaint = store.get_complaint((tracking_id or "").strip())
    if not complaint:
        return {"status": "error", "message": f"No complaint found with ID {tracking_id}."}

    ward = store.ward(complaint.get("ward", "")) or {}
    ward_name = ward.get("name", complaint.get("ward", ""))
    dept = store.department(complaint.get("issue", "")) or {}
    city = store.city

    label = ISSUE_LABEL.get(complaint.get("issue", "other"), "Civic issue")
    area = (complaint.get("address") or ward_name).split(",")[0].strip()
    # "Pothole at Navrangpura, Navrangpura" reads badly - say the ward once.
    place = ward_name if area.lower() == ward_name.lower() else f"{area}, {ward_name}"
    severity = int(complaint.get("severity", 3))
    supporters = int(complaint.get("supporters", 1))
    handles = " ".join(h for h in (city.get("x_handle"), dept.get("x_handle")) if h)
    tags = [_hashtag(ward_name), "#AMC", "#Ahmedabad", _hashtag(complaint.get("issue", "civic"))]

    try:
        expected = geo.parse_iso(complaint["expectedBy"]).strftime("%d %b")
    except Exception:  # noqa: BLE001
        expected = ""

    x_lines = [
        f"{label} at {place} ({complaint.get('ward')}).",
        f"Severity {severity}/5. Filed with AMC: {complaint['trackingId']}"
        + (f", expected by {expected}." if expected else "."),
    ]
    if supporters > 1:
        x_lines.append(f"{supporters} residents have reported it.")
    x_lines.append(f"{handles} {' '.join(tags)}".strip())
    x_text = "\n".join(line for line in x_lines if line)

    # Trim from the middle lines if we exceed the X limit, keeping ID + handles.
    if len(x_text) > 280:
        x_text = "\n".join(
            [
                f"{label} at {place}. Severity {severity}/5.",
                f"AMC complaint {complaint['trackingId']}.",
                f"{handles} {' '.join(tags[:3])}".strip(),
            ]
        )[:280]

    ig_text = (
        f"{label} at {place} ({complaint.get('ward')}), Ahmedabad.\n\n"
        f"{complaint.get('description', '')}\n\n"
        f"Severity {severity}/5 - {complaint.get('priority', '')} priority. "
        f"Reported to {complaint.get('department', 'AMC')} through the AMC complaint system.\n"
        f"Tracking ID: {complaint['trackingId']}"
        + (f"\nExpected resolution: {expected}" if expected else "")
        + (f"\n{supporters} residents have reported this spot.\n" if supporters > 1 else "\n")
        + f"\nIf you pass this way, report it too.\n\n{' '.join(tags)} #CivicIssue #FixOurCity"
    )

    image_url = ""
    if complaint.get("imageId"):
        image_url = f"{_public_base()}/uploads/{complaint['imageId']}"

    return {
        "status": "success",
        "tracking_id": complaint["trackingId"],
        "x_text": x_text,
        "x_chars": len(x_text),
        "x_intent_url": "https://twitter.com/intent/tweet?text=" + quote(x_text),
        "instagram_text": ig_text,
        "hashtags": tags,
        "image_url": image_url,
        "note": "Draft only. Nagrik never posts on the user's behalf.",
    }
