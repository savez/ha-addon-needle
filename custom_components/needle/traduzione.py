"""Traduzione delle chiamate di Needle negli intent di Home Assistant.

Modulo puro: nessuna dipendenza da Home Assistant né import relativi (il
benchmark lo carica per percorso). Riceve i tool generati come argomento.
"""

from __future__ import annotations

from typing import Any

import yaml

# Tool di lettura generati -> device_class da filtrare (get_time: nessun filtro).
# Deve coincidere con strumenti.MISURE (verificato nei test).
LETTURE: dict[str, str | None] = {
    "get_temperature": "temperature",
    "get_humidity": "humidity",
    "get_illuminance": "illuminance",
    "get_power": "power",
    "get_battery": "battery",
    "get_time": None,
}

_MEDIA = {
    "pause": ("HassMediaPause", {}),
    "resume": ("HassMediaUnpause", {}),
    "next": ("HassMediaNext", {}),
    "previous": ("HassMediaPrevious", {}),
    "louder": ("HassSetVolumeRelative", {"volume_step": "up"}),
    "quieter": ("HassSetVolumeRelative", {"volume_step": "down"}),
}
_VACUUM = {"start": "HassVacuumStart", "return_to_base": "HassVacuumReturnToBase"}
_ON_OFF = {"on": "HassTurnOn", "off": "HassTurnOff"}
# Domini del tool "device": devono coincidere con strumenti._DEVICE_DOMINI (verificato nei test).
DOMINI_DEVICE = ("switch", "fan", "input_boolean")


def e_lettura(nome_tool: str) -> bool:
    return nome_tool in LETTURE


def _numero(valore: Any) -> float | int | None:
    if isinstance(valore, bool):
        return None
    if isinstance(valore, (int, float)):
        return valore
    if isinstance(valore, str):
        try:
            return float(valore.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def _percentuale(valore: Any) -> int | None:
    numero = _numero(valore)
    return None if numero is None else round(numero)


def _normalizza(call: dict, tool: dict) -> dict[str, Any]:
    """Tiene solo gli argomenti noti; gli enum sono riportati al valore reale."""
    proprieta = (tool.get("parameters") or {}).get("properties") or {}
    argomenti = call.get("arguments")
    if not isinstance(argomenti, dict):
        return {}
    risultato: dict[str, Any] = {}
    for chiave, valore in argomenti.items():
        schema = proprieta.get(chiave)
        if schema is None:
            continue
        if "enum" in schema:
            if not isinstance(valore, str):
                continue
            reali = {v.casefold(): v for v in schema["enum"]}
            trovato = reali.get(valore.strip().casefold())
            if trovato is not None:
                risultato[chiave] = trovato
        elif schema.get("type") in ("integer", "number"):
            numero = (
                _percentuale(valore) if schema["type"] == "integer" else _numero(valore)
            )
            if numero is not None:
                risultato[chiave] = numero
    return risultato


def _chiamata(intent: str, disponibili: set[str], **args: Any) -> list[dict]:
    if intent not in disponibili:
        return []
    return [{"tool": intent, "args": args}]


def _con_area(area: str | None, args: dict[str, Any]) -> dict[str, Any]:
    return ({"area": area} if area else {}) | args


def traduci(
    call: dict, strumenti: list[dict], intent_disponibili: set[str], aree: set[str]
) -> list[dict]:
    """Converte una chiamata di Needle in [{"tool": intent, "args": {...}}] o []."""
    nome = call.get("name") if isinstance(call, dict) else None
    tool = next((t for t in strumenti if t["name"] == nome), None)
    if tool is None:
        return []
    a = _normalizza(call, tool)
    proprieta = tool["parameters"]["properties"]
    stato = a.get("state")
    ok = intent_disponibili

    if nome == "lights":
        stanza = a.get("room")
        if stanza is None:
            return []
        area = None if stanza == "all" else stanza
        if "brightness" in a:
            return _chiamata(
                "HassLightSet", ok, **_con_area(area, {"brightness": a["brightness"]})
            )
        if stato in _ON_OFF:
            return _chiamata(
                _ON_OFF[stato], ok, **_con_area(area, {"domain": ["light"]})
            )
        return []

    if nome in ("air_conditioner", "blinds"):
        area = a.get("room")
        if "room" in proprieta and area is None:
            return []
        if nome == "air_conditioner":
            if "temperature" in a:
                return _chiamata(
                    "HassClimateSetTemperature",
                    ok,
                    **_con_area(area, {"temperature": a["temperature"]}),
                )
            if stato in _ON_OFF:
                return _chiamata(
                    _ON_OFF[stato], ok, **_con_area(area, {"domain": ["climate"]})
                )
            return []
        if "position" in a:
            return _chiamata(
                "HassSetPosition",
                ok,
                **_con_area(area, {"position": a["position"], "domain": ["cover"]}),
            )
        intent = {"open": "HassTurnOn", "close": "HassTurnOff"}.get(a.get("action"))
        if intent:
            return _chiamata(intent, ok, **_con_area(area, {"domain": ["cover"]}))
        return []

    if nome == "media":
        voce = _MEDIA.get(a.get("action"))
        return _chiamata(voce[0], ok, **voce[1]) if voce else []

    if nome == "device":
        if "name" in a and stato in _ON_OFF:
            return _chiamata(
                _ON_OFF[stato], ok, name=a["name"], domain=list(DOMINI_DEVICE)
            )
        return []

    if nome == "vacuum":
        intent = _VACUUM.get(a.get("action"))
        if not intent:
            return []
        return _chiamata(intent, ok, **({"name": a["name"]} if "name" in a else {}))

    if nome == "get_time":
        return _chiamata("GetDateTime", ok)

    if e_lettura(nome):
        stanza = a.get("room")
        if stanza is None:
            return _chiamata("GetLiveContext", ok)
        chiave = "area" if stanza in aree else "name"
        return _chiamata("GetLiveContext", ok, **{chiave: stanza})

    return []


def filtra_misura(data: dict, device_class: str) -> dict:
    """Tiene nel risultato di GetLiveContext solo le entità di quella device_class."""
    risultato = data.get("result") if isinstance(data, dict) else None
    if not isinstance(risultato, str):
        return data
    testa, separatore, corpo = risultato.partition("\n")
    if not separatore:
        return data
    try:
        elementi = yaml.safe_load(corpo)
    except yaml.YAMLError:
        return data
    if not isinstance(elementi, list):
        return data
    filtrati = [
        e
        for e in elementi
        if isinstance(e, dict)
        and isinstance(e.get("attributes"), dict)
        and e["attributes"].get("device_class") == device_class
    ]
    testo = yaml.safe_dump(filtrati, allow_unicode=True, sort_keys=False)
    return {**data, "result": f"{testa}\n{testo}"}
