"""Reusable Material 3 Expressive rendering helpers for Pulse's pages.

Single Responsibility: this module only renders — it never fetches data
or holds state. Keeping presentation separate from app.py's orchestration
keeps both files small and independently testable.
"""

from __future__ import annotations

import streamlit as st

from release_agent.theme import badge_class, severity_class


def render_appbar(title: str, subtitle: str, icon: str = "\U0001f4e1") -> None:
    """Renders the Pulse M3 Expressive top app bar (icon badge + title).

    Uses a native Unicode emoji rather than an icon web font: emoji render
    reliably offline/behind restrictive networks with zero external font
    request, avoiding the ligature-text-leak failure mode of web icon
    fonts when the font request is blocked or slow to load.
    """
    st.markdown(
        f"""
        <div class="pulse-appbar">
            <div class="pulse-logo-badge">{icon}</div>
            <div>
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero_empty_state(icon: str, title: str, subtitle: str) -> None:
    """Renders the M3 Expressive "hero moment" empty state for a fresh chat.

    Per M3 Expressive guidance: use 1-2 hero moments per product to make a
    stand-alone, editorial statement. The chat's blank-slate state is the
    natural hero moment for Pulse.
    """
    st.markdown(
        f"""
        <div class="pulse-hero">
            <div class="pulse-hero-icon">{icon}</div>
            <h2>{title}</h2>
            <p>{subtitle}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_empty_state(icon: str, title: str, subtitle: str) -> None:
    """Renders a compact centered empty/placeholder state (e.g. no results)."""
    st.markdown(
        f"""
        <div class="pulse-empty">
            <div class="pulse-empty-icon">{icon}</div>
            <div style="font-size:16px; margin-top:8px;">{title}</div>
            <div style="font-size:13px; margin-top:4px;">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_loading_wave() -> None:
    """Renders the M3 Expressive loading indicator (bouncing-dot wave)."""
    st.markdown(
        '<div class="pulse-loading-wave"><span></span><span></span><span></span></div>',
        unsafe_allow_html=True,
    )


def render_note_card(note: dict) -> None:
    """Renders a single deduplicated release note as an M3 card with a type chip."""
    chip = badge_class(note.get("type", ""))
    product = note.get("product", "Unknown")
    date = note.get("date", "")
    description = note.get("description", "").strip()
    st.markdown(
        f"""
        <div class="pulse-card">
            <span class="pulse-chip {chip}">{note.get("type", "")}</span>
            <strong>{product}</strong>
            <span style="opacity:0.6; font-size:12px;"> · {date}</span>
            <div style="margin-top:6px; font-size:14px; line-height:1.5;">{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_incident_banner(incidents: list[dict]) -> None:
    """Renders active GCP Service Health incidents as a compact banner list."""
    if not incidents:
        st.markdown(
            '<span class="pulse-chip pulse-status-ok">'
            '<span class="pulse-dot"></span> All monitored services normal</span>',
            unsafe_allow_html=True,
        )
        return

    for incident in incidents:
        sev_chip = severity_class(incident.get("severity", ""))
        products = ", ".join(incident.get("affected_products", [])) or "Unknown product"
        st.markdown(
            f"""
            <div class="pulse-card">
                <span class="pulse-chip {sev_chip}">{incident.get("severity", "unknown").upper()}</span>
                <strong>{products}</strong>
                <div style="margin-top:6px; font-size:13px;">{incident.get("description", "")}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_status_pill(active_incident_count: int) -> None:
    """Renders a compact live-status pill for the sidebar or header."""
    if active_incident_count == 0:
        st.markdown(
            '<span class="pulse-chip pulse-status-ok">'
            '<span class="pulse-dot"></span> All systems normal</span>',
            unsafe_allow_html=True,
        )
    else:
        label = "incident" if active_incident_count == 1 else "incidents"
        st.markdown(
            f'<span class="pulse-chip pulse-status-bad"><span class="pulse-dot">'
            f"</span> {active_incident_count} active {label}</span>",
            unsafe_allow_html=True,
        )


def render_model_unavailable_banner(model: str, location: str, detail: str) -> None:
    """Renders a single clear banner when the configured model can't be reached.

    Replaces the old failure mode where every chat turn silently 404'd
    identically (looked like an infinite loop) — now shown once, up front,
    with the actual reason so it's diagnosable at a glance.
    """
    st.error(
        f"⚠️ **Model unavailable**: `{model}` could not be reached at "
        f"location `{location}`. Chat is disabled until this is fixed.\n\n"
        f"Details: {detail[:300]}",
        icon="🚫",
    )
