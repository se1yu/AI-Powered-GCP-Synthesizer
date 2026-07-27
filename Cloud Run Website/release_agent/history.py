"""Chat-history persistence: durably stores and reloads TAM conversations.

Cloud Run instances are ephemeral and st.session_state resets on every
browser refresh, so without this a TAM's conversation vanishes the moment
the tab reloads. Messages are keyed by session_id — a UUID app.py pins to
a long-lived browser cookie rather than letting it regenerate on every
refresh — so history can be reloaded for the same browser later.

Best-effort, same as feedback.py: failures are logged, never surfaced as
blocking errors. A failed load just looks like a fresh chat, which is the
correct degrade-gracefully behavior here.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from google.cloud import bigquery

from release_agent.config import SETTINGS
from release_agent.sources import get_bigquery_client

logger = logging.getLogger(__name__)

_MAX_HISTORY_MESSAGES = 50


def save_chat_message(session_id: str, role: str, content: str) -> bool:
    """Persists a single chat turn (one row per user or assistant message).

    Args:
        session_id: The browser's long-lived session identifier.
        role: "user" or "assistant".
        content: The message text.

    Returns:
        True if the row was written successfully, False otherwise.
    """
    row = {
        "message_id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": role,
        "content": content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        errors = get_bigquery_client().insert_rows_json(SETTINGS.chat_history_table_fqn, [row])
        if errors:
            logger.warning("save_chat_message insert errors: %s", errors)
            return False
        return True
    except Exception:  # noqa: BLE001 - persistence must never crash the chat
        logger.exception("save_chat_message failed")
        return False


def load_chat_history(session_id: str) -> list[dict]:
    """Loads the most recent messages for a session_id, oldest first.

    Args:
        session_id: The browser's long-lived session identifier.

    Returns:
        A list of {"role", "content"} dicts, oldest first — or an empty
        list (never raises) if BigQuery is unreachable or there's no prior
        history for this session.
    """
    # nosec B608: session_id/limit are bound query parameters below;
    # table_fqn is server config. No user input is string-interpolated.
    sql = f"""
        SELECT role, content, created_at
        FROM `{SETTINGS.chat_history_table_fqn}`
        WHERE session_id = @session_id
        ORDER BY created_at DESC
        LIMIT @limit
    """  # nosec B608

    try:
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("session_id", "STRING", session_id),
                bigquery.ScalarQueryParameter("limit", "INT64", _MAX_HISTORY_MESSAGES),
            ]
        )
        rows = list(get_bigquery_client().query(sql, job_config=job_config).result())
        return [{"role": row.role, "content": row.content} for row in reversed(rows)]
    except Exception:  # noqa: BLE001 - a failed load just looks like a fresh chat
        logger.exception("load_chat_history failed")
        return []
