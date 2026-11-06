-- The deployed Glue catalog currently contains exactly two external tables.
-- Counts are snapshot observations, not proof of raw-source lineage.
SELECT 'vehicles' AS dataset, COUNT(*) AS rows
FROM auto_market_curated.vehicles
UNION ALL
SELECT 'reviews' AS dataset, COUNT(*) AS rows
FROM auto_market_curated.reviews;
