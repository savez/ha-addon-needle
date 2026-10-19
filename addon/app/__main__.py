"""Avvio dell'add-on Needle."""

from __future__ import annotations

import asyncio
from importlib.metadata import version
import json
import logging
import os
from pathlib import Path
from typing import Any

from aiohttp import web

from .assets import ensure_assets, needle_factory
from .embedder import GemmaEmbedder, ensure_model
from .engine import NeedleEngine
from .risolvi import Risolutore
from .server import STATE, create_app, load_model

DATA_DIR = Path(os.environ.get("NEEDLE_DATA_DIR", "/data"))
PORT = 8765
_LOGGER = logging.getLogger(__name__)
_LOADER: web.AppKey[asyncio.Task[None]] = web.AppKey("loader", asyncio.Task)


def _options() -> dict[str, Any]:
    try:
        options = json.loads((DATA_DIR / "options.json").read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return options if isinstance(options, dict) else {}


def _log_level() -> str:
    return str(_options().get("log_level", "info")).upper()


def _risolutore() -> Risolutore | None:
    options = _options()
    if not options.get("ricerca_entita", True):
        _LOGGER.info("Ricerca delle entità con EmbeddingGemma disattivata")
        return None
    try:
        embedder = GemmaEmbedder(ensure_model(DATA_DIR))
    except Exception:  # noqa: BLE001 - senza embedding Needle funziona comunque
        _LOGGER.exception("EmbeddingGemma non disponibile: continuo senza")
        return None
    soglia = float(options.get("soglia_entita", 0.5))
    _LOGGER.info("EmbeddingGemma 2 pronto (soglia %.2f)", soglia)
    return Risolutore(embedder, soglia)


def _load() -> tuple[NeedleEngine, str]:
    weights = ensure_assets(DATA_DIR)
    engine = NeedleEngine(needle_factory(weights), risolutore=_risolutore())
    return engine, version("cactus-needle")


async def _on_startup(app: web.Application) -> None:
    app[_LOADER] = asyncio.create_task(load_model(app[STATE], _load))


def main() -> None:
    os.environ.setdefault("NEEDLE_TELEMETRY", "0")
    logging.basicConfig(
        level=_log_level(), format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    # Le librerie restano a INFO anche in debug: i dettagli utili sono i nostri.
    for name in ("asyncio", "aiohttp", "urllib3", "httpx", "filelock", "huggingface_hub"):
        logging.getLogger(name).setLevel(max(logging.INFO, logging.root.level))
    for name in ("llama_cpp",):
        logging.getLogger(name).setLevel(max(logging.INFO, logging.root.level))
    _LOGGER.debug("Log di debug attivi")
    from .server import AppState  # noqa: PLC0415

    app = create_app(AppState())
    app.on_startup.append(_on_startup)
    web.run_app(app, host="0.0.0.0", port=PORT)  # noqa: S104 - rete interna add-on


if __name__ == "__main__":
    main()
