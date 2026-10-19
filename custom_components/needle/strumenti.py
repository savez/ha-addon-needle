"""Generatore dei tool per Needle a partire dalla casa.

Modulo puro: solo libreria standard, nessuna dipendenza da Home Assistant né
import relativi (il benchmark lo carica per percorso).
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)

MAX_ENUM = 40

MISURE: dict[str, tuple[str, str]] = {
    "temperature": (
        "get_temperature",
        "Tell the current temperature measured in a room, e.g. 'what's the temperature in the "
        "bedroom', 'temperature bathroom', 'how many degrees outside', 'how hot is it'.",
    ),
    "humidity": (
        "get_humidity",
        "Tell the current humidity measured in a room, e.g. 'what's the humidity in the "
        "bathroom', 'how humid is the bedroom', 'humidity outside'.",
    ),
    "illuminance": (
        "get_illuminance",
        "Tell the current light level measured in a room, e.g. 'how bright is the living "
        "room', 'light level in the kitchen', 'illuminance outside'.",
    ),
    "power": (
        "get_power",
        "Tell the current power consumption of a room or device, e.g. 'how much power is "
        "the washing machine using', 'power consumption of the kitchen', 'how many watts now'.",
    ),
    "battery": (
        "get_battery",
        "Tell the battery level of a device, e.g. 'how much battery is left in the door "
        "sensor', 'battery level of the remote', 'is the battery low'.",
    ),
}

_DEVICE_DOMINI = ("switch", "fan", "input_boolean")

_MEDIA_AZIONI = (
    ("pause", "HassMediaPause"),
    ("resume", "HassMediaUnpause"),
    ("next", "HassMediaNext"),
    ("previous", "HassMediaPrevious"),
    ("louder", "HassSetVolumeRelative"),
    ("quieter", "HassSetVolumeRelative"),
)

_VACUUM_AZIONI = (
    ("start", "HassVacuumStart"),
    ("return_to_base", "HassVacuumReturnToBase"),
)


@dataclass(frozen=True)
class Entita:
    entity_id: str
    nome: str
    aree: tuple[str, ...]
    dominio: str
    device_class: str | None


def _split(valore: Any) -> list[str]:
    if not valore:
        return []
    if isinstance(valore, str):
        valore = valore.split(",")
    return [v.strip() for v in valore if isinstance(v, str) and v.strip()]


def entita_da_esposte(esposte: dict[str, dict]) -> list[Entita]:
    """Converte l'output di async_get_exposed_entities in Entita."""
    risultato = []
    for entity_id, info in esposte.items():
        nomi = _split(info.get("names"))
        attributi = info.get("attributes") or {}
        risultato.append(
            Entita(
                entity_id=entity_id,
                nome=nomi[0] if nomi else entity_id,
                aree=tuple(_split(info.get("areas"))),
                dominio=info.get("domain") or entity_id.split(".", 1)[0],
                device_class=attributi.get("device_class"),
            )
        )
    return risultato


def _limita(valori: set[str] | list[str], tool: str, parametro: str) -> list[str]:
    ordinati = sorted(set(valori))
    if len(ordinati) > MAX_ENUM:
        _LOGGER.warning(
            "Tool %s, parametro %s: %d valori, tengo i primi %d in ordine alfabetico",
            tool,
            parametro,
            len(ordinati),
            MAX_ENUM,
        )
        ordinati = ordinati[:MAX_ENUM]
    return ordinati


def _aree(entita: list[Entita]) -> set[str]:
    return {area for e in entita for area in e.aree}


def _stringa(descrizione: str, valori: list[str] | None = None) -> dict[str, Any]:
    schema: dict[str, Any] = {"type": "string", "description": descrizione}
    if valori is not None:
        schema["enum"] = valori
    return schema


def _tool(
    nome: str, descrizione: str, proprieta: dict[str, Any], required: list[str]
) -> dict[str, Any]:
    return {
        "name": nome,
        "description": descrizione,
        "parameters": {"type": "object", "properties": proprieta, "required": required},
    }


def _numero(descrizione: str, minimo: int, massimo: int) -> dict[str, Any]:
    return {
        "type": "integer",
        "description": descrizione,
        "minimum": minimo,
        "maximum": massimo,
    }


