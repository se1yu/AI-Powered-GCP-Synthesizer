"""Reusable Material 3 Expressive rendering helpers for Cloud Comms' pages.

Single Responsibility: this module only renders — it never fetches data
or holds state. Keeping presentation separate from app.py's orchestration
keeps both files small and independently testable.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from release_agent.theme import badge_class, severity_class

_GRAPHICS_DIR = Path(__file__).resolve().parent.parent / "graphics"
_LOGO_PATH = _GRAPHICS_DIR / "CloudComms_Logo.svg"
_ICON_PATH = _GRAPHICS_DIR / "CloudComms_Icon.svg"


@st.cache_resource
def _logo_data_uri() -> str:
    """Base64-encodes the team's CloudComms wordmark logo for inline embedding.

    Streamlit doesn't serve arbitrary repo files as static assets by default,
    so the SVG is inlined as a data URI rather than referenced by path.
    """
    encoded = base64.b64encode(_LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


@st.cache_resource
def _icon_data_uri() -> str:
    """Base64-encodes the CloudComms icon mark for inline embedding in raw HTML.

    Used by render_appbar's badge, which is hand-rolled HTML rather than a
    native st.image call, so it needs the same data-URI treatment as the
    wordmark logo above rather than Streamlit's built-in SVG-path support.
    """
    encoded = base64.b64encode(_ICON_PATH.read_bytes()).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


def render_appbar(title: str, subtitle: str, icon: str | None = None) -> None:
    """Renders the Cloud Comms M3 Expressive top app bar (icon badge + title).

    icon defaults to the CloudComms icon mark; pass a plain emoji string
    (e.g. "\U0001f4ca") to use that instead, for pages that want a
    different glyph than the brand icon.
    """
    icon_html = (
        f'<img src="{_icon_data_uri()}" alt="" style="width:100%;height:100%;object-fit:contain;" />'
        if icon is None
        else icon
    )
    st.markdown(
        f"""
        <div class="pulse-appbar">
            <div class="pulse-logo-badge">{icon_html}</div>
            <div>
                <h1>{title}</h1>
                <p>{subtitle}</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero_empty_state(title: str, subtitle: str) -> None:
    """Renders the CloudComms "hero moment" header: tagline, wordmark, caption.

    Mirrors the team's Figma mockup: a light tagline above the CloudComms
    wordmark logo, with the fuller description as a small caption below.
    Called on every render (not just the blank-slate state) so the brand
    logo persists at the top of the page throughout the conversation.
    """
    st.markdown(
        f"""
        <div class="pulse-hero">
            <p class="pulse-hero-subtext">{title}</p>
            <img class="pulse-hero-logo" src="{_logo_data_uri()}" alt="CloudComms logo" />
            <p class="pulse-hero-caption">{subtitle}</p>
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
