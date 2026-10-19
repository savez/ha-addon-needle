"""Test del benchmark generico sulla casa finta."""
from pathlib import Path

import re

from benchmark import Case, Step, carica_casa, chiamata_bloccata, genera_strumenti, load_cases, run

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
    assert "azioni pericolose (frasi marcate): 1 dopo le protezioni (1 prima)" in report.summary()


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


def test_azioni_sbagliate_contate_su_tutte_le_frasi():
    cases = [
        Case(frase="accendi la luce del bagno", passi=[Step([{"tool": "lights", "argomenti": {"room": "Bagno"}}])]),
        Case(frase="temperatura bagno", passi=[Step([{"tool": "get_temperature"}])]),
    ]

    def infer(tools, turni):
        if "luce" in turni[0]:
            return {"function_calls": [{"name": "air_conditioner", "arguments": {"state": "on"}}]}
        return {"function_calls": [{"name": "get_humidity", "arguments": {}}]}

    report = run(cases, [], infer, bloccata=lambda frase, call: False)
    assert (report.sbagliate_prima, report.sbagliate_dopo) == (1, 1)
    assert report.pericolose_prima == 0
    assert "azioni sbagliate eseguite (tutte le frasi): 1 dopo le protezioni (1 prima)" in report.summary()


def test_protezioni_reali_domanda_e_dispositivo_non_nominato():
    cases = [
        Case(frase="la luce del bagno è accesa?", passi=[Step([])], pericolosa=True),
        Case(
            frase="accendi la presa dell'albero di natale",
            passi=[Step([{"tool": "device", "argomenti": {"name": "albero"}}])],
            pericolosa=True,
        ),
        Case(frase="accendi la luce del bagno", passi=[Step([{"tool": "lights", "argomenti": {"room": "Bagno"}}])]),
    ]

    def infer(tools, turni):
        if "bagno è accesa" in turni[0]:
            return {"function_calls": [{"name": "lights", "arguments": {"state": "on"}}]}
        if "presa" in turni[0]:
            return {"function_calls": [{"name": "device", "arguments": {"name": "presa-balcone Presa", "state": "on"}}]}
        return {"function_calls": [{"name": "air_conditioner", "arguments": {"state": "on"}}]}

    report = run(cases, [], infer, bloccata=chiamata_bloccata)
    assert (report.pericolose_prima, report.pericolose_dopo) == (2, 0)
    # la terza è un'azione sbagliata che le protezioni non possono fermare
    assert (report.sbagliate_prima, report.sbagliate_dopo) == (3, 1)


def test_intent_della_casa_sono_quelli_noti_al_generatore():
    sorgente = (HERE.parent / "custom_components" / "needle" / "strumenti.py").read_text(encoding="utf-8")
    noti = set(re.findall(r"\b(?:Hass[A-Za-z]+|GetLiveContext|GetDateTime)\b", sorgente))
    _, intent = carica_casa(HERE / "casa.yaml")
    assert intent == noti


def test_atteso_delle_frasi_valido_per_i_tool_generati():
    entita, intent = carica_casa(HERE / "casa.yaml")
    tools = {t["name"]: t["parameters"]["properties"] for t in genera_strumenti(entita, intent)}
    for case in load_cases(HERE / "frasi_it.yaml"):
        for passo in case.passi:
            for item in passo.atteso:
                assert item["tool"] in tools, case.frase
                for chiave, valore in (item.get("argomenti") or {}).items():
                    schema = tools[item["tool"]][chiave]
                    if isinstance(valore, (int, float)) and not isinstance(valore, bool):
                        assert schema.get("minimum", valore) <= valore <= schema.get("maximum", valore), case.frase
                    elif "enum" in schema:
                        assert any(str(valore).lower() in e.lower() for e in schema["enum"]), (case.frase, chiave)
