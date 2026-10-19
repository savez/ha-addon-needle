"""Test del config flow."""
import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_LLM_HASS_API, CONF_URL
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.setup import async_setup_component

from custom_components.needle.const import (
    CONF_MAX_PASSI,
    CONF_MOSTRA_AVVISO,
    CONF_STRUMENTI,
    CONF_TIMEOUT_S,
    DOMAIN,
)
from custom_components.needle.config_flow import DEFAULT_OPTIONS

URL = "http://needle.test:8765"


@pytest.fixture(autouse=True)
async def _setup_homeassistant(hass):
    """`conversation` (dipendenza) richiede il componente `homeassistant`."""
    await async_setup_component(hass, "homeassistant", {})


async def test_user_flow_ok(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/health", json={"stato": "ok", "versione": "3.2.7"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: f"{URL}/"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_URL: URL}
    assert result["options"] == {
        CONF_LLM_HASS_API: ["assist"],
        CONF_MOSTRA_AVVISO: True,
        CONF_MAX_PASSI: 5,
        CONF_TIMEOUT_S: 10,
        CONF_STRUMENTI: "generati",
    }


async def test_user_flow_cannot_connect(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/health", status=503, json={"stato": "caricamento"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/health", json={"stato": "ok", "versione": "3.2.7"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL})
    entry = result["result"]
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_LLM_HASS_API: ["assist"],
            CONF_MOSTRA_AVVISO: False,
            CONF_MAX_PASSI: 3,
            CONF_TIMEOUT_S: 5,
            CONF_STRUMENTI: "assist",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_MOSTRA_AVVISO] is False
    assert entry.options[CONF_MAX_PASSI] == 3
    assert entry.options[CONF_STRUMENTI] == "assist"


def test_default_options_use_generated_tools():
    assert DEFAULT_OPTIONS[CONF_STRUMENTI] == "generati"


@pytest.mark.parametrize("valore", ["generati", "assist"])
async def test_options_flow_strumenti(hass, aioclient_mock, valore):
    aioclient_mock.get(f"{URL}/health", json={"stato": "ok", "versione": "3.2.7"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL})
    entry = result["result"]
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {CONF_MOSTRA_AVVISO: True, CONF_MAX_PASSI: 5, CONF_TIMEOUT_S: 10, CONF_STRUMENTI: valore},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_STRUMENTI] == valore


async def test_options_flow_rejects_unknown_strumenti(hass, aioclient_mock):
    aioclient_mock.get(f"{URL}/health", json={"stato": "ok", "versione": "3.2.7"})
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL})
    entry = result["result"]
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData) as err:
        await hass.config_entries.options.async_configure(
            result["flow_id"],
            {CONF_MOSTRA_AVVISO: True, CONF_MAX_PASSI: 5, CONF_TIMEOUT_S: 10, CONF_STRUMENTI: "altro"},
        )
    assert "must be one of" in err.value.schema_errors[CONF_STRUMENTI]
