"""Test end-to-end dell'agente con add-on simulato."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.const import CONF_URL
from homeassistant.core import Context
from homeassistant.helpers import area_registry as ar, entity_registry as er, intent
from homeassistant.setup import async_setup_component

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.needle.client import NeedleBadRequest, NeedleUnavailable
from custom_components.needle.const import CONF_MOSTRA_AVVISO, CONF_STRUMENTI, DOMAIN
from custom_components.needle.config_flow import DEFAULT_OPTIONS
from custom_components.needle.responses import (
    AVVISO_FALLBACK,
    CONDIZIONE_NON_VERIFICATA,
    DISPOSITIVO_INCERTO,
    DOMANDA_O_COMANDO,
    ERRORE_DISPOSITIVO,
    ERRORE_INTERNO,
    NON_DOMOTICA,
    NOTA_CONDIZIONALE,
)

AGENT = "conversation.needle_local_ai"


def tool_name(tools, suffix):
    return next(t["name"] for t in tools if t["name"].endswith(suffix))


def call(tool, /, **args):
    return {"name": tool, "arguments": args}


def needle_reply(*calls, ungrounded=()):
    return {"type": "call", "function_calls": list(calls), "confidence": 0.5, "validation": {"ungrounded": list(ungrounded)}}


async def _casa(hass):
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "conversation", {})
    assert await async_setup_component(hass, "vacuum", {})
    bagno = ar.async_get(hass).async_create("Bagno")
    registry = er.async_get(hass)
    for entity_id, nome in (("light.bagno", "Luce bagno"), ("sensor.temp_bagno", "Temperatura bagno")):
        dominio, oggetto = entity_id.split(".")
        registry.async_get_or_create(dominio, "test", oggetto, suggested_object_id=oggetto, original_name=nome)
        registry.async_update_entity(entity_id, area_id=bagno.id)
    hass.states.async_set("light.bagno", "on", {"friendly_name": "Luce bagno"})
    hass.states.async_set("light.cucina", "off", {"friendly_name": "Luce cucina"})
    hass.states.async_set("light.garage", "off", {"friendly_name": "Luce garage"})
    hass.states.async_set("sensor.temp_bagno", "55", {"friendly_name": "Temperatura bagno", "unit_of_measurement": "°C", "device_class": "temperature"})
    hass.states.async_set("sensor.umido_cameretta", "48", {"friendly_name": "cameretta Umidità", "unit_of_measurement": "%", "device_class": "humidity"})
    hass.states.async_set("sensor.temp_cameretta", "21", {"friendly_name": "cameretta Temperatura", "unit_of_measurement": "°C", "device_class": "temperature"})
    hass.states.async_set("vacuum.robot", "docked", {"friendly_name": "Robot", "supported_features": 8192})
    for entity_id in ("light.bagno", "light.cucina", "sensor.temp_bagno", "sensor.umido_cameretta", "sensor.temp_cameretta", "vacuum.robot"):
        async_expose_entity(hass, "conversation", entity_id, True)
    async_expose_entity(hass, "conversation", "light.garage", False)


async def _entry(hass, **options):
    await _casa(hass)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://needle.test:8765"}, options={**DEFAULT_OPTIONS, **options})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


@pytest.fixture
async def setup(hass):
    """Tool generati (predefinito)."""
    return await _entry(hass)


@pytest.fixture
async def setup_assist(hass):
    """Tool dell'API Assist, come prima dei tool generati."""
    return await _entry(hass, **{CONF_STRUMENTI: "assist"})


async def converse(hass, text):
    result = await conversation.async_converse(hass, text, None, Context(), language="it", agent_id=AGENT)
    return result.response.speech["plain"]["speech"]


def patch_infer(side_effect):
    return patch("custom_components.needle.client.NeedleClient.infer", AsyncMock(side_effect=side_effect))


async def test_single_action(hass, setup_assist):
    off = async_mock_service(hass, "light", "turn_off")

    async def infer(tools, turni):
        return needle_reply(call(tool_name(tools, "HassTurnOff"), name="Luce bagno"))

    with patch_infer(infer):
        speech = await converse(hass, "spegni la luce del bagno")
    assert [c.data["entity_id"] for c in off] == [["light.bagno"]]
    assert speech == "Ho spento Luce bagno."


