# Contribuire a Needle per Home Assistant

> **English** — Contributions are welcome. Open an issue first for anything beyond a small
> fix, work on a branch of your fork, add tests, and open a pull request against `main`.
> Every pull request needs the maintainer's approval before merging. Issues and pull
> requests can be written in Italian or English.

Grazie per l'interesse! Questo progetto è sperimentale: segnalazioni, misure del benchmark
sulle vostre case e correzioni sono molto utili.

## Prima di iniziare

- Per bug e proposte apri una **issue**: descrivi cosa ti aspettavi, cosa è successo, la
  versione di Home Assistant, l'architettura (es. Raspberry Pi 5) e, se puoi, i log con
  `log_level: debug`.
- Per modifiche non banali apri una issue **prima** di scrivere codice, così concordiamo
  l'approccio.
- Le vulnerabilità di sicurezza **non** vanno nelle issue pubbliche: vedi [SECURITY.md](SECURITY.md).

## Struttura del repository

| Cartella | Contenuto |
|---|---|
| `addon/` | add-on Home Assistant: solo inferenza con Needle (`/v1/infer`, `/health`) |
| `custom_components/needle/` | integrazione: agente conversazionale di Assist |
| `benchmark/` | frasi italiane e script per misurare l'accuratezza |
| `tests/` | test dell'integrazione |

Il confine tra add-on e integrazione è solo l'API HTTP `/v1/infer`: l'add-on non deve
conoscere Home Assistant e l'integrazione non deve conoscere il modello.

## Ambiente di sviluppo

Servono [uv](https://docs.astral.sh/uv/), Python 3.13 e 3.14, Docker (facoltativo, per
provare l'add-on).

```
uv venv .venv-addon --python 3.13 && uv pip install --python .venv-addon -r addon/requirements.txt -r addon/requirements_test.txt
uv venv .venv --python 3.14 && uv pip install --python .venv -r requirements_test.txt
```

## Test

Le tre suite vanno lanciate separatamente e devono passare tutte prima di aprire una PR:

```
.venv-addon/bin/pytest addon/tests
.venv-addon/bin/pytest benchmark
.venv/bin/pytest
```

- Ogni correzione o funzionalità va accompagnata da test (meglio se scritti prima del codice).
- I test dell'integrazione usano Home Assistant vero (`pytest-homeassistant-custom-component`):
  simula solo la chiamata HTTP all'add-on, non le API di Home Assistant.
- Se tocchi le descrizioni dei tool, il motore o le frasi di risposta, allega alla PR il
  risultato del benchmark prima e dopo. Non modificare `benchmark/frasi_it.yaml` per
  migliorare il punteggio.

## Pull request

1. Fai un fork e crea un branch da `main` (es. `fix/timeout-fallback`).
2. Commit piccoli con messaggi chiari, in stile [Conventional Commits](https://www.conventionalcommits.org/)
   (`feat:`, `fix:`, `docs:`, `test:`, `chore:`).
3. Apri la PR verso `main` compilando il modello: cosa cambia, perché, come l'hai testata.
4. **Ogni PR richiede l'approvazione del maintainer** prima del merge. I push diretti su
   `main` non sono consentiti.

## Linee guida

- Segui lo stile del codice esistente: file piccoli con una responsabilità, nomi chiari.
- Le frasi rivolte all'utente sono in italiano e stanno in `custom_components/needle/responses.py`.
- Niente dati personali, token o nomi dei tuoi dispositivi nei commit (attenzione a
  `benchmark/tools_snapshot.json` e `benchmark/frasi_it.yaml`).
- L'add-on deve restare senza accesso a Home Assistant e con la telemetria disattivata.

## Licenza

Contribuendo accetti che il tuo contributo sia distribuito con la licenza
[Apache-2.0](LICENSE) del progetto.
