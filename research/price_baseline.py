"""Reproducible median baseline for historical Craigslist asking prices.

This is a NEW baseline, not the original CatBoost V0 experiment. It uses
strictly earlier posting dates for fitting and later dates for testing.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pipelines.common import file_sha256, model_family


def evaluate_baseline(listings: pd.DataFrame, test_fraction: float = 0.2) -> dict:
    """Evaluate a make/model-family median with make/global fallbacks."""
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")

    required = {"id", "manufacturer", "model", "posting_date", "price"}
    missing = sorted(required - set(listings.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    data = listings.copy()
    data["posting_date"] = pd.to_datetime(
        data["posting_date"], errors="coerce", utc=True
    )
    data["price"] = pd.to_numeric(data["price"], errors="coerce")
    data["model_family"] = data["model"].map(model_family)
    data = data.dropna(subset=["id", "manufacturer", "posting_date", "price"])
    data = data[data["price"] > 0].drop_duplicates("id", keep="first")
    data = data.sort_values(["posting_date", "id"], kind="mergesort")

    if len(data) < 5:
        raise ValueError("At least five valid listings are required")

    split_row = max(1, min(len(data) - 1, int(len(data) * (1 - test_fraction))))
    cutoff = data.iloc[split_row]["posting_date"]
    train = data[data["posting_date"] < cutoff]
    test = data[data["posting_date"] >= cutoff]
    if train.empty or test.empty:
        raise ValueError("Posting dates do not support a strict chronological split")

    family_medians = (
        train.groupby(["manufacturer", "model_family"], observed=True)["price"]
        .median().rename("family_median").reset_index()
    )
    make_medians = (
        train.groupby("manufacturer", observed=True)["price"]
        .median().rename("make_median").reset_index()
    )
    scored = test.merge(family_medians, on=["manufacturer", "model_family"], how="left")
    scored = scored.merge(make_medians, on="manufacturer", how="left")
    predictions = (
        scored["family_median"].fillna(scored["make_median"])
        .fillna(float(train["price"].median()))
        .to_numpy(dtype=float)
    )
    actual = scored["price"].to_numpy(dtype=float)
    errors = actual - predictions
    total_variance = float(np.square(actual - actual.mean()).sum())

    return {
        "experiment": "new_chronological_median_baseline",
        "not_historical_catboost_v0": True,
        "split": {
            "method": "strict_posting_date",
            "test_fraction_requested": test_fraction,
            "test_start": cutoff.isoformat(),
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "train_latest_posting": train["posting_date"].max().isoformat(),
        },
        "metrics": {
            "mae": float(np.abs(errors).mean()),
            "rmse": float(np.sqrt(np.square(errors).mean())),
            "r2": (float(1 - np.square(errors).sum() / total_variance)
                   if total_variance else None),
        },
        "fallback_counts": {
            "make": int(scored["family_median"].isna().sum()
                        - (scored["family_median"].isna() & scored["make_median"].isna()).sum()),
            "global": int((scored["family_median"].isna()
                           & scored["make_median"].isna()).sum()),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-parquet", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--test-fraction", type=float, default=0.2)
    args = parser.parse_args()

    paths = sorted(args.input_parquet.rglob("*.parquet")) if args.input_parquet.is_dir() else [args.input_parquet]
    if not paths:
        raise FileNotFoundError(args.input_parquet)

    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(args.input_parquet) if args.input_parquet.is_dir() else path.name).encode())
        digest.update(file_sha256(path).encode())
    report = evaluate_baseline(pd.read_parquet(args.input_parquet), args.test_fraction)
    report["source_parquet_fingerprint_sha256"] = digest.hexdigest()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
