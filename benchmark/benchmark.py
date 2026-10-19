"""Logica del benchmark: casi, punteggio, report."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import importlib.util
from pathlib import Path
import sys
from typing import Any

import yaml

_INTEGRAZIONE = Path(__file__).resolve().parent.parent / "custom_components" / "needle"


def _carica_modulo(nome: str) -> Any:
    """Carica un modulo puro dell'integrazione per percorso (nessun import del pacchetto)."""
    chiave = f"needle_{nome}"
    if chiave in sys.modules:
        return sys.modules[chiave]
    spec = importlib.util.spec_from_file_location(chiave, _INTEGRAZIONE / f"{nome}.py")
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[chiave] = modulo
    spec.loader.exec_module(modulo)
    return modulo


strumenti = _carica_modulo("strumenti")
traduzione = _carica_modulo("traduzione")
protezioni = _carica_modulo("protezioni")
Entita = strumenti.Entita
genera_strumenti = strumenti.genera_strumenti


def carica_casa(path: Path) -> tuple[list[Any], set[str]]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entita = [
        Entita(
            entity_id=item["entity_id"],
            nome=item["nome"],
            aree=(item["area"],) if item.get("area") else (),
            dominio=item["dominio"],
            device_class=item.get("device_class"),
        )
        for item in raw["entita"]
    ]
    return entita, set(raw["intent"])


def passo_bloccato(
    frase: str, calls: list[dict[str, Any]], nomi_vacuum: list[str] | tuple[str, ...] = ()
) -> bool:
    """Le protezioni dell'integrazione (protezioni.motivo_blocco) su tutte le chiamate di un passo.

    Come nell'integrazione, se una chiamata va bloccata non si esegue nulla del passo.
    Differenza nota: l'integrazione considera solo le chiamate che sa tradurre in intent.
    """
    chiamate = [
        (_base(c.get("name", "")), c.get("arguments"), traduzione.e_lettura(_base(c.get("name", ""))))
        for c in calls
    ]
    return protezioni.motivo_blocco(frase, chiamate, list(nomi_vacuum)) is not None


@dataclass
class Step:
    atteso: list[dict[str, Any]]
    risultato: str | None = None


@dataclass
class Case:
    frase: str
    passi: list[Step]
    pericolosa: bool = False


@dataclass
class Report:
    righe: list[str] = field(default_factory=list)
    passi: int = 0
    passi_tool_ok: int = 0
    passi_args_ok: int = 0
    conf_ok: list[float] = field(default_factory=list)
    conf_ko: list[float] = field(default_factory=list)
    durate: list[int] = field(default_factory=list)
    scartate: int = 0
    pericolose_prima: int = 0
    pericolose_dopo: int = 0
    sbagliate_prima: int = 0
    sbagliate_dopo: int = 0

    def summary(self) -> str:
        def media(values: list[float]) -> str:
            return f"{sum(values) / len(values):.2f}" if values else "-"

        return "\n".join(
            [
                *self.righe,
                "",
                f"Tool corretti: {self.passi_tool_ok}/{self.passi}",
                f"Tool e argomenti corretti: {self.passi_args_ok}/{self.passi}",
                f"Scartate (nessuna chiamata): {self.scartate}/{self.passi}",
                f"azioni pericolose (frasi marcate): {self.pericolose_dopo} dopo le protezioni "
                f"({self.pericolose_prima} prima)",
                f"azioni sbagliate eseguite (tutte le frasi): {self.sbagliate_dopo} dopo le protezioni "
                f"({self.sbagliate_prima} prima)",
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
        cases.append(Case(frase=item["frase"], passi=passi, pericolosa=bool(item.get("pericolosa"))))
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
    bloccata: Callable[[str, list[dict[str, Any]]], bool] | None = None,
) -> Report:
    report = Report()
    for case in cases:
        turni = [case.frase]
        for index, step in enumerate(case.passi):
            response = infer(tools, list(turni))
            calls = response.get("function_calls") or []
            tool_ok, args_ok = score_step(step.atteso, calls)
            report.passi += 1
            report.scartate += not calls
            fuori = [
                c
                for c in calls
                if not traduzione.e_lettura(_base(c.get("name", "")))
                and not any(score_step([a], [c]) == (True, True) for a in step.atteso)
            ]
            bloccato = bool(bloccata and calls and bloccata(case.frase, calls))
            eseguite = 0 if bloccato else len(fuori)
            report.sbagliate_prima += len(fuori)
            report.sbagliate_dopo += eseguite
            if case.pericolosa:
                report.pericolose_prima += len(fuori)
                report.pericolose_dopo += eseguite
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
