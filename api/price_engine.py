"""Price inference and historical comparable listings."""

import json

from .runtime import ensure_artifacts, normalize_model


class PriceEngine:
    def __init__(self):
        import pandas as pd
        from catboost import CatBoostRegressor
        self.pd = pd
        paths = ensure_artifacts()
        self.vehicles = pd.read_parquet(paths["vehicles_clean.parquet"])

        # The Part 1 export stores the cleaned modeling table before the
        # V2 model_family experiment column is added. Reconstruct that
        # deterministic feature at serving time so market-comparable lookup
        # uses the same two-token family convention as the trained model.
        self.vehicles["model_family"] = self.vehicles["model"].map(
            lambda value: " ".join(normalize_model(value).split()[:2])
        )

        with open(paths["model_improvement_metrics.json"]) as f:
            self.metrics = json.load(f)
        self.model = CatBoostRegressor()
        self.model.load_model(paths["price_model.cbm"])
        self.features = self.metrics["selected_features"]
        self.use_bias = bool(self.metrics.get("bias_correction_used", False))
        self.bias = float(self.metrics.get("bias_correction", 0.0))
        self.market_year = int(self.vehicles["posting_year"].mode().iloc[0]) if "posting_year" in self.vehicles.columns else 2021

    @staticmethod
    def _text(value):
        return "unknown" if value is None else str(value).lower().strip()

    def _row(self, payload):
        age = max(self.market_year - int(payload.year), 0)
        model_norm = normalize_model(payload.model)
        family = " ".join(model_norm.split()[:2])
        row = {
            "manufacturer": payload.manufacturer.lower().strip(),
            "model": model_norm,
            "vehicle_age": age,
            "odometer": float(payload.mileage),
            "condition": self._text(payload.condition),
            "fuel": self._text(payload.fuel),
            "title_status": self._text(payload.title_status),
            "transmission": self._text(payload.transmission),
            "drive": self._text(payload.drive),
            "type": self._text(payload.vehicle_type),
            "state": self._text(payload.state),
            "vehicle_year": int(payload.year),
            "miles_per_year": float(payload.mileage) / max(age, 1),
            "condition_missing": int(payload.condition is None),
            "fuel_missing": int(payload.fuel is None),
            "title_status_missing": int(payload.title_status is None),
            "transmission_missing": int(payload.transmission is None),
            "drive_missing": int(payload.drive is None),
            "type_missing": int(payload.vehicle_type is None),
            "model_family": family,
        }
        return self.pd.DataFrame([row])[self.features], family, age

    def predict(self, payload):
        X, family, age = self._row(payload)
        make = payload.manufacturer.lower().strip()
        same = self.vehicles["manufacturer"].eq(make) & self.vehicles["model_family"].eq(family)
        if not same.any():
            raise ValueError("No historical listings exist for the selected make and model family.")

        prediction = float(self.model.predict(X)[0])
        if self.use_bias:
            prediction += self.bias

        window = max(25000.0, float(payload.mileage) * 0.30)
        narrow = self.vehicles[
            same
            & self.vehicles["vehicle_age"].between(max(age - 2, 0), age + 2)
            & self.vehicles["odometer"].between(max(float(payload.mileage) - window, 0), float(payload.mileage) + window)
        ]

        if len(narrow) >= 10:
            comps, scope = narrow, "same model family + similar age/mileage"
        else:
            comps, scope = self.vehicles[same], "same model family"

        if len(comps) < 10:
            comps = self.vehicles[self.vehicles["manufacturer"].eq(make)]
            scope = "same manufacturer"

        return {
            "predicted_price": round(prediction, 0),
            "comparable_count": int(len(comps)),
            "comparable_median": round(float(comps["price"].median()), 0),
            "comparable_q25": round(float(comps["price"].quantile(0.25)), 0),
            "comparable_q75": round(float(comps["price"].quantile(0.75)), 0),
            "comparable_scope": scope,
            "market_year": self.market_year,
        }
