"""Server HTTP dell'add-on: /health e /v1/infer."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import json
import logging
from typing import Any

from aiohttp import web

from .engine import NeedleEngine

_LOGGER = logging.getLogger(__name__)


@dataclass
class AppState:
    engine: NeedleEngine | None = None
    versione: str = "sconosciuta"
    errore: str | None = None


STATE: web.AppKey[AppState] = web.AppKey("state", AppState)


def create_app(state: AppState) -> web.Application:
    app = web.Application(client_max_size=4 * 1024 * 1024)
    app[STATE] = state
    app.router.add_get("/health", _health)
    app.router.add_post("/v1/infer", _infer)
    return app


async def load_model(
    state: AppState, loader: Callable[[], tuple[NeedleEngine, str]]
) -> None:
    try:
        engine, versione = await asyncio.to_thread(loader)
    except Exception as err:  # noqa: BLE001 - qualsiasi errore va mostrato in /health
        _LOGGER.exception("Caricamento del modello fallito")
        state.errore = str(err)
        return
    state.engine = engine
    state.versione = versione
    _LOGGER.info("Modello Needle pronto (cactus-needle %s)", versione)


async def _health(request: web.Request) -> web.Response:
    state = request.app[STATE]
    if state.engine is not None:
        return web.json_response({"stato": "ok", "versione": state.versione})
    if state.errore is not None:
        return web.json_response({"stato": "errore", "errore": state.errore}, status=503)
    return web.json_response({"stato": "caricamento"}, status=503)


def _bad_request(message: str) -> web.Response:
    return web.json_response({"errore": message}, status=400)


async def _infer(request: web.Request) -> web.Response:
    state = request.app[STATE]
    if state.engine is None:
        return web.json_response({"errore": "modello non pronto"}, status=503)
    try:
        body: Any = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _bad_request("JSON non valido")
    if not isinstance(body, dict):
        return _bad_request("il corpo deve essere un oggetto JSON")
    tools = body.get("tools")
    turni = body.get("turni")
    if not isinstance(tools, list) or not all(
        isinstance(tool, dict) and isinstance(tool.get("name"), str) for tool in tools
    ):
        return _bad_request("tools deve essere una lista di oggetti con 'name'")
    if not isinstance(turni, list) or not turni or not all(isinstance(t, str) for t in turni):
        return _bad_request("turni deve essere una lista non vuota di stringhe")
    try:
        result = await asyncio.to_thread(state.engine.infer, tools, turni)
    except Exception as err:  # noqa: BLE001 - errore del motore restituito al client
        _LOGGER.exception("Errore del motore Needle")
        return web.json_response({"errore": str(err)}, status=500)
    return web.json_response(result)
