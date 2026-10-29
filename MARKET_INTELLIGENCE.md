# Vehicle Market Intelligence — Historical Listing Trends

## Product question

How did **asking prices and the number of observed Craigslist listings** for comparable vehicles change **within the captured historical snapshot**? This is not a current-price signal, a sale-price dataset, or a market-wide inventory census.

## Audit and forecasting decision

The source pipeline cleans Craigslist vehicle advertisements, de-duplicates by listing ID, enforces valid posting dates, prices ($1,000–$100,000), odometers (0–300,000), and model-year rules. The validated modeling cohort has 238,959 listings; its documented dates cover approximately **2021-04-04 to 2021-05-05**, only about one month. Source snapshots and raw-to-curated lineage were not independently fully audited. The actual coverage, duplicates and missing-date counts are recomputed on every run and included in the output. The data is heavily filtered by the top-10 manufacturer scope; scraped postings are not a random sample.

**Decision: do not forecast.** A short collection window cannot establish multi-month seasonality or reliable out-of-time forecasting. No Prophet/ARIMA model is added. A forecast would be misleading without more dated observations and a naive chronological benchmark.

## Method

- Read **existing curated manufacturer-partitioned Parquet** without retraining CatBoost or modifying the review RAG.
- Group by manufacturer + normalized model family + *vehicle model year*. Avoid pooling disparate model years.
- Normalize timestamps to UTC calendar days. Count unique listing IDs, after defending against accidental duplicates.
- Report daily median asking price, observed listing count and median odometer for days meeting the **minimum 5** listings; offer a group only if it has **20+** listings and at least **two supported dates**.
- Surface total listings, supported days, observed days, first/last observed date and source file SHA-256s. The minimum sample filter **suppresses** thin days; missing dates must never be presented as zero listings.
- No percent-change KPI or causal price statement: changing mix of location/trim/condition/mileage can change median prices without underlying market-price movement.
- Avoid extrapolating beyond the observation window or suggesting that listing counts equal market supply.

## Reproduce

```bash
pip install -r requirements-data.txt
python -m market_intelligence.trends \
  --curated-path data-platform-output/curated/vehicles \
  --output-dir market-intelligence-output
python -m pytest tests/test_market_intelligence.py -q
```

The JSON output is `market-intelligence-output/market_intelligence.json`; it includes detailed snapshot quality/coverage information and SHA-256 hashes for all input Parquet files. Open `market_intelligence/viewer.html` in a browser and choose the JSON output using the file picker to inspect vehicle groups. Nothing is uploaded and no API/cloud changes are required.

## Limitations

Listings are historical *asking* prices, not transaction prices. The scraped source can have geographic and vehicle-composition bias. Model-family normalization might group trims, variants and drive configurations. Even with the same make/model/year, price movements may reflect mileage, seller, region, condition or collection effects. Daily counts represent **observed samples**, not live stock or total availability. Supported days are not necessarily consecutive. A user should not infer depreciation or a price forecast from the trend visualization.

## Extension gate for future data

Forecasting remains explicitly disabled until longer continuous coverage is acquired, coverage and composition changes are audited, and walk-forward holdouts show improvement against a seasonal-naive or last-observation baseline on relevant metrics. This gate is documentation, not implemented forecasting.
