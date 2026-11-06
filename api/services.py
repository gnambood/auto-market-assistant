"""Public serving helpers and the vehicle catalog.

Existing callers can continue importing PriceEngine and RagEngine here.
"""

import json
import re
from functools import lru_cache

from .runtime import ENABLE_GENERATION, ensure_artifacts, load_answerability_policy, normalize_model
from .price_engine import PriceEngine
from .review_engine import RagEngine
@lru_cache(maxsize=1)
def load_vehicle_catalog():
    import pandas as pd

    paths = ensure_artifacts()
    vehicles = pd.read_parquet(paths["vehicles_clean.parquet"])
    reviews = pd.read_parquet(paths["review_documents.parquet"])

    vehicles = vehicles.copy()
    vehicles["manufacturer"] = vehicles["manufacturer"].astype(str).str.lower().str.strip()
    vehicles["model_family"] = vehicles["model"].map(
        lambda value: " ".join(normalize_model(value).split()[:2])
    )

    # Fresh Part 1 exports can omit an explicit vehicle_year column.
    # Reconstruct it for catalog browsing from the persisted feature columns
    # instead of failing the whole /catalog request.
    market_year = (
        int(vehicles["posting_year"].mode().iloc[0])
        if "posting_year" in vehicles.columns and not vehicles["posting_year"].dropna().empty
        else 2021
    )
    if "vehicle_year" in vehicles.columns:
        vehicles["vehicle_year"] = pd.to_numeric(vehicles["vehicle_year"], errors="coerce")
    elif "year" in vehicles.columns:
        vehicles["vehicle_year"] = pd.to_numeric(vehicles["year"], errors="coerce")
    elif "vehicle_age" in vehicles.columns:
        vehicles["vehicle_year"] = market_year - pd.to_numeric(
            vehicles["vehicle_age"], errors="coerce"
        )
    else:
        raise RuntimeError(
            "Vehicle artifact is missing vehicle_year/year/vehicle_age; cannot build catalog"
        )

    reviews = reviews.copy()
    reviews["manufacturer"] = reviews["manufacturer"].astype(str).str.lower().str.strip()
    reviews["model_family"] = reviews["model_family"].astype(str).str.lower().str.strip()

    review_counts = (
        reviews.groupby(["manufacturer", "model_family"])
        .size()
        .rename("review_count")
    )
    listing_counts = (
        vehicles.groupby(["manufacturer", "model_family"])
        .size()
        .rename("listing_count")
    )

    supported = listing_counts.to_frame().join(review_counts, how="inner").reset_index()
    supported = supported[(supported["listing_count"] >= 20) & (supported["review_count"] >= 5)]

    if supported.empty:
        raise RuntimeError("No vehicle families have both listing and review support")

    top_makes = (
        supported.groupby("manufacturer")["listing_count"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .index
        .tolist()
    )

    def clean_mode(frame, column):
        if column not in frame.columns:
            return None
        values = frame[column].dropna().astype(str).str.lower().str.strip()
        values = values[~values.isin(["", "nan", "none", "unknown"])]
        if values.empty:
            return None
        return str(values.mode().iloc[0])

    manufacturers = []
    for make in top_makes:
        make_supported = supported[supported["manufacturer"].eq(make)]
        families = (
            make_supported.sort_values(["listing_count", "review_count"], ascending=False)
            .head(6)
            .to_dict("records")
        )

        models = []
        for family_row in families:
            family = family_row["model_family"]
            segment = vehicles[
                vehicles["manufacturer"].eq(make)
                & vehicles["model_family"].eq(family)
            ].copy()
            if segment.empty:
                continue

            raw_models = segment["model"].dropna().astype(str).str.strip()
            representative = str(raw_models.mode().iloc[0]) if not raw_models.empty else family

            years_series = pd.to_numeric(segment["vehicle_year"], errors="coerce").dropna()
            years_series = years_series[(years_series >= 1990) & (years_series <= 2030)]
            years = sorted({int(x) for x in years_series.tolist()}, reverse=True)
            if not years:
                continue

            mileage_series = pd.to_numeric(segment["odometer"], errors="coerce").dropna()
            mileage_series = mileage_series[(mileage_series >= 0) & (mileage_series <= 300000)]
            mileages = []
            if not mileage_series.empty:
                for value in mileage_series.quantile([0.25, 0.5, 0.75]).tolist():
                    rounded = int(round(float(value) / 5000.0) * 5000)
                    mileages.append(max(0, min(300000, rounded)))
                mileages = sorted(set(mileages))
            if not mileages:
                mileages = [50000, 100000, 150000]

            condition_values = []
            if "condition" in segment.columns:
                condition_values = (
                    segment["condition"].dropna().astype(str).str.lower().str.strip()
                    .value_counts().head(5).index.tolist()
                )
                condition_values = [x for x in condition_values if x not in {"", "nan", "none", "unknown"}]
            if not condition_values:
                condition_values = ["good"]

            defaults = {
                "fuel": clean_mode(segment, "fuel"),
                "title_status": clean_mode(segment, "title_status"),
                "transmission": clean_mode(segment, "transmission"),
                "drive": clean_mode(segment, "drive"),
                "vehicle_type": clean_mode(segment, "type"),
                "state": clean_mode(segment, "state"),
            }

            models.append({
                "value": representative.lower(),
                "label": representative.title(),
                "family": family,
                "years": years,
                "mileages": mileages,
                "conditions": condition_values,
                "defaults": defaults,
                "listing_count": int(family_row["listing_count"]),
                "review_count": int(family_row["review_count"]),
            })

        if models:
            manufacturers.append({
                "value": make,
                "label": make.title(),
                "models": models,
            })

    return {
        "market_year": market_year,
        "manufacturer_count": len(manufacturers),
        "model_count": sum(len(item["models"]) for item in manufacturers),
        "manufacturers": manufacturers,
    }

@lru_cache(maxsize=1)
def get_price_engine():
    return PriceEngine()

@lru_cache(maxsize=1)
def get_rag_engine():
    return RagEngine()

def load_public_metrics():
    paths = ensure_artifacts()
    output = {}

    for name in [
        "model_improvement_metrics.json",
        "rag_metrics.json",
    ]:
        path = paths.get(name)
        if path and path.exists():
            with open(path) as f:
                output[name] = json.load(f)

    output["answerability_runtime"] = {
        "policy": load_answerability_policy(),
        "generation_enabled": ENABLE_GENERATION,
        "scope_guard": "capability + exact-vehicle/current-data/specification",
        "retrieval_query": "question-only embedding after vehicle-family filtering",
    }
    return output
