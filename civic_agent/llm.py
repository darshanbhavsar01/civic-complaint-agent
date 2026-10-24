"""Key and model failover for the Gemini calls the agent makes directly.

Free-tier quota on AI Studio is per-key and per-model, so an exhausted quota is
the single most likely thing to break a live demo. Every direct Gemini call goes
through `generate()`, which walks a chain of (model, key) pairs and only gives up
once every combination has failed.

What counts as "try the next one":
  - 429 / RESOURCE_EXHAUSTED  -> this model+key pair is out of quota
  - 404 / NOT_FOUND           -> this key cannot see this model
  - 400 with a schema/mime complaint -> this model cannot do structured output
  - 500 / 503 / UNAVAILABLE   -> transient; the next pair is a fresh shot
Anything else (a malformed request, a bad image) is a real bug and is raised, so
it is not silently masked by a fallback.

Configure with env vars:
  GOOGLE_API_KEY         primary key (GEMINI_API_KEY also accepted)
  GOOGLE_API_KEY_BACKUP  backup key, used when the primary is exhausted
  GEMINI_MODEL           first model to try; prepended to the chain
  GEMINI_MODEL_FALLBACKS comma-separated chain, overriding DEFAULT_MODEL_CHAIN
"""
from __future__ import annotations

import os
import time
import threading
from dataclasses import dataclass
from typing import Any, Callable

# Ordered chain, measured against these keys on 2026-10-24 with a real
# image + response_schema call. Every entry answered correctly; the order is
# roughly fastest-and-most-accurate first.
#
#   gemini-3-flash-preview     4.1s   classified the test image best
#   gemini-2.5-flash           5.6s   the stable workhorse
#   gemini-3.1-flash-lite      5.1s
#   gemini-flash-lite-latest   2.4s   fastest of the lot
#   gemini-3.6-flash          11.5s
#   gemini-3.5-flash-lite     10.6s
#   gemini-flash-latest       16.3s   slowest, kept as a last resort
#
# Deliberately NOT in the chain, because they were measured as unusable:
#   gemini-3.8-flash      timed out past 90s, twice
#   gemini-3.7-flash      answered, but took 78s - worse than failing fast
#   gemini-3.5-flash      503 "experiencing high demand" on every attempt
#   gemini-2.5-flash-lite 404, "no longer available to new users"
#   gemma-4-31b-it,
#   gemma-4-26b-a4b-it    500 INTERNAL for every request, even text-only
#                         with no schema - listed by the API but not serving
DEFAULT_MODEL_CHAIN: list[str] = [
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-flash-latest",
]

# Models that reject response_schema / response_mime_type=application/json.
# Nothing in the default chain needs this, but it keeps the chain extensible:
# add a Gemma model via GEMINI_MODEL_FALLBACKS and the vision tool will ask for
# JSON in the prompt instead of through the schema.
NO_SCHEMA_MODELS: set[str] = {"gemma", "gemini-robotics"}

_RETRYABLE_MARKERS = (
    "resource_exhausted",
    "resource exhausted",
    "quota",
    "rate limit",
    "rate_limit",
    "too many requests",
    "429",
    "not_found",
    "not found",
    "404",
    "unavailable",
    "503",
    "500",
    "internal error",
    "overloaded",
    "deadline",
    "timeout",
    "timed out",
    "readtimeout",
    "connecterror",
    "connection reset",
    "api key not valid",
    "api_key_invalid",
    "permission_denied",
)

_SCHEMA_MARKERS = (
    "response_schema",
    "response_mime_type",
    "responseschema",
    "json mode",
    "json_mode",
    "structured output",
    "does not support",
)


def _env(name: str, *aliases: str) -> str:
    for key in (name, *aliases):
        value = (os.getenv(key) or "").strip()
        if value:
            return value
    return ""


def api_keys() -> list[str]:
    """Primary key first, then the backup, de-duplicated and blank-free."""
    found = [
        _env("GOOGLE_API_KEY", "GEMINI_API_KEY"),
        _env("GOOGLE_API_KEY_BACKUP", "GEMINI_API_KEY_BACKUP"),
    ]
    keys: list[str] = []
    for key in found:
        if key and not key.startswith("your_") and key not in keys:
            keys.append(key)
    return keys


def model_chain() -> list[str]:
    """The ordered model chain, with GEMINI_MODEL honoured as the first choice."""
    override = _env("GEMINI_MODEL_FALLBACKS")
    chain = (
        [m.strip() for m in override.split(",") if m.strip()]
        if override
        else list(DEFAULT_MODEL_CHAIN)
    )
    preferred = _env("GEMINI_MODEL")
    if preferred:
        chain = [preferred] + [m for m in chain if m != preferred]
    return chain


def supports_schema(model: str) -> bool:
    """Whether this model honours response_schema."""
    return not any(marker in model for marker in NO_SCHEMA_MODELS)


def is_retryable(exc: Exception) -> bool:
    """True when the failure is about this model+key pair, not about our request."""
    text = f"{type(exc).__name__} {exc}".lower()
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if status in (429, 404, 500, 503, 403):
        return True
    if any(marker in text for marker in _SCHEMA_MARKERS):
        return True
    return any(marker in text for marker in _RETRYABLE_MARKERS)


