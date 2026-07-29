"""Cloud Comms — GCP Release Notes & Service Health assistant for Google TAMs.

Run with: streamlit run app.py

Architecture: this file is the Streamlit orchestration layer only — it
never talks to BigQuery/HTTP directly (see release_agent/sources.py) and
never builds HTML for data (see release_agent/ui.py). See
docs/ARCHITECTURE.md for the full data-flow diagram.

Single-file, session-state-routed multipage UI: the sidebar has exactly
three destinations (Dashboard, Ask Comms, Weekly Digest) that swap the
main-content render function rather than relying on
Streamlit's native pages/ directory navigation, so the sidebar can stay a
fixed, minimal nav rail instead of an auto-generated page list.
"""

from __future__ import annotations

import html
import logging
import uuid
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from release_agent.agent import root_agent
from release_agent.config import RELEASE_TYPES, SETTINGS
from release_agent.feedback import record_feedback
from release_agent.health import check_model_health
from release_agent.history import load_chat_history, save_chat_message
from release_agent.sources import fetch_service_health, get_recent_summary
from release_agent.theme import GLOBAL_CSS
from release_agent.ui import (
    render_appbar,
    render_brand_mark,
    render_hero_empty_state,
    render_incident_banner,
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
_CUSTOMER_CATEGORIES = (
    "General",
    "Agriculture",
    "Media & Entertainment",
    "Technology",
    "Financial Services",
    "Healthcare & Life Sciences",
    "Retail & E-commerce",
    "Public Sector & Government",
    "Manufacturing",
    "Energy & Utilities",
    "Education",
)

_PAGES = ("Dashboard", "Ask Comms", "Weekly Digest")
_PAGE_SLUGS = {label.lower().replace(" ", "_"): label for label in _PAGES}

# Pins session_id to the browser across refreshes (st.session_state alone
# doesn't survive one) so chat history can be reloaded from BigQuery — see
# _set_session_cookie and release_agent/history.py.
_SESSION_COOKIE_NAME = "cc_session_id"
_SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365

st.set_page_config(
    page_title="Cloud Comms — GCP Release Assistant", page_icon=_ASSISTANT_ICON, layout="wide"
)
# st.html() sandboxes its content (Streamlit renders it in an isolated
# context, similar to an iframe), so CSS placed there can't reach anything
# outside itself — sidebar, buttons, chat input never saw GLOBAL_CSS.
# st.markdown+unsafe_allow_html renders in the main document instead, so
# the <style> block applies page-wide like a normal stylesheet.
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
# The pages/ directory would make Streamlit auto-render its own page list at
# the top of the sidebar. That nav would be redundant with — and visually
# clash with — the fixed Dashboard/Ask Comms/Weekly Digest rail below, so
# it's hidden; every page now lives in this file instead.
st.markdown(
    '<style>[data-testid="stSidebarNav"] {display: none;}</style>', unsafe_allow_html=True
)


def _set_session_cookie(session_id: str) -> None:
    """Pins `session_id` to a long-lived browser cookie.

    st.markdown can't execute injected <script> tags — Streamlit's
    unsafe_allow_html renders them via React's dangerouslySetInnerHTML,
    which never runs embedded scripts. st.components.v1.html renders into
    a real (same-origin) iframe instead, which does execute normal <script>
    content, so `document.cookie` set here actually takes effect.
    """
    st.components.v1.html(
        f"""<script>
        document.cookie = "{_SESSION_COOKIE_NAME}={session_id}; """
        f"""max-age={_SESSION_COOKIE_MAX_AGE_SECONDS}; path=/; samesite=lax";
        </script>""",
        height=0,
    )


def _init_session_state() -> None:
    """Initializes chat/session/page state exactly once per browser session.

    Fixes the original app's races: the ADK Runner/session are created
    lazily on first use, and session_id is generated once up front rather
    than being recreated implicitly by other code paths.

    session_id itself comes from a long-lived cookie rather than always
    being freshly generated: st.session_state resets on every page refresh
    (a new Streamlit session), so without the cookie there'd be no stable
    key to reload prior chat history under — every refresh would look like
    a brand-new TAM with no history, regardless of what's in BigQuery.
    """
    if "messages" not in st.session_state:
        cookie_session_id = st.context.cookies.get(_SESSION_COOKIE_NAME)
        if cookie_session_id:
            st.session_state["session_id"] = cookie_session_id
            st.session_state["messages"] = load_chat_history(cookie_session_id)
        else:
            st.session_state["session_id"] = str(uuid.uuid4())
            st.session_state["messages"] = []
            _set_session_cookie(st.session_state["session_id"])
    if "runner" not in st.session_state:
        session_service = InMemorySessionService()
        st.session_state["runner"] = Runner(
            agent=root_agent,
            app_name=SETTINGS.app_name,
            session_service=session_service,
        )
        st.session_state["_adk_session_ready"] = False
    if "page" not in st.session_state:
        st.session_state["page"] = "Dashboard"
    if "active_filters" not in st.session_state:
        st.session_state["active_filters"] = {}


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
            "⚠️ Cloud Comms hit an error reaching the model or a data source. "
            f"Please try again in a moment, or rephrase your question.\n\n"
            f"`{detail}`"
        )
        return

    if not emitted:
        yield "I couldn't find an answer for that. Try rephrasing or broadening your question."


