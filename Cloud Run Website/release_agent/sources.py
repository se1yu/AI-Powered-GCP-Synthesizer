"""Data access layer for Pulse: BigQuery release notes + GCP Service Health.

Single Responsibility: this module owns all I/O to external data sources.
The ADK agent (agent.py) and UI (ui/*) never talk to BigQuery or HTTP
directly — they call functions here. All queries are parameterized (no
string-built SQL from user input). All I/O failures degrade gracefully,
returning a typed error dict instead of raising, so a single failing
source never crashes the whole assistant.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import httpx
from google.cloud import bigquery

from release_agent.config import SETTINGS

logger = logging.getLogger(__name__)

_STATUS_REQUEST_TIMEOUT_SECONDS = 5.0
_MAX_DAYS_BACK = 365
_MAX_LIMIT = 50

_bq_client: bigquery.Client | None = None


def get_bigquery_client() -> bigquery.Client:
    """Lazily initializes and caches the BigQuery client (green coding: reuse)."""
    global _bq_client
    if _bq_client is None:
        _bq_client = bigquery.Client(project=SETTINGS.project, location=SETTINGS.location)
    return _bq_client


@dataclass(frozen=True)
class ReleaseNote:
    """A single, deduplicated GCP release note row."""

    note_key: str
    product: str
    type: str
    date: str
    description: str


def _rows_to_notes(rows) -> list[ReleaseNote]:
    """Maps raw BigQuery rows to typed, deduplication-ready notes."""
    return [
        ReleaseNote(
            note_key=getattr(row, "note_key", "") or "",
            product=row.product_name or "Unknown",
            type=(row.release_note_type or "").upper(),
            date=str(row.published_at),
            description=row.description or "",
        )
        for row in rows
    ]


def search_release_notes(
    product_name: str = "",
    release_type: str = "",
    days_back: int = 30,
    limit: int = 10,
) -> dict:
    """Searches release notes by product, type, and recency.

    Uses parameterized queries (no interpolation of user-supplied values
    into SQL) and deduplicates by note_key via QUALIFY, keeping the most
    recent row per key.

    Args:
        product_name: GCP product substring filter, case-insensitive.
        release_type: One of FEATURE/FIX/DEPRECATION/BREAKING_CHANGE/ISSUE/
            SERVICE_ANNOUNCEMENT. Leave empty for all types.
        days_back: How many days back to search (clamped to 365).
        limit: Max rows to return (clamped to 50).

    Returns:
        Dict with status, count, and notes (list of dicts), or status
        "error" with a message on failure.
    """
    days_back = max(1, min(int(days_back), _MAX_DAYS_BACK))
    limit = max(1, min(int(limit), _MAX_LIMIT))

    filters = ["published_at >= DATE_SUB(CURRENT_DATE(), INTERVAL @days_back DAY)"]
    params: list[bigquery.ScalarQueryParameter] = [
        bigquery.ScalarQueryParameter("days_back", "INT64", days_back)
    ]

    if product_name:
        filters.append("LOWER(product_name) LIKE LOWER(@product_pattern)")
        params.append(
            bigquery.ScalarQueryParameter("product_pattern", "STRING", f"%{product_name}%")
        )

    if release_type:
        filters.append("UPPER(release_note_type) = @release_type")
        params.append(
            bigquery.ScalarQueryParameter("release_type", "STRING", release_type.upper())
        )

    # nosec B608: no user input is interpolated here. `where` is built from
    # fixed clause templates (values passed via `params` below), `limit` is
    # an int clamped to _MAX_LIMIT, and table_fqn comes from server config.
    where = " AND ".join(filters)
    sql = f"""
        SELECT note_key, product_name, release_note_type, published_at,
               REGEXP_REPLACE(description, r'<[^>]+>', '') AS description
        FROM `{SETTINGS.table_fqn}`
        WHERE {where}
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY note_key ORDER BY published_at DESC
        ) = 1
        ORDER BY published_at DESC
        LIMIT {limit}
    """  # nosec B608

    try:
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        rows = list(get_bigquery_client().query(sql, job_config=job_config).result())
        notes = _rows_to_notes(rows)
        return {
            "status": "success",
            "count": len(notes),
            "notes": [note.__dict__ for note in notes],
            "message": "" if notes else "No release notes found for those filters.",
        }
    except Exception as exc:  # noqa: BLE001 - convert to typed error for the agent
        logger.exception("search_release_notes failed")
        return {"status": "error", "message": str(exc)}


def get_products_list() -> dict:
    """Returns all distinct GCP products present in the release notes table."""
    # nosec B608: table_fqn is server config, no user input in this query.
    sql = f"""
        SELECT DISTINCT product_name
        FROM `{SETTINGS.table_fqn}`
        WHERE product_name IS NOT NULL
        ORDER BY product_name
    """  # nosec B608

    try:
        rows = list(get_bigquery_client().query(sql).result())
        return {
            "status": "success",
            "products": [row.product_name for row in rows],
            "count": len(rows),
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_products_list failed")
        return {"status": "error", "message": str(exc)}


def get_recent_summary(days_back: int = 7) -> dict:
    """Summarizes deduplicated release note activity by product + type.

    Args:
        days_back: Number of days to summarize (clamped to 365).

    Returns:
        Dict with status and a summary list grouped by product/type.
    """
    days_back = max(1, min(int(days_back), _MAX_DAYS_BACK))
    # nosec B608: days_back is bound via @days_back parameter below;
    # table_fqn is server config. No user input is string-interpolated.
    sql = f"""
        WITH deduped AS (
            SELECT note_key, product_name, release_note_type, published_at
            FROM `{SETTINGS.table_fqn}`
            WHERE published_at >= DATE_SUB(CURRENT_DATE(), INTERVAL @days_back DAY)
              AND product_name IS NOT NULL
            QUALIFY ROW_NUMBER() OVER (
                PARTITION BY note_key ORDER BY published_at DESC
            ) = 1
        )
        SELECT product_name, release_note_type, COUNT(*) AS count,
               MAX(published_at) AS latest
        FROM deduped
        GROUP BY product_name, release_note_type
        ORDER BY count DESC
        LIMIT 50
    """  # nosec B608

    params = [bigquery.ScalarQueryParameter("days_back", "INT64", days_back)]
    try:
        job_config = bigquery.QueryJobConfig(query_parameters=params)
        rows = list(get_bigquery_client().query(sql, job_config=job_config).result())
        return {
            "status": "success",
            "days_back": days_back,
            "summary": [
                {
                    "product": row.product_name,
                    "type": row.release_note_type,
                    "count": row.count,
                    "latest": str(row.latest),
                }
                for row in rows
            ],
            "message": "" if rows else "No recent activity found.",
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("get_recent_summary failed")
        return {"status": "error", "message": str(exc)}


@dataclass(frozen=True)
class Incident:
    """A single GCP Service Health incident."""

    incident_id: str
    external_desc: str
    severity: str
    status_impact: str
    affected_products: tuple[str, ...]
    begin: str
    end: str | None

    @property
    def is_active(self) -> bool:
        """An incident with no end timestamp is still ongoing."""
        return self.end is None


def _parse_affected_products(raw_products: list | None) -> tuple[str, ...]:
    """Parses affected_products, a list of JSON-encoded strings, into titles."""
    titles: list[str] = []
    for entry in raw_products or []:
        try:
            parsed = json.loads(entry) if isinstance(entry, str) else entry
            title = parsed.get("title") if isinstance(parsed, dict) else None
            if title:
                titles.append(title)
        except (json.JSONDecodeError, AttributeError):
            continue
    return tuple(titles)


def fetch_service_health(active_only: bool = True) -> dict:
    """Fetches current GCP Service Health incidents.

    Graceful degradation: network or parse errors return status="error"
    rather than raising, so the agent can still answer from BigQuery data
    alone if the status feed is unreachable.

    Args:
        active_only: If True, only include incidents with no end time.

    Returns:
        Dict with status and a list of incident dicts.
    """
    try:
        response = httpx.get(SETTINGS.status_url, timeout=_STATUS_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        raw_incidents = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("fetch_service_health failed: %s", exc)
        return {"status": "error", "message": str(exc), "incidents": []}

    incidents = []
    for item in raw_incidents:
        end = item.get("end")
        if active_only and end is not None:
            continue
        incidents.append(
            Incident(
                incident_id=item.get("id", ""),
                external_desc=item.get("external_desc", ""),
                severity=item.get("severity", "unknown"),
                status_impact=item.get("status_impact", "unknown"),
                affected_products=_parse_affected_products(item.get("affected_products", [])),
                begin=item.get("begin", ""),
                end=end,
            )
        )

    return {
        "status": "success",
        "count": len(incidents),
        "incidents": [
            {
                "id": incident.incident_id,
                "description": incident.external_desc,
                "severity": incident.severity,
                "impact": incident.status_impact,
                "affected_products": list(incident.affected_products),
                "begin": incident.begin,
                "active": incident.is_active,
            }
            for incident in incidents
        ],
    }
