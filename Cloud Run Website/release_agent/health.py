"""Startup self-check: verifies the configured Gemini model is reachable.

Single Responsibility: this module only answers "can we actually call the
model right now?" It exists because a misconfigured model/location used to
fail identically on every chat turn (looked like an infinite loop to the
user) instead of surfacing one clear, actionable message up front.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from google import genai
from google.genai import types

from release_agent.config import SETTINGS

logger = logging.getLogger(__name__)

_PROBE_PROMPT = "ping"
_PROBE_TIMEOUT_SECONDS = 10
_PROBE_CACHE_TTL_SECONDS = 300

_cached_result: ModelHealth | None = None
_cached_at: float = 0.0


@dataclass(frozen=True)
class ModelHealth:
    """Result of a one-time model reachability probe."""

    reachable: bool
    model: str
    location: str
    message: str


def _probe_model() -> ModelHealth:
    """Makes one minimal generateContent call to confirm the model responds."""
    try:
        client = genai.Client(
            vertexai=True,
            project=SETTINGS.project,
            location=SETTINGS.vertex_location,
        )
        client.models.generate_content(
            model=SETTINGS.model,
            contents=_PROBE_PROMPT,
            config=types.GenerateContentConfig(
                max_output_tokens=1,
                http_options=types.HttpOptions(timeout=_PROBE_TIMEOUT_SECONDS * 1000),
            ),
        )
        return ModelHealth(
            reachable=True,
            model=SETTINGS.model,
            location=SETTINGS.vertex_location,
            message="",
        )
    except Exception as exc:  # noqa: BLE001 - this IS the error-reporting path
        logger.warning("Model reachability probe failed: %s", exc)
        return ModelHealth(
            reachable=False,
            model=SETTINGS.model,
            location=SETTINGS.vertex_location,
            message=str(exc),
        )


def check_model_health(force: bool = False) -> ModelHealth:
    """Returns cached model reachability, probing at most once per TTL.

    Args:
        force: Bypasses the cache to re-probe immediately (e.g. a manual
            "retry" action in the UI).

    Returns:
        A ModelHealth describing whether SETTINGS.model is currently
        callable at SETTINGS.vertex_location.
    """
    global _cached_result, _cached_at
    now = time.monotonic()
    if (
        not force
        and _cached_result is not None
        and (now - _cached_at) < _PROBE_CACHE_TTL_SECONDS
    ):
        return _cached_result

    _cached_result = _probe_model()
    _cached_at = now
    return _cached_result
