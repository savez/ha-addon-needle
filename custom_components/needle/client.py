"""Client HTTP dell'add-on Needle."""

from __future__ import annotations

from typing import Any

import aiohttp


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

    async def infer(self, tools: list[dict[str, Any]], turni: list[str]) -> dict[str, Any]:
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
                return await resp.json()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise NeedleUnavailable(str(err) or type(err).__name__) from err
