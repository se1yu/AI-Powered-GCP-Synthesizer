"""Centralized configuration for the Pulse release agent.

Single source of truth for GCP resource identifiers, model name, and
tunables. A frozen dataclass enforces immutability-by-default; every value
can be overridden via environment variable for local/dev/prod parity.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

_DEFAULT_PROJECT = "sprinternship-aus-2026"
_DEFAULT_DATASET = "release_notes"
_DEFAULT_TABLE_NAME = "notes"
_DEFAULT_LOCATION = "US"
# gemini-3.6-flash is served on the GLOBAL Vertex AI endpoint only — regional
# endpoints (e.g. us-central1) 404 for this model. Verified live against
# sprinternship-aus-2026: global -> 200, us-central1 -> 404 NOT_FOUND.
_DEFAULT_VERTEX_LOCATION = "global"
_DEFAULT_MODEL = "gemini-3.6-flash"
_DEFAULT_STATUS_URL = "https://status.cloud.google.com/incidents.json"


_DEFAULT_STATUS_TTL_SECONDS = 300
_DEFAULT_APP_NAME = "pulse-release-agent"
_DEFAULT_SERVICE_ACCOUNT = (
    "aus-sprinternship-2026-sa@sprinternship-aus-2026.iam.gserviceaccount.com"
)

# Single source of truth for valid release note types — shared by the agent
# (tool docstrings/validation) and the UI (sidebar filter options) so they
# can never drift out of sync.
RELEASE_TYPES: tuple[str, ...] = (
    "FEATURE",
    "FIX",
    "DEPRECATION",
    "BREAKING_CHANGE",
    "ISSUE",
    "SERVICE_ANNOUNCEMENT",
)


@dataclass(frozen=True)
class Settings:
    """Immutable runtime configuration for Pulse.

    Attributes:
        project: GCP project ID hosting BigQuery + Vertex AI resources.
        dataset: BigQuery dataset containing release notes.
        table_name: BigQuery table containing release notes.
        location: BigQuery dataset location (must match the table's).
        vertex_location: Vertex AI region used to serve the Gemini model.
        model: Gemini model identifier used by the ADK agent.

        status_url: GCP Service Health incidents JSON feed.
        status_ttl_seconds: Cache TTL for the status feed.
        app_name: ADK application name used for session scoping.
        service_account: Runtime service account email (Cloud Run).
        vertex_engine_id: Vertex AI Search engine ID for semantic search.
            Empty string disables semantic search gracefully.
    """

    project: str = os.environ.get("PULSE_PROJECT", _DEFAULT_PROJECT)
    dataset: str = os.environ.get("PULSE_DATASET", _DEFAULT_DATASET)
    table_name: str = os.environ.get("PULSE_TABLE", _DEFAULT_TABLE_NAME)
    location: str = os.environ.get("PULSE_BQ_LOCATION", _DEFAULT_LOCATION)
    vertex_location: str = os.environ.get("GOOGLE_CLOUD_LOCATION", _DEFAULT_VERTEX_LOCATION)
    model: str = os.environ.get("PULSE_MODEL", _DEFAULT_MODEL)
    status_url: str = os.environ.get("PULSE_STATUS_URL", _DEFAULT_STATUS_URL)

    status_ttl_seconds: int = int(
        os.environ.get("PULSE_STATUS_TTL_SECONDS", _DEFAULT_STATUS_TTL_SECONDS)
    )
    app_name: str = os.environ.get("PULSE_APP_NAME", _DEFAULT_APP_NAME)
    service_account: str = os.environ.get("PULSE_SERVICE_ACCOUNT", _DEFAULT_SERVICE_ACCOUNT)
    vertex_engine_id: str = os.environ.get("PULSE_VERTEX_ENGINE_ID", "")

    @property
    def table_fqn(self) -> str:
        """Fully-qualified BigQuery table name, e.g. `project.dataset.table`."""
        return f"{self.project}.{self.dataset}.{self.table_name}"

    @property
    def feedback_table_fqn(self) -> str:
        """Fully-qualified BigQuery table name for feedback persistence."""
        return f"{self.project}.{self.dataset}.pulse_feedback"


SETTINGS = Settings()
