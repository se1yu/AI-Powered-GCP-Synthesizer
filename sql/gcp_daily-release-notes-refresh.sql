DELETE FROM `sprinternship-aus-2026.release_notes.notes`
WHERE source = 'public_dataset'
  AND published_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY);

INSERT INTO `sprinternship-aus-2026.release_notes.notes`
  (description, release_note_type, published_at, product_id,
   product_name, product_version_name, note_key, source, ingested_at)
SELECT
  description,
  release_note_type,
  published_at,
  SAFE_CAST(product_id AS INT64),
  product_name,
  product_version_name,
  TO_HEX(SHA256(CONCAT(
    IFNULL(product_name,''),'|',
    CAST(published_at AS STRING),'|',
    IFNULL(description,'')
  ))),
  'public_dataset',
  CURRENT_TIMESTAMP()
FROM `bigquery-public-data.google_cloud_release_notes.release_notes`
WHERE published_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 14 DAY);
