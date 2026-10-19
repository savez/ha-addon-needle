"""Config flow dell'integrazione Needle."""

from __future__ import annotations

from typing import Any

import probatio

from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_LLM_HASS_API, CONF_URL
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import llm
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    TextSelector,
)

from .client import NeedleClient, NeedleUnavailable
from .const import (
    CONF_MAX_PASSI,
    CONF_MOSTRA_AVVISO,
    CONF_TIMEOUT_S,
    DEFAULT_LLM_API,
    DEFAULT_MAX_PASSI,
    DEFAULT_MOSTRA_AVVISO,
    DEFAULT_TIMEOUT_S,
    DEFAULT_URL,
    DOMAIN,
)

DEFAULT_OPTIONS: dict[str, Any] = {
    CONF_LLM_HASS_API: DEFAULT_LLM_API,
    CONF_MOSTRA_AVVISO: DEFAULT_MOSTRA_AVVISO,
    CONF_MAX_PASSI: DEFAULT_MAX_PASSI,
    CONF_TIMEOUT_S: DEFAULT_TIMEOUT_S,
}


class NeedleConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configura l'URL dell'add-on."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = user_input[CONF_URL].rstrip("/")
            self._async_abort_entries_match({CONF_URL: url})
            client = NeedleClient(async_get_clientsession(self.hass), url, DEFAULT_TIMEOUT_S)
            try:
                await client.health()
            except NeedleUnavailable:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title="Needle Local AI", data={CONF_URL: url}, options=dict(DEFAULT_OPTIONS)
                )
        return self.async_show_form(
            step_id="user",
            data_schema=probatio.Schema(
                {probatio.Required(CONF_URL, default=DEFAULT_URL): TextSelector()}
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return NeedleOptionsFlow()


class NeedleOptionsFlow(OptionsFlow):
    """Opzioni dell'agente."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init", data_schema=_options_schema(self.hass, self.config_entry.options)
        )


def _options_schema(hass: HomeAssistant, options: dict[str, Any]) -> probatio.Schema:
    apis = [SelectOptionDict(label=api.name, value=api.id) for api in llm.async_get_apis(hass)]
    return probatio.Schema(
        {
            probatio.Optional(
                CONF_LLM_HASS_API,
                description={"suggested_value": options.get(CONF_LLM_HASS_API, DEFAULT_LLM_API)},
            ): SelectSelector(SelectSelectorConfig(options=apis, multiple=True)),
            probatio.Required(
                CONF_MOSTRA_AVVISO,
                default=options.get(CONF_MOSTRA_AVVISO, DEFAULT_MOSTRA_AVVISO),
            ): BooleanSelector(),
            probatio.Required(
                CONF_MAX_PASSI, default=options.get(CONF_MAX_PASSI, DEFAULT_MAX_PASSI)
            ): NumberSelector(NumberSelectorConfig(min=1, max=10, step=1, mode=NumberSelectorMode.BOX)),
            probatio.Required(
                CONF_TIMEOUT_S, default=options.get(CONF_TIMEOUT_S, DEFAULT_TIMEOUT_S)
            ): NumberSelector(NumberSelectorConfig(min=1, max=30, step=1, mode=NumberSelectorMode.BOX)),
        }
    )
