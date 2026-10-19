"""Test end-to-end dell'agente con add-on simulato."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components import conversation
from homeassistant.components.homeassistant.exposed_entities import async_expose_entity
from homeassistant.const import CONF_URL
from homeassistant.core import Context
from homeassistant.helpers import intent
from homeassistant.setup import async_setup_component

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service

from custom_components.needle.client import NeedleBadRequest, NeedleUnavailable
from custom_components.needle.const import CONF_MOSTRA_AVVISO, DOMAIN
from custom_components.needle.config_flow import DEFAULT_OPTIONS
from custom_components.needle.responses import AVVISO_FALLBACK, ERRORE_INTERNO, NON_DOMOTICA, NOTA_CONDIZIONALE

AGENT = "conversation.needle_local_ai"


def tool_name(tools, suffix):
    return next(t["name"] for t in tools if t["name"].endswith(suffix))


def call(tool, /, **args):
    return {"name": tool, "arguments": args}


def needle_reply(*calls, ungrounded=()):
    return {"type": "call", "function_calls": list(calls), "confidence": 0.5, "validation": {"ungrounded": list(ungrounded)}}


@pytest.fixture
async def setup(hass):
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    assert await async_setup_component(hass, "conversation", {})
    hass.states.async_set("light.bagno", "on", {"friendly_name": "Luce bagno"})
    hass.states.async_set("light.cucina", "off", {"friendly_name": "Luce cucina"})
    hass.states.async_set("light.garage", "off", {"friendly_name": "Luce garage"})
    hass.states.async_set("sensor.temp_bagno", "55", {"friendly_name": "Temperatura bagno", "unit_of_measurement": "°C"})
    for entity_id in ("light.bagno", "light.cucina", "sensor.temp_bagno"):
        async_expose_entity(hass, "conversation", entity_id, True)
    async_expose_entity(hass, "conversation", "light.garage", False)
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://needle.test:8765"}, options=dict(DEFAULT_OPTIONS))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def converse(hass, text):
    result = await conversation.async_converse(hass, text, None, Context(), language="it", agent_id=AGENT)
    return result.response.speech["plain"]["speech"]


def patch_infer(side_effect):
    return patch("custom_components.needle.client.NeedleClient.infer", AsyncMock(side_effect=side_effect))


async def test_single_action(hass, setup):
    off = async_mock_service(hass, "light", "turn_off")

    async def infer(tools, turni):
        return needle_reply(call(tool_name(tools, "HassTurnOff"), name="Luce bagno"))

    with patch_infer(infer):
        speech = await converse(hass, "spegni la luce del bagno")
    assert [c.data["entity_id"] for c in off] == [["light.bagno"]]
    assert speech == "Ho spento Luce bagno."


async def test_multiple_actions(hass, setup):
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


async def test_action_step_ends_loop(hass, setup):
    off = async_mock_service(hass, "light", "turn_off")
    mock = AsyncMock(side_effect=lambda tools, turni: needle_reply(call(tool_name(tools, "HassTurnOff"), name="Luce bagno")))
    with patch("custom_components.needle.client.NeedleClient.infer", mock):
        await converse(hass, "spegni la luce del bagno")
    assert mock.await_count == 1
    assert len(off) == 1


async def test_conditional_true(hass, setup):
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


async def test_conditional_false(hass, setup):
    off = async_mock_service(hass, "light", "turn_off")

    async def infer(tools, turni):
        if len(turni) == 1:
            return needle_reply(call(tool_name(tools, "GetLiveContext"), name="Temperatura bagno"))
        return needle_reply()

    with patch_infer(infer):
        speech = await converse(hass, "se la temperatura del bagno è sopra 60 spegni la luce del bagno")
    assert len(off) == 0
    assert speech == "Ho controllato ora: Temperatura bagno: 55 °C. Non ho fatto nulla e non ho creato una regola."


async def test_question(hass, setup):
    async def infer(tools, turni):
        if len(turni) == 1:
            return needle_reply(call(tool_name(tools, "GetLiveContext"), name="Luce bagno"))
        return needle_reply()

    with patch_infer(infer):
        speech = await converse(hass, "la luce del bagno è accesa?")
    assert speech == "Luce bagno: acceso."


async def test_reads_until_max_passi(hass, setup):
    mock = AsyncMock(side_effect=lambda tools, turni: needle_reply(call(tool_name(tools, "GetLiveContext"), name="Luce bagno")))
    with patch("custom_components.needle.client.NeedleClient.infer", mock):
        speech = await converse(hass, "la luce del bagno è accesa?")
    assert mock.await_count == 5
    assert speech == "Luce bagno: acceso."


async def test_not_exposed_entity_is_refused(hass, setup):
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


async def test_base_name_resolved(hass, setup):
    async def infer(tools, turni):
        if len(turni) == 1:
            return needle_reply(call("GetLiveContext", name="Luce bagno"))
        return needle_reply()

    with patch_infer(infer):
        speech = await converse(hass, "la luce del bagno è accesa?")
    assert speech == "Luce bagno: acceso."


async def test_string_domain_and_ungrounded_arg(hass, setup):
    off = async_mock_service(hass, "light", "turn_off")

    async def infer(tools, turni):
        return needle_reply(
            call(tool_name(tools, "HassTurnOff"), name="Luce bagno", domain="light", device_class="light_set"),
            ungrounded=["hass_turn_off.device_class"],
        )

    with patch_infer(infer):
        await converse(hass, "spegni la luce del bagno")
    assert len(off) == 1


async def test_prefixed_ungrounded_path(hass, setup):
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


async def test_duplicate_calls_executed_once(hass, setup):
    off = async_mock_service(hass, "light", "turn_off")

    async def infer(tools, turni):
        name = tool_name(tools, "HassTurnOff")
        return needle_reply(call(name, name="Luce bagno"), call(name, name="Luce bagno"))

    with patch_infer(infer):
        speech = await converse(hass, "spegni la luce del bagno")
    assert len(off) == 1
    assert speech == "Ho spento Luce bagno."


async def test_get_date_time(hass, setup):
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