def _render_sidebar() -> None:
    """Renders the fixed sidebar nav rail — exactly the 3 page tabs + New Chat.

    Each nav button switches `st.session_state["page"]` rather than linking
    to a separate Streamlit page, so the sidebar itself never changes shape.
    The active page's button gets a distinct CSS key (see theme.py) so it
    reads as selected, tonal rather than the solid brand-blue reserved for
    the "+ New Chat" call to action.
    """
    with st.sidebar:
        render_brand_mark(width_px=156, nav_href="?nav=ask_comms")

        with st.container(key="sidebar_nav"):
            current_page = st.session_state["page"]
            for label in _PAGES:
                slug = label.lower().replace(" ", "_")
                state = "active" if current_page == label else "inactive"
                if st.button(label, key=f"nav_{slug}_{state}", use_container_width=True):
                    st.session_state["page"] = label
                    st.rerun()

            st.write("")
            if st.button("+ New Chat", key="new_chat", use_container_width=True):
                new_session_id = str(uuid.uuid4())
                st.session_state["messages"] = []
                st.session_state["session_id"] = new_session_id
                st.session_state["_adk_session_ready"] = False
                st.session_state["page"] = "Ask Comms"
                # Rotates the cookie too — otherwise refreshing right after
                # "New Chat" would reload the conversation just cleared.
                _set_session_cookie(new_session_id)
                st.rerun()


def _render_dashboard() -> None:
    """Renders the landing page: logo, tagline, and a customer-category picker only.

    "General" sits first in the dropdown and is the default selection, so
    Cloud Comms gives generic recommendations until a TAM narrows it to a
    specific industry. Whatever is picked here persists in
    `st.session_state["dashboard_category"]` (via the widget's `key`) and is
    picked up as standing chat context by `_apply_active_filters` — this
    page has no free-text input, only this closed dropdown.
    """
    _, center, _ = st.columns([1, 2, 1])
    with center:
        render_hero_empty_state("Stay updated in the cloud!", "")
        st.selectbox(
            "Customer category",
            _CUSTOMER_CATEGORIES,
            index=0,
            label_visibility="collapsed",
            key="dashboard_category",
        )


