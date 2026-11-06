"""Small synthetic checks for the new, independently runnable price baseline."""

import pandas as pd
import pytest

from research.price_baseline import evaluate_baseline


def listings():
    return pd.DataFrame(
        {
            "id": list(range(20)),
            "manufacturer": ["ford"] * 18 + ["toyota"] * 2,
            "model": ["F-150"] * 18 + ["Camry"] * 2,
            "posting_date": pd.date_range("2021-01-01", periods=20, freq="D"),
            "price": [10000 + 100 * i for i in range(20)],
        }
    )


def test_chronological_split_never_trains_on_test_dates():
    report = evaluate_baseline(listings(), test_fraction=0.25)
    split = report["split"]
    assert split["train_rows"] == 15
    assert split["test_rows"] == 5
    assert split["train_latest_posting"] < split["test_start"]
    assert report["metrics"]["mae"] > 0
    assert report["not_historical_catboost_v0"]


def test_unseen_manufacturer_uses_global_train_median():
    report = evaluate_baseline(listings(), test_fraction=0.25)
    assert report["fallback_counts"]["global"] == 2


def test_one_posting_date_cannot_be_chronologically_split():
    data = listings()
    data["posting_date"] = "2021-01-01"
    with pytest.raises(ValueError, match="strict chronological split"):
        evaluate_baseline(data)


def test_invalid_baseline_arguments():
    with pytest.raises(ValueError, match="test_fraction"):
        evaluate_baseline(listings(), test_fraction=1)
    with pytest.raises(ValueError, match="Missing required"):
        evaluate_baseline(pd.DataFrame({"price": [1]}))
