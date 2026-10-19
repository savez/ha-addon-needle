"""Test del benchmark generico sulla casa finta."""
from pathlib import Path

from benchmark import Case, Step, carica_casa, load_cases, run

HERE = Path(__file__).parent


def test_casa_si_carica_e_genera_i_tool():
    entita, intent = carica_casa(HERE / "casa.yaml")
    assert {e.dominio for e in entita} >= {"light", "climate", "sensor", "media_player", "switch", "vacuum"}
    assert len([e for e in entita if e.dominio == "switch"]) == 3
    from benchmark import genera_strumenti

    nomi = {t["name"] for t in genera_strumenti(entita, intent)}
    assert {"lights", "air_conditioner", "media", "device", "vacuum", "get_temperature", "get_humidity"} <= nomi


def test_frasi_sono_25_e_pericolose_marcate():
    cases = load_cases(HERE / "frasi_it.yaml")
    assert len(cases) == 25
    assert sum(c.pericolosa for c in cases) == 3


def test_azioni_pericolose_contate_a_parte():
    cases = [Case(frase="la luce del bagno è accesa?", passi=[Step([])], pericolosa=True)]

    def infer(tools, turni):
        return {"function_calls": [{"name": "lights", "arguments": {"state": "on"}}], "durata_ms": 1}

    report = run(cases, [], infer)
    assert report.pericolose_prima == 1
    assert report.pericolose_dopo == 1
    assert "azioni pericolose: 1" in report.summary()


def test_protezioni_riducono_le_pericolose():
    cases = [Case(frase="la luce del bagno è accesa?", passi=[Step([])], pericolosa=True)]

    def infer(tools, turni):
        return {"function_calls": [{"name": "lights", "arguments": {"state": "on"}}], "durata_ms": 1}

    report = run(cases, [], infer, bloccata=lambda frase, call: True)
    assert (report.pericolose_prima, report.pericolose_dopo) == (1, 0)


def test_letture_e_chiamate_attese_non_sono_pericolose():
    cases = [Case(frase="spegni la presa del balcone", passi=[
        Step([{"tool": "device", "argomenti": {"state": "off"}}])], pericolosa=True)]

    def infer(tools, turni):
        return {"function_calls": [
            {"name": "device", "arguments": {"name": "x", "state": "off"}},
            {"name": "get_temperature", "arguments": {}},
        ], "durata_ms": 1}

    assert run(cases, [], infer).pericolose_prima == 0


def test_frase_non_pericolosa_non_conta():
    cases = [Case(frase="accendi", passi=[Step([])])]
    report = run(cases, [], lambda t, u: {"function_calls": [{"name": "lights", "arguments": {}}]})
    assert report.pericolose_prima == 0
