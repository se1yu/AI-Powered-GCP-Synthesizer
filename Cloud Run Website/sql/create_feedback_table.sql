-- Pulse feedback persistence table.
-- Run once against sprinternship-aus-2026.release_notes before enabling
-- feedback in the UI (release_agent/feedback.py writes here).
CREATE TABLE IF NOT EXISTS `sprinternship-aus-2026.release_notes.pulse_feedback` (
  feedback_id STRING NOT NULL,
  session_id  STRING NOT NULL,
  question    STRING,
  answer      STRING,
  rating      INT64 NOT NULL,  -- -1 thumbs down, 1 thumbs up
  created_at  TIMESTAMP NOT NULL
)
PARTITION BY DATE(created_at)
OPTIONS (
  description = "TAM feedback on Pulse chat answers, partitioned by day."
);
