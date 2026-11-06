"""Feature-schema checks without loading the heavyweight CatBoost model."""

from types import SimpleNamespace

import pytest

from api.price_engine import resolve_features


def test_model_feature_names_used_when_metrics_omit_them():
    model = SimpleNamespace(feature_names_=["manufacturer", "vehicle_age"])
    assert resolve_features({}, model) == ["manufacturer", "vehicle_age"]


def test_saved_feature_order_must_match_trained_model():
    model = SimpleNamespace(feature_names_=["manufacturer", "vehicle_age"])
    with pytest.raises(ValueError, match="differs"):
        resolve_features({"selected_features": ["vehicle_age", "manufacturer"]}, model)


def test_feature_names_cannot_be_guessed():
    with pytest.raises(ValueError, match="No feature names"):
        resolve_features({}, SimpleNamespace(feature_names_=[]))
