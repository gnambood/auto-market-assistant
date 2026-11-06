-- The deployed reviews table already holds model-scope-matched reviews.
-- No vehicle_review_matches table is provisioned by the two-table catalog.
SELECT
    manufacturer,
    model_family,
    COUNT(*) AS matched_reviews,
    COUNT(DISTINCT vehicle_year) AS covered_years,
    ROUND(AVG(rating), 2) AS avg_owner_rating
FROM auto_market_curated.reviews
GROUP BY manufacturer, model_family
ORDER BY matched_reviews DESC;
