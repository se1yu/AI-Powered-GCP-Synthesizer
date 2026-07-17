CREATE OR REPLACE TABLE `sprinternship-aus-2026.gcp_updates.release_notes` AS
SELECT
  product_name,
  release_note_type,
  description,
  published_at,
  CONCAT(
    'https://docs.cloud.google.com/release-notes#',
    FORMAT_DATE('%B_%d_%Y', DATE(published_at))
  ) AS source_url,
  TO_HEX(SHA256(CONCAT(product_name, CAST(published_at AS STRING), description))) AS row_id
FROM `bigquery-public-data.google_cloud_release_notes.release_notes`;
