"""Feedback persistence: writes TAM thumbs up/down ratings to BigQuery.

Best-effort telemetry — failures are logged, never surfaced as blocking
errors to the chat UI. See sql/create_feedback_table.sql for the schema.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from release_agent.config import SETTINGS
from release_agent.sources import get_bigquery_client

logger = logging.getLogger(__name__)


def record_feedback(session_id: str, question: str, answer: str, rating: int) -> bool:
    """Persists a single feedback event.

    Args:
        session_id: The chat session this feedback belongs to.
        question: The user's question.
        answer: Pulse's answer being rated.
        rating: -1 (thumbs down), 0 (neutral), or 1 (thumbs up).

    Returns:
        True if the row was written successfully, False otherwise.
    """
    row = {
        "feedback_id": str(uuid.uuid4()),
        "session_id": session_id,
        "question": question,
        "answer": answer,
        "rating": rating,
        "created_at": datetime.now(UTC).isoformat(),
    }
    try:
        errors = get_bigquery_client().insert_rows_json(
            SETTINGS.feedback_table_fqn, [row]
        )
        if errors:
            logger.warning("record_feedback insert errors: %s", errors)
            return False
        return True
    except Exception:  # noqa: BLE001 - feedback must never crash the UI
        logger.exception("record_feedback failed")
        return False