def _render_weekly_digest() -> None:
    """Renders the Weekly Digest page: chart-backed release activity + live status."""
    render_appbar(
        "Weekly Digest",
        "Release activity + live status across Google Cloud",
    )

    days_back = st.segmented_control(
        "Window", [7, 14, 30], default=7, format_func=lambda d: f"{d}d"
    )
    days_back = days_back or 7

    summary = get_recent_summary(days_back=days_back)

    col_metrics, col_status = st.columns([2, 1])

    with col_metrics:
        if summary.get("status") != "success":
            st.error(f"Couldn't load the digest: {summary.get('message', 'unknown error')}")
        elif not summary.get("summary"):
            st.info("No release activity in this window.")
        else:
            rows = summary["summary"]
            total = sum(r["count"] for r in rows)
            products_touched = len({r["product"] for r in rows})

            m1, m2, m3 = st.columns(3)
            m1.metric("Total updates", total)
            m2.metric("Products touched", products_touched)
            m3.metric("Window", f"{days_back} days")

            df = pd.DataFrame(rows)
            st.markdown("#### By product")
            chart_df = (
                df.groupby("product")["count"]
                .sum()
                .sort_values(ascending=False)
                .head(15)
                .reset_index()
            )
            # st.bar_chart doesn't expose axis config, so this drops to Altair
            # directly to angle the product labels — with 15 product names,
            # horizontal labels overlap into an unreadable smear.
            chart = (
                alt.Chart(chart_df)
                .mark_bar(color="#0B57D0")
                .encode(
                    x=alt.X("product", sort="-y", title=None, axis=alt.Axis(labelAngle=-45)),
                    y=alt.Y("count", title=None),
                )
            )
            st.altair_chart(chart, use_container_width=True)

            st.markdown("#### Breakdown")
            st.dataframe(
                df.rename(
                    columns={
                        "product": "Product",
                        "type": "Type",
                        "count": "Count",
                        "latest": "Most recent",
                        "source_url": "Source",
                    }
                ),
                use_container_width=True,
                hide_index=True,
                column_config={"Source": st.column_config.LinkColumn()},
            )

            csv_bytes = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Export CSV",
                data=csv_bytes,
                file_name=f"cloudcomms_digest_{days_back}d.csv",
                mime="text/csv",
                icon="\U0001f4e5",
            )

    with col_status:
        st.markdown("#### Live status")
        health = fetch_service_health(active_only=True)
        if health.get("status") == "error":
            st.warning("Status feed unavailable right now.")
        else:
            render_incident_banner(health.get("incidents", []))


def _render_user_message(text: str) -> None:
    """Renders the TAM's own chat turn as plain text — no avatar/icon at all.

    st.chat_message always shows some avatar for name "user" (a default
    icon, or the first letter of the name if you swap it), so there's no
    supported way to get a blank one from that widget. This bypasses it
    entirely for the user's own turns; the assistant keeps its avatar via
    st.chat_message as before. Content is HTML-escaped since it renders
    through unsafe_allow_html.
    """
    st.markdown(
        f'<div class="pulse-user-message">{html.escape(text)}</div>',
        unsafe_allow_html=True,
    )


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


def _consume_nav_query() -> None:
    """Reads a `?nav=<slug>` param (e.g. from the clickable sidebar logo) once.

    Same mechanism as `_consume_deep_link_query`'s `?q=` — a plain link
    click triggers a normal page load with this query param set, which gets
    translated into a page switch here and then cleared.
    """
    nav_value = st.query_params.get("nav")
    if nav_value in _PAGE_SLUGS:
        st.session_state["page"] = _PAGE_SLUGS[nav_value]
        st.query_params.clear()


def _render_ask_comms_filters() -> None:
    """Renders the collapsed filters/live-status panel.

    "Apply filters" only writes the selection into
    `st.session_state["active_filters"]` — it never builds or submits a chat
    query itself. The filters are picked up (see `_apply_active_filters`)
    whenever the TAM actually types a question, so they act as standing
    context rather than one-off canned questions.
    """
    with st.expander("Filters & live status"):
        st.markdown("**Live status**")
        health = fetch_service_health(active_only=True)
        active_count = health.get("count", 0) if health.get("status") == "success" else 0
        render_status_pill(active_count)
        if health.get("status") == "error":
            st.caption("⚠️ Status feed unavailable right now.")

        st.divider()
        st.markdown("### Quick filters")
        product = st.selectbox("Product", ("",) + _PRODUCT_OPTIONS, index=0, key="filter_product")
        note_type = st.selectbox(
            "Update type", ("",) + RELEASE_TYPES, index=0, key="filter_note_type"
        )
        days = st.selectbox(
            "Time range",
            (7, 14, 30, 60, 90),
            index=2,
            format_func=lambda d: f"Last {d} days",
            key="filter_days",
        )
        if st.button("Apply filters", icon="\U0001f50d"):
            st.session_state["active_filters"] = {
                "product": product,
                "note_type": note_type,
                "days": days,
            }

        active = st.session_state["active_filters"]
        if active:
            summary_bits = []
            if active.get("product"):
                summary_bits.append(active["product"])
            if active.get("note_type"):
                summary_bits.append(active["note_type"])
            if active.get("days"):
                summary_bits.append(f"last {active['days']}d")
            st.caption(
                "Active filters (applied to your next questions): "
                + (", ".join(summary_bits) if summary_bits else "none")
            )
            if st.button("Clear filters"):
                st.session_state["active_filters"] = {}
                st.rerun()


