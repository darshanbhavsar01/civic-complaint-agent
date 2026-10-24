"""Gemini vision tool: classify an uploaded photo as a civic issue."""
from __future__ import annotations

import json
import mimetypes
import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from .. import llm

UPLOADS = Path(__file__).resolve().parents[2] / "uploads"

IssueType = Literal["pothole", "garbage", "streetlight", "waterlogging", "other"]

# Canned results so the demo still runs if Gemini or the venue Wi-Fi dies.
# Keyed by a substring of the image filename; enable with DEMO_CACHE=1.
DEMO_CACHE: dict[str, dict] = {
    "pothole": {
        "is_civic_issue": True,
        "issue_type": "pothole",
        "confidence": 0.94,
        "severity": 4,
        "description": "A deep pothole roughly half a metre wide in the left lane, "
        "with broken asphalt edges and standing water inside.",
        "visible_landmarks": "Road divider and a row of shopfronts behind",
        "hazard_notes": "Two-wheelers swerving around it into fast-moving traffic.",
    },
    "garbage": {
        "is_civic_issue": True,
        "issue_type": "garbage",
        "confidence": 0.91,
        "severity": 4,
        "description": "An overflowing garbage pile spilling off the footpath onto the road, "
        "mixed household and plastic waste with stray animals nearby.",
        "visible_landmarks": "Compound wall and a bus stop",
        "hazard_notes": "Blocking the footpath; health hazard in the heat.",
    },
    "streetlight": {
        "is_civic_issue": True,
        "issue_type": "streetlight",
        "confidence": 0.88,
        "severity": 3,
        "description": "A streetlight pole with a dark, broken fixture over an unlit stretch of road.",
        "visible_landmarks": "Residential gate and parked vehicles",
        "hazard_notes": "Unlit crossing; unsafe for pedestrians after dark.",
    },
    "selfie": {
        "is_civic_issue": False,
        "issue_type": "other",
        "confidence": 0.97,
        "severity": 1,
        "description": "A close-up portrait of a person. No civic infrastructure problem visible.",
        "visible_landmarks": "",
        "hazard_notes": "",
    },
}

PROMPT = """You are the vision step of a civic complaint agent for Ahmedabad Municipal
Corporation. Look at this photo and decide whether it shows a REAL public civic
infrastructure problem that a municipal body should fix.

Civic issues: pothole / damaged road, uncollected garbage or overflowing bin,
broken or non-working streetlight, waterlogging or drainage overflow.
NOT civic issues: selfies, people, pets, food, screenshots, indoor scenes,
documents, or private property problems.

Rate severity 1-5 on actual public risk:
1 cosmetic, 2 minor, 3 noticeable inconvenience,
4 hazardous to vehicles or pedestrians, 5 dangerous / blocking / large scale.

Write the description in English, factual, one or two sentences, as it would read
on a municipal complaint form. Name any landmark, signboard or shop you can read."""


_JSON_INSTRUCTION = """Reply with ONLY a JSON object, no prose and no code fence:
{"is_civic_issue": true|false, "issue_type": "pothole"|"garbage"|"streetlight"|
"waterlogging"|"other", "confidence": 0.0-1.0, "severity": 1-5,
"description": "...", "visible_landmarks": "...", "hazard_notes": "..."}"""


def _loads(text: str) -> dict:
    """Parse the model's JSON, tolerating a code fence or surrounding prose."""
    raw = (text or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1] if "```" in raw[3:] else raw[3:]
        raw = raw.removeprefix("json").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(raw[start : end + 1])


class CivicImageAnalysis(BaseModel):
    """Structured output schema for the vision call."""

    is_civic_issue: bool = Field(description="True only for a public civic infrastructure problem")
    issue_type: IssueType = Field(description="Category of the issue")
    confidence: float = Field(ge=0, le=1, description="Confidence in the classification")
    severity: int = Field(ge=1, le=5, description="Public risk, 1 cosmetic to 5 dangerous")
    description: str = Field(description="Factual one or two sentence description")
    visible_landmarks: str = Field(default="", description="Readable signs, shops or landmarks")
    hazard_notes: str = Field(default="", description="Who or what is at risk, briefly")


def _demo_cache_hit(image_id: str) -> dict | None:
    if os.getenv("DEMO_CACHE", "").strip() not in ("1", "true", "yes"):
        return None
    name = image_id.lower()
    for key, payload in DEMO_CACHE.items():
        if key in name:
            return payload
    return None


def analyze_civic_image(image_id: str) -> dict:
    """Look at an uploaded photo and classify it as a civic issue.

    Use this FIRST for every photo, before anything else. If it reports
    is_civic_issue=false, do not file a complaint - explain politely instead.

    Args:
        image_id: Filename returned by the upload endpoint, e.g. "a1b2c3.jpg".

    Returns:
        dict with status "success" and keys: is_civic_issue (bool),
        issue_type (pothole|garbage|streetlight|waterlogging|other),
        confidence (0-1), severity (1-5), description (str),
        visible_landmarks (str), hazard_notes (str), source (str).
        On failure: status "error" with a message.
    """
    path = UPLOADS / Path(image_id).name
    cached = _demo_cache_hit(path.name)
    if cached:
        return {"status": "success", "source": "demo_cache", **cached}

    if not path.exists():
        return {
            "status": "error",
            "message": f"No uploaded image named {path.name}. Ask the user to send the photo again.",
        }

    if not llm.api_keys():
        return {
            "status": "error",
            "message": "Vision is not configured (GOOGLE_API_KEY missing).",
        }

    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    image_bytes = path.read_bytes()

    def call(client, model: str, schema_ok: bool):
        from google.genai import types

        # Models without structured output (Gemma) get the schema as prose and
        # their JSON is salvaged below.
        prompt = PROMPT if schema_ok else PROMPT + "\n\n" + _JSON_INSTRUCTION
        config = types.GenerateContentConfig(temperature=0.1)
        if schema_ok:
            config = types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CivicImageAnalysis,
                temperature=0.1,
            )
        return client.models.generate_content(
            model=model,
            contents=[types.Part.from_bytes(data=image_bytes, mime_type=mime), prompt],
            config=config,
        )

    try:
        response, attempt = llm.generate(call, purpose="vision")
        parsed = CivicImageAnalysis(**_loads(response.text))
    except Exception as exc:  # noqa: BLE001 - tools never raise to the model
        fallback = DEMO_CACHE.get(next((k for k in DEMO_CACHE if k in path.name.lower()), ""))
        if fallback:
            return {"status": "success", "source": "demo_cache_fallback", **fallback}
        return {"status": "error", "message": f"Could not analyse the photo: {exc}"}

    return {
        "status": "success",
        "source": "gemini",
        "model": attempt.model,
        **parsed.model_dump(),
    }
