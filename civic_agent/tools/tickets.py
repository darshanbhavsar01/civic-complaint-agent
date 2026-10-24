"""Complaint lifecycle tools: department lookup, duplicates, filing, status, escalation."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from google.adk.tools import ToolContext

import geo
from store import get_store

STATUS_ORDER = ["Filed", "Assigned", "In Progress", "Resolved"]


def _state_set(tool_context: ToolContext | None, key: str, value: Any) -> None:
    if tool_context is not None:
        tool_context.state[key] = value


def _state_get(tool_context: ToolContext | None, key: str) -> Any:
    if tool_context is None:
        return None
    try:
        return tool_context.state.get(key)
    except Exception:  # noqa: BLE001
        return None


def _is_overdue(complaint: dict) -> bool:
    if complaint.get("status") == "Resolved":
        return False
    try:
        return geo.parse_iso(complaint["expectedBy"]) < geo.now_ist()
    except Exception:  # noqa: BLE001
        return False


def _overdue_days(complaint: dict) -> float:
    try:
        delta = geo.now_ist() - geo.parse_iso(complaint["expectedBy"])
        return round(delta.total_seconds() / 86400, 1)
    except Exception:  # noqa: BLE001
        return 0.0


def public_view(complaint: dict) -> dict:
    """Shape a stored complaint for the API and the UI."""
    return {
        **complaint,
        "is_overdue": _is_overdue(complaint),
        "overdue_days": _overdue_days(complaint) if _is_overdue(complaint) else 0.0,
    }


def get_department(issue_type: str) -> dict:
    """Find which AMC department handles an issue type, and its SLA.

    Args:
        issue_type: One of pothole, garbage, streetlight, waterlogging, other.

    Returns:
        dict with status "success" and keys department, sla_hours, x_handle.
        On failure: status "error" with a message.
    """
    store = get_store()
    dept = store.department(issue_type)
    if not dept:
        return {
            "status": "error",
            "message": f"No department mapped for issue type '{issue_type}'.",
        }
    return {
        "status": "success",
        "issue_type": issue_type,
        "department": dept["name"],
        "sla_hours": int(dept["sla_hours"]),
        "x_handle": dept.get("x_handle", ""),
    }


def check_duplicates(ward_id: str, issue_type: str, lat: float, lng: float) -> dict:
    """Check whether this issue is already reported nearby and still open.

    Call this before create_complaint. If a match is found, tell the user and
    then call create_complaint with duplicate_of set to the match's tracking
    ID - that adds them as a supporter and raises the priority instead of
    filing a second ticket.

    Args:
        ward_id: Ward from resolve_ward, e.g. "W12".
        issue_type: Issue category from analyze_civic_image.
        lat: Latitude of the new report.
        lng: Longitude of the new report.

    Returns:
        dict with status "success" and keys duplicate_found (bool), and when
        true: tracking_id, distance_m, status, supporters, filed_at, description.
    """
    store = get_store()
    best: dict | None = None
    best_m = geo.DUPLICATE_RADIUS_M

    for row in store.list_complaints(ward=ward_id):
        if row.get("issue") != issue_type or row.get("status") == "Resolved":
            continue
        if row.get("lat") is None or row.get("lng") is None:
            continue
        d = geo.haversine_m(lat, lng, float(row["lat"]), float(row["lng"]))
        if d <= best_m:
            best, best_m = row, d

    if not best:
        return {"status": "success", "duplicate_found": False, "radius_m": geo.DUPLICATE_RADIUS_M}

    return {
        "status": "success",
        "duplicate_found": True,
        "tracking_id": best["trackingId"],
        "distance_m": round(best_m),
        "complaint_status": best.get("status"),
        "supporters": int(best.get("supporters", 1)),
        "filed_at": best.get("filedAt"),
        "description": best.get("description", ""),
    }


def create_complaint(
    issue_type: str,
    ward_id: str,
    lat: float,
    lng: float,
    address: str,
    description: str,
    severity: int,
    image_id: str,
    tool_context: ToolContext,
    duplicate_of: str = "",
) -> dict:
    """File the complaint with the mock AMC system and return a tracking ID.

    This is the only way a tracking ID is ever created - never invent one.
    If check_duplicates found a match, pass its tracking ID as duplicate_of:
    the user is added as a supporter on the existing ticket and no new ticket
    is created.

    Args:
        issue_type: Issue category from analyze_civic_image.
        ward_id: Ward from resolve_ward.
        lat: Latitude in decimal degrees.
        lng: Longitude in decimal degrees.
        address: Street address from reverse_geocode or geocode_area.
        description: Factual description from analyze_civic_image.
        severity: 1-5 from analyze_civic_image.
        image_id: Uploaded photo filename.
        tool_context: Provided by the runtime; do not fill this in.
        duplicate_of: Tracking ID of an existing open complaint, or "".

    Returns:
        dict with status "success" and keys tracking_id, is_duplicate,
        complaint_status, department, ward_name, zone, priority, severity,
        supporters, expected_by, address, filed_at.
    """
    store = get_store()

    if duplicate_of:
        existing = store.get_complaint(duplicate_of.strip())
        if not existing:
            return {
                "status": "error",
                "message": f"No complaint {duplicate_of} to support. File a new one instead.",
            }
        existing["supporters"] = int(existing.get("supporters", 1)) + 1
        existing["priority"] = geo.priority_for(
            int(existing.get("severity", 3)), existing["supporters"]
        )
        existing.setdefault("history", []).append(
            {
                "status": existing.get("status", "Filed"),
                "at": geo.iso_ist(geo.now_ist()),
                "note": f"Supporter #{existing['supporters']} added via Nagrik agent; "
                f"priority {existing['priority']}",
            }
        )
        store.put_complaint(existing)
        _state_set(tool_context, "last_tracking_id", existing["trackingId"])
        ward = store.ward(existing.get("ward", "")) or {}
        return {
            "status": "success",
            "tracking_id": existing["trackingId"],
            "is_duplicate": True,
            "complaint_status": existing.get("status"),
            "department": existing.get("department"),
            "ward_id": existing.get("ward"),
            "ward_name": ward.get("name", ""),
            "zone": existing.get("zone"),
            "priority": existing["priority"],
            "severity": existing.get("severity"),
            "supporters": existing["supporters"],
            "expected_by": existing.get("expectedBy"),
            "address": existing.get("address", ""),
            "filed_at": existing.get("filedAt"),
        }

    dept = store.department(issue_type)
    if not dept:
        return {"status": "error", "message": f"No department mapped for '{issue_type}'."}
    ward = store.ward(ward_id)
    if not ward:
        return {"status": "error", "message": f"Unknown ward '{ward_id}'."}

    severity = max(1, min(5, int(severity)))
    filed_at = geo.now_ist()
    expected_by = filed_at + timedelta(hours=int(dept["sla_hours"]))
    tracking_id = store.next_tracking_id()

    complaint = {
        "trackingId": tracking_id,
        "ward": ward["id"],
        "zone": ward["zone"],
        "issue": issue_type,
        "department": dept["name"],
        "severity": severity,
        "priority": geo.priority_for(severity, 1),
        "description": description,
        "address": address,
        "lat": round(float(lat), 6),
        "lng": round(float(lng), 6),
        "imageId": image_id or None,
        "status": "Filed",
        "supporters": 1,
        "filedAt": geo.iso_ist(filed_at),
        "expectedBy": geo.iso_ist(expected_by),
        "history": [
            {
                "status": "Filed",
                "at": geo.iso_ist(filed_at),
                "note": "Filed via Nagrik agent",
            }
        ],
    }
    store.put_complaint(complaint)
    _state_set(tool_context, "last_tracking_id", tracking_id)

    return {
        "status": "success",
        "tracking_id": tracking_id,
        "is_duplicate": False,
        "complaint_status": "Filed",
        "department": dept["name"],
        "sla_hours": int(dept["sla_hours"]),
        "ward_id": ward["id"],
        "ward_name": ward["name"],
        "zone": ward["zone"],
        "priority": complaint["priority"],
        "severity": severity,
        "supporters": 1,
        "expected_by": complaint["expectedBy"],
        "address": address,
        "filed_at": complaint["filedAt"],
    }


def get_complaint_status(tool_context: ToolContext, tracking_id: str = "") -> dict:
    """Look up the current status and history of a filed complaint.

    Args:
        tool_context: Provided by the runtime; do not fill this in.
        tracking_id: Tracking ID like "AMC-2026-000124". Leave empty to use
            the complaint filed earlier in this conversation.

    Returns:
        dict with status "success" and keys tracking_id, complaint_status,
        issue, severity, priority, department, ward_name, zone, address,
        supporters, filed_at, expected_by, is_overdue, overdue_days, history
        (list of {status, at, note}).
    """
    store = get_store()
    tid = (tracking_id or "").strip() or (_state_get(tool_context, "last_tracking_id") or "")
    if not tid:
        return {
            "status": "error",
            "need": "tracking_id",
            "message": "No tracking ID yet in this conversation. Ask the user for theirs.",
        }

    complaint = store.get_complaint(tid)
    if not complaint:
        return {"status": "error", "message": f"No complaint found with ID {tid}."}

    ward = store.ward(complaint.get("ward", "")) or {}
    _state_set(tool_context, "last_tracking_id", complaint["trackingId"])
    return {
        "status": "success",
        "tracking_id": complaint["trackingId"],
        "complaint_status": complaint.get("status"),
        "issue": complaint.get("issue"),
        "severity": complaint.get("severity"),
        "priority": complaint.get("priority"),
        "department": complaint.get("department"),
        "ward_id": complaint.get("ward"),
        "ward_name": ward.get("name", ""),
        "zone": complaint.get("zone"),
        "address": complaint.get("address", ""),
        "supporters": int(complaint.get("supporters", 1)),
        "filed_at": complaint.get("filedAt"),
        "expected_by": complaint.get("expectedBy"),
        "is_overdue": _is_overdue(complaint),
        "overdue_days": _overdue_days(complaint) if _is_overdue(complaint) else 0.0,
        "history": complaint.get("history", []),
    }


def escalate_complaint(tracking_id: str, tool_context: ToolContext) -> dict:
    """Draft an escalation to the Zone Deputy Commissioner for an overdue complaint.

    Only works when the complaint is past its expected resolution date. Adds
    an Escalated event to the complaint history and returns a draft note. The
    note is a draft for the user - nothing is sent anywhere.

    Args:
        tracking_id: Tracking ID of the overdue complaint.
        tool_context: Provided by the runtime; do not fill this in.

    Returns:
        dict with status "success" and keys tracking_id, complaint_status,
        officer, overdue_days, escalation_note. If not overdue: status "error".
    """
    store = get_store()
    tid = (tracking_id or "").strip() or (_state_get(tool_context, "last_tracking_id") or "")
    complaint = store.get_complaint(tid) if tid else None
    if not complaint:
        return {"status": "error", "message": f"No complaint found with ID {tid or '(none)'}."}

    if not _is_overdue(complaint):
        return {
            "status": "error",
            "message": f"{complaint['trackingId']} is not overdue yet "
            f"(expected by {complaint.get('expectedBy')}). Nothing to escalate.",
        }

    days = _overdue_days(complaint)
    officer = store.zone_officers.get(
        complaint.get("zone", ""), "Deputy Commissioner (mock)"
    )
    note = (
        f"To: {officer}\n"
        f"Subject: Overdue civic complaint {complaint['trackingId']} - "
        f"{complaint.get('issue')} in {complaint.get('ward')}\n\n"
        f"Complaint {complaint['trackingId']} ({complaint.get('issue')}, severity "
        f"{complaint.get('severity')}) at {complaint.get('address')} was filed on "
        f"{str(complaint.get('filedAt', ''))[:10]} and assigned to "
        f"{complaint.get('department')}. The expected resolution date "
        f"({str(complaint.get('expectedBy', ''))[:10]}) passed {days} days ago and the "
        f"status is still '{complaint.get('status')}'. "
        f"{int(complaint.get('supporters', 1))} resident(s) have reported it.\n\n"
        f"Requesting your intervention to have the work scheduled this week."
    )

    complaint["status"] = "Escalated"
    complaint.setdefault("history", []).append(
        {
            "status": "Escalated",
            "at": geo.iso_ist(geo.now_ist()),
            "note": f"Escalated to {officer} - {days} days overdue",
        }
    )
    store.put_complaint(complaint)
    _state_set(tool_context, "last_tracking_id", complaint["trackingId"])

    return {
        "status": "success",
        "tracking_id": complaint["trackingId"],
        "complaint_status": "Escalated",
        "officer": officer,
        "overdue_days": days,
        "escalation_note": note,
    }
