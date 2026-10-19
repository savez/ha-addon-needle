"""Risoluzione dei nomi con un modello di embedding.

Needle sceglie il tool ed estrae nome e area così come li ha detti l'utente
("bagnetto", "temperatrua cameretta"). Home Assistant però riconosce solo i
nomi, gli alias e le aree reali. Il modello di embedding sostituisce il valore
estratto con l'entità o l'area reale più vicina, se è abbastanza simile.
"""

from __future__ import annotations

from typing import Any, Protocol


class Embedder(Protocol):
    """Vettori normalizzati: il prodotto scalare è la similarità del coseno."""

    def query(self, text: str) -> list[float]: ...

    def documento(self, text: str) -> list[float]: ...


# Peso della frase intera rispetto al valore estratto da Needle: con "cameretta"
# la frase ("temperatura") sceglie tra le entità della stessa stanza.
PESO_FRASE = 0.5


def _dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=False))


def _testo_entita(entita: dict[str, Any]) -> str:
    parti = [str(entita.get("nome") or "")]
    parti += [str(a) for a in entita.get("alias") or []]
    parti += [str(a) for a in entita.get("aree") or []]
    return ", ".join(p for p in parti if p)


class Risolutore:
    """Riscrive name e area delle chiamate di Needle con i nomi reali."""

    def __init__(self, embedder: Embedder, soglia: float) -> None:
        self._embedder = embedder
        self._soglia = soglia

    def risolvi(
        self, response: dict[str, Any], frase: str, entita: list[dict[str, Any]]
    ) -> dict[str, Any]:
        # Anche le chiamate scartate: l'integrazione esegue quelle di sola lettura.
        chiavi = [k for k in ("function_calls", "suppressed_calls") if response.get(k)]
        if not chiavi or not entita:
            return response
        aree = sorted({str(a) for e in entita for a in e.get("aree") or [] if a})
        # Un'area usata come nome ("cameretta") non è un nome valido per HA.
        noti = {
            "name": {
                str(n).casefold()
                for e in entita
                for n in [e.get("nome"), *(e.get("alias") or [])]
                if n
            },
            "area": {a.casefold() for a in aree},
        }
        vettore_frase = self._embedder.query(frase)
        candidati = {
            "name": [(str(e["nome"]), _testo_entita(e)) for e in entita if e.get("nome")],
            "area": [(a, a) for a in aree],
        }
        risoluzioni: list[dict[str, Any]] = []
        result = dict(response)
        for lista in chiavi:
            nuove = []
            for call in response[lista]:
                args = dict(call.get("arguments") or {})
                for chiave in ("name", "area"):
                    valore = args.get(chiave)
                    if not isinstance(valore, str) or not valore or valore.casefold() in noti[chiave]:
                        continue
                    scelta = self._migliore(valore, vettore_frase, candidati[chiave])
                    risoluzioni.append({"argomento": chiave, "da": valore, **scelta})
                    if scelta["similarita"] >= self._soglia:
                        args[chiave] = scelta["a"]
                nuove.append({**call, "arguments": args})
            result[lista] = nuove
        result["risoluzioni"] = risoluzioni
        return result

    def _migliore(
        self, valore: str, vettore_frase: list[float], candidati: list[tuple[str, str]]
    ) -> dict[str, Any]:
        vettore = self._embedder.query(valore)
        punteggi = []
        for nome, testo in candidati:
            doc = self._embedder.documento(testo)
            punteggi.append((_dot(vettore, doc) + PESO_FRASE * _dot(vettore_frase, doc), nome, doc))
        _, nome, doc = max(punteggi)
        # La soglia vale sul valore estratto da solo: la frase serve a scegliere,
        # non a far passare un nome che non c'entra.
        return {"a": nome, "similarita": round(_dot(vettore, doc), 3)}
