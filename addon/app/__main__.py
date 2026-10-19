"""Avvio dell'add-on Needle."""

from __future__ import annotations

import asyncio
from importlib.metadata import version
import json
import logging
import os
from pathlib import Path

from aiohttp import web

from .assets import ensure_assets, needle_factory
from .engine import NeedleEngine
from .server import STATE, create_app, load_model

DATA_DIR = Path(os.environ.get("NEEDLE_DATA_DIR", "/data"))
PORT = 8765
_LOADER: web.AppKey[asyncio.Task[None]] = web.AppKey("loader", asyncio.Task)


def _log_level() -> str:
    options_file = DATA_DIR / "options.json"
    try:
        options = json.loads(options_file.read_text())
    except (OSError, json.JSONDecodeError):
        return "INFO"
    return str(options.get("log_level", "info")).upper()


def _load() -> tuple[NeedleEngine, str]:
    weights = ensure_assets(DATA_DIR)
    return NeedleEngine(needle_factory(weights)), version("cactus-needle")


async def _on_startup(app: web.Application) -> None:
    app[_LOADER] = asyncio.create_task(load_model(app[STATE], _load))


def main() -> None:
    os.environ.setdefault("NEEDLE_TELEMETRY", "0")
    logging.basicConfig(
        level=_log_level(), format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    from .server import AppState  # noqa: PLC0415

    app = create_app(AppState())
    app.on_startup.append(_on_startup)
    web.run_app(app, host="0.0.0.0", port=PORT)  # noqa: S104 - rete interna add-on


if __name__ == "__main__":
    main()
