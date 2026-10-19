"""Esegue il benchmark contro un add-on Needle in esecuzione.

Uso:
    .venv-addon/bin/python -I benchmark/run_benchmark.py --url http://localhost:8765
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import urllib.request

sys.path.insert(0, str(Path(__file__).parent))

from benchmark import load_cases, run  # noqa: E402

HERE = Path(__file__).parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://localhost:8765")
    parser.add_argument("--frasi", type=Path, default=HERE / "frasi_it.yaml")
    parser.add_argument("--tools", type=Path, default=HERE / "tools_snapshot.json")
    args = parser.parse_args()

    tools = json.loads(args.tools.read_text(encoding="utf-8"))
    if isinstance(tools, dict):  # file di diagnostica completo di HA
        tools = tools.get("data", tools).get("tools", [])

    def infer(tools_: list, turni: list) -> dict:
        body = json.dumps({"tools": tools_, "turni": turni}).encode("utf-8")
        request = urllib.request.Request(
            f"{args.url}/v1/infer", data=body, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(request, timeout=30) as resp:  # noqa: S310 - URL locale
            return json.loads(resp.read())

    print(run(load_cases(args.frasi), tools, infer).summary())


if __name__ == "__main__":
    main()
