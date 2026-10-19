"""Ricerca a parole nel contesto della casa.

Needle estrae spesso una parola sola ("cameretta") mentre il filtro di Home
Assistant vuole il nome intero ("cameretta Temperatura"). L'integrazione legge
quindi tutte le entità esposte e tiene quelle che contengono più parole della
richiesta: prima quelle scelte da Needle, poi quelle della frase.
"""

from __future__ import annotations

import re
from typing import Any
import unicodedata

import yaml

# Parole italiane per tipo di sensore e dominio: entrano nel testo cercabile.
ETICHETTE_CLASSE = {
    "temperature": "temperatura gradi",
    "humidity": "umidita umido",
    "battery": "batteria",
    "power": "potenza consumo",
    "energy": "energia consumo",
    "illuminance": "luminosita luce",
    "pressure": "pressione",
    "co2": "anidride carbonica",
}
ETICHETTE_DOMINIO = {
    "light": "luce luci",
    "cover": "tapparella tapparelle tenda tende",
    "climate": "termostato riscaldamento clima",
    "media_player": "musica lettore",
    "fan": "ventilatore",
    "lock": "serratura",
    "vacuum": "aspirapolvere robot",
}
_PAROLA = re.compile(r"[a-z0-9]+")


def _norm(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def parole(text: str) -> set[str]:
    """Parole di almeno tre lettere, minuscole e senza accenti."""
    return {p for p in _PAROLA.findall(_norm(text)) if len(p) >= 3}


def parse_live_context(data: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Separa l'intestazione dall'elenco YAML delle entità."""
    header, _, body = str(data.get("result") or "").partition("\n")
    try:
        parsed = yaml.safe_load(body)
    except yaml.YAMLError:
        return header, []
    if not isinstance(parsed, list):
        return header, []
    return header, [item for item in parsed if isinstance(item, dict)]


def _cercabile(entity: dict[str, Any]) -> set[str]:
    attributes = entity.get("attributes") or {}
    testo = " ".join(
        [
            str(entity.get("names") or ""),
            str(entity.get("areas") or ""),
            ETICHETTE_DOMINIO.get(str(entity.get("domain") or ""), ""),
            ETICHETTE_CLASSE.get(str(attributes.get("device_class") or ""), ""),
        ]
    )
    return parole(testo)


def filtra_live_context(
    data: dict[str, Any], termini_needle: set[str], termini_frase: set[str]
) -> dict[str, Any]:
    """Tiene le entità con il punteggio più alto; se nessuna corrisponde, tutte."""
    header, entities = parse_live_context(data)
    if not entities:
        return data
    punteggi = []
    for entity in entities:
        cercabile = _cercabile(entity)
        punteggi.append((len(termini_needle & cercabile), len(termini_frase & cercabile)))
    migliore = max(punteggi)
    if migliore == (0, 0):
        return data
    scelte = [e for e, p in zip(entities, punteggi, strict=True) if p == migliore]
    body = yaml.safe_dump(scelte, allow_unicode=True, sort_keys=False)
    return {**data, "result": f"{header}\n{body}"}
