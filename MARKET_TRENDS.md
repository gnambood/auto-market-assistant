# Historical Vehicle Market Trends

This descriptive analytics feature supports the résumé statement: historical asking-price and daily listing-count charts grouped by **manufacturer, model family and vehicle year**.

## Source of truth

The implementation is \`pipelines/market_trends.py\` in this repository. It consumes the existing **curated Parquet vehicle data** produced by \`pipelines/run_pipeline.py\`, with no new external services or changes to CatBoost, retrieval, or the API.

\`\`\`bash
pip install -r requirements-data.txt
python -m pipelines.market_trends \
  --input data-platform-output/curated/vehicles \
  --output-dir market-trends-output
\`\`\`

Open \`market-trends-output/index.html\` locally. Outputs also include \`daily_trends.csv\`, \`group_coverage.csv\` and \`diagnostics.json\`. Run tests with \`python -m pytest tests/test_market_trends.py\` in the project's test environment.

## What the plots show

- **Asking prices:** median listed price per posting date for a single manufacturer/model-family/year group, shown only when the daily sample is at least 3 listings, the group has at least 12 listings overall, and at least 2 observed posting days.
- **Availability:** number of unique listings posted that date in the curated snapshot. This is *posting volume*, not live active inventory or dealership stock.
- **Data quality:** duplicate listing IDs removed, missing/unparseable dates, valid row counts, eligible groups, and suppressed daily price observations are recorded.
- **Consistency:** model-family naming and cleaning are inherited from the existing vehicle ETL; no new prediction inputs or labels are introduced.

These conservative defaults are configurable. Suppressed price data is omitted rather than interpolated or forecast.

## Limitations

The historical Craigslist extract reflects **2021 asking prices**, not sales transactions or current values. Changes in price can result from changes in vehicle trim, mileage, condition, region or advertiser mix, even within the same make/model-family/year group. Daily volume counts are affected by source coverage and collection activity. Neither a causal price trend nor a future-price forecast is claimed.

The generated viewer embeds only **aggregated** data in a standalone HTML file. Large raw listings, trained artifacts and participant data are not published.
