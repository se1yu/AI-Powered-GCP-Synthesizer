# Cloud Comms — GCP Release & Service Health Assistant

Cloud Comms is a Streamlit chat assistant for Google Technical Account Managers
(TAMs). It answers questions about Google Cloud release notes and live
service health in plain, well-formatted language, backed by BigQuery,
Vertex AI Search, and the public GCP Service Health feed.

## Quick start

1. Clone the repository and create a virtual environment:

   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

1. Copy the environment template and fill in any overrides you need:

   ```bash
   cp .env.example release_agent/.env
   ```

1. Authenticate to GCP locally (Cloud Comms uses Application Default
   Credentials):

   ```bash
   gcloud auth application-default login
   ```

1. Run the app:

   ```bash
   streamlit run app.py
   ```

The app opens at `http://localhost:8501`. The **Weekly Digest** page is
available from the sidebar or at `/Digest`.

## Installation

See [Quick start](#quick-start). Production dependencies are pinned in
`requirements.txt`; dev tools (`pytest`, `ruff`, `bandit`) are declared in
`pyproject.toml` and the CI workflow.

## Usage

Ask Cloud Comms things like:

- "What new features dropped in Vertex AI this week?"
- "Is BigQuery having any issues right now?"
- "Any breaking changes in Cloud Run recently?"
- "Give me a summary of everything that changed in the last 7 days"

Use the sidebar quick filters to prefill a question, or share a deep link
like `?q=Any+breaking+changes+in+Cloud+Run` to auto-ask a question on
page load.

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system
design, data flow, and RAG strategy, and
[docs/CUJ.md](docs/CUJ.md) for critical user journeys.

## Deployment

Cloud Comms deploys to Cloud Run via buildpacks (no Dockerfile needed) using
the `Procfile`:

```bash
gcloud run deploy release-agent \
  --source . \
  --project sprinternship-aus-2026 \
  --region europe-west1 \
  --service-account aus-sprinternship-2026-sa@sprinternship-aus-2026.iam.gserviceaccount.com \
  --allow-unauthenticated \
  --set-env-vars PULSE_MODEL=gemini-3.6-flash
```

## Testing

```bash
pytest -v --tb=short
```

Run linting and security scans before committing:

```bash
ruff check .
bandit -c pyproject.toml -r release_agent app.py pages
pre-commit run --all-files
```

## Contributing

1. Create a feature branch.
1. Make focused, incremental changes with tests.
1. Run `pre-commit run --all-files` before opening a pull request.
1. Update `CHANGELOG.md` for any user-facing change.

## See also

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/CUJ.md](docs/CUJ.md)
- [CHANGELOG.md](CHANGELOG.md)
