"""Risposta parlata: Needle non genera testo, la costruiamo dai risultati dei tool."""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
from typing import Any

import yaml

from .convert import base_name

NON_DOMOTICA = "Non ho capito, posso aiutarti solo con i dispositivi di casa."
ERRORE_INTERNO = "Errore interno di Needle."
AVVISO_FALLBACK = "⚠️ Needle non risponde, ho usato l'agente standard."
ERRORE_DISPOSITIVO = (
    "Non sono riuscito a eseguire il comando: non trovo il dispositivo o non è esposto ad Assist."
)
ERRORE_GENERICO = "Non sono riuscito a eseguire il comando."
NOTA_CONDIZIONALE = "Ho controllato ora, non ho creato una regola."

MAX_ENTITA_LETTE = 5

VERBI = {
    "HassTurnOn": "Ho acceso",
    "HassTurnOff": "Ho spento",
    "HassLightSet": "Ho regolato",
    "HassClimateSetTemperature": "Ho impostato la temperatura di",
    "HassSetPosition": "Ho impostato la posizione di",
    "HassMediaPause": "Ho messo in pausa",
    "HassMediaUnpause": "Ho ripreso",
    "HassSetVolume": "Ho impostato il volume di",
}

STATI = {
    "on": "acceso",
    "off": "spento",
    "open": "aperto",
    "closed": "chiuso",
    "opening": "in apertura",
    "closing": "in chiusura",
    "locked": "chiuso a chiave",
    "unlocked": "sbloccato",
    "unavailable": "non disponibile",
    "unknown": "sconosciuto",
    "playing": "in riproduzione",
    "paused": "in pausa",
    "idle": "inattivo",
    "home": "a casa",
    "not_home": "fuori casa",
    "heat": "riscaldamento",
    "cool": "raffreddamento",
}

_CONDIZIONALE = re.compile(r"^\s*(se|qualora)\b", re.IGNORECASE)
_ERRORI_DISPOSITIVO = {"MatchFailedError", "NoStatesMatchedError"}


@dataclass(frozen=True)
class ToolOutcome:
    name: str
    data: dict[str, Any]
    error: bool
    read_only: bool


def serialize_outcomes(outcomes: list[ToolOutcome]) -> str:
    return json.dumps(
        [{"tool": o.name, "data": o.data, "error": o.error} for o in outcomes],
        ensure_ascii=False,
        default=str,
    )


def build_response(query: str, outcomes: list[ToolOutcome]) -> str:
    if not outcomes:
        return NON_DOMOTICA
    condizionale = bool(_CONDIZIONALE.match(query))
    azioni = [o for o in outcomes if not o.read_only]
    if azioni:
        testo = " ".join(_descrivi_azione(o) for o in azioni)
        return f"{testo} {NOTA_CONDIZIONALE}" if condizionale else testo
    stati = _descrivi_letture(outcomes)
    if stati is None:
        return ERRORE_DISPOSITIVO
    if condizionale:
        return f"Ho controllato ora: {stati}. Non ho fatto nulla e non ho creato una regola."
    return f"{stati}."


def _speech(data: dict[str, Any]) -> str:
    plain = (data.get("speech") or {}).get("plain") or {}
    return str(plain.get("speech") or "")


def _descrivi_azione(outcome: ToolOutcome) -> str:
    data = outcome.data
    if outcome.error or data.get("response_type") == "error":
        if data.get("error") in _ERRORI_DISPOSITIVO:
            return ERRORE_DISPOSITIVO
        return ERRORE_GENERICO
    nomi = [t["name"] for t in (data.get("data") or {}).get("success", []) if t.get("name")]
    verbo = VERBI.get(base_name(outcome.name))
    if verbo and nomi:
        return f"{verbo} {', '.join(nomi)}."
    # I testi degli intent di HA possono essere in inglese: solo come ripiego.
    if speech := _speech(data):
        return speech
    return "Fatto."


def _descrivi_letture(outcomes: list[ToolOutcome]) -> str | None:
    descrizioni: list[str] = []
    for outcome in outcomes:
        if outcome.error:
            continue
        if base_name(outcome.name) == "GetLiveContext":
            descrizioni.extend(_descrivi_entita(e) for e in _parse_live_context(outcome.data))
        elif base_name(outcome.name) == "GetDateTime":
            if ora := _ora(outcome.data):
                descrizioni.append(f"Sono le {ora}")
        elif speech := _speech(outcome.data):
            descrizioni.append(speech)
    if not descrizioni:
        # Letture riuscite ma senza nulla da descrivere: non è un errore.
        return None if any(o.error for o in outcomes) else "Fatto"
    testo = "; ".join(descrizioni[:MAX_ENTITA_LETTE])
    if len(descrizioni) > MAX_ENTITA_LETTE:
        testo += f" e altri {len(descrizioni) - MAX_ENTITA_LETTE}"
    return testo


def _ora(data: dict[str, Any]) -> str:
    return ":".join(str(data.get("time") or "").split(":")[:2]) if data.get("time") else ""


def _parse_live_context(data: dict[str, Any]) -> list[dict[str, Any]]:
    _, _, body = str(data.get("result") or "").partition("\n")
    try:
        parsed = yaml.safe_load(body)
    except yaml.YAMLError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _descrivi_entita(entity: dict[str, Any]) -> str:
    nome = str(entity.get("names") or "").split(",")[0].strip()
    stato_raw = str(entity.get("state", ""))
    stato = STATI.get(stato_raw, stato_raw)
    unita = (entity.get("attributes") or {}).get("unit_of_measurement")
    return f"{nome}: {stato} {unita}" if unita else f"{nome}: {stato}"
