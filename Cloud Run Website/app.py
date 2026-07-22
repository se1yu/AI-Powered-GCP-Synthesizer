"""Cloud Comms — GCP Release & Service Health assistant for Google TAMs.

Run with: streamlit run app.py

Architecture: this file is the Streamlit orchestration layer only — it
never talks to BigQuery/HTTP directly (see release_agent/sources.py) and
never builds HTML for data (see release_agent/ui.py). See
docs/ARCHITECTURE.md for the full data-flow diagram.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from release_agent.agent import root_agent
from release_agent.config import RELEASE_TYPES, SETTINGS
from release_agent.feedback import record_feedback
from release_agent.health import check_model_health
from release_agent.sources import fetch_service_health
from release_agent.theme import GLOBAL_CSS
from release_agent.ui import (
    render_appbar,
    render_hero_empty_state,
    render_model_unavailable_banner,
    render_status_pill,
)

load_dotenv("release_agent/.env")

# Streamlit's page_icon/chat avatar both accept a local SVG file path
# natively (image_to_url inlines it as a data URI) — no manual base64
# needed here, unlike the hand-rolled HTML in ui.py's render_appbar badge.
_ASSISTANT_ICON = str(Path(__file__).resolve().parent / "graphics" / "CloudComms_Icon.svg")

_PRODUCT_OPTIONS = (
    "Cloud Run",
    "BigQuery",
    "Vertex AI",
    "GKE",
    "Cloud SQL",
    "Pub/Sub",
    "Cloud Storage",
    "Compute Engine",
    "Cloud Functions",
    "Apigee",
    "Looker",
    "Spanner",
)
_EXAMPLE_PROMPTS = (
    "What new features dropped in Vertex AI this week?",
    "Is BigQuery having any issues right now?",
    "Any breaking changes in Cloud Run recently?",
    "Give me a summary of everything that changed in the last 7 days",
    "What products had the most updates this month?",
)

st.set_page_config(
    page_title="Cloud Comms — GCP Release Assistant", page_icon=_ASSISTANT_ICON, layout="wide"
)
# st.html() sandboxes its content (Streamlit renders it in an isolated
# context, similar to an iframe), so CSS placed there can't reach anything
# outside itself — sidebar, buttons, chat input never saw GLOBAL_CSS.
# st.markdown+unsafe_allow_html renders in the main document instead, so
# the <style> block applies page-wide like a normal stylesheet.
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def _init_session_state() -> None:
    """Initializes chat/session state exactly once per browser session.

    Fixes the original app's races: the ADK Runner/session are created
    lazily on first use, and session_id is generated once up front rather
    than being recreated implicitly by other code paths.
    """
    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = str(uuid.uuid4())
    if "runner" not in st.session_state:
        session_service = InMemorySessionService()
        st.session_state["runner"] = Runner(
            agent=root_agent,
            app_name=SETTINGS.app_name,
            session_service=session_service,
        )
        st.session_state["_adk_session_ready"] = False


async def _ensure_adk_session() -> None:
    """Creates the backing ADK session once, idempotently, before first run."""
    if st.session_state.get("_adk_session_ready"):
        return
    runner: Runner = st.session_state["runner"]
    await runner.session_service.create_session(
        app_name=SETTINGS.app_name,
        user_id="tam-user",
        session_id=st.session_state["session_id"],
    )
    st.session_state["_adk_session_ready"] = True


async def _stream_agent_response(query: str):
    """Yields incremental text chunks from the ADK runner for st.write_stream.

    Streaming (rather than waiting for the full response) removes the long
    blank-spinner wait the original UI had and lets Cloud Comms' answer
    render progressively, matching modern chat UX expectations.

    Fail-fast principle applied defensively: any exception from the model
    or tool layer (auth, quota, unavailable model, network) is caught here
    so a single failed turn never crashes the whole page — it degrades to
    a clear, user-facing message instead.
    """
    await _ensure_adk_session()
    runner: Runner = st.session_state["runner"]
    content = types.Content(role="user", parts=[types.Part(text=query)])

    emitted = ""
    try:
        async for event in runner.run_async(
            user_id="tam-user",
            session_id=st.session_state["session_id"],
            new_message=content,
        ):
            if not (event.content and event.content.parts):
                continue
            text = "".join(part.text or "" for part in event.content.parts)
            if not text:
                continue
            new_chunk = text[len(emitted) :] if text.startswith(emitted) else text
            emitted = text
            if new_chunk:
                yield new_chunk
    except Exception as exc:  # noqa: BLE001 - surface a safe message, never a raw traceback
        logging.getLogger(__name__).exception("Cloud Comms agent turn failed")
        detail = str(exc)[:200]
        yield (
            "\u26a0\ufe0f Cloud Comms hit an error reaching the model or a data source. "
            f"Please try again in a moment, or rephrase your question.\n\n"
            f"`{detail}`"
        )
        return

    if not emitted:
        yield "I couldn't find an answer for that. Try rephrasing or broadening your question."


def _render_sidebar() -> str | None:
    """Renders the sidebar (filters, examples, live status, clear) and
    returns a prefill string if the user picked a quick action, else None.
    """
    prefill: str | None = None

    with st.sidebar:
        render_appbar("Cloud Comms", "GCP Release & Health Assistant")

        st.markdown("**Live status**")
        health = fetch_service_health(active_only=True)
        active_count = health.get("count", 0) if health.get("status") == "success" else 0
        render_status_pill(active_count)
        if health.get("status") == "error":
            st.caption("⚠️ Status feed unavailable right now.")

        st.divider()
        st.markdown("### Quick filters")
        product = st.selectbox("Product", ("",) + _PRODUCT_OPTIONS, index=0)
        note_type = st.selectbox("Update type", ("",) + RELEASE_TYPES, index=0)
        days = st.selectbox(
            "Time range",
            (7, 14, 30, 60, 90),
            index=2,
            format_func=lambda d: f"Last {d} days",
        )
        if st.button("Apply filters", use_container_width=True, icon="\U0001f50d"):
            parts = []
            if product:
                parts.append(f"for {product}")
            if note_type:
                parts.append(f"type {note_type}")
            parts.append(f"in the last {days} days")
            prefill = "Show me release notes " + " ".join(parts)

        st.divider()
        st.markdown("### Try asking")
        chosen = st.pills("Examples", _EXAMPLE_PROMPTS, label_visibility="collapsed")
        if chosen:
            prefill = chosen

        st.divider()
        st.page_link("pages/1_Digest.py", label="Weekly digest", icon="\U0001f4ca")

        st.divider()
        if st.button("Clear chat", use_container_width=True, icon="\U0001f5d1\ufe0f"):
            st.session_state["messages"] = []
            st.session_state["session_id"] = str(uuid.uuid4())
            st.session_state["_adk_session_ready"] = False
            st.rerun()

    return prefill


def _render_history() -> None:
    """Renders the CloudComms header, then prior chat turns (native st.chat_message).

    The header (tagline + wordmark logo + caption) renders unconditionally
    so the brand logo persists at the top of the page throughout the
    conversation, not just on the pristine, no-messages-yet state.
    """
    render_hero_empty_state(
        "Ask Comms about GCP release notes or live status",
        "Assistance on reliablly searching across every Google Cloud product",
    )

    if not st.session_state["messages"]:
        return

    for i, msg in enumerate(st.session_state["messages"]):
        avatar = "\U0001f9d1\u200d\U0001f4bb" if msg["role"] == "user" else _ASSISTANT_ICON
        with st.chat_message(msg["role"], avatar=avatar):
            st.markdown(msg["content"])
            if msg["role"] == "assistant":
                _render_feedback_row(i, msg)


def _render_feedback_row(index: int, msg: dict) -> None:
    """Renders a thumbs up/down feedback control under an assistant message."""
    feedback_key = f"feedback_{index}"
    rating = st.feedback("thumbs", key=feedback_key)
    if rating is not None and not msg.get("_feedback_sent"):
        # thumbs down -> 0, thumbs up -> 1 per st.feedback's contract; map to -1/1.
        score = 1 if rating == 1 else -1
        question = st.session_state["messages"][index - 1]["content"] if index > 0 else ""
        record_feedback(st.session_state["session_id"], question, msg["content"], score)
        st.session_state["messages"][index]["_feedback_sent"] = True


def _consume_deep_link_query() -> str | None:
    """Reads a `?q=` deep-link query param once, then clears it.

    Lets TAMs share a link like `?q=Any+breaking+changes+in+Cloud+Run`
    that pre-fills and auto-asks Cloud Comms a question.
    """
    query_value = st.query_params.get("q")
    if query_value:
        st.query_params.clear()
        return query_value
    return None


def main() -> None:
    """Entry point: renders the Cloud Comms chat page."""
    _init_session_state()
    prefill = _render_sidebar()
    deep_link_query = _consume_deep_link_query()

    render_appbar("Cloud Comms", "GCP Release Notes & Service Health, for Google TAMs")

    # Fail-fast, once: verify the configured model is actually reachable
    # before letting a TAM type a question into a broken chat. Previously
    # a bad model/location 404'd identically on every turn, which looked
    # like an infinite loop instead of one diagnosable error.
    model_health = check_model_health()
    if not model_health.reachable:
        render_model_unavailable_banner(
            model_health.model, model_health.location, model_health.message
        )

    _render_history()

    user_input = st.chat_input(
        "Ask about GCP updates, features, fixes, or live status...",
        disabled=not model_health.reachable,
    )
    query = user_input or deep_link_query or prefill

    if not query or not model_health.reachable:
        return

    st.session_state["messages"].append({"role": "user", "content": query})
    with st.chat_message("user", avatar="\U0001f9d1\u200d\U0001f4bb"):
        st.markdown(query)

    with (
        st.chat_message("assistant", avatar=_ASSISTANT_ICON),
        st.spinner("Checking release notes and live status..."),
    ):
        response = st.write_stream(_stream_agent_response(query))

    st.session_state["messages"].append({"role": "assistant", "content": response})
    st.rerun()


if __name__ == "__main__":
    main()
