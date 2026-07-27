"""
Local Flask backend for the GoogleComms custom UI.

Run:  pip install -r requirements.txt
      python subscribe_server.py

Two independent things live here:
  1. /subscribe, /unsubscribe — writes to BigQuery `comms.subscribers`
     (unchanged from the original — your subscription form).
  2. /ask — the real Cloud Comms brain: the same google-adk Agent, Gemini
     model, BigQuery release-notes lookups, Vertex AI Search semantic
     search, and GCP Service Health check that used to live behind the
     Streamlit app, now behind a plain JSON endpoint for this custom UI.
     See release_agent/ (copied verbatim from the Streamlit app — it never
     imported streamlit, so nothing had to change to port it here).

Needs the same GCP auth as the Streamlit app did locally: either
`gcloud auth application-default login`, or a service account key path in
GOOGLE_APPLICATION_CREDENTIALS (see release_agent/.env.example).
"""

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.cloud import bigquery
from google.genai import types

from release_agent.agent import root_agent
from release_agent.config import SETTINGS
from release_agent.history import load_chat_history, save_chat_message

load_dotenv("release_agent/.env")
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

PROJECT = "sprinternship-aus-2026"
SUBSCRIBERS_TABLE = f"{PROJECT}.comms.subscribers"

bq_client = bigquery.Client(project=PROJECT)

# One shared agent Runner for the process lifetime — same pattern app.py
# used per-browser-session via st.session_state, just now process-wide
# since Flask has no equivalent built in. _known_sessions tracks which
# session_ids already have a live ADK session so we don't recreate one on
# every request (mirrors app.py's _adk_session_ready flag).
_runner = Runner(
    agent=root_agent,
    app_name=SETTINGS.app_name,
    session_service=InMemorySessionService(),
)
_known_sessions: set[str] = set()

_SESSION_COOKIE_NAME = "cc_session_id"
_SESSION_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365


async def _ensure_adk_session(session_id: str) -> None:
    if session_id in _known_sessions:
        return
    await _runner.session_service.create_session(
        app_name=SETTINGS.app_name,
        user_id="tam-user",
        session_id=session_id,
    )
    _known_sessions.add(session_id)


async def _ask_agent(session_id: str, question: str) -> str:
    """Runs one turn through the real agent and returns its final text.

    Non-streaming on purpose for this first pass — collects the full
    response before replying, rather than the token-by-token streaming
    app.py did via st.write_stream. Streaming over plain fetch() is doable
    later (Server-Sent Events or chunked responses) but adds real
    complexity; skip it until the simple version is confirmed working.
    """
    await _ensure_adk_session(session_id)
    content = types.Content(role="user", parts=[types.Part(text=question)])

    emitted = ""
    async for event in _runner.run_async(
        user_id="tam-user", session_id=session_id, new_message=content
    ):
        if not (event.content and event.content.parts):
            continue
        text = "".join(part.text or "" for part in event.content.parts)
        if text:
            emitted = text

    return emitted or "I couldn't find an answer for that. Try rephrasing or broadening your question."


@app.route("/ask", methods=["POST", "OPTIONS"])
def ask():
    if request.method == "OPTIONS":  # browser preflight
        return ("", 204)

    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify(ok=False, error="question is required"), 400

    # Cookie-pinned session_id, same idea as the Streamlit app's persistent
    # chat history — lets a browser's conversation carry real ADK context
    # (and get reloaded from BigQuery) across requests instead of every
    # /ask call starting the agent from a blank slate.
    session_id = request.cookies.get(_SESSION_COOKIE_NAME) or str(uuid.uuid4())

    try:
        answer = asyncio.run(_ask_agent(session_id, question))
    except Exception:  # noqa: BLE001 - never crash the endpoint on a model/tool error
        logger.exception("Cloud Comms agent turn failed")
        answer = (
            "⚠️ Cloud Comms hit an error reaching the model or a data source. "
            "Please try again in a moment, or rephrase your question."
        )

    save_chat_message(session_id, "user", question)
    save_chat_message(session_id, "assistant", answer)

    resp = jsonify(ok=True, answer=answer)
    resp.set_cookie(
        _SESSION_COOKIE_NAME,
        session_id,
        max_age=_SESSION_COOKIE_MAX_AGE_SECONDS,
        samesite="Lax",
    )
    return resp


@app.route("/history", methods=["GET"])
def history():
    """Reloads this browser's prior chat turns, oldest first — call this
    once on page load so a refresh doesn't lose the conversation."""
    session_id = request.cookies.get(_SESSION_COOKIE_NAME)
    if not session_id:
        return jsonify(ok=True, messages=[])
    return jsonify(ok=True, messages=load_chat_history(session_id))


@app.route("/subscribe", methods=["POST", "OPTIONS"])
def subscribe():
    if request.method == "OPTIONS":
        return ("", 204)

    data = request.get_json(silent=True) or {}
    first_name = (data.get("first_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    industry = (data.get("industry") or "").strip()

    if not first_name or not email or not industry:
        return jsonify(ok=False, error="Please fill out all three fields."), 400
    if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email):
        return jsonify(ok=False, error="That email doesn't look right."), 400

    row = {
        "first_name": first_name,
        "email": email,
        "industry": industry,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    errors = bq_client.insert_rows_json(SUBSCRIBERS_TABLE, [row])
    if errors:
        logger.warning("subscribe insert errors: %s", errors)
        return jsonify(ok=False, error="Database write failed."), 500

    return jsonify(ok=True)


@app.route("/subscriber-counts", methods=["GET"])
def subscriber_counts():
    """Subscriber counts per industry, for the Recommendations chart.

    Queries comms.subscribers directly rather than a local file — this
    replaces the JSON-file-backed version from the earlier prototype now
    that subscribe writes to BigQuery for real.
    """
    sql = f"""
        SELECT industry, COUNT(*) AS count
        FROM `{SUBSCRIBERS_TABLE}`
        GROUP BY industry
        ORDER BY count DESC
    """
    try:
        rows = list(bq_client.query(sql).result())
        counts = {row.industry: row.count for row in rows}
    except Exception:  # noqa: BLE001 - an empty/missing table just looks like no subscribers yet
        logger.exception("subscriber_counts failed")
        counts = {}
    return jsonify(ok=True, counts=counts)


if __name__ == "__main__":
    # debug=True is intentionally omitted: with host="0.0.0.0" (bound to the
    # whole network, not just localhost), Werkzeug's debug mode exposes an
    # interactive Python console to anyone else on the same Wi-Fi — a real
    # remote-code-execution risk, not just a lint nitpick.
    app.run(host="0.0.0.0", port=8000)
