"""Conversione tra i tool di Home Assistant e il formato di Needle."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any

import probatio

from homeassistant.helpers import llm


def format_tools(api: llm.APIInstance) -> list[dict[str, Any]]:
    """Tool dell'API LLM in JSON schema, come fa l'integrazione Ollama."""
    return [
        {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": probatio.to_openapi(
                tool.parameters,
                custom_serializer=api.custom_serializer,
                openapi_version="3.1.0",
            ),
        }
        for tool in api.tools
    ]


def needle_tools(api: llm.APIInstance) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Tool come li vede Needle, più la mappa nome per Needle → nome reale in HA.

    HA 2026.10 prefissa i nomi dei tool ("intent__HassTurnOn", "media_player__…"):
    il prefisso confonde Needle, che finisce per scegliere i tool con il prefisso
    più frequente. Lo togliamo quando il nome base resta univoco.
    """
    tools = format_tools(api)
    counts = Counter(base_name(tool["name"]) for tool in tools)
    real_names: dict[str, str] = {}
    shown: list[dict[str, Any]] = []
    for tool in tools:
        name = base_name(tool["name"]) if counts[base_name(tool["name"])] == 1 else tool["name"]
        real_names[name] = tool["name"]
        shown.append({**tool, "name": name})
    return shown, real_names


def read_only_tools(api: llm.APIInstance) -> set[str]:
    return {tool.name for tool in api.tools if tool.annotations.read_only}


def base_name(tool_name: str) -> str:
    return tool_name.rsplit("__", 1)[-1]


def clean_args(args: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    """Ripara gli errori tipici dei modelli piccoli prima della validazione di HA."""
    properties: dict[str, Any] = parameters.get("properties") or {}
    cleaned: dict[str, Any] = {}
    for key, value in args.items():
        if value is None or value == "" or key not in properties:
            continue
        if isinstance(value, str) and _array_only(properties[key]):
            value = [value]
        cleaned[key] = value
    return cleaned


def drop_ungrounded(
    tool_name: str, args: dict[str, Any], ungrounded: list[str]
) -> dict[str, Any]:
    """Rimuove gli argomenti che Needle segnala come inventati.

    I percorsi hanno la forma "<nome del tool>.<argomento>", dove il nome può
    essere prefissato (es. "intent__HassTurnOff.device_class") o in snake_case
    ("hass_turn_off.device_class").
    """
    target = _norm(base_name(tool_name))
    bad: set[str] = set()
    for path in ungrounded:
        tool_part, _, arg_path = path.partition(".")
        if arg_path and _norm(base_name(tool_part)) == target:
            bad.add(re.split(r"[.\[]", arg_path, maxsplit=1)[0])
    return {key: value for key, value in args.items() if key not in bad}


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _types(schema: dict[str, Any]) -> set[str]:
    if "type" in schema:
        kind = schema["type"]
        return set(kind) if isinstance(kind, list) else {kind}
    found: set[str] = set()
    for sub in [*schema.get("anyOf", []), *schema.get("oneOf", [])]:
        found |= _types(sub)
    return found


def _array_only(schema: dict[str, Any]) -> bool:
    kinds = _types(schema)
    return "array" in kinds and "string" not in kinds
