"""Diagnostica: esporta i tool correnti, da usare come tools_snapshot.json del benchmark."""

from __future__ import annotations

from typing import Any

from homeassistant.components import conversation
from homeassistant.const import CONF_LLM_HASS_API
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from . import NeedleConfigEntry
from .const import DEFAULT_LLM_API, DOMAIN
from .convert import needle_tools


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NeedleConfigEntry
) -> dict[str, Any]:
    tools: list[dict[str, Any]] = []
    if api_ids := entry.options.get(CONF_LLM_HASS_API, DEFAULT_LLM_API):
        api = await llm.async_get_api(
            hass,
            api_ids,
            llm.LLMContext(
                platform=DOMAIN,
                context=None,
                language=hass.config.language,
                assistant=conversation.DOMAIN,
                device_id=None,
            ),
        )
        tools, _ = needle_tools(api)
    return {"options": dict(entry.options), "tools": tools}
