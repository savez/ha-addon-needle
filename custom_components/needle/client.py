"""Client HTTP dell'add-on Needle."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class NeedleError(Exception):
    """Errore generico del client."""


class NeedleUnavailable(NeedleError):
    """Add-on irraggiungibile, in caricamento, in timeout o in errore."""


class NeedleBadRequest(NeedleError):
    """Richiesta rifiutata dall'add-on: bug dell'integrazione."""


class NeedleClient:
    """Parla con l'add-on Needle."""

    def __init__(self, session: aiohttp.ClientSession, url: str, timeout_s: float) -> None:
        self._session = session
        self._url = url.rstrip("/")
        self._timeout = aiohttp.ClientTimeout(total=timeout_s)

    async def health(self) -> dict[str, Any]:
        try:
            async with self._session.get(f"{self._url}/health", timeout=self._timeout) as resp:
                if resp.status != 200:
                    raise NeedleUnavailable(f"health HTTP {resp.status}")
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise NeedleUnavailable(str(err) or type(err).__name__) from err

    @property
    def url(self) -> str:
        return self._url

    async def infer(self, tools: list[dict[str, Any]], turni: list[str]) -> dict[str, Any]:
        _LOGGER.debug("POST %s/v1/infer: %d tool, turni=%s", self._url, len(tools), turni)
        start = time.monotonic()
        try:
            async with self._session.post(
                f"{self._url}/v1/infer",
                json={"tools": tools, "turni": turni},
                timeout=self._timeout,
            ) as resp:
                if resp.status == 400:
                    raise NeedleBadRequest(await resp.text())
                if resp.status != 200:
                    raise NeedleUnavailable(f"infer HTTP {resp.status}")
                result: dict[str, Any] = await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug(
                "Chiamata fallita dopo %d ms: %r",
                int((time.monotonic() - start) * 1000),
                err,
            )
            raise NeedleUnavailable(str(err) or type(err).__name__) from err
        _LOGGER.debug(
            "Risposta in %d ms: %s",
            int((time.monotonic() - start) * 1000),
            json.dumps(result, ensure_ascii=False, default=str),
        )
        return result
