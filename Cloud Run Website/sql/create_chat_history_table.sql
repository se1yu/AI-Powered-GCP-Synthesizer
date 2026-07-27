-- Pulse chat history persistence table.
-- Run once against sprinternship-aus-2026.release_notes before enabling
-- persistent chat history in the UI (release_agent/history.py writes here).
CREATE TABLE IF NOT EXISTS `sprinternship-aus-2026.release_notes.pulse_chat_history` (
  message_id STRING NOT NULL,
  session_id STRING NOT NULL,  -- pinned to a long-lived browser cookie, see app.py
  role       STRING NOT NULL,  -- "user" or "assistant"
  content    STRING NOT NULL,
  created_at TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
OPTIONS (
  description = "Persisted Cloud Comms chat turns, keyed by session_id, partitioned by day."
);
