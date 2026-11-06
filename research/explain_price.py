"""Summarize CatBoost feature contributions on a saved feature-ready dataset.

A SHAP value describes how a feature contributes to this model's prediction,
not why a vehicle has that asking price. Use held-out rows when reporting
generalization; training data can give a misleadingly optimistic picture.
"""

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from pipelines.common import file_sha256


def summarize_shap(values, feature_names):
    """Return ranked mean absolute contributions, excluding the bias column."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 2 or values.shape[1] != len(feature_names) + 1:
        raise ValueError("Expected one SHAP value per feature plus a bias column")
    if not len(values):
        raise ValueError("At least one prediction is required")

    magnitudes = np.abs(values[:, :-1]).mean(axis=0)
    return sorted(
        [
            {"feature": name, "mean_abs_shap": float(magnitude)}
            for name, magnitude in zip(feature_names, magnitudes)
        ],
        key=lambda item: item["mean_abs_shap"],
        reverse=True,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--features-parquet", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=500)
    args = parser.parse_args()
    if args.max_rows < 1:
        parser.error("--max-rows must be positive")

    from catboost import CatBoostRegressor, Pool

    model = CatBoostRegressor()
    model.load_model(str(args.model))
    features = list(model.feature_names_)
    if not features:
        raise ValueError("The model does not record named input features")

    frame = pd.read_parquet(args.features_parquet).head(args.max_rows)
    missing = sorted(set(features) - set(frame.columns))
    if missing:
        raise ValueError(f"Input must be a feature-ready table; missing: {missing}")

    pool = Pool(frame[features], cat_features=model.get_cat_feature_indices())
    shap_values = model.get_feature_importance(pool, type="ShapValues")
    report = {
        "method": "CatBoost ShapValues",
        "interpretation": "model contribution, not a causal vehicle-price effect",
        "model_sha256": file_sha256(args.model),
        "feature_ready_input": str(args.features_parquet),
        "sample_rows": int(len(frame)),
        "feature_contributions": summarize_shap(shap_values, features),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Wrote explainability summary to {args.output_json}")


if __name__ == "__main__":
    main()
