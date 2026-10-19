"""Test della risposta parlata."""
import json

from custom_components.needle.responses import (
    ERRORE_DISPOSITIVO,
    ERRORE_GENERICO,
    NON_DOMOTICA,
    NOTA_CONDIZIONALE,
    ToolOutcome,
    build_response,
    serialize_outcomes,
)

LIVE = "homeassistant__GetLiveContext"


def action(name, names, speech=""):
    return ToolOutcome(
        name=name,
        data={
            "speech": {"plain": {"speech": speech}} if speech else {},
            "response_type": "action_done",
            "data": {"success": [{"name": n, "type": "entity", "id": "x"} for n in names], "failed": []},
        },
        error=False,
        read_only=False,
    )


def live(entities_yaml):
    return ToolOutcome(
        name=LIVE,
        data={"result": "Live Context: An overview of the areas and the devices in this smart home:\n" + entities_yaml},
        error=False,
        read_only=True,
    )


TEMP_55 = "- names: Temperatura bagno\n  domain: sensor\n  state: '55'\n  attributes:\n    unit_of_measurement: °C\n"
LUCE_ON = "- names: Luce bagno, Bagno\n  domain: light\n  state: 'on'\n  areas: Bagno\n"


def test_no_outcomes_is_non_domotica():
    assert build_response("raccontami una barzelletta", []) == NON_DOMOTICA


def test_single_action_from_template():
    assert build_response("spegni la luce", [action("HassTurnOff", ["Luce bagno"])]) == "Ho spento Luce bagno."


def test_template_preferred_over_ha_speech():
    out = action("HassTurnOff", ["Luce bagno"], speech="Turned off the light")
    assert build_response("spegni la luce", [out]) == "Ho spento Luce bagno."


def test_ha_speech_used_when_no_template():
    out = action("HassStartTimer", [], speech="Timer avviato")
    assert build_response("timer di 10 minuti", [out]) == "Timer avviato"


def test_multiple_actions_joined():
    outs = [action("HassTurnOff", ["Luce bagno"]), action("HassTurnOn", ["Luce cucina"])]
    assert build_response("spegni il bagno e accendi la cucina", outs) == "Ho spento Luce bagno. Ho acceso Luce cucina."


def test_action_without_targets_is_fatto():
    assert build_response("timer di 10 minuti", [action("HassStartTimer", [])]) == "Fatto."


def test_action_error_not_found():
    out = ToolOutcome(name="HassTurnOn", data={"error": "MatchFailedError", "error_text": "No entity named x"}, error=True, read_only=False)
    assert build_response("accendi x", [out]) == ERRORE_DISPOSITIVO


def test_action_error_generic():
    out = ToolOutcome(name="HassTurnOn", data={"error": "HomeAssistantError"}, error=True, read_only=False)
    assert build_response("accendi x", [out]) == ERRORE_GENERICO


def test_question_reads_state():
    assert build_response("la luce del bagno è accesa?", [live(LUCE_ON)]) == "Luce bagno: acceso."


def test_question_with_unit():
    assert build_response("quanti gradi in bagno?", [live(TEMP_55)]) == "Temperatura bagno: 55 °C."


def test_conditional_false():
    expected = "Ho controllato ora: Temperatura bagno: 55 °C. Non ho fatto nulla e non ho creato una regola."
    assert build_response("se la temperatura del bagno è sopra 60 spegni la luce", [live(TEMP_55)]) == expected


def test_conditional_true_adds_note():
    outs = [live(TEMP_55), action("HassTurnOff", ["Luce bagno"])]
    result = build_response("se la temperatura del bagno è sopra 50 spegni la luce", outs)
    assert result == f"Ho spento Luce bagno. {NOTA_CONDIZIONALE}"


def test_read_error_is_not_found():
    out = ToolOutcome(name=LIVE, data={"error": "No device named x"}, error=True, read_only=True)
    assert build_response("la luce x è accesa?", [out]) == ERRORE_DISPOSITIVO


def test_many_entities_truncated():
    yaml_text = "".join(f"- names: Luce {i}\n  domain: light\n  state: 'off'\n" for i in range(8))
    result = build_response("com'è la casa?", [live(yaml_text)])
    assert result.startswith("Luce 0: spento; Luce 1: spento")
    assert "Luce 5" not in result
    assert result.endswith("e altri 3.")


def test_serialize_outcomes():
    payload = json.loads(serialize_outcomes([live(TEMP_55)]))
    assert payload[0]["tool"] == LIVE
    assert payload[0]["error"] is False
    assert "55" in payload[0]["data"]["result"]


def datetime_outcome(data):
    return ToolOutcome(name="llm__GetDateTime", data=data, error=False, read_only=True)


def test_get_date_time_template():
    out = datetime_outcome({"date": "2026-10-19", "time": "14:05:33", "timezone": "CEST", "weekday": "Monday"})
    assert build_response("che ore sono?", [out]) == "Sono le 14:05."


def test_get_date_time_without_time_is_fatto():
    assert build_response("che ore sono?", [datetime_outcome({"date": "2026-10-19"})]) == "Fatto."


def test_successful_read_without_description_is_fatto():
    out = ToolOutcome(name="qualcosa__Leggi", data={"result": "ok"}, error=False, read_only=True)
    assert build_response("dimmi qualcosa", [out]) == "Fatto."


def test_quando_question_is_plain_answer():
    result = build_response("quando si è accesa la luce del bagno?", [live(LUCE_ON)])
    assert result == "Luce bagno: acceso."
