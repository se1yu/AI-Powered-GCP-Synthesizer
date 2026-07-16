-- Refreshes the release notes table and exports it to Cloud Storage.
-- Scheduled in BigQuery to run every 12 hours.
--
-- When scheduling: leave the destination table fields EMPTY. Both statements
-- name their own targets.

-- add release notes we haven't seen before.
-- Matching on row_id means re-running is harmless and nothing duplicates,
-- even if a scheduled run is missed or delayed.
MERGE `sprinternship-aus-2026.gcp_updates.release_notes` AS target
USING (
  SELECT
    product_name,
    release_note_type,
    description,
    published_at,
    'https://cloud.google.com/release-notes' AS source_url,
    TO_HEX(SHA256(CONCAT(product_name, CAST(published_at AS STRING), description))) AS row_id
  FROM `bigquery-public-data.google_cloud_release_notes.release_notes`
) AS source
ON target.row_id = source.row_id
WHEN NOT MATCHED THEN
  INSERT (product_name, release_note_type, description, published_at, source_url, row_id)
  VALUES (product_name, release_note_type, description, published_at, source_url, row_id);

-- export the full table as newline-delimited JSON (one note per line).
-- overwrite=true replaces the previous export, so the bucket holds exactly one
-- current copy rather than accumulating duplicates.
EXPORT DATA OPTIONS(
  uri='gs://gcp-updates-rag-aus2026/release_notes/*.json',
  format='JSON',
  overwrite=true
) AS
SELECT
  product_name,
  release_note_type,
  description,
  published_at,
  source_url,
  row_id
FROM `sprinternship-aus-2026.gcp_updates.release_notes`
ORDER BY published_at DESC;
