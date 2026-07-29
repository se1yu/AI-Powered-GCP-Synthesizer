CREATE TABLE IF NOT EXISTS `sprinternship-aus-2026.comms.subscribers` (
  email STRING NOT NULL,
  first_name STRING NOT NULL,
  industry STRING NOT NULL,
  frequency STRING NOT NULL,
  frequency_days INT64 NOT NULL,
  active BOOL NOT NULL,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  next_send_at TIMESTAMP NOT NULL,
  last_sent_at TIMESTAMP,
  unsubscribe_token STRING NOT NULL
)
CLUSTER BY active, industry;