async def test_multiple_actions(hass, setup_assist):
    off = async_mock_service(hass, "light", "turn_off")
    on = async_mock_service(hass, "light", "turn_on")

    async def infer(tools, turni):
        return needle_reply(
            call(tool_name(tools, "HassTurnOff"), name="Luce bagno"),
            call(tool_name(tools, "HassTurnOn"), name="Luce cucina"),
        )

    with patch_infer(infer):
        speech = await converse(hass, "spegni il bagno e accendi la cucina")
    assert len(off) == 1 and len(on) == 1
    assert speech == "Ho spento Luce bagno. Ho acceso Luce cucina."


async def test_needle_sees_names_without_prefix(hass, setup_assist):
    off = async_mock_service(hass, "light", "turn_off")
    seen = []

    async def infer(tools, turni):
        seen.extend(t["name"] for t in tools)
        return needle_reply(call("HassTurnOff", name="Luce bagno"))

    with patch_infer(infer):
        speech = await converse(hass, "spegni la luce del bagno")
    assert "HassTurnOff" in seen
    assert not any("__" in name for name in seen)
    assert len(off) == 1
    assert speech == "Ho spento Luce bagno."


async def test_full_prefixed_name_still_accepted(hass, setup_assist):
    off = async_mock_service(hass, "light", "turn_off")

    async def infer(tools, turni):
        return needle_reply(call("intent__HassTurnOff", name="Luce bagno"))

    with patch_infer(infer):
        await converse(hass, "spegni la luce del bagno")
    assert len(off) == 1


async def test_result_turn_uses_needle_names(hass, setup_assist):
    seen = []

    async def infer(tools, turni):
        seen.append(list(turni))
        if len(turni) == 1:
            return needle_reply(call("GetLiveContext", name="Temperatura bagno"))
        return needle_reply()

    with patch_infer(infer):
        await converse(hass, "se la temperatura del bagno è sopra 60 spegni la luce")
    assert '"tool": "GetLiveContext"' in seen[1][1]


async def test_conditional_action_without_read_is_blocked(hass, setup_assist):
    on = async_mock_service(hass, "light", "turn_on")
    mock = AsyncMock(side_effect=lambda tools, turni: needle_reply(call("HassTurnOn", name="Luce cucina")))
    with patch("custom_components.needle.client.NeedleClient.infer", mock):
        speech = await converse(hass, "se luce bagno spenta allora accendi la luce della cucina")
    assert len(on) == 0
    assert mock.await_count == 1
    assert speech == CONDIZIONE_NON_VERIFICATA


async def test_conditional_mixed_read_and_action_is_blocked(hass, setup_assist):
    on = async_mock_service(hass, "light", "turn_on")

    async def infer(tools, turni):
        return needle_reply(call("GetLiveContext", name="Luce bagno"), call("HassTurnOn", name="Luce cucina"))

    with patch_infer(infer):
        speech = await converse(hass, "se luce bagno spenta allora accendi la luce della cucina")
    assert len(on) == 0
    assert speech == CONDIZIONE_NON_VERIFICATA


async def test_plain_action_not_blocked(hass, setup_assist):
    on = async_mock_service(hass, "light", "turn_on")
    with patch_infer(lambda tools, turni: needle_reply(call("HassTurnOn", name="Luce cucina"))):
        await converse(hass, "accendi la luce della cucina")
    assert len(on) == 1


async def test_action_step_ends_loop(hass, setup_assist):
    off = async_mock_service(hass, "light", "turn_off")
    mock = AsyncMock(side_effect=lambda tools, turni: needle_reply(call(tool_name(tools, "HassTurnOff"), name="Luce bagno")))
    with patch("custom_components.needle.client.NeedleClient.infer", mock):
        await converse(hass, "spegni la luce del bagno")
    assert mock.await_count == 1
    assert len(off) == 1


async def test_conditional_true(hass, setup_assist):
    off = async_mock_service(hass, "light", "turn_off")
    seen = []

    async def infer(tools, turni):
        seen.append(list(turni))
        if len(turni) == 1:
            return needle_reply(call(tool_name(tools, "GetLiveContext"), name="Temperatura bagno"))
        return needle_reply(call(tool_name(tools, "HassTurnOff"), name="Luce bagno"))

    with patch_infer(infer):
        speech = await converse(hass, "se la temperatura del bagno è sopra 50 spegni la luce del bagno")
    assert len(seen) == 2
    assert "55" in seen[1][1]
    assert len(off) == 1
    assert speech == f"Ho spento Luce bagno. {NOTA_CONDIZIONALE}"


