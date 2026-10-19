"""Integrazione Needle per Home Assistant."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import NeedleClient
from .const import CONF_TIMEOUT_S, DEFAULT_TIMEOUT_S

PLATFORMS = (Platform.CONVERSATION,)

type NeedleConfigEntry = ConfigEntry[NeedleClient]


async def async_setup_entry(hass: HomeAssistant, entry: NeedleConfigEntry) -> bool:
    """Configura l'integrazione. Non serve che l'add-on sia già pronto."""
    entry.runtime_data = NeedleClient(
        async_get_clientsession(hass),
        entry.data[CONF_URL],
        entry.options.get(CONF_TIMEOUT_S, DEFAULT_TIMEOUT_S),
    )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NeedleConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload(hass: HomeAssistant, entry: NeedleConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)
