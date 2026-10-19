"""Agente conversazionale Needle: come Gemini, ma con inferenza locale."""

from __future__ import annotations

import json
import logging
from typing import Any, Literal, override

from homeassistant.components import conversation
from homeassistant.components.conversation import async_converse
from homeassistant.const import CONF_LLM_HASS_API, MATCH_ALL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, llm
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NeedleConfigEntry
from .client import NeedleBadRequest, NeedleUnavailable
from .const import (
    CONF_MAX_PASSI,
    CONF_MOSTRA_AVVISO,
    DEFAULT_LLM_API,
    DEFAULT_MAX_PASSI,
    DEFAULT_MOSTRA_AVVISO,
    DOMAIN,
)
from .convert import base_name, clean_args, drop_ungrounded, format_tools, read_only_tools
from .responses import (
    AVVISO_FALLBACK,
    ERRORE_INTERNO,
    ToolOutcome,
    build_response,
    serialize_outcomes,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NeedleConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([NeedleConversationEntity(entry)])


class NeedleConversationEntity(conversation.ConversationEntity, conversation.AbstractConversationAgent):
    """Agente Assist che usa Needle per scegliere i tool."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: NeedleConfigEntry) -> None:
        self.entry = entry
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = dr.DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Needle",
            manufacturer="Cactus Compute",
            model="Needle 3",
            entry_type=dr.DeviceEntryType.SERVICE,
        )
        if entry.options.get(CONF_LLM_HASS_API, DEFAULT_LLM_API):
            self._attr_supported_features = conversation.ConversationEntityFeature.CONTROL

    @property
    @override
    def supported_languages(self) -> list[str] | Literal["*"]:
        return MATCH_ALL

    @override
    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        conversation.async_set_agent(self.hass, self.entry, self)

    @override
    async def async_will_remove_from_hass(self) -> None:
        conversation.async_unset_agent(self.hass, self.entry)
        await super().async_will_remove_from_hass()

    @override
    async def _async_handle_message(
        self,
        user_input: conversation.ConversationInput,
        chat_log: conversation.ChatLog,
    ) -> conversation.ConversationResult:
        options = self.entry.options
        try:
            await chat_log.async_provide_llm_data(
                user_input.as_llm_context(DOMAIN),
                options.get(CONF_LLM_HASS_API, DEFAULT_LLM_API),
                None,
                user_input.extra_system_prompt,
            )
        except conversation.ConverseError as err:
            return err.as_conversation_result()

        try:
            outcomes = await self._async_run_loop(user_input.text, chat_log)
        except NeedleUnavailable as err:
            _LOGGER.warning("Needle non risponde (%s): uso l'agente standard", err)
            return await self._async_fallback(user_input)
        except NeedleBadRequest as err:
            _LOGGER.error("L'add-on ha rifiutato la richiesta: %s", err)
            speech = ERRORE_INTERNO
        else:
            speech = build_response(user_input.text, _unique(outcomes))

        chat_log.async_add_assistant_content_without_tools(
            conversation.AssistantContent(agent_id=self.entity_id, content=speech)
        )
        return conversation.async_get_result_from_chat_log(user_input, chat_log)

    async def _async_run_loop(
        self, text: str, chat_log: conversation.ChatLog
    ) -> list[ToolOutcome]:
        api = chat_log.llm_api
        if api is None:
            return []
        tools = format_tools(api)
        schemas = {tool["name"]: tool["parameters"] for tool in tools}
        read_only = read_only_tools(api)
        max_passi = int(self.entry.options.get(CONF_MAX_PASSI, DEFAULT_MAX_PASSI))

        turni = [text]
        outcomes: list[ToolOutcome] = []
        for _ in range(max_passi):
            response = await self.entry.runtime_data.infer(tools, turni)
            tool_inputs = self._tool_inputs(response, schemas)
            if not tool_inputs:
                break
            step: list[ToolOutcome] = []
            async for result in chat_log.async_add_assistant_content(
                conversation.AssistantContent(agent_id=self.entity_id, tool_calls=tool_inputs)
            ):
                step.append(
                    ToolOutcome(
                        name=result.tool_name,
                        data=dict(result.result.data),
                        error=result.result.error,
                        read_only=result.tool_name in read_only,
                    )
                )
            outcomes.extend(step)
            if any(not outcome.read_only for outcome in step):
                # Un'azione è stata eseguita: non chiediamo altro a Needle,
                # che tenderebbe a ripeterla dopo averne visto il risultato.
                break
            turni.append(serialize_outcomes(step))
        return outcomes

    @staticmethod
    def _tool_inputs(
        response: dict[str, Any], schemas: dict[str, dict[str, Any]]
    ) -> list[llm.ToolInput]:
        ungrounded = list((response.get("validation") or {}).get("ungrounded") or [])
        inputs: list[llm.ToolInput] = []
        seen: set[tuple[str, str]] = set()
        for call in response.get("function_calls") or []:
            name = call.get("name")
            if name not in schemas:
                # Needle può omettere il prefisso "homeassistant__".
                candidates = [known for known in schemas if base_name(known) == name]
                if len(candidates) != 1:
                    _LOGGER.debug("Needle ha proposto un tool inesistente: %s", name)
                    continue
                name = candidates[0]
            args = drop_ungrounded(name, dict(call.get("arguments") or {}), ungrounded)
            cleaned = clean_args(args, schemas[name])
            key = (name, json.dumps(cleaned, sort_keys=True, default=str))
            if key in seen:
                continue
            seen.add(key)
            inputs.append(llm.ToolInput(tool_name=name, tool_args=cleaned))
        return inputs

    async def _async_fallback(
        self, user_input: conversation.ConversationInput
    ) -> conversation.ConversationResult:
        result = await async_converse(
            self.hass,
            user_input.text,
            None,
            user_input.context,
            language=user_input.language,
            agent_id=conversation.HOME_ASSISTANT_AGENT,
            device_id=user_input.device_id,
            satellite_id=user_input.satellite_id,
        )
        if self.entry.options.get(CONF_MOSTRA_AVVISO, DEFAULT_MOSTRA_AVVISO):
            speech = result.response.speech.get("plain", {}).get("speech", "")
            result.response.async_set_speech(f"{AVVISO_FALLBACK} {speech}".strip())
        return result


def _unique(outcomes: list[ToolOutcome]) -> list[ToolOutcome]:
    """Toglie i risultati identici: Needle può ripetere la stessa lettura a ogni passo."""
    seen: set[tuple[str, str, bool]] = set()
    unique: list[ToolOutcome] = []
    for outcome in outcomes:
        key = (outcome.name, json.dumps(outcome.data, sort_keys=True, default=str), outcome.error)
        if key not in seen:
            seen.add(key)
            unique.append(outcome)
    return unique
