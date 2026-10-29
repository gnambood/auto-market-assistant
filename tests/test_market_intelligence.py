import pandas as pd
import pytest

from market_intelligence.trends import analyze


def sample():
    rows = []
    for day in range(1, 5):
        for i in range(6):
            rows.append({
                "id": f"{day}-{i}", "manufacturer": "ford", "model_family": "f 150",
                "year": 2019, "posting_date": f"2021-04-{day:02d}T12:00:00Z",
                "price": 10000 + day * 100 + i * 10, "odometer": 60000 + i * 500,
            })
    return pd.DataFrame(rows)


def test_medians_counts_and_scope():
    result = analyze(sample())
    assert len(result["groups"]) == 1
    group = result["groups"][0]
    assert group["total_listings"] == 24
    assert group["supported_days"] == 4
    assert group["daily"][0]["median_asking_price"] == 10125
    assert group["daily"][0]["listing_count"] == 6
    assert result["metadata"]["forecasting"] == "not_supported"


def test_duplicate_missing_date_and_different_model_year():
    df = sample()
    extra = pd.concat([
        df, df.iloc[[0]],
        pd.DataFrame([{**df.iloc[0].to_dict(), "id": "missing", "posting_date": None}]),
        pd.DataFrame([{**df.iloc[0].to_dict(), "id": "different-year", "year": 2018}]),
    ], ignore_index=True)
    result = analyze(extra)
    assert result["metadata"]["duplicate_ids"] == 1
    assert result["metadata"]["missing_dates"] == 1
    assert len(result["groups"]) == 1


def test_thin_daily_groups_suppressed():
    data = sample()
    assert analyze(data, min_daily=7)["groups"] == []


def test_required_fields_and_thresholds():
    with pytest.raises(ValueError):
        analyze(sample().drop(columns=["posting_date"]))
    with pytest.raises(ValueError):
        analyze(sample(), min_daily=1)


def test_price_is_asking_not_transaction_weighted():
    data = sample()
    data.loc[data["id"] == "1-0", "price"] = 90000
    result = analyze(data)
    assert result["groups"][0]["daily"][0]["median_asking_price"] == 10135
