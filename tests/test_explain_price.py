"""Pure numerical checks for the explainability summary."""

import pytest

from research.explain_price import summarize_shap


def test_ranking_uses_mean_absolute_shap_and_ignores_bias():
    report = summarize_shap([[1, -2, 100], [-3, -4, 100]], ["mileage", "age"])
    assert report == [
        {"feature": "age", "mean_abs_shap": 3.0},
        {"feature": "mileage", "mean_abs_shap": 2.0},
    ]


def test_mismatched_shap_shape_is_rejected():
    with pytest.raises(ValueError, match="bias column"):
        summarize_shap([[1, 2]], ["mileage", "age"])
