"""Regression tests for descriptive market intelligence."""

import pandas as pd
import pytest

from pipelines.market_trends import daily_listing_volume, monthly_market_trends


def example():
    return pd.DataFrame(
        [
            {"id": "a", "manufacturer": "ford", "model_family": "f 150", "year": 2018,
             "price": 10000, "posting_date": "2021-01-05"},
            {"id": "b", "manufacturer": "ford", "model_family": "f 150", "year": 2018,
             "price": 14000, "posting_date": "2021-01-06"},
            {"id": "b", "manufacturer": "ford", "model_family": "f 150", "year": 2018,
             "price": 999999, "posting_date": "2021-01-06"},
            {"id": "c", "manufacturer": "ford", "model_family": "f 150", "year": 2018,
             "price": 17000, "posting_date": "2021-02-06"},
            {"id": "d", "manufacturer": "ford", "model_family": "f 150", "year": 2019,
             "price": 20000, "posting_date": "2021-01-06"},
            {"id": "e", "manufacturer": "ford", "model_family": "f 150", "year": 2018,
             "price": 15000, "posting_date": "no date"},
        ]
    )


def test_grouping_is_by_posting_month_and_vehicle_year():
    result, info = monthly_market_trends(example(), min_listings=2)
    assert len(result) == 1
    row = result.iloc[0]
    assert (row["month"], row["year"], row["listing_count"]) == ("2021-01", 2018, 2)
    assert row["median_asking_price"] == 12000
    assert info["duplicate_id_rows"] == 1
    assert info["invalid_posting_dates"] == 1
    assert info["suppressed_small_groups"] == 2


def test_small_groups_suppressed():
    result, info = monthly_market_trends(example(), min_listings=3)
    assert result.empty
    assert info["suppressed_small_groups"] == 3


def test_bad_inputs_explained():
    with pytest.raises(ValueError, match="Missing required columns"):
        monthly_market_trends(pd.DataFrame({"price": [10]}))
    with pytest.raises(ValueError, match="min_listings must be positive"):
        monthly_market_trends(example(), min_listings=0)
    with pytest.raises(ValueError, match="min_listings must be positive"):
        daily_listing_volume(example(), min_listings=0)


def test_invalid_price_is_not_counted():
    records = example()
    records.loc[1, "price"] = -20
    result, info = monthly_market_trends(records, min_listings=1)
    assert info["invalid_asking_prices"] == 1
    assert result.loc[result["month"].eq("2021-01") & result["year"].eq(2018), "listing_count"].iloc[0] == 1


def test_daily_counts_are_not_model_year_counts():
    daily, info = daily_listing_volume(example())
    jan_sixth = daily[daily["date"].eq("2021-01-06")]
    assert jan_sixth["listing_count"].sum() == 2
    assert jan_sixth["year"].tolist() == [2018, 2019]
    assert info["rows_after_validation"] == 4


def test_repeatable_on_identical_input():
    first, first_info = monthly_market_trends(example(), min_listings=1)
    second, second_info = monthly_market_trends(example(), min_listings=1)
    pd.testing.assert_frame_equal(first, second)
    assert first_info == second_info
