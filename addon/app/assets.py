"""Download di pesi ed engine di Needle nella cartella persistente."""

from __future__ import annotations

from collections.abc import Callable
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from .engine import AgentFactory

_LOGGER = logging.getLogger(__name__)

WEIGHTS_NAME = "needle3.cact"
# Il CLI sta accanto all'interprete anche quando il venv non è nel PATH.
NEEDLE_CLI = shutil.which("needle") or str(Path(sys.executable).with_name("needle"))


def ensure_assets(data_dir: Path, run: Callable[..., Any] = subprocess.run) -> Path:
    embedding_dir = data_dir / "embedding"
    if embedding_dir.exists():
        _LOGGER.info("Rimuovo il modello di embedding non più usato in %s", embedding_dir)
        shutil.rmtree(embedding_dir, ignore_errors=True)
    weights_dir = data_dir / "weights"
    engine_dir = data_dir / "engine"
    weights = weights_dir / WEIGHTS_NAME
    if not weights.exists():
        _LOGGER.info("Scarico i pesi di Needle in %s", weights_dir)
        run([NEEDLE_CLI, "download", "needle3", "--out", str(weights_dir)], check=True)
    engine = next(engine_dir.glob("libneedle.*"), None) if engine_dir.exists() else None
    if engine is None:
        _LOGGER.info("Scarico l'engine di Needle in %s", engine_dir)
        run([NEEDLE_CLI, "fetch", "--out", str(engine_dir)], check=True)
        engine = next(engine_dir.glob("libneedle.*"))
    os.environ["NEEDLE3_LIB_PATH"] = str(engine)
    return weights


def needle_factory(weights: Path) -> AgentFactory:
    import needle  # noqa: PLC0415 - import pesante, solo quando serve

    def factory(tools: list[dict[str, Any]]) -> Any:
        # stateless=False: il motore chiama reset() e poi riesegue i turni.
        return needle.Needle(tools=tools, weights=str(weights))

    return factory
