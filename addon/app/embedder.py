"""EmbeddingGemma 2 (solo testo, 270M, GGUF Q8) eseguito con llama.cpp."""

from __future__ import annotations

import logging
import math
from pathlib import Path

_LOGGER = logging.getLogger(__name__)

REPO = "ggml-org/embeddinggemma-2-GGUF"
FILE = "embeddinggemma-2-Q8_0.gguf"
# Prefissi raccomandati per EmbeddingGemma nella ricerca.
PREFISSO_QUERY = "task: search result | query: "
PREFISSO_DOC = "title: none | text: "


def ensure_model(data_dir: Path) -> Path:
    from huggingface_hub import hf_hub_download  # noqa: PLC0415

    target = data_dir / "embedding"
    if not (target / FILE).exists():
        _LOGGER.info("Scarico EmbeddingGemma 2 in %s", target)
    return Path(hf_hub_download(REPO, FILE, local_dir=target))


def _normalizza(vettore: list[float]) -> list[float]:
    norma = math.sqrt(sum(x * x for x in vettore)) or 1.0
    return [x / norma for x in vettore]


class GemmaEmbedder:
    """Calcola i vettori; quelli dei documenti (entità, aree) restano in cache."""

    def __init__(self, model_path: Path) -> None:
        from llama_cpp import Llama  # noqa: PLC0415 - import pesante

        self._llm = Llama(model_path=str(model_path), embedding=True, n_ctx=512, verbose=False)
        self._cache: dict[str, list[float]] = {}

    def _embed(self, text: str) -> list[float]:
        vettore = self._llm.embed(text)
        if vettore and isinstance(vettore[0], list):
            # Modello senza pooling: media dei vettori dei token.
            vettore = [sum(col) / len(vettore) for col in zip(*vettore, strict=True)]
        return _normalizza(vettore)

    def query(self, text: str) -> list[float]:
        return self._embed(PREFISSO_QUERY + text)

    def documento(self, text: str) -> list[float]:
        if text not in self._cache:
            if len(self._cache) > 5000:
                self._cache.clear()
            self._cache[text] = self._embed(PREFISSO_DOC + text)
        return self._cache[text]
