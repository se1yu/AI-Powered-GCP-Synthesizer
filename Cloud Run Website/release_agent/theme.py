"""Material 3 Expressive design system for Cloud Comms.

All tokens below are sourced from Google's live M3 specification (pulled
via Firecrawl MCP, July 2026): m3.material.io/styles/{color,elevation,
motion,shape,spacing,typography}. This is the single source of design
truth — every page imports GLOBAL_CSS and the helper functions here
instead of writing its own CSS (DRY).

Axes implemented, per M3 Expressive:
  - Color: full dynamic role set, Google-blue baseline, light + dark, WCAG AA.
  - Typography: Roboto/Google Sans type scale with emphasized weights.
  - Shape: variable corner-radius scale (xs..xl, full) for expressive tension.
  - Elevation: tonal surface-container levels, shadows reserved for
    hover/FAB/overlay only (M3 replaces default shadow stacking with tone).
  - Spacing: 4dp base grid.
  - Motion: spring-style easing (spatial + effects springs approximated via
    cubic-bezier overshoot, since CSS has no native spring physics).
  - Icons: native Unicode emoji (zero external font dependency, never
    fails to render or shows as raw ligature text if a font is blocked).
"""

from __future__ import annotations

_RELEASE_TYPE_CLASSES = (
    "FEATURE",
    "FIX",
    "DEPRECATION",
    "BREAKING_CHANGE",
    "ISSUE",
    "SERVICE_ANNOUNCEMENT",
)
_SEVERITY_CLASSES = ("HIGH", "MEDIUM", "LOW")
_DEFAULT_CLASS = "DEFAULT"


def badge_class(release_type: str) -> str:
    """Returns the CSS class for a release-note-type chip, e.g. 'pulse-badge-FIX'."""
    key = (
        release_type.upper()
        if release_type.upper() in _RELEASE_TYPE_CLASSES
        else _DEFAULT_CLASS
    )
    return f"pulse-badge-{key}"


def severity_class(severity: str) -> str:
    """Returns the CSS class for an incident-severity chip, e.g. 'pulse-sev-HIGH'."""
    key = severity.upper() if severity.upper() in _SEVERITY_CLASSES else _DEFAULT_CLASS
    return f"pulse-sev-{key}"