async def test_conditional_false(hass, setup_assist):
    off = async_mock_service(hass, "light", "turn_off")

    async def infer(tools, turni):
        if len(turni) == 1:
            return needle_reply(call(tool_name(tools, "GetLiveContext"), name="Temperatura bagno"))
        return needle_reply()

    with patch_infer(infer):
        speech = await converse(hass, "se la temperatura del bagno è sopra 60 spegni la luce del bagno")
    assert len(off) == 0
    assert speech == "Ho controllato ora: Temperatura bagno: 55 °C. Non ho fatto nulla e non ho creato una regola."


async def test_question(hass, setup_assist):
    async def infer(tools, turni):
        if len(turni) == 1:
            return needle_reply(call(tool_name(tools, "GetLiveContext"), name="Luce bagno"))
        return needle_reply()

    with patch_infer(infer):
        speech = await converse(hass, "la luce del bagno è accesa?")
    assert speech == "Luce bagno: acceso."


async def test_reads_until_max_passi(hass, setup_assist):
    mock = AsyncMock(side_effect=lambda tools, turni: needle_reply(call(tool_name(tools, "GetLiveContext"), name="Luce bagno")))
    with patch("custom_components.needle.client.NeedleClient.infer", mock):
        speech = await converse(hass, "la luce del bagno è accesa?")
    assert mock.await_count == 5
    assert speech == "Luce bagno: acceso."


async def test_not_exposed_entity_is_refused(hass, setup_assist):
    on = async_mock_service(hass, "light", "turn_on")

    async def infer(tools, turni):
        return needle_reply(call(tool_name(tools, "HassTurnOn"), name="Luce garage"))

    with patch_infer(infer):
        speech = await converse(hass, "accendi la luce del garage")
    assert len(on) == 0
    assert speech.startswith("Non sono riuscito a eseguire il comando")


async def test_non_domotica(hass, setup):
    with patch_infer(lambda tools, turni: needle_reply()):
        speech = await converse(hass, "raccontami una barzelletta")
    assert speech == NON_DOMOTICA


async def test_unknown_tool_ignored(hass, setup):
    with patch_infer(lambda tools, turni: needle_reply(call("ToolInventato", x=1))):
        speech = await converse(hass, "fai una magia")
    assert speech == NON_DOMOTICA


async def test_base_name_resolved(hass, setup_assist):
    async def infer(tools, turni):
        if len(turni) == 1:
            return needle_reply(call("GetLiveContext", name="Luce bagno"))
        return needle_reply()

    with patch_infer(infer):
        speech = await converse(hass, "la luce del bagno è accesa?")
    assert speech == "Luce bagno: acceso."


async def test_string_domain_and_ungrounded_arg(hass, setup_assist):
    off = async_mock_service(hass, "light", "turn_off")

    async def infer(tools, turni):
        return needle_reply(
            call(tool_name(tools, "HassTurnOff"), name="Luce bagno", domain="light", device_class="light_set"),
            ungrounded=["hass_turn_off.device_class"],
        )

    with patch_infer(infer):
        await converse(hass, "spegni la luce del bagno")
    assert len(off) == 1


async def test_prefixed_ungrounded_path(hass, setup_assist):
    off = async_mock_service(hass, "light", "turn_off")

    async def infer(tools, turni):
        name = tool_name(tools, "HassTurnOff")
        return needle_reply(
            call(name, name="Luce bagno", device_class="light_set"),
            ungrounded=[f"{name}.device_class"],
        )

    with patch_infer(infer):
        await converse(hass, "spegni la luce del bagno")
    assert len(off) == 1
    assert "device_class" not in off[0].data


async def test_duplicate_calls_executed_once(hass, setup_assist):
    off = async_mock_service(hass, "light", "turn_off")

    async def infer(tools, turni):
        name = tool_name(tools, "HassTurnOff")
        return needle_reply(call(name, name="Luce bagno"), call(name, name="Luce bagno"))

    with patch_infer(infer):
        speech = await converse(hass, "spegni la luce del bagno")
    assert len(off) == 1
    assert speech == "Ho spento Luce bagno."


async def test_get_date_time(hass, setup_assist):
    async def infer(tools, turni):
        if len(turni) == 1:
            return needle_reply(call(tool_name(tools, "GetDateTime")))
        return needle_reply()

    with patch_infer(infer):
        speech = await converse(hass, "che ore sono?")
    assert speech.startswith("Sono le ")


