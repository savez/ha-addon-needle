"""Esegue il benchmark contro un add-on Needle in esecuzione.

Uso:
    .venv-addon/bin/python -I benchmark/run_benchmark.py --url http://localhost:8765 [--tools generati|snapshot]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).parent))

from benchmark import carica_casa, genera_strumenti, load_cases, passo_bloccato, run  # noqa: E402

HERE = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8765")
    parser.add_argument("--tools", choices=["generati", "snapshot"], default="generati")
    parser.add_argument("--frasi", type=Path, default=None)
    parser.add_argument("--snapshot", type=Path, default=HERE / "tools_snapshot.json")
    args = parser.parse_args()

    if args.tools == "generati":
        entita, intent = carica_casa(HERE / "casa.yaml")
        tools = genera_strumenti(entita, intent)
        frasi = args.frasi or HERE / "frasi_it.yaml"
        nomi_vacuum = [e.nome for e in entita if e.dominio == "vacuum"]

        def bloccata(frase: str, calls: list) -> bool:
            return passo_bloccato(frase, calls, nomi_vacuum)

    else:
        tools = json.loads(args.snapshot.read_text(encoding="utf-8"))
        if isinstance(tools, dict):  # file di diagnostica completo di HA
            tools = tools.get("data", tools).get("tools", [])
        frasi = args.frasi or HERE / "frasi_assist_it.yaml"
        bloccata = None

    def infer(tools_: list, turni: list) -> dict:
        body = json.dumps({"tools": tools_, "turni": turni}).encode("utf-8")
        request = urllib.request.Request(
            f"{args.url}/v1/infer", data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=30) as resp:  # noqa: S310 - URL locale
            return json.loads(resp.read())

    print(run(load_cases(frasi), tools, infer, bloccata).summary())


if __name__ == "__main__":
    main()
