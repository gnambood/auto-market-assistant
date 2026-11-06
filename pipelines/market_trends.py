"""Descriptive trends in historical vehicle asking prices and listing volume.

The time axis is listing posting date, not the vehicle's model year.
The aggregates are descriptive; they are not predictions or sale prices.
"""

import pandas as pd

GROUP = ["manufacturer", "model_family", "year"]
COLUMNS = ["id", *GROUP, "posting_date", "price"]


def _clean_listings(listings: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Keep unique, usable listings and report how many records were excluded."""
    missing = sorted(set(COLUMNS) - set(listings.columns))
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    data = listings[COLUMNS].copy()
    diagnostics = {"raw_rows": len(data), "missing_id_rows": int(data["id"].isna().sum())}
    data = data.dropna(subset=["id"])
    diagnostics["duplicate_id_rows"] = int(data.duplicated("id").sum())
    data = data.drop_duplicates("id", keep="first")

    data["posting_date"] = pd.to_datetime(data["posting_date"], errors="coerce", utc=True)
    data["price"] = pd.to_numeric(data["price"], errors="coerce")
    data["year"] = pd.to_numeric(data["year"], errors="coerce")
    diagnostics.update(
        invalid_posting_dates=int(data["posting_date"].isna().sum()),
        invalid_asking_prices=int((data["price"].isna() | data["price"].le(0)).sum()),
        missing_group_fields=int(data[GROUP].isna().any(axis=1).sum()),
    )
    data = data.dropna(subset=GROUP + ["posting_date", "price"])
    data = data[data["price"] > 0].copy()
    diagnostics["rows_after_validation"] = len(data)
    diagnostics["months_available"] = int(data["posting_date"].dt.strftime("%Y-%m").nunique())
    diagnostics["scope"] = "historical asking prices, not sales, current valuations or forecasts"
    return data, diagnostics


def monthly_market_trends(
    listings: pd.DataFrame, *, min_listings: int = 10
) -> tuple[pd.DataFrame, dict]:
    """Report price distributions only for sufficiently populated monthly cohorts."""
    if min_listings < 1:
        raise ValueError("min_listings must be positive")

    data, diagnostics = _clean_listings(listings)
    data["month"] = data["posting_date"].dt.strftime("%Y-%m")
    keys = GROUP + ["month"]
    summary = (
        data.groupby(keys, observed=True)
        .agg(
            listing_count=("id", "size"),
            median_asking_price=("price", "median"),
            mean_asking_price=("price", "mean"),
        )
        .reset_index()
        .sort_values(keys)
        .reset_index(drop=True)
    )
    diagnostics["suppressed_small_groups"] = int(summary["listing_count"].lt(min_listings).sum())
    diagnostics["min_listings_per_group"] = min_listings
    return summary[summary["listing_count"] >= min_listings].reset_index(drop=True), diagnostics


def daily_listing_volume(
    listings: pd.DataFrame, *, min_listings: int = 1
) -> tuple[pd.DataFrame, dict]:
    """Count observed listings by vehicle cohort and posting date.

    These counts reflect the available snapshot, not complete market inventory.
    """
    if min_listings < 1:
        raise ValueError("min_listings must be positive")

    data, diagnostics = _clean_listings(listings)
    data["date"] = data["posting_date"].dt.strftime("%Y-%m-%d")
    keys = GROUP + ["date"]
    counts = (
        data.groupby(keys, observed=True)
        .size()
        .rename("listing_count")
        .reset_index()
        .sort_values(keys)
        .reset_index(drop=True)
    )
    diagnostics["suppressed_small_groups"] = int(counts["listing_count"].lt(min_listings).sum())
    diagnostics["min_listings_per_group"] = min_listings
    return counts[counts["listing_count"] >= min_listings].reset_index(drop=True), diagnostics
