"""Test della diagnostica."""
from homeassistant.const import CONF_URL
from homeassistant.setup import async_setup_component

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.needle.config_flow import DEFAULT_OPTIONS
from custom_components.needle.const import DOMAIN
from custom_components.needle.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics_exports_tools(hass):
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "intent", {})
    hass.states.async_set("light.bagno", "on", {"friendly_name": "Luce bagno"})
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_URL: "http://needle.test:8765"}, options=dict(DEFAULT_OPTIONS))
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, entry)
    names = [tool["name"] for tool in result["tools"]]
    assert any(name.endswith("HassTurnOn") for name in names)
    assert any(name.endswith("GetLiveContext") for name in names)
    assert not any("__" in name for name in names)
    assert result["options"]["max_passi"] == 5
