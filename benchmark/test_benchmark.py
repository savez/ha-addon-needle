"""Test della logica del benchmark."""
from pathlib import Path

from benchmark import Case, Step, load_cases, run, score_step


def test_score_exact_tool_and_args():
    atteso = [{"tool": "HassTurnOff", "argomenti": {"name": "bagno"}}]
    calls = [{"name": "homeassistant__HassTurnOff", "arguments": {"name": "Luce del Bagno"}}]
    assert score_step(atteso, calls) == (True, True)


def test_score_wrong_args():
    atteso = [{"tool": "HassLightSet", "argomenti": {"brightness": 50}}]
    calls = [{"name": "HassLightSet", "arguments": {"brightness": 80}}]
    assert score_step(atteso, calls) == (True, False)


def test_score_wrong_tool():
    atteso = [{"tool": "HassTurnOff"}]
    calls = [{"name": "HassTurnOn", "arguments": {}}]
    assert score_step(atteso, calls) == (False, False)


def test_score_expected_none():
    assert score_step([], []) == (True, True)
    assert score_step([], [{"name": "HassTurnOn", "arguments": {}}]) == (False, False)


def test_score_multiple_any_order():
    atteso = [{"tool": "HassTurnOn"}, {"tool": "HassTurnOff"}]
    calls = [{"name": "HassTurnOff", "arguments": {}}, {"name": "HassTurnOn", "arguments": {}}]
    assert score_step(atteso, calls) == (True, True)


def test_load_cases(tmp_path):
    path = tmp_path / "frasi.yaml"
    path.write_text(
        "- frase: spegni\n  atteso: [{tool: HassTurnOff}]\n"
        "- frase: se caldo spegni\n  passi:\n    - atteso: [{tool: GetLiveContext}]\n      risultato: '[]'\n    - atteso: [{tool: HassTurnOff}]\n"
    )
    cases = load_cases(path)
    assert cases[0].passi == [Step(atteso=[{"tool": "HassTurnOff"}], risultato=None)]
    assert len(cases[1].passi) == 2
    assert cases[1].passi[0].risultato == "[]"


def test_run_sends_simulated_results_as_turns():
    seen = []

    def infer(tools, turni):
        seen.append(list(turni))
        name = "GetLiveContext" if len(turni) == 1 else "HassTurnOff"
        return {"function_calls": [{"name": name, "arguments": {}}], "confidence": 0.4, "durata_ms": 100}

    case = Case(frase="se caldo spegni", passi=[Step([{"tool": "GetLiveContext"}], "[R]"), Step([{"tool": "HassTurnOff"}], None)])
    report = run([case], [], infer)
    assert seen == [["se caldo spegni"], ["se caldo spegni", "[R]"]]
    assert report.passi_tool_ok == 2
    assert "2/2" in report.summary()