def genera_strumenti(entita: list[Entita], intent_disponibili: set[str]) -> list[dict]:
    """Tool per Needle: uno solo se esistono entità del dominio e l'intent di HA."""
    per_dominio: dict[str, list[Entita]] = {}
    for e in sorted(entita, key=lambda x: (x.nome, x.entity_id)):
        per_dominio.setdefault(e.dominio, []).append(e)
    on_off = {"HassTurnOn", "HassTurnOff"} <= intent_disponibili
    tools: list[dict] = []

    luci = per_dominio.get("light", [])
    if luci and on_off:
        stanze = _limita(_aree(luci), "lights", "room")[: MAX_ENUM - 1] + ["all"]
        proprieta = {
            "room": _stringa("Room name, or 'all' for the whole house", stanze),
            "state": _stringa("Desired state", ["on", "off"]),
        }
        if "HassLightSet" in intent_disponibili:
            proprieta["brightness"] = _numero("Brightness percentage", 1, 100)
        tools.append(
            _tool(
                "lights",
                "Turn lights on or off, or set brightness, in one room or in the whole house, "
                "e.g. 'turn on the bathroom light', 'turn off all the lights', "
                "'kitchen light at 50%'.",
                proprieta,
                ["state"],
            )
        )

    clima = per_dominio.get("climate", [])
    if clima and on_off:
        proprieta = {}
        stanze = _limita(_aree(clima), "air_conditioner", "room")
        if stanze:
            proprieta["room"] = _stringa("Room name", stanze)
        proprieta["state"] = _stringa("Desired state", ["on", "off"])
        if "HassClimateSetTemperature" in intent_disponibili:
            proprieta["temperature"] = {
                "type": "number",
                "description": "Target temperature in degrees",
            }
        tools.append(
            _tool(
                "air_conditioner",
                "Turn the air conditioner or heating on or off, or set the target "
                "temperature, e.g. 'turn on the bedroom air conditioner', "
                "'set the living room to 22 degrees', 'turn off the heating'.",
                proprieta,
                [],
            )
        )

    tende = per_dominio.get("cover", [])
    if tende and on_off:
        proprieta = {}
        stanze = _limita(_aree(tende), "blinds", "room")
        if stanze:
            proprieta["room"] = _stringa("Room name", stanze)
        proprieta["action"] = _stringa("Desired action", ["open", "close"])
        if "HassSetPosition" in intent_disponibili:
            proprieta["position"] = _numero("Opening percentage, 0 closed, 100 open", 0, 100)
        tools.append(
            _tool(
                "blinds",
                "Open or close the blinds, shutters or curtains, or set how far they are "
                "open, e.g. 'open the bedroom blinds', 'close the shutters', "
                "'living room curtains at 30%'.",
                proprieta,
                ["action"],
            )
        )

    if per_dominio.get("media_player"):
        azioni = [a for a, intent in _MEDIA_AZIONI if intent in intent_disponibili]
        if azioni:
            tools.append(
                _tool(
                    "media",
                    "Control the media player: pause, resume, skip to next or previous "
                    "track, change volume, e.g. 'pause the music', 'next song', "
                    "'turn the volume up'.",
                    {"action": _stringa("Desired action", azioni)},
                    ["action"],
                )
            )

    dispositivi = [e for d in _DEVICE_DOMINI for e in per_dominio.get(d, [])]
    if dispositivi and on_off:
        nomi = _limita([e.nome for e in dispositivi], "device", "name")
        tools.append(
            _tool(
                "device",
                "Turn a named device such as a plug, switch or fan on or off, e.g. "
                "'turn on the coffee machine', 'turn off the fan', 'switch off the "
                "christmas tree plug'.",
                {
                    "name": _stringa("Device name", nomi),
                    "state": _stringa("Desired state", ["on", "off"]),
                },
                ["name", "state"],
            )
        )

    aspirapolveri = per_dominio.get("vacuum", [])
    if aspirapolveri:
        azioni = [a for a, intent in _VACUUM_AZIONI if intent in intent_disponibili]
        if azioni:
            proprieta = {"action": _stringa("Desired action", azioni)}
            if len(aspirapolveri) > 1:
                nomi = _limita([e.nome for e in aspirapolveri], "vacuum", "name")
                proprieta["name"] = _stringa("Vacuum name", nomi)
            tools.append(
                _tool(
                    "vacuum",
                    "Start the robot vacuum cleaner or send it back to its base, e.g. "
                    "'start the vacuum', 'clean the house', 'send the robot back to the dock'.",
                    proprieta,
                    ["action"],
                )
            )

    if "GetLiveContext" in intent_disponibili:
        sensori = per_dominio.get("sensor", [])
        for device_class, (nome_tool, descrizione) in MISURE.items():
            candidati = [e for e in sensori if e.device_class == device_class]
            stanze = _aree(candidati)
            senza_area = {e.nome for e in candidati if not e.aree}
            valori = sorted(stanze) + sorted(senza_area - stanze)
            if len(valori) > MAX_ENUM:
                _LOGGER.warning(
                    "Tool %s, parametro room: %d valori, tengo i primi %d",
                    nome_tool,
                    len(valori),
                    MAX_ENUM,
                )
                valori = valori[:MAX_ENUM]
            if not valori:
                continue
            tools.append(
                _tool(
                    nome_tool,
                    descrizione,
                    {"room": _stringa("Room name or sensor name", valori)},
                    [],
                )
            )

    if "GetDateTime" in intent_disponibili:
        tools.append(
            _tool(
                "get_time",
                "Tell the current time or date, e.g. 'what time is it', 'what day is it "
                "today', 'what's the date'.",
                {},
                [],
            )
        )

    return tools
