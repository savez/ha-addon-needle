"""Motore Needle: cache delle istanze per set di tool e riesecuzione dei turni."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
import hashlib
import json
import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from .risolvi import Risolutore

_LOGGER = logging.getLogger(__name__)


class Agent(Protocol):
    """Sottoinsieme di needle.Needle usato dal motore."""

    def reset(self) -> None: ...

    def complete(self, text: str) -> dict[str, Any]: ...


AgentFactory = Callable[[list[dict[str, Any]]], Agent]


def _tools_key(tools: list[dict[str, Any]]) -> str:
    raw = json.dumps(tools, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class NeedleEngine:
    """Esegue l'inferenza senza stato tra una richiesta e l'altra.

    Ogni richiesta riparte da zero (reset) e riesegue tutti i turni, come fa
    Needle.run() al suo interno. La libreria ha un'istanza attiva per processo,
    quindi le inferenze sono serializzate da un lock.
    """

    def __init__(
        self,
        factory: AgentFactory,
        max_cached: int = 2,
        risolutore: Risolutore | None = None,
    ) -> None:
        self._factory = factory
        self._risolutore = risolutore
        self._max_cached = max_cached
        self._agents: OrderedDict[str, Agent] = OrderedDict()
        self._lock = threading.Lock()

    def infer(
        self,
        tools: list[dict[str, Any]],
        turni: list[str],
        entita: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not turni:
            raise ValueError("turni non può essere vuoto")
        start = time.monotonic()
        with self._lock:
            agent = self._agent_for(tools)
            agent.reset()
            response: dict[str, Any] = {}
            for turno in turni:
                response = agent.complete(turno)
            if self._risolutore is not None and entita:
                response = self._risolutore.risolvi(response, turni[0], entita)
        result = dict(response)
        if len(turni) > 1:
            # Il controllo sugli argomenti inventati confronta con il testo del
            # turno: sui turni di risultato non ha senso.
            result["validation"] = {"ungrounded": []}
        else:
            result.setdefault("validation", {"ungrounded": []})
        result["durata_ms"] = int((time.monotonic() - start) * 1000)
        return result

    def _agent_for(self, tools: list[dict[str, Any]]) -> Agent:
        key = _tools_key(tools)
        if key in self._agents:
            self._agents.move_to_end(key)
            return self._agents[key]
        start = time.monotonic()
        agent = self._factory(tools)
        _LOGGER.debug(
            "Nuova istanza Needle per %d tool in %d ms",
            len(tools),
            int((time.monotonic() - start) * 1000),
        )
        self._agents[key] = agent
        while len(self._agents) > self._max_cached:
            _, old = self._agents.popitem(last=False)
            close = getattr(old, "close", None)
            if close is not None:
                close()
        return agent
