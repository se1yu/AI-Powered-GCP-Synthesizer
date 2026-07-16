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
