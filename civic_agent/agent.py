"""Nagrik root agent: a single LlmAgent with civic complaint function tools."""
from __future__ import annotations

from google.adk.agents import LlmAgent

from .failover_llm import FailoverLlm
from .prompts import AGENT_INSTRUCTION
from .tools.location import geocode_area, get_photo_location, resolve_ward, reverse_geocode
from .tools.social import draft_social_post
from .tools.tickets import (
    check_duplicates,
    create_complaint,
    escalate_complaint,
    get_complaint_status,
    get_department,
)
from .tools.vision import analyze_civic_image

root_agent = LlmAgent(
    name="civic_agent",
    # Walks every (model, key) pair rather than pinning one model, so an
    # exhausted free-tier quota degrades instead of ending the demo.
    model=FailoverLlm(),
    description=(
        "Files civic complaints with the Ahmedabad Municipal Corporation from a photo: "
        "classifies the issue, locates it, resolves the ward and department, checks for "
        "duplicates, files a tracking ID and reports status."
    ),
    instruction=AGENT_INSTRUCTION,
    tools=[
        analyze_civic_image,
        get_photo_location,
        geocode_area,
        reverse_geocode,
        resolve_ward,
        get_department,
        check_duplicates,
        create_complaint,
        get_complaint_status,
        draft_social_post,
        escalate_complaint,
    ],
)