def _apply_active_filters(query: str) -> str:
    """Silently appends standing filter + customer-category context to the model's input.

    The TAM's visible chat message stays exactly what they typed — this
    extra context is only added to what's actually sent to the agent, so a
    filter (or the Dashboard's customer-category dropdown) tailors the
    answer without pretending the TAM asked for it.
    """
    active = st.session_state.get("active_filters") or {}
    constraints = []
    if active.get("product"):
        constraints.append(f"product = {active['product']}")
    if active.get("note_type"):
        constraints.append(f"update type = {active['note_type']}")
    if active.get("days"):
        constraints.append(f"within the last {active['days']} days")

    notes = []
    if constraints:
        notes.append(
            "Standing TAM filters to consider for this answer, if relevant: "
            + "; ".join(constraints)
            + "."
        )

    category = st.session_state.get("dashboard_category")
    if category and category != "General":
        notes.append(
            f"The TAM's customer is in the {category} industry — where "
            "relevant, briefly tie the answer to why it matters for that "
            "kind of customer."
        )

    if not notes:
        return query

    return f"{query}\n\n(" + " ".join(notes) + ")"


def _render_ask_comms() -> None:
    """Renders the Cloud Comms chat page: filters, history, suggestions, and input.

    Only mounted when the user is on the "Ask Comms" page — the ADK runner
    is created lazily in `_init_session_state`, but no model call or health
    check happens unless this function actually runs.
    """
    _render_ask_comms_filters()
    deep_link_query = _consume_deep_link_query()

    # check_model_health() makes a real network call to Vertex AI on its
    # first probe each 5-minute cache window (see health.py) — without this
    # spinner, that pause looked exactly like the page being stuck showing
    # only the filters expander above, since nothing below this line has
    # rendered yet while the script is blocked here.
    with st.spinner("Checking Cloud Comms availability..."):
        model_health = check_model_health()
    if not model_health.reachable:
        render_model_unavailable_banner(
            model_health.model, model_health.location, model_health.message
        )

    render_hero_empty_state(
        "Ask Comms about GCP release notes or live status",
        "Assistance on reliablly searching across every Google Cloud product",
    )

    for i, msg in enumerate(st.session_state["messages"]):
        if msg["role"] == "user":
            _render_user_message(msg["content"])
            continue
        with st.chat_message("assistant", avatar=_ASSISTANT_ICON):
            st.markdown(msg["content"])
            _render_feedback_row(i, msg)

    suggestion = None
    if not st.session_state["messages"]:
        st.markdown("**Suggestions on what to ask our AI**")
        suggestion = st.pills("Examples", _EXAMPLE_PROMPTS, label_visibility="collapsed")

    user_input = st.chat_input(
        "Ask about GCP updates, features, fixes, or live status...",
        disabled=not model_health.reachable,
    )
    query = user_input or deep_link_query or suggestion

    if not query or not model_health.reachable:
        return

    st.session_state["messages"].append({"role": "user", "content": query})
    _render_user_message(query)
    save_chat_message(st.session_state["session_id"], "user", query)

    model_query = _apply_active_filters(query)

    with (
        st.chat_message("assistant", avatar=_ASSISTANT_ICON),
        st.spinner("Checking release notes and live status..."),
    ):
        response = st.write_stream(_stream_agent_response(model_query))

    st.session_state["messages"].append({"role": "assistant", "content": response})
    save_chat_message(st.session_state["session_id"], "assistant", response)
    st.rerun()


def main() -> None:
    """Entry point: routes between Dashboard, Ask Comms, Weekly Digest."""
    _init_session_state()
    _consume_nav_query()
    _render_sidebar()

    page = st.session_state["page"]
    if page == "Dashboard":
        _render_dashboard()
    elif page == "Ask Comms":
        _render_ask_comms()
    else:
        _render_weekly_digest()


if __name__ == "__main__":
    main()
