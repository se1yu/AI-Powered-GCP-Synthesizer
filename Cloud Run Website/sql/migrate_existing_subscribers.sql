-- Extends the original Flask subscriber table without replacing or deleting rows.
ALTER TABLE `sprinternship-aus-2026.comms.subscribers`
  ADD COLUMN IF NOT EXISTS frequency STRING,
  ADD COLUMN IF NOT EXISTS frequency_days INT64,
  ADD COLUMN IF NOT EXISTS active BOOL,
  ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS next_send_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS last_sent_at TIMESTAMP,
  ADD COLUMN IF NOT EXISTS unsubscribe_token STRING;

-- Existing subscribers default to a weekly active digest. Generate stable,
-- opaque unsubscribe tokens only for rows that do not already have one.
UPDATE `sprinternship-aus-2026.comms.subscribers`
SET
  frequency = COALESCE(frequency, 'Weekly'),
  frequency_days = COALESCE(frequency_days, 7),
  active = COALESCE(active, TRUE),
  updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP()),
  next_send_at = COALESCE(next_send_at, CURRENT_TIMESTAMP()),
  unsubscribe_token = COALESCE(unsubscribe_token, GENERATE_UUID())
WHERE
  frequency IS NULL
  OR frequency_days IS NULL
  OR active IS NULL
  OR updated_at IS NULL
  OR next_send_at IS NULL
  OR unsubscribe_token IS NULL;