# A rung that just reported "out of quota" will almost certainly say so again on
# the next call, and walking fourteen dead rungs makes a degraded demo feel
# broken rather than slow. Park a failed rung briefly instead. Free-tier limits
# are largely per-minute, so a short parking time self-heals.
COOLDOWN_SECONDS = 60.0

_cooling: dict[tuple[str, str], float] = {}
_cooling_lock = threading.Lock()


def mark_unavailable(model: str, key_label: str) -> None:
    """Park a (model, key) rung for COOLDOWN_SECONDS."""
    with _cooling_lock:
        _cooling[(model, key_label)] = time.monotonic() + COOLDOWN_SECONDS


def is_cooling(model: str, key_label: str) -> bool:
    """Whether this rung is still parked from a recent failure."""
    with _cooling_lock:
        until = _cooling.get((model, key_label))
        if until is None:
            return False
        if time.monotonic() >= until:
            del _cooling[(model, key_label)]
            return False
        return True


def reset_cooldowns() -> None:
    """Clear all parked rungs. For tests, and for a manual retry."""
    with _cooling_lock:
        _cooling.clear()


@dataclass
class Attempt:
    """One rung of the chain, reported back so callers can log what was used."""

    model: str
    key_label: str
    schema: bool


class _Clients:
    """Caches one genai.Client per key; clients are cheap but not free."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Any:
        with self._lock:
            if key not in self._cache:
                from google import genai
                from google.genai import types

                self._cache[key] = genai.Client(
                    api_key=key,
                    http_options=types.HttpOptions(timeout=30_000),
                )
            return self._cache[key]


_clients = _Clients()

# Remember the pair that last worked and start there next time, so one exhausted
# model does not cost every later call a wasted round-trip.
_preferred: dict[str, Attempt] = {}
_preferred_lock = threading.Lock()


def _ordered_attempts(purpose: str) -> list[Attempt]:
    keys = api_keys()
    attempts: list[Attempt] = []
    # Model-major order: exhaust both keys on the best model before dropping to a
    # weaker one, since a stronger model matters more than which key pays for it.
    for model in model_chain():
        for index, key in enumerate(keys):
            label = ("primary", "backup")[index] if index < 2 else f"key{index + 1}"
            attempts.append(Attempt(model=model, key_label=label, schema=supports_schema(model)))

    with _preferred_lock:
        best = _preferred.get(purpose)
    if best:
        attempts.sort(key=lambda a: (a.model != best.model or a.key_label != best.key_label))
    return attempts


def _key_for(label: str) -> str:
    keys = api_keys()
    index = {"primary": 0, "backup": 1}.get(label)
    if index is None:
        index = int(label.removeprefix("key")) - 1
    return keys[index]


def generate(
    build_call: Callable[[Any, str, bool], Any],
    purpose: str = "default",
) -> tuple[Any, Attempt]:
    """Run a Gemini call against the first (model, key) pair that works.

    Args:
        build_call: Receives (client, model_name, schema_supported) and performs
            the actual generate_content call, returning its response. It is
            re-invoked per attempt, so it must not mutate shared state.
        purpose: Groups the "what worked last time" memory, e.g. "vision".

    Returns:
        (response, attempt) where attempt names the model and key that answered.

    Raises:
        RuntimeError: No usable API key is configured.
        Exception: The last error, once every pair has been tried, or immediately
            for a failure that is our fault rather than a quota or availability one.
    """
    keys = api_keys()
    if not keys:
        raise RuntimeError(
            "No Gemini API key configured. Set GOOGLE_API_KEY "
            "(and optionally GOOGLE_API_KEY_BACKUP) in .env."
        )

    attempts = _ordered_attempts(purpose)
    last_exc: Exception | None = None
    tried: list[str] = []

    # Parked rungs go to the back rather than being dropped, so a total outage
    # still retries everything instead of failing with nothing attempted.
    attempts.sort(key=lambda a: is_cooling(a.model, a.key_label))

    for attempt in attempts:
        try:
            client = _clients.get(_key_for(attempt.key_label))
        except Exception as exc:  # noqa: BLE001 - a bad key should not end the chain
            last_exc = exc
            continue

        try:
            response = build_call(client, attempt.model, attempt.schema)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            tried.append(f"{attempt.model}/{attempt.key_label}: {type(exc).__name__}")
            if not is_retryable(exc):
                print(f"[llm] {attempt.model} via {attempt.key_label} failed hard: {exc}")
                raise
            mark_unavailable(attempt.model, attempt.key_label)
            print(
                f"[llm] {attempt.model} via {attempt.key_label} unavailable "
                f"({str(exc)[:120]}); trying the next option"
            )
            continue

        with _preferred_lock:
            _preferred[purpose] = attempt
        if tried:
            print(f"[llm] {purpose}: fell back to {attempt.model} via {attempt.key_label}")
        return response, attempt

    raise RuntimeError(
        f"Every Gemini model and key failed for {purpose}. Tried: {'; '.join(tried)}"
    ) from last_exc
