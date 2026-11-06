# Research workflows

This directory distinguishes new executable experiments from historical, reported results. Read [EXPERIMENTS.md](EXPERIMENTS.md) before interpreting any metric.

## Environment

Python 3.11:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-research.txt
python -m pytest -q
```

The raw CSV and model artifacts are **not committed**. The model and FAISS index are large; follow [../reproducibility/README.md](../reproducibility/README.md) to locate the historical data evidence. Do not replace reference artifacts during experiments.

## Experiment B-01: chronological median baseline

```bash
python -m research.price_baseline \
  --input-parquet /path/to/vehicles_clean.parquet \
  --output-json results/price_median_baseline.json \
  --test-fraction 0.2
```

Training rows are strictly earlier than test rows by listing **posting date**, with all records on the split date assigned to the test set. The baseline uses the training-set median for each make/model family, falling back to make median and finally global median. It records the split cutoff, counts, MAE, RMSE, R² and input SHA-256. This is a **new benchmark**, not the original CatBoost V0 or a directly comparable reconstruction of its split. The current repository cannot faithfully repeat the historical CatBoost evaluation without its original training sources and held-out row IDs.

## Experiment X-01: CatBoost explainability

```bash
python -m research.explain_price \
  --model /path/to/price_model.cbm \
  --features-parquet /path/to/feature_ready_holdout.parquet \
  --output-json results/feature_contributions.json \
  --max-rows 500
```

The input must be the **feature-ready evaluation table** with every feature recorded by the saved CatBoost model. `vehicles_clean.parquet` is not automatically feature-ready: some derived fields were built in the original training notebook. The command stops with an explicit missing-column error instead of guessing transformations.

It reports mean absolute CatBoost SHAP values on the selected sample. These describe the model's predictions, **not causal effects**, and should be accompanied by the evaluation cohort and its model/data hash. Do not interpret the output as showing what physically causes vehicle prices.

## Market intelligence M-01

The maintained functions in [../pipelines/market_trends.py](../pipelines/market_trends.py) return historical median asking prices and observed listing counts with duplicate-ID, invalid posting-date and minimum-sample diagnostics. Call them against the curated data; do not present synthetic-fixture tests as empirical time-series results. Dataset coverage is concentrated in 2021, so causal market trends, current valuations and forecasting are not established.

## Reproducibility gaps

The archived 2026-10-10 scripts reproduced **data content** against reference Parquet. They did not independently retrain CatBoost, regenerate MiniLM embeddings, or evaluate Qwen. Recover the exact Part 1/Part 2 experimental notebooks before claiming complete research reproducibility. Preserve historical notebooks/metrics unchanged and link each new run to a configuration, split, input checksums and saved outputs.

## AWS pause

Research scripts run locally and do not require a running ECS service. Read [../operations/AWS_PAUSE_PLAN.md](../operations/AWS_PAUSE_PLAN.md) before pausing cloud serving. Keep a verified offline portfolio example available.
