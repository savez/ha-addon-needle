"""Smoke test con il modello vero (scarica ~35 MB). Esegui con: -m slow"""
import os

import pytest

from app.assets import ensure_assets, needle_factory
from app.engine import NeedleEngine

TOOLS = [
    {
        "name": "HassTurnOn",
        "description": "Turns on a device or entity",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "area": {"type": "string"}}},
    },
    {
        "name": "HassTurnOff",
        "description": "Turns off a device or entity",
        "parameters": {"type": "object", "properties": {"name": {"type": "string"}, "area": {"type": "string"}}},
    },
]


@pytest.mark.slow
def test_real_model_turns_off(tmp_path_factory):
    os.environ["NEEDLE_TELEMETRY"] = "0"
    data_dir = tmp_path_factory.getbasetemp() / "needle-data"
    weights = ensure_assets(data_dir)
    engine = NeedleEngine(needle_factory(weights))
    result = engine.infer(TOOLS, ["spegni la luce della cucina"])
    names = [call["name"] for call in result["function_calls"]]
    assert names == ["HassTurnOff"]
    again = engine.infer(TOOLS, ["spegni la luce della cucina"])
    assert again["function_calls"] == result["function_calls"], "la riesecuzione deve essere deterministica"
