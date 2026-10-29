"""Historical descriptive asking-price and listing-count analytics."""
import argparse
import hashlib
import json
from pathlib import Path

import pandas as pd

REQUIRED = {"id", "price", "posting_date", "manufacturer", "model_family", "year", "odometer"}
MIN_DAILY = 5
MIN_TOTAL = 20


def analyze(data, min_daily=MIN_DAILY, min_total=MIN_TOTAL):
    """Analyze an existing curated listing snapshot; never return price forecasts."""
    missing = REQUIRED - set(data.columns)
    if missing:
        raise ValueError("Curated dataset missing columns: " + ", ".join(sorted(missing)))
    if min_daily < 2 or min_total < min_daily:
        raise ValueError("Invalid sample thresholds")
    raw_count = len(data)
    df = data.copy()
    df["posting_date"] = pd.to_datetime(df["posting_date"], utc=True, errors="coerce")
    missing_date = int(df["posting_date"].isna().sum())
    duplicates = int(df["id"].duplicated().sum())
    df = df.drop_duplicates(subset="id")
    for key in ["price", "year", "odometer"]:
        df[key] = pd.to_numeric(df[key], errors="coerce")
    valid = (
        df["posting_date"].notna()
        & df["price"].between(1000, 100000)
        & df["year"].between(1990, 2100)
        & df["odometer"].between(0, 300000)
        & df["manufacturer"].notna()
        & df["model_family"].notna()
    )
    invalid = int((~valid).sum())
    df = df.loc[valid].copy()
    for col in ["manufacturer", "model_family"]:
        df[col] = df[col].astype(str).str.strip().str.lower()
    df = df[(df["manufacturer"] != "") & (df["model_family"] != "")]
    df["day"] = df["posting_date"].dt.strftime("%Y-%m-%d")
    groups = []
    for (make, model, year), rows in df.groupby(
        ["manufacturer", "model_family", "year"], sort=True
    ):
        if len(rows) < min_total:
            continue
        daily = (
            rows.groupby("day", sort=True)
            .agg(count=("id", "size"), median_asking_price=("price", "median"),
                 median_odometer=("odometer", "median"))
            .reset_index()
        )
        supported = daily.loc[daily["count"] >= min_daily]
        if len(supported) < 2:
            continue
        groups.append({
            "manufacturer": make, "model_family": model, "vehicle_year": int(year),
            "total_listings": int(len(rows)), "observed_days": int(len(daily)),
            "supported_days": int(len(supported)),
            "first_date": str(daily["day"].iloc[0]),
            "last_date": str(daily["day"].iloc[-1]),
            "daily": [{
                "date": str(r.day), "listing_count": int(r.count),
                "median_asking_price": round(float(r.median_asking_price), 2),
                "median_odometer": round(float(r.median_odometer), 1),
            } for r in supported.itertuples(index=False)],
        })
    groups.sort(key=lambda x: (-x["total_listings"], x["manufacturer"], x["model_family"], x["vehicle_year"]))
    return {
        "metadata": {
            "source": "curated Craigslist historical asking-price listings",
            "source_rows": int(raw_count), "usable_rows": int(len(df)),
            "missing_dates": missing_date, "duplicate_ids": duplicates,
            "invalid_after_dedup": invalid,
            "earliest_date": df["day"].min() if len(df) else None,
            "latest_date": df["day"].max() if len(df) else None,
            "distinct_observed_days": int(df["day"].nunique()),
            "min_daily_listings": min_daily, "min_total_listings": min_total,
            "comparison": "make + normalized model family + model year",
            "forecasting": "not_supported",
            "caution": "Historical sampled asking prices, not sales or live inventory. "
                       "Listing counts are observed dataset records, not market-wide supply. "
                       "Changes may reflect location, trim, mileage, condition or seller mix.",
        },
        "groups": groups,
    }


def run(curated_path, output_dir, min_daily=MIN_DAILY, min_total=MIN_TOTAL):
    path = Path(curated_path)
    if path.is_dir():
        files = sorted(path.rglob("*.parquet"))
        if not files:
            raise ValueError("No curated Parquet files found")
        df = pd.read_parquet(path)
    else:
        if path.suffix != ".parquet":
            raise ValueError("Expected curated Parquet input")
        files = [path]
        df = pd.read_parquet(path)
    payload = analyze(df, min_daily, min_total)
    inputs = []
    for item in files:
        digest = hashlib.sha256()
        with item.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        inputs.append({
            "path": str(item.relative_to(path) if path.is_dir() else item.name),
            "sha256": digest.hexdigest(),
        })
    payload["metadata"]["inputs"] = inputs
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "market_intelligence.json").write_text(
        json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8"
    )
    return payload


def main():
    parser = argparse.ArgumentParser(description="Historical asking-price snapshot trends")
    parser.add_argument("--curated-path", required=True)
    parser.add_argument("--output-dir", default="market-intelligence-output")
    parser.add_argument("--min-daily", type=int, default=MIN_DAILY)
    parser.add_argument("--min-total", type=int, default=MIN_TOTAL)
    args = parser.parse_args()
    result = run(args.curated_path, args.output_dir, args.min_daily, args.min_total)
    print(json.dumps({"groups": len(result["groups"]), "metadata": result["metadata"]}, indent=2))


if __name__ == "__main__":
    main()
