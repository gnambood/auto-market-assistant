"""Regression tests: review evidence must match the selected vehicle model."""
from types import SimpleNamespace
import pandas as pd
from api.services import RagEngine

REVIEWS = pd.DataFrame({"manufacturer": ["ford", "ford", "ford"], "model_family": ["f 150", "escape", "escape"], "vehicle_year": [2018, 2018, 2017]})

def scope(model, year, k=5):
    request = SimpleNamespace(manufacturer="ford", model=model, year=year, k=k)
    return RagEngine._candidate_scope(REVIEWS, request)

def test_sparse_family_never_expands_to_entire_manufacturer():
    mask, label = scope("f-150", 2018, 10)
    assert REVIEWS.loc[mask, "model_family"].tolist() == ["f 150"]
    assert label == "same model family, year ±1"

def test_old_year_can_expand_only_within_family():
    mask, label = scope("escape", 2001)
    assert REVIEWS.loc[mask, "model_family"].tolist() == ["escape", "escape"]
    assert label == "same model family"

def test_unknown_model_returns_no_evidence():
    mask, _ = scope("bronco", 2018)
    assert not mask.any()