# ── Global CSS: M3 Expressive tokens + components ──────────────────────────
# The ONLY unsafe_allow_html in the app — scoped to visual polish only.
# Chat text itself always renders through native st.markdown/st.chat_message.
GLOBAL_CSS = """<style>
  /* IMPORTANT: never write the literal closing-style-tag text anywhere
     in this string (including comments) - the HTML tokenizer treats
     style as raw text and ends the block at the first such occurrence,
     which leaks the remaining CSS as visible page text. Fonts are
     loaded via @import (not a <link> tag) to keep this single block.
     Icons intentionally use native Unicode emoji, not a web icon font:
     emoji render with zero external requests and never fail/flash. */
  @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600;700&family=Roboto:wght@400;500;700&display=swap');
  :root {



    /* ── M3 color roles — light ─────────────────────────────────────── */
    --pulse-primary: #0B57D0;
    --pulse-on-primary: #FFFFFF;
    --pulse-primary-container: #D3E3FD;
    --pulse-on-primary-container: #041E49;
    --pulse-secondary: #565F71;
    --pulse-secondary-container: #DAE2F9;
    --pulse-tertiary: #00639B;
    --pulse-tertiary-container: #C2E7FF;
    --pulse-on-tertiary-container: #001D33;
    --pulse-error: #B3261E;
    --pulse-error-container: #F9DEDC;
    --pulse-success: #146C2E;
    --pulse-success-container: #C4EED0;
    --pulse-surface: #FFFFFF;
    --pulse-surface-dim: #DAD9DE;
    --pulse-surface-container-low: #F7F9FF;
    --pulse-surface-container: #F0F4F9;
    --pulse-surface-container-high: #E9EDF4;
    --pulse-surface-container-highest: #E2E6ED;
    --pulse-on-surface: #1F1F1F;
    --pulse-on-surface-variant: #444746;
    --pulse-outline: #747775;
    --pulse-outline-variant: #C4C7C5;

    /* ── Brand gradient (per team Figma: yellow -> blue wash) ─────────── */
    --pulse-brand-yellow: #FBBC05;
    --pulse-brand-blue: #3C84FC;
    --pulse-grey-inactive: #D7D9DA;

    /* ── Shape scale ─────────────────────────────────────────────────── */
    --pulse-shape-xs: 4px;
    --pulse-shape-sm: 8px;
    --pulse-shape-md: 12px;
    --pulse-shape-lg: 16px;
    --pulse-shape-xl: 28px;
    --pulse-shape-full: 999px;

    /* ── Spacing (4dp grid) ──────────────────────────────────────────── */
    --pulse-space-1: 4px;
    --pulse-space-2: 8px;
    --pulse-space-3: 12px;
    --pulse-space-4: 16px;
    --pulse-space-6: 24px;
    --pulse-space-8: 32px;

    /* ── Motion: spring-approximated easing ─────────────────────────── */
    --pulse-ease-standard: cubic-bezier(0.2, 0, 0, 1);
    --pulse-ease-emphasized: cubic-bezier(0.05, 0.7, 0.1, 1);
    --pulse-ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
    --pulse-duration-short: 150ms;
    --pulse-duration-medium: 300ms;
    --pulse-duration-long: 450ms;
  }

  @media (prefers-color-scheme: dark) {
    :root {
      --pulse-primary: #A8C7FA;
      --pulse-on-primary: #062E6F;
      --pulse-primary-container: #0842A0;
      --pulse-on-primary-container: #D3E3FD;
      --pulse-secondary: #BFC6DC;
      --pulse-secondary-container: #3E4759;
      --pulse-tertiary: #7FCFFF;
      --pulse-tertiary-container: #004A77;
      --pulse-on-tertiary-container: #C2E7FF;
      --pulse-error: #F2B8B5;
      --pulse-error-container: #8C1D18;
      --pulse-success: #8FDDA1;
      --pulse-success-container: #0A5323;
      --pulse-surface: #131314;
      --pulse-surface-dim: #131314;
      --pulse-surface-container-low: #1B1B1C;
      --pulse-surface-container: #1E1F20;
      --pulse-surface-container-high: #282A2C;
      --pulse-surface-container-highest: #333537;
      --pulse-on-surface: #E3E3E3;
      --pulse-on-surface-variant: #C4C7C5;
      --pulse-outline: #8E918F;
      --pulse-outline-variant: #444746;
    }
  }

  /* ── Typography scale (Roboto / Google Sans, M3 Expressive weights) ── */
  .pulse-display { font-family: "Google Sans", sans-serif; font-weight: 700; font-size: 36px; line-height: 44px; letter-spacing: -0.4px; }
  .pulse-headline { font-family: "Google Sans", sans-serif; font-weight: 600; font-size: 24px; line-height: 32px; }
  .pulse-title { font-family: "Google Sans", sans-serif; font-weight: 600; font-size: 16px; line-height: 24px; }
  .pulse-body { font-family: "Roboto", sans-serif; font-weight: 400; font-size: 14px; line-height: 20px; }
  .pulse-label { font-family: "Roboto", sans-serif; font-weight: 500; font-size: 12px; line-height: 16px; letter-spacing: 0.4px; }

  .material-symbols-rounded {
    font-variation-settings: "FILL" 1, "wght" 500, "GRAD" 0, "opsz" 24;
    vertical-align: middle;
    font-size: 20px;
  }

  /* ── App bar (M3 Expressive top app bar) ─────────────────────────── */
  .pulse-appbar {
      display: flex;
      align-items: center;
      gap: var(--pulse-space-3);
      padding: var(--pulse-space-3) 0 var(--pulse-space-4) 0;
      margin-bottom: var(--pulse-space-4);
      border-bottom: 1px solid var(--pulse-outline-variant);
  }
  .pulse-appbar .pulse-logo-badge {
      width: 40px; height: 40px;
      border-radius: var(--pulse-shape-lg);
      background: linear-gradient(135deg, rgba(251, 188, 5, 0.35), rgba(60, 132, 252, 0.35));
      color: var(--pulse-on-primary-container);
      display: flex; align-items: center; justify-content: center;
      font-size: 22px;
      flex-shrink: 0;
      transition: border-radius var(--pulse-duration-medium) var(--pulse-ease-spring);
  }
  .pulse-appbar .pulse-logo-badge:hover { border-radius: var(--pulse-shape-full); }
  .pulse-appbar h1 {
      font-family: "Google Sans", sans-serif;
      font-size: 20px;
      font-weight: 700;
      margin: 0;
      color: var(--pulse-on-surface);
      letter-spacing: -0.2px;
  }
  .pulse-appbar p { font-family: "Roboto", sans-serif; font-size: 12px; margin: 2px 0 0 0; color: var(--pulse-on-surface-variant); }

  /* ── Cards / containers (tonal elevation, not shadow) ────────────── */
  .pulse-card {
      background: var(--pulse-surface-container-low);
      border-radius: var(--pulse-shape-lg);
      padding: var(--pulse-space-4);
      margin: var(--pulse-space-2) 0;
      border: 1px solid var(--pulse-outline-variant);
      transition: background var(--pulse-duration-short) var(--pulse-ease-standard);
  }
  .pulse-card:hover { background: var(--pulse-surface-container); }

  .pulse-hero {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      text-align: center;
      padding: var(--pulse-space-8) var(--pulse-space-6) var(--pulse-space-6);
      margin: var(--pulse-space-4) 0;
      animation: pulse-fade-in var(--pulse-duration-long) var(--pulse-ease-emphasized);
  }
  .pulse-hero .pulse-hero-subtext {
      font-family: "Google Sans", sans-serif;
      font-weight: 300;
      font-size: clamp(16px, 1.6vw, 22px);
      letter-spacing: -0.2px;
      color: var(--pulse-on-surface-variant);
      margin: 0 0 var(--pulse-space-4) 0;
  }
  .pulse-hero .pulse-hero-logo {
      max-width: min(420px, 80%);
      width: 100%;
      height: auto;
      margin-bottom: var(--pulse-space-2);
  }
  .pulse-hero p.pulse-hero-caption {
      color: var(--pulse-on-surface-variant);
      font-size: 13px;
      margin: var(--pulse-space-2) 0 0 0;
  }

  @keyframes pulse-fade-in {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
  }

  /* ── Chips (pill shape, full radius per M3 Expressive) ──────────── */
  .pulse-chip {
      display: inline-flex;
      align-items: center;
      gap: 4px;
      border-radius: var(--pulse-shape-full);
      padding: 3px 12px;
      font-family: "Roboto", sans-serif;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.3px;
      margin-right: 6px;
      transition: transform var(--pulse-duration-short) var(--pulse-ease-spring);
  }
  .pulse-chip:hover { transform: scale(1.04); }

  /* Release-note-type badges: light mode */
  .pulse-badge-FEATURE { background: var(--pulse-success-container); color: var(--pulse-success); }
  .pulse-badge-FIX { background: var(--pulse-primary-container); color: var(--pulse-primary); }
  .pulse-badge-DEPRECATION { background: #FCE8B2; color: #7B5800; }
  .pulse-badge-BREAKING_CHANGE { background: var(--pulse-error-container); color: var(--pulse-error); }
  .pulse-badge-ISSUE { background: var(--pulse-error-container); color: var(--pulse-error); }
  .pulse-badge-SERVICE_ANNOUNCEMENT { background: var(--pulse-tertiary-container); color: var(--pulse-tertiary); }
  .pulse-badge-DEFAULT { background: var(--pulse-surface-container-high); color: var(--pulse-on-surface-variant); }

  .pulse-sev-HIGH { background: var(--pulse-error-container); color: var(--pulse-error); }
  .pulse-sev-MEDIUM { background: #FCE8B2; color: #7B5800; }
  .pulse-sev-LOW { background: var(--pulse-tertiary-container); color: var(--pulse-tertiary); }
  .pulse-sev-DEFAULT { background: var(--pulse-surface-container-high); color: var(--pulse-on-surface-variant); }

  .pulse-status-ok { background: var(--pulse-success-container); color: var(--pulse-success); }
  .pulse-status-bad { background: var(--pulse-error-container); color: var(--pulse-error); }
  .pulse-status-ok .pulse-dot, .pulse-status-bad .pulse-dot {
      width: 8px; height: 8px; border-radius: 50%;
      background: currentColor; display: inline-block;
      animation: pulse-breathe 2s ease-in-out infinite;
  }
  @keyframes pulse-breathe {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
  }

  /* ── Loading indicator (M3 Expressive: new component) ────────────── */
  .pulse-loading-wave {
      display: inline-flex;
      gap: 4px;
      align-items: center;
      padding: 4px 0;
  }
  .pulse-loading-wave span {
      width: 6px; height: 6px; border-radius: 50%;
      background: var(--pulse-primary);
      animation: pulse-wave 1s var(--pulse-ease-standard) infinite;
  }
  .pulse-loading-wave span:nth-child(2) { animation-delay: 0.15s; }
  .pulse-loading-wave span:nth-child(3) { animation-delay: 0.3s; }
  @keyframes pulse-wave {
      0%, 60%, 100% { transform: translateY(0); opacity: 0.5; }
      30% { transform: translateY(-6px); opacity: 1; }
  }

  /* ── Sidebar / nav-rail styling (Figma: yellow -> blue wash) ──────── */
  section[data-testid="stSidebar"] {
      background: linear-gradient(180deg, rgba(251, 188, 5, 0.35) 0%, rgba(60, 132, 252, 0.35) 100%);
      border-right: 1px solid var(--pulse-outline-variant);
  }

  /* ── Chat message density + shape (M3 Expressive bubble tension) ─── */
  div[data-testid="stChatMessage"] {
      border-radius: var(--pulse-shape-xl);
      padding: var(--pulse-space-2) var(--pulse-space-2);
      animation: pulse-fade-in var(--pulse-duration-medium) var(--pulse-ease-emphasized);
  }

  /* ── Buttons: Figma "dashboard-button" pill treatment ─────────────── */
  .stButton > button, .stDownloadButton > button {
      border-radius: var(--pulse-shape-full) !important;
      border: 2px solid var(--pulse-grey-inactive) !important;
      background: #FFFFFF !important;
      color: #333333 !important;
      font-weight: 600 !important;
      transition: transform var(--pulse-duration-short) var(--pulse-ease-spring) !important,
                  background var(--pulse-duration-short) var(--pulse-ease-standard) !important;
  }
  .stButton > button:hover, .stDownloadButton > button:hover {
      background: #F0F3FF !important;
      transform: translateY(-2px);
  }

  /* ── Chat input: rounded search-bar treatment ─────────────────────── */
  div[data-testid="stChatInput"] {
      border-radius: var(--pulse-shape-full) !important;
  }
  div[data-testid="stChatInput"] textarea {
      border-radius: var(--pulse-shape-full) !important;
  }
  div[data-testid="stChatInputContainer"] {
      border-radius: var(--pulse-shape-full) !important;
      border: 1.5px solid var(--pulse-grey-inactive) !important;
      background: #FFFFFF !important;
  }

  .pulse-empty { text-align: center; padding: var(--pulse-space-8) 0; opacity: 0.7; }
  .pulse-empty .pulse-empty-icon { font-size: 44px; }

  @media (prefers-color-scheme: dark) {
    .pulse-badge-DEPRECATION { background: #5C4200; color: #F3CB63; }
    .pulse-sev-MEDIUM { background: #5C4200; color: #F3CB63; }
    .pulse-card { border-color: rgba(255,255,255,0.14); }
  }
</style>
"""
