"""Nagrik backend: ADK agent API + upload, officer and static routes in one container."""
from __future__ import annotations

import io
import os
import re
import secrets
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app
from pydantic import BaseModel

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")  # before tools read their keys

import geo  # noqa: E402
from civic_agent.tools.location import get_photo_location  # noqa: E402
from civic_agent.tools.tickets import STATUS_ORDER, public_view  # noqa: E402
from store import get_store  # noqa: E402

ROOT = Path(__file__).resolve().parent
UPLOADS = ROOT / "uploads"
STATIC = ROOT / "static"
UPLOADS.mkdir(exist_ok=True)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

# Formats Gemini accepts directly, mapped to the extension we store them under.
GEMINI_NATIVE = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "HEIF": ".heic"}


def _looks_like_heif(payload: bytes) -> bool:
    """Detect HEIC/HEIF by its ISO-BMFF brand, for when Pillow lacks the plugin."""
    if len(payload) < 16 or payload[4:8] != b"ftyp":
        return False
    return payload[8:12] in (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1")


def _normalise_image(payload: bytes, filename: str) -> tuple[bytes, str]:
    """Validate by content and return (bytes_to_store, extension).

    Converts anything Gemini cannot read natively into JPEG, preserving EXIF so
    GPS coordinates survive the conversion.
    """
    from PIL import Image

    try:
        with Image.open(io.BytesIO(payload)) as probe:
            fmt = (probe.format or "").upper()
            probe.load()
    except Exception:  # noqa: BLE001 - not a decodable image, or an unsupported codec
        if _looks_like_heif(payload):
            # Pillow has no HEIF plugin here, but Gemini reads HEIC directly.
            return payload, ".heic"
        shown = Path(filename).name or "that file"
        raise HTTPException(
            415,
            f"{shown} does not look like an image we can read. "
            "Send a JPEG, PNG, WEBP or HEIC photo.",
        ) from None

    if fmt in GEMINI_NATIVE:
        return payload, GEMINI_NATIVE[fmt]

    # e.g. BMP, GIF, TIFF, AVIF - decodable, but Gemini will not take them.
    try:
        with Image.open(io.BytesIO(payload)) as img:
            # getexif().tobytes() works across formats; info["exif"] is only
            # populated for some of them (TIFF notably leaves it empty), and
            # losing the GPS here would cost the user their location.
            try:
                exif = img.getexif().tobytes() or img.info.get("exif")
            except Exception:  # noqa: BLE001
                exif = img.info.get("exif")
            rgb = img.convert("RGB")
            out = io.BytesIO()
            rgb.save(out, "JPEG", quality=90, **({"exif": exif} if exif else {}))
        return out.getvalue(), ".jpg"
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(415, f"Could not convert that {fmt or 'image'} file: {exc}") from None

app = get_fast_api_app(
    agents_dir=str(ROOT),
    web=False,
    allow_origins=["*"],
    auto_create_session=True,
)


# --------------------------------------------------------------------------
# Citizen app: upload
# --------------------------------------------------------------------------
@app.post("/api/upload")
async def upload_image(file: UploadFile = File(...)) -> JSONResponse:
    """Store a photo and report whether it carries EXIF GPS.

    What the file is called is irrelevant - only its actual content decides.
    Windows/Chrome saves JPEGs as .jfif, phones produce .heic, and people hand
    you .bmp and .avif; rejecting those on the extension turns a working photo
    into a dead end. Anything Pillow can decode is accepted, and anything Gemini
    cannot read natively is converted to JPEG with its EXIF carried over.
    """
    payload = await file.read()
    if not payload:
        raise HTTPException(400, "That file was empty. Try taking the photo again.")
    if len(payload) > MAX_UPLOAD_BYTES:
        mb = len(payload) / (1024 * 1024)
        raise HTTPException(
            413, f"That photo is {mb:.0f} MB; the limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )

    stored, suffix = _normalise_image(payload, file.filename or "")

    # Keep a sanitised trace of the original name in the stored id. The random
    # prefix guarantees uniqueness; the kept stem is what DEMO_CACHE matches on,
    # so naming a demo photo "pothole.jpg" still works through the real upload.
    stem = re.sub(r"[^a-z0-9]+", "-", Path(file.filename or "photo").stem.lower()).strip("-")
    image_id = f"{secrets.token_hex(4)}-{stem[:32]}{suffix}" if stem else f"{secrets.token_hex(6)}{suffix}"
    (UPLOADS / image_id).write_bytes(stored)

    exif = get_photo_location(image_id)
    gps = (
        {"lat": exif["lat"], "lng": exif["lng"]}
        if exif.get("status") == "success" and exif.get("found")
        else None
    )
    return JSONResponse(
        {"image_id": image_id, "exif_gps": gps, "image_url": f"/uploads/{image_id}"}
    )


@app.get("/uploads/{image_id}")
async def serve_upload(image_id: str) -> FileResponse:
    """Serve a stored photo."""
    path = UPLOADS / Path(image_id).name
    if not path.exists():
        raise HTTPException(404, "No such image.")
    return FileResponse(path)


# --------------------------------------------------------------------------
# Officer console
# --------------------------------------------------------------------------
class StatusUpdate(BaseModel):
    status: str
    note: str = ""


@app.get("/api/complaints")
async def list_complaints(ward: str = "", status: str = "") -> dict[str, Any]:
    """Complaints for the officer console, newest first."""
    store = get_store()
    rows = [public_view(r) for r in store.list_complaints(ward=ward, status=status)]
    return {
        "complaints": rows,
        "wards": [
            {"id": w["id"], "name": w["name"], "zone": w["zone"]} for w in store.wards
        ],
        "statuses": [*STATUS_ORDER, "Escalated"],
        "overdue_count": sum(1 for r in rows if r["is_overdue"]),
    }


@app.get("/api/complaints/{tracking_id}")
async def get_complaint(tracking_id: str) -> dict[str, Any]:
    """One complaint, with overdue flags, for the slip and timeline."""
    complaint = get_store().get_complaint(tracking_id)
    if not complaint:
        raise HTTPException(404, f"No complaint {tracking_id}.")
    return public_view(complaint)


@app.post("/api/officer/{tracking_id}/status")
async def set_status(tracking_id: str, body: StatusUpdate) -> dict[str, Any]:
    """Move a complaint along the workflow and append a history event."""
    store = get_store()
    complaint = store.get_complaint(tracking_id)
    if not complaint:
        raise HTTPException(404, f"No complaint {tracking_id}.")

    new_status = body.status.strip()
    if new_status not in (*STATUS_ORDER, "Escalated"):
        raise HTTPException(400, f"Unknown status '{new_status}'.")

    complaint["status"] = new_status
    complaint.setdefault("history", []).append(
        {
            "status": new_status,
            "at": geo.iso_ist(geo.now_ist()),
            "note": body.note.strip() or f"Status set to {new_status} by ward officer (mock)",
        }
    )
    store.put_complaint(complaint)
    return public_view(complaint)


# --------------------------------------------------------------------------
# Config for the frontend + health
# --------------------------------------------------------------------------
@app.get("/api/config")
async def frontend_config() -> dict[str, Any]:
    """Keys and labels the static frontend needs. Only the referrer-restricted embed key."""
    store = get_store()
    return {
        "maps_embed_key": os.getenv("MAPS_EMBED_KEY", ""),
        "app_name": "civic_agent",
        "city": store.city["name"],
        "corporation": store.city["corporation"],
        "departments": {k: v["name"] for k, v in store.departments.items()},
        "demo_cache": os.getenv("DEMO_CACHE", "").strip() in ("1", "true", "yes"),
    }


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Liveness probe.

    Deliberately not `/healthz`: Cloud Run's front end reserves that exact path
    and answers it with its own 404 before the request reaches the container.
    ADK also exposes `/health`, which works both locally and on Cloud Run.
    """
    return {"status": "ok", "store": os.getenv("STORE", "json")}


# Mounted last so it never shadows the API routes above.
app.mount("/", StaticFiles(directory=str(STATIC), html=True), name="static")
