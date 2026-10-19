"""Tool generati nel ciclo dell'agente: dalla casa ai tool, dalle chiamate agli intent.

Il generatore, la traduzione e le protezioni sono moduli puri; qui li si collega
all'API LLM di Home Assistant (entità esposte, nomi reali dei tool, ToolInput).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from typing import Any

from homeassistant.components.homeassistant.llm import async_get_exposed_entities
from homeassistant.core import HomeAssistant
from homeassistant.helpers import llm

from .convert import base_name
from .protezioni import dispositivo_nominato, e_domanda
from .responses import DISPOSITIVO_INCERTO, DOMANDA_O_COMANDO
from .strumenti import Entita, entita_da_esposte, genera_strumenti
from .traduzione import LETTURE, e_lettura, traduci

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Chiamata:
    """Tool di Home Assistant da eseguire, con il nome che Needle ha usato."""

    tool_input: llm.ToolInput
    nome_needle: str
    lettura: bool
    misura: str | None = None


class Bloccato(Exception):
    """Needle ha proposto qualcosa che non va eseguito: si risponde con `risposta`."""

    def __init__(self, risposta: str) -> None:
        super().__init__(risposta)
        self.risposta = risposta


def nomi_reali(api: llm.APIInstance) -> dict[str, str]:
    """Nome base dell'intent → nome reale del tool (HA 2026.10 aggiunge un prefisso).

    Se due tool hanno lo stesso nome base si preferisce quello dell'API intent.
    """
    reali: dict[str, str] = {}
    for tool in api.tools:
        base = base_name(tool.name)
        if base not in reali or tool.name.startswith("intent__"):
            reali[base] = tool.name
    return reali


class StrumentiGenerati:
    """Tool generati dalla casa e traduzione delle chiamate di Needle."""

    def __init__(self, hass: HomeAssistant, api: llm.APIInstance) -> None:
        assistant = api.llm_context.assistant
        esposte = async_get_exposed_entities(hass, assistant, include_state=True) if assistant else {}
        self._entita: list[Entita] = entita_da_esposte(esposte)
        self._reali = nomi_reali(api)
        self._intent = set(self._reali)
        self._aree = {area for e in self._entita for area in e.aree}
        self.tools: list[dict[str, Any]] = genera_strumenti(self._entita, self._intent)

    def chiamate(self, response: dict[str, Any], text: str) -> list[Chiamata]:
        # Needle scarta le chiamate poco sicure: le letture si eseguono comunque.
        proposte = list(response.get("function_calls") or []) + [
            call
            for call in response.get("suppressed_calls") or []
            if isinstance(call, dict) and e_lettura(str(call.get("name")))
        ]
        tradotte: list[tuple[str, dict[str, Any], list[dict[str, Any]]]] = []
        for call in proposte:
            intent = traduci(call, self.tools, self._intent, self._aree)
            if not intent:
                _LOGGER.debug("Chiamata di Needle ignorata: %s", call)
                continue
            tradotte.append((str(call["name"]), call, intent))

        if e_domanda(text) and any(not e_lettura(nome) for nome, _, _ in tradotte):
            # Nessuna esecuzione parziale: si bloccano anche le letture.
            _LOGGER.debug("Domanda con un'azione proposta, nulla eseguito: %s", tradotte)
            raise Bloccato(DOMANDA_O_COMANDO)
        for nome, call, _ in tradotte:
            if not dispositivo_nominato(text, nome, self._nome_entita(nome, call)):
                _LOGGER.debug("Dispositivo non nominato nella frase: %s", call)
                raise Bloccato(DISPOSITIVO_INCERTO)

        risultato: list[Chiamata] = []
        visti: set[tuple[str, str, str]] = set()
        for nome, _, intent in tradotte:
            for voce in intent:
                chiave = (nome, voce["tool"], json.dumps(voce["args"], sort_keys=True, default=str))
                if chiave in visti:
                    continue
                visti.add(chiave)
                risultato.append(
                    Chiamata(
                        tool_input=llm.ToolInput(
                            tool_name=self._reali[voce["tool"]], tool_args=voce["args"]
                        ),
                        nome_needle=nome,
                        lettura=e_lettura(nome),
                        misura=LETTURE.get(nome),
                    )
                )
        return risultato

    def _nome_entita(self, nome: str, call: dict[str, Any]) -> str | None:
        """Nome dell'entità scelta: argomento `name`, o l'unico aspirapolvere."""
        argomenti = call.get("arguments")
        if isinstance(argomenti, dict) and isinstance(argomenti.get("name"), str):
            return argomenti["name"]
        if nome == "vacuum":
            aspirapolveri = [e for e in self._entita if e.dominio == "vacuum"]
            if len(aspirapolveri) == 1:
                return aspirapolveri[0].nome
        return None
