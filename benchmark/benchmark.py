"""Logica del benchmark: casi, punteggio, report."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class Step:
    atteso: list[dict[str, Any]]
    risultato: str | None = None


@dataclass
class Case:
    frase: str
    passi: list[Step]


@dataclass
class Report:
    righe: list[str] = field(default_factory=list)
    passi: int = 0
    passi_tool_ok: int = 0
    passi_args_ok: int = 0
    conf_ok: list[float] = field(default_factory=list)
    conf_ko: list[float] = field(default_factory=list)
    durate: list[int] = field(default_factory=list)

    def summary(self) -> str:
        def media(values: list[float]) -> str:
            return f"{sum(values) / len(values):.2f}" if values else "-"

        return "\n".join(
            [
                *self.righe,
                "",
                f"Tool corretti: {self.passi_tool_ok}/{self.passi}",
                f"Tool e argomenti corretti: {self.passi_args_ok}/{self.passi}",
                f"Confidenza media: giusti {media(self.conf_ok)}, sbagliati {media(self.conf_ko)}",
                f"Latenza: media {media([float(d) for d in self.durate])} ms, max {max(self.durate, default=0)} ms",
            ]
        )


def load_cases(path: Path) -> list[Case]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    cases: list[Case] = []
    for item in raw:
        if "passi" in item:
            passi = [Step(atteso=p.get("atteso") or [], risultato=p.get("risultato")) for p in item["passi"]]
        else:
            passi = [Step(atteso=item.get("atteso") or [])]
        cases.append(Case(frase=item["frase"], passi=passi))
    return cases


def _base(name: str) -> str:
    return name.rsplit("__", 1)[-1]


def _arg_ok(expected: Any, actual: Any) -> bool:
    if actual is None:
        return False
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return float(actual) == float(expected)
        except (TypeError, ValueError):
            return False
    text = " ".join(map(str, actual)) if isinstance(actual, list) else str(actual)
    return str(expected).lower() in text.lower()


def score_step(atteso: list[dict[str, Any]], calls: list[dict[str, Any]]) -> tuple[bool, bool]:
    expected_tools = sorted(item["tool"] for item in atteso)
    actual_tools = sorted(_base(call.get("name", "")) for call in calls)
    if expected_tools != actual_tools:
        return False, False
    remaining = list(calls)
    for item in atteso:
        match = next(
            (
                call
                for call in remaining
                if _base(call.get("name", "")) == item["tool"]
                and all(
                    _arg_ok(value, (call.get("arguments") or {}).get(key))
                    for key, value in (item.get("argomenti") or {}).items()
                )
            ),
            None,
        )
        if match is None:
            return True, False
        remaining.remove(match)
    return True, True


def run(
    cases: list[Case],
    tools: list[dict[str, Any]],
    infer: Callable[[list[dict[str, Any]], list[str]], dict[str, Any]],
) -> Report:
    report = Report()
    for case in cases:
        turni = [case.frase]
        for index, step in enumerate(case.passi):
            response = infer(tools, list(turni))
            calls = response.get("function_calls") or []
            tool_ok, args_ok = score_step(step.atteso, calls)
            report.passi += 1
            report.passi_tool_ok += tool_ok
            report.passi_args_ok += args_ok
            if (conf := response.get("confidence")) is not None:
                (report.conf_ok if args_ok else report.conf_ko).append(float(conf))
            report.durate.append(int(response.get("durata_ms", 0)))
            esito = "OK  " if args_ok else ("TOOL" if tool_ok else "NO  ")
            report.righe.append(
                f"{esito} {case.frase!r} passo {index + 1}: atteso {[a['tool'] for a in step.atteso]} "
                f"→ {[(_base(c.get('name', '')), c.get('arguments')) for c in calls]} conf={response.get('confidence')}"
            )
            if step.risultato is None:
                break
            turni.append(step.risultato)
    return report