def _default_result(text):
    response = intent.IntentResponse(language="it")
    response.async_set_speech(text)
    return conversation.ConversationResult(response=response, conversation_id="fallback")


async def test_fallback_with_warning(hass, setup):
    fallback = AsyncMock(return_value=_default_result("Fatto"))
    with patch_infer(NeedleUnavailable("giù")), patch("custom_components.needle.conversation.async_converse", fallback):
        speech = await converse(hass, "spegni la luce del bagno")
    assert speech == f"{AVVISO_FALLBACK} Fatto"
    assert fallback.await_args.kwargs["agent_id"] == conversation.HOME_ASSISTANT_AGENT
    assert "satellite_id" in fallback.await_args.kwargs


async def test_fallback_without_warning(hass, setup):
    hass.config_entries.async_update_entry(setup, options={**setup.options, CONF_MOSTRA_AVVISO: False})
    await hass.async_block_till_done()
    fallback = AsyncMock(return_value=_default_result("Fatto"))
    with patch_infer(NeedleUnavailable("giù")), patch("custom_components.needle.conversation.async_converse", fallback):
        speech = await converse(hass, "spegni la luce del bagno")
    assert speech == "Fatto"


async def test_bad_request_is_internal_error(hass, setup):
    with patch_infer(NeedleBadRequest("bug")):
        speech = await converse(hass, "spegni la luce del bagno")
    assert speech == ERRORE_INTERNO


def needle_suppressed(*calls):
    return {"type": "call", "function_calls": [], "suppressed_calls": list(calls), "confidence": 0.02, "validation": {"ungrounded": []}}


async def test_suppressed_read_is_executed(hass, setup_assist):
    async def infer(tools, turni):
        if len(turni) == 1:
            return needle_suppressed(call(tool_name(tools, "GetLiveContext"), name="cameretta Temperatura", domain=["sensor"]))
        return needle_reply()

    with patch_infer(infer):
        speech = await converse(hass, "dimmi il valore di cameretta temperatura")
    assert speech == "cameretta Temperatura: 21 °C."


async def test_suppressed_action_is_not_executed(hass, setup_assist):
    on = async_mock_service(hass, "light", "turn_on")

    async def infer(tools, turni):
        return needle_suppressed(call(tool_name(tools, "HassTurnOn"), name="Luce cucina"))

    with patch_infer(infer):
        speech = await converse(hass, "accendi cucina")
    assert len(on) == 0
    assert speech == NON_DOMOTICA




# --- Tool generati ---


async def test_generated_tools_sent(hass, setup):
    seen = []

    async def infer(tools, turni):
        seen.extend(t["name"] for t in tools)
        return needle_reply()

    with patch_infer(infer):
        await converse(hass, "accendi la luce del bagno")
    assert {"lights", "get_temperature", "get_humidity", "vacuum", "get_time"} <= set(seen)
    assert not any("__" in name or name.startswith("Hass") for name in seen)


async def test_lights_command(hass, setup):
    on = async_mock_service(hass, "light", "turn_on")

    async def infer(tools, turni):
        return needle_reply(call("lights", room="Bagno", state="on"))

    with patch_infer(infer):
        speech = await converse(hass, "accendi la luce del bagno")
    assert [c.data["entity_id"] for c in on] == [["light.bagno"]]
    assert speech.startswith("Ho acceso")
    assert "Luce bagno" in speech


async def test_get_temperature(hass, setup):
    seen = []

    async def infer(tools, turni):
        seen.append(list(turni))
        if len(turni) == 1:
            return needle_reply(call("get_temperature", room="Bagno"))
        return needle_reply()

    with patch_infer(infer):
        speech = await converse(hass, "che temperatura c'è in bagno")
    assert "55 °C" in speech
    assert "Luce" not in speech
    assert '"tool": "get_temperature"' in seen[1][1]


async def test_get_temperature_by_sensor_name(hass, setup):
    async def infer(tools, turni):
        if len(turni) == 1:
            return needle_reply(call("get_temperature", room="cameretta Temperatura"))
        return needle_reply()

    with patch_infer(infer):
        speech = await converse(hass, "temperatura della cameretta")
    assert speech == "cameretta Temperatura: 21 °C."


