-- Creates the raw GCP release notes table from Google's public dataset.
-- The table is intentionally RAW: `description` still contains source HTML.
-- Cleaning happens AFTER : this is just raw ingesting :) 

CREATE OR REPLACE TABLE `sprinternship-aus-2026.gcp_updates.release_notes` AS
SELECT
  product_name,
  release_note_type,
  description,
  published_at,
  -- cite the consolidated page.
  'https://cloud.google.com/release-notes' AS source_url,
  -- Content hash: stable document ID, and used to skip duplicates on refresh.
  -- Hashed from the RAW description so it stays stable if cleaning changes.
  TO_HEX(SHA256(CONCAT(product_name, CAST(published_at AS STRING), description))) AS row_id
FROM `bigquery-public-data.google_cloud_release_notes.release_notes`;
