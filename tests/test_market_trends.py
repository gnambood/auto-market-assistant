import pandas as pd
import pytest

from pipelines.market_trends import build_market_trends, write_viewer


def rows():
    return pd.DataFrame([
        {"id": "a", "manufacturer": "ford", "model_family": "f 150",
         "year": 2018, "posting_date": "2021-05-01", "price": 10000},
        {"id": "b", "manufacturer": "ford", "model_family": "f 150",
         "year": 2018, "posting_date": "2021-05-01", "price": 12000},
        {"id": "c", "manufacturer": "ford", "model_family": "f 150",
         "year": 2018, "posting_date": "2021-05-02", "price": 14000},
        {"id": "d", "manufacturer": "ford", "model_family": "f 150",
         "year": 2018, "posting_date": "2021-05-02", "price": 16000},
        {"id": "d", "manufacturer": "ford", "model_family": "f 150",
         "year": 2018, "posting_date": "2021-05-02", "price": 50000},
        {"id": "e", "manufacturer": "ford", "model_family": "f 150",
         "year": 2018, "posting_date": None, "price": 9000},
        {"id": "f", "manufacturer": "honda", "model_family": "civic",
         "year": 2019, "posting_date": "2021-05-01", "price": 15000},
    ])


def test_deduplicates_and_reports_missing_dates():
    daily, coverage, stats = build_market_trends(rows(), min_group=4, min_days=2, min_daily=2)
    selected = daily.loc[daily["manufacturer"] == "ford"]
    assert selected["listing_count"].tolist() == [2, 2]
    assert selected["median_asking_price"].tolist() == [11000, 15000]
    assert stats["duplicate_listing_ids_removed"] == 1
    assert stats["missing_or_invalid_posting_dates"] == 1
    assert stats["eligible_groups"] == 1
    assert coverage.loc[coverage["manufacturer"] == "honda", "eligible"].iloc[0] == False


def test_sparse_daily_prices_suppressed_but_counts_retained():
    daily, _, stats = build_market_trends(rows(), min_group=4, min_days=2, min_daily=3)
    ford = daily.loc[daily["manufacturer"] == "ford"]
    assert ford["listing_count"].sum() == 4
    assert ford["median_asking_price"].isna().all()
    assert stats["suppressed_daily_price_observations"] >= 2


def test_empty_input_and_invalid_schema():
    empty = rows().iloc[:0]
    daily, coverage, stats = build_market_trends(empty)
    assert daily.empty and coverage.empty and stats["eligible_groups"] == 0
    with pytest.raises(ValueError):
        build_market_trends(pd.DataFrame({"price": [1]}))


def test_offline_viewer_has_no_remote_chart_dependencies(tmp_path):
    daily, _, _ = build_market_trends(rows(), min_group=4, min_days=2, min_daily=2)
    output = tmp_path / "index.html"
    write_viewer(daily, output)
    html = output.read_text(encoding="utf-8")
    assert "Historical market trends" in html
    assert "11000.0" in html
    assert "cdn" not in html.lower()
