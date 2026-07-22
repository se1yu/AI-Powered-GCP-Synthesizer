# Changelog

All notable changes to Pulse are documented in this file.

## [1.0.0] - 2026-07-22

### Added

- Full redesign and rebrand from "Ask John" to **Pulse**.
- Material 3 design system (Google blue baseline, light + dark mode,
  WCAG AA contrast) across all pages.
- Native Streamlit chat UI (`st.chat_message`, `st.chat_input`,
  `st.write_stream`) replacing hand-rolled HTML message bubbles.
- Streaming responses via `st.write_stream` + `Runner.run_async`.
- `get_service_health` tool backed by the public GCP Service Health feed
  (`status.cloud.google.com/incidents.json`), with a live status pill.
- Weekly Digest page (`pages/1_Digest.py`) with metrics, bar chart, and
  CSV export.
- Deep-link support via `?q=` query parameter.
- Thumbs up/down feedback (`st.feedback`) persisted to BigQuery
  (`release_notes.pulse_feedback`).
- Full test suite (pytest + Streamlit `AppTest`), GitHub Actions CI,
  `bandit` + `detect-secrets` pre-commit hooks.
- `docs/ARCHITECTURE.md` and `docs/CUJ.md` with Mermaid diagrams.

### Changed

- Model upgraded from `gemini-2.5-flash` to `gemini-3.6-flash`.
- Corrected BigQuery table from `sprinternship-aus-2026.gcp_updates.release_notes`
  to `sprinternship-aus-2026.release_notes.notes` (US location).
- All SQL is now parameterized (`bigquery.ScalarQueryParameter`) instead
  of string-interpolated.
- Results are deduplicated by `note_key` (fixes duplicate cards seen in
  the previous UI).
- Deploy target clarified as Cloud Run via buildpacks + `Procfile`
  (no `Dockerfile`), per Google's documented Streamlit deployment path.

### Fixed

- Double-submit race between `st.text_input` and the send button.
- `asyncio.run()` event-loop churn on every message; ADK session is now
  created once and reused.
- Invalid `"CHANGE"` value in the sidebar type filter (replaced with the
  real dataset enum: FEATURE, FIX, DEPRECATION, BREAKING_CHANGE, ISSUE,
  SERVICE_ANNOUNCEMENT).
- Raw `note_key` hashes leaking into chat answers.
- Blank assistant bubble on empty/failed tool responses.

## [0.1.0] - prior

- Initial "Ask John" prototype.