async def test_measure_filtered_to_nothing_is_device_error(hass, setup):
    async def infer(tools, turni):
        if len(turni) == 1:
            return needle_reply(call("get_temperature", room="Bagno"))
        return needle_reply()

    vuoto = lambda data, device_class: {**data, "result": "Live Context:\n[]\n"}  # noqa: E731
    with patch_infer(infer), patch("custom_components.needle.conversation.filtra_misura", vuoto):
        speech = await converse(hass, "che temperatura c'è in bagno")
    assert speech == ERRORE_DISPOSITIVO


async def test_question_with_action_blocked(hass, setup):
    on = async_mock_service(hass, "light", "turn_on")

    async def infer(tools, turni):
        return needle_reply(call("lights", room="Bagno", state="on"))

    with patch_infer(infer):
        speech = await converse(hass, "la luce del bagno è accesa?")
    assert len(on) == 0
    assert speech == DOMANDA_O_COMANDO


async def test_question_mixed_read_and_action_blocked(hass, setup):
    on = async_mock_service(hass, "light", "turn_on")
    mock = AsyncMock(
        side_effect=lambda tools, turni: needle_reply(
            call("get_temperature", room="Bagno"), call("lights", room="Bagno", state="on")
        )
    )
    with patch("custom_components.needle.client.NeedleClient.infer", mock):
        speech = await converse(hass, "quanti gradi ci sono in bagno?")
    assert len(on) == 0
    assert mock.await_count == 1
    assert speech == DOMANDA_O_COMANDO


async def test_question_with_read_answered(hass, setup):
    async def infer(tools, turni):
        if len(turni) == 1:
            return needle_reply(call("get_temperature", room="Bagno"))
        return needle_reply()

    with patch_infer(infer):
        speech = await converse(hass, "quanti gradi ci sono in bagno?")
    assert speech == "Temperatura bagno: 55 °C."


async def test_vacuum_not_named_blocked(hass, setup):
    start = async_mock_service(hass, "vacuum", "start")
    seen = []

    async def infer(tools, turni):
        seen.extend(t["name"] for t in tools)
        return needle_reply(call("vacuum", action="start"))

    with patch_infer(infer):
        speech = await converse(hass, "accendi la presa dell'albero")
    assert "vacuum" in seen
    assert len(start) == 0
    assert speech == DISPOSITIVO_INCERTO


async def test_vacuum_named_executed(hass, setup):
    start = async_mock_service(hass, "vacuum", "start")

    async def infer(tools, turni):
        return needle_reply(call("vacuum", action="start"))

    with patch_infer(infer):
        await converse(hass, "fai partire il robot")
    assert [c.data["entity_id"] for c in start] == ["vacuum.robot"]


async def test_generated_suppressed_read_is_executed(hass, setup):
    async def infer(tools, turni):
        if len(turni) == 1:
            return needle_suppressed(call("get_humidity", room="cameretta Umidità"))
        return needle_reply()

    with patch_infer(infer):
        speech = await converse(hass, "umidità della cameretta")
    assert speech == "cameretta Umidità: 48 %."


async def test_generated_suppressed_action_is_not_executed(hass, setup):
    on = async_mock_service(hass, "light", "turn_on")

    async def infer(tools, turni):
        return needle_suppressed(call("lights", room="Bagno", state="on"))

    with patch_infer(infer):
        speech = await converse(hass, "accendi bagno")
    assert len(on) == 0
    assert speech == NON_DOMOTICA


async def test_generated_conditional_action_without_read_is_blocked(hass, setup):
    on = async_mock_service(hass, "light", "turn_on")
    with patch_infer(lambda tools, turni: needle_reply(call("lights", room="all", state="on"))):
        speech = await converse(hass, "se fa caldo accendi le luci")
    assert len(on) == 0
    assert speech == CONDIZIONE_NON_VERIFICATA


async def test_assist_mode_unchanged(hass, setup_assist):
    off = async_mock_service(hass, "light", "turn_off")
    seen = []

    async def infer(tools, turni):
        seen.extend(t["name"] for t in tools)
        return needle_reply(call("HassTurnOff", name="Luce bagno"))

    with patch_infer(infer):
        speech = await converse(hass, "spegni la luce del bagno")
    assert {"HassTurnOff", "GetLiveContext"} <= set(seen)
    assert "lights" not in seen
    assert not any("__" in name for name in seen)
    assert [c.data["entity_id"] for c in off] == [["light.bagno"]]
    assert speech == "Ho spento Luce bagno."
