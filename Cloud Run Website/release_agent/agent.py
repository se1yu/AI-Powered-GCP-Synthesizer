"""Pulse: the GCP Release & Service Health agent for Google TAMs.

This module wires the ADK Agent to the data-access layer in sources.py
(Single Responsibility: agent.py owns persona + orchestration only, never
raw I/O). Pulse blends three signal types when answering:
  1. Structured RAG — parameterized BigQuery lookups over release notes.
  2. Semantic RAG — Vertex AI Search over the same corpus (fuzzy queries).
  3. Live signal — GCP Service Health incidents (is something down *now*).
"""

from __future__ import annotations

from datetime import UTC, datetime

from google.adk.agents.llm_agent import Agent
from google.cloud import discoveryengine_v1 as discoveryengine

from release_agent.config import RELEASE_TYPES, SETTINGS
from release_agent.sources import (
    fetch_service_health,
    get_products_list,
    get_recent_summary,
    search_release_notes,
)


def get_service_health(active_only: bool = True) -> dict:
    """Checks current GCP Service Health incidents.

    Use this when a TAM asks whether a product is currently having issues,
    is down, or is experiencing an outage/disruption — this is live signal,
    separate from the historical release notes dataset.

    Args:
        active_only: If True (default), only return ongoing incidents.
            Set False to include recently resolved incidents too.

    Returns:
        A dict with a list of incidents, each with severity, impact,
        affected products, and whether it is still active.
    """
    return fetch_service_health(active_only=active_only)


def search_release_notes_semantic(query: str, num_results: int = 5) -> dict:
    """Semantic search over GCP release notes using Vertex AI Search.

    Use this for fuzzy or conceptual questions like "what security changes
    happened recently" or "anything affecting networking in Cloud Run"
    that don't map cleanly to a single product/type filter.

    Args:
        query: Natural language search query from the TAM.
        num_results: Number of results to return. Default 5.

    Returns:
        A dict with semantically matched release notes, or a graceful
        "unavailable" status if semantic search isn't configured.
    """
    if not SETTINGS.vertex_engine_id:
        return {
            "status": "unavailable",
            "message": (
                "Semantic search isn't configured. Falling back to structured "
                "search_release_notes is recommended."
            ),
        }

    try:
        client = discoveryengine.SearchServiceClient()
        serving_config = (
            f"projects/{SETTINGS.project}/locations/global"
            "/collections/default_collection"
            f"/engines/{SETTINGS.vertex_engine_id}"
            "/servingConfigs/default_config"
        )
        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            page_size=num_results,
        )
        response = client.search(request)

        results = []
        for result in response.results:
            doc = result.document.derived_struct_data
            results.append(
                {
                    "product": doc.get("product_name", ""),
                    "type": doc.get("release_note_type", ""),
                    "date": str(doc.get("published_at", "")),
                    "description": doc.get("description", ""),
                }
            )

        return {
            "status": "success",
            "query": query,
            "count": len(results),
            "results": results,
        }
    except Exception as exc:  # noqa: BLE001 - graceful fallback for the agent
        return {"status": "error", "message": str(exc)}


_TODAY = datetime.now(UTC).strftime("%Y-%m-%d")

_INSTRUCTION = f"""
You are Pulse, the GCP Release & Service Health assistant built for Google
Technical Account Managers (TAMs). You help TAMs stay ahead of what's
changing across Google Cloud — and whether anything is broken right now —
without digging through release note pages themselves.

Today's date: {_TODAY}

## Tools and when to use them
- search_release_notes: structured lookup by product / type / days_back.
  Use this first for concrete questions ("what changed in Cloud Run").
- search_release_notes_semantic: fuzzy/conceptual questions that don't map
  to a single product or type ("anything about networking security").
  If it returns status "unavailable", fall back to search_release_notes.
- get_recent_summary: weekly/recent digest across all products.
- get_products_list: when a TAM asks what products are covered.
- get_service_health: live GCP Service Health — use whenever a TAM asks if
  something is "down", "having issues", or "experiencing an outage" RIGHT
  NOW. This is a different signal than release notes (historical changes
  vs. live incidents) — do not conflate them, but do mention both when
  relevant (e.g. a product changed recently AND currently has an incident).

## Rules
- Always call a tool before answering about GCP data. Never invent release
  notes, dates, or incidents.
- Valid release_type values: {", ".join(RELEASE_TYPES)}.

- Never show raw internal identifiers (note_key, incident id) to the user.
- Strip HTML from descriptions.
- If a tool returns zero results or an error, say so plainly and suggest a
  broader search — never fabricate a substitute answer.
- Be concise. TAMs are busy. Lead with the most action-worthy item
  (breaking changes and active incidents first), then group the rest by
  product using clear markdown: short headers, bullet lists, **bold** for
  product names and severities. No walls of text.
- If asked something general about GCP that isn't in your data, answer
  from general knowledge but say clearly it's not from the release notes
  dataset or live status feed.

## Example questions you can answer
- "What new features dropped in Vertex AI this week?"
- "Is BigQuery having any issues right now?"
- "Any breaking changes in Cloud Run recently?"
- "Give me a summary of everything that changed in the last 7 days"
- "What GCP products had the most updates this month?"
"""

root_agent = Agent(
    model=SETTINGS.model,
    name="pulse_agent",
    description="Pulse — GCP Release Notes & Service Health assistant for Google TAMs.",
    instruction=_INSTRUCTION,
    tools=[
        search_release_notes,
        search_release_notes_semantic,
        get_products_list,
        get_recent_summary,
        get_service_health,
    ],
)
