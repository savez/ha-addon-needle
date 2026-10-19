"""Agente conversazionale Needle: come Gemini, ma con inferenza locale."""

from __future__ import annotations

from dataclasses import replace
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
from .ciclo_generati import Bloccato, Chiamata, StrumentiGenerati
from .const import (
    CONF_MAX_PASSI,
    CONF_MOSTRA_AVVISO,
    CONF_STRUMENTI,
    DEFAULT_LLM_API,
    DEFAULT_MAX_PASSI,
    DEFAULT_MOSTRA_AVVISO,
    DEFAULT_STRUMENTI,
    DOMAIN,
    STRUMENTI_ASSIST,
)
from .convert import base_name, clean_args, drop_ungrounded, needle_tools, read_only_tools
from .responses import (
    AVVISO_FALLBACK,
    CONDIZIONE_NON_VERIFICATA,
    ERRORE_INTERNO,
    ToolOutcome,
    build_response,
    is_condizionale,
    parse_live_context,
    serialize_outcomes,
)
from .traduzione import filtra_misura

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
            name="Needle Local AI",
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
            _LOGGER.warning(
                "Needle non risponde su %s (%s): uso l'agente standard",
                self.entry.runtime_data.url,
                err,
            )
            return await self._async_fallback(user_input)
        except NeedleBadRequest as err:
            _LOGGER.error("L'add-on ha rifiutato la richiesta: %s", err)
            speech = ERRORE_INTERNO
        except Bloccato as err:
            speech = err.risposta
        else:
            speech = build_response(user_input.text, _unique(outcomes))

        _LOGGER.debug("Frase %r, risposta %r", user_input.text, speech)
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
        strumenti: StrumentiGenerati | _StrumentiAssist
        if self.entry.options.get(CONF_STRUMENTI, DEFAULT_STRUMENTI) == STRUMENTI_ASSIST:
            strumenti = _StrumentiAssist(api)
        else:
            strumenti = StrumentiGenerati(self.hass, api)
        max_passi = int(self.entry.options.get(CONF_MAX_PASSI, DEFAULT_MAX_PASSI))

        turni = [text]
        outcomes: list[ToolOutcome] = []
        for _ in range(max_passi):
            response = await self.entry.runtime_data.infer(strumenti.tools, turni)
            chiamate = strumenti.chiamate(response, text)
            _LOGGER.debug("Passo %d, tool da eseguire: %s", len(turni), chiamate)
            if not chiamate:
                break
            if is_condizionale(text) and not outcomes and any(not c.lettura for c in chiamate):
                # Needle propone l'azione senza aver letto lo stato: la condizione
                # non verrebbe mai controllata, quindi non eseguiamo nulla.
                _LOGGER.debug("Condizione non verificata, azioni bloccate: %s", chiamate)
                raise Bloccato(CONDIZIONE_NON_VERIFICATA)
            per_id = {c.tool_input.id: c for c in chiamate}
            step: list[ToolOutcome] = []
            nomi_needle: list[str] = []
            async for result in chat_log.async_add_assistant_content(
                conversation.AssistantContent(
                    agent_id=self.entity_id, tool_calls=[c.tool_input for c in chiamate]
                )
            ):
                chiamata = per_id.get(result.tool_call_id)
                step.append(_esito(result, chiamata))
                nomi_needle.append(chiamata.nome_needle if chiamata else result.tool_name)
            _LOGGER.debug("Risultati: %s", step)
            outcomes.extend(step)
            if any(not outcome.read_only for outcome in step):
                # Un'azione è stata eseguita: non chiediamo altro a Needle,
                # che tenderebbe a ripeterla dopo averne visto il risultato.
                break
            # I risultati tornano a Needle con il nome del tool che ha scelto.
            turni.append(
                serialize_outcomes(
                    [replace(o, name=nome) for o, nome in zip(step, nomi_needle, strict=True)]
                )
            )
        return outcomes

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


class _StrumentiAssist:
    """Tool dell'API Assist mostrati a Needle senza prefisso (opzione `assist`)."""

    def __init__(self, api: llm.APIInstance) -> None:
        self.tools, self._real_names = needle_tools(api)
        self._schemas = {tool["name"]: tool["parameters"] for tool in self.tools}
        self._read_only = read_only_tools(api)

    def chiamate(self, response: dict[str, Any], text: str) -> list[Chiamata]:
        ungrounded = list((response.get("validation") or {}).get("ungrounded") or [])
        calls = list(response.get("function_calls") or [])
        # Needle scarta le chiamate poco sicure. Una lettura non cambia nulla in
        # casa, quindi la eseguiamo comunque; le azioni scartate restano scartate.
        letture = {
            shown for shown, real in self._real_names.items() if real in self._read_only
        }
        letture_scartate = [
            call
            for call in response.get("suppressed_calls") or []
            if _resolve(str(call.get("name")), self._schemas) in letture
        ]
        if letture_scartate:
            _LOGGER.debug("Letture scartate da Needle eseguite comunque: %s", letture_scartate)
        chiamate: list[Chiamata] = []
        seen: set[tuple[str, str]] = set()
        for call in calls + letture_scartate:
            name = _resolve(str(call.get("name")), self._schemas)
            if name is None:
                _LOGGER.debug("Needle ha proposto un tool inesistente: %s", call.get("name"))
                continue
            args = drop_ungrounded(name, dict(call.get("arguments") or {}), ungrounded)
            cleaned = clean_args(args, self._schemas[name])
            key = (name, json.dumps(cleaned, sort_keys=True, default=str))
            if key in seen:
                continue
            seen.add(key)
            real = self._real_names[name]
            chiamate.append(
                Chiamata(
                    tool_input=llm.ToolInput(tool_name=real, tool_args=cleaned),
                    nome_needle=name,
                    lettura=real in self._read_only,
                )
            )
        return chiamate


def _esito(
    result: conversation.ToolResultContent, chiamata: Chiamata | None
) -> ToolOutcome:
    """Risultato di un tool; per le misure tiene solo le entità della device_class."""
    data = dict(result.result.data)
    error = result.result.error
    if chiamata is not None and chiamata.misura and not error:
        data = filtra_misura(data, chiamata.misura)
        if not parse_live_context(data)[1]:
            # Nessun sensore di quel tipo: non è un "Fatto.".
            error = True
    return ToolOutcome(
        name=result.tool_name,
        data=data,
        error=error,
        read_only=chiamata.lettura if chiamata is not None else False,
    )


def _resolve(name: str, schemas: dict[str, dict[str, Any]]) -> str | None:
    """Nome mostrato a Needle; Needle può usare il nome reale con prefisso."""
    if name in schemas:
        return name
    candidates = [known for known in schemas if base_name(known) == base_name(name)]
    return candidates[0] if len(candidates) == 1 else None


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
