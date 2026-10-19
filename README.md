# Needle Local AI

> **English summary** — A **local** conversation agent for Home Assistant Assist, like the
> Gemini integration but running the tiny [Needle 3](https://cactuscompute.com/needle)
> tool-calling model (~35 MB, Apache-2.0) on your own hardware, even a Raspberry Pi 5.
> It ships as an **add-on** (inference only, no access to Home Assistant) plus a **custom
> integration** (the Assist agent: Home Assistant executes the actions on exposed entities).
> Built and tested for **Italian**. Experimental: measured accuracy with the base model is
> still low — see *Limiti noti* and run the benchmark on your setup.

Agente conversazionale **locale** per Assist, come l'integrazione Gemini ma con il
modello [Needle 3](https://cactuscompute.com/needle) (Cactus Compute, Apache-2.0, ~35 MB)
che gira sul tuo Home Assistant, anche su Raspberry Pi 5.

Supporta comandi, domande sullo stato e più azioni nella stessa frase. Le frasi
condizionali ("se la luce del bagno è spenta accendi la camera") sono **bloccate per
sicurezza**: vedi [Frasi condizionali](#frasi-condizionali).

## Come funziona

```
Assist ──► integrazione Needle ──(frase + tool)──► add-on Needle (inferenza locale)
                │        ▲                                │
                │        └────────── tool call ───────────┘
                ▼
       Home Assistant esegue le azioni sulle entità esposte ad Assist
```

- **Add-on Needle Local AI**: fa solo inferenza. Riceve la frase e i tool di Assist, restituisce le
  chiamate ai tool. Non ha accesso a Home Assistant e non espone porte sull'host.
- **Integrazione Needle Local AI**: è l'agente di Assist. Usa l'API LLM "Assist" di Home Assistant
  (gli stessi tool che usa Gemini), lascia che sia Home Assistant a eseguirli e costruisce
  la risposta in italiano.
- Se l'add-on non risponde, la frase passa all'agente standard di Home Assistant (con un
  avviso, disattivabile).

## Requisiti

- Home Assistant **2026.10** o successivo (Home Assistant OS o Supervised, per l'add-on).
- Architettura `aarch64` (es. Raspberry Pi 5) o `amd64`.
- Circa 150 MB di RAM per l'add-on.
- Connessione internet solo al primo avvio dell'add-on, per scaricare il modello (~35 MB) da
  Hugging Face. Poi funziona offline.

## Installazione

1. **Add-on**: Impostazioni → Add-on → Store → ⋮ → Repository → aggiungi
   `https://github.com/savez/ha-addon-needle`, installa **Needle Local AI** e avvialo. Al primo avvio
   scarica il modello: attendi nel log il messaggio "Modello Needle pronto".
2. **Integrazione**: con HACS aggiungi questo repository come *Integration* (repository
   personalizzato), oppure copia `custom_components/needle/` in `config/custom_components/`.
   Riavvia Home Assistant.
3. Impostazioni → Dispositivi e servizi → Aggiungi integrazione → **Needle Local AI**. L'URL di default
   è `http://local-needle:8765` (add-on installato in locale); se hai installato l'add-on da
   questo repository il nome host è diverso: lo trovi nella pagina dell'add-on (campo
   *Hostname*), usa `http://<hostname>:8765`.
4. Impostazioni → Assistenti vocali → il tuo assistente → **Agente di conversazione: Needle Local AI**.
   Lascia **disattivato** "Preferisci gestire i comandi localmente": così ogni frase passa da Needle.
5. Scegli quali entità esporre ad Assist (Impostazioni → Assistenti vocali → Esponi): Needle
   può comandare e leggere solo quelle.

## Opzioni dell'integrazione

| Opzione | Default | |
|---|---|---|
| API di Home Assistant | Assist | tool disponibili a Needle |
| Mostra avviso di ripiego | sì | se l'add-on non risponde, la risposta inizia con "⚠️ Needle non risponde…" (in voce viene letto) |
| Passi massimi | 5 | limite di letture per richiesta |
| Timeout | 10 s | per chiamata all'add-on |

L'add-on ha una sola opzione: `log_level` (`debug`, `info`, `warning`, `error`).

## Privacy e sicurezza

- Tutto gira in locale; nessuna frase lascia la tua rete.
- La telemetria della libreria `cactus-needle` è disattivata (`NEEDLE_TELEMETRY=0`).
- L'add-on non ha accesso a Home Assistant: può solo proporre chiamate ai tool.
- Le azioni passano dagli intent di Home Assistant: le entità non esposte ad Assist non sono
  raggiungibili.
- Le frasi condizionali non eseguono azioni se lo stato non è stato letto prima (vedi sotto).

## Frasi condizionali

Una frase come "se la luce del bagno è spenta accendi quella della camera" va eseguita in due
passi: prima si legge lo stato del bagno, poi si decide se accendere la camera.

Nei test, Needle con i pesi base **non fa la lettura**: estrae correttamente l'azione
("accendi la camera") ma la propone subito, senza controllare la condizione. Succede sia con
i tool di Home Assistant sia con pochi tool semplici. Eseguirla vorrebbe dire accendere la
camera anche quando il bagno è acceso.

Per questo l'integrazione applica un **blocco di sicurezza**: se la frase inizia con "se" o
"qualora" e Needle propone un'azione senza aver letto prima lo stato, non viene eseguito
nulla e la risposta è:

> Non riesco ancora a verificare le condizioni, quindi non ho fatto nulla. Dimmi direttamente cosa fare.

Se invece Needle legge prima lo stato e poi propone l'azione, il ciclo funziona: l'azione
viene eseguita solo dopo la lettura e la risposta lo dice ("Ho controllato ora, non ho
creato una regola"). Le condizioni sono sempre controlli fatti in quel momento: non viene
creata nessuna automazione.

Prossimo passo (roadmap): far verificare la condizione all'integrazione invece che al
modello. Needle scompone la frase in condizione (entità e stato atteso) e azione,
l'integrazione legge lo stato da Home Assistant, confronta in modo deterministico ed esegue
l'azione solo se la condizione è vera.

## Risoluzione dei problemi

| Problema | Causa probabile |
|---|---|
| "Impossibile raggiungere l'add-on Needle" nella configurazione | l'add-on non è avviato o sta ancora scaricando il modello: controlla il log e riprova |
| Le risposte iniziano con "⚠️ Needle non risponde" | add-on fermo, in caricamento o troppo lento: controlla il log o aumenta il timeout |
| "Non trovo il dispositivo o non è esposto ad Assist" | l'entità non è esposta, oppure Needle ha scelto un nome sbagliato |
| "Non ho capito, posso aiutarti solo con i dispositivi di casa" | Needle non ha proposto nessun tool per la frase |
| "Non riesco ancora a verificare le condizioni" | frase condizionale ("se … allora …") bloccata per sicurezza: dai il comando direttamente |

Per vedere cosa ha proposto Needle: imposta `log_level: debug` nell'add-on e il logger
`custom_components.needle` a `debug` in Home Assistant.

## Benchmark

Il benchmark misura quante frasi italiane Needle interpreta correttamente con i tool della
tua casa.

1. Scarica la diagnostica dell'integrazione (pagina dell'integrazione → ⋮ → Scarica
   diagnostica) e salvala come `benchmark/tools_snapshot.json`.
2. Adatta i nomi in `benchmark/frasi_it.yaml` ai tuoi dispositivi.
3. Avvia l'add-on in locale con Docker (l'add-on su Home Assistant non espone porte) ed
   esegui il benchmark:

```
docker build -t needle-addon addon
docker run -d --name needle -p 8765:8765 -v "$PWD/addon/data:/data" needle-addon
until curl -sf localhost:8765/health; do sleep 2; done
.venv-addon/bin/python -I benchmark/run_benchmark.py --url http://localhost:8765
docker rm -f needle
```

## Sviluppo

```
uv venv .venv-addon --python 3.13 && uv pip install --python .venv-addon -r addon/requirements.txt -r addon/requirements_test.txt
uv venv .venv --python 3.14 && uv pip install --python .venv -r requirements_test.txt
.venv-addon/bin/pytest addon/tests
.venv-addon/bin/pytest benchmark
.venv/bin/pytest
```

Le tre suite vanno lanciate separatamente: ognuna ha la sua configurazione pytest. Il test
col modello vero (scarica ~35 MB) si lancia con `.venv-addon/bin/pytest addon/tests -m slow`.

## Limiti noti

- Progetto sperimentale: con i pesi base di Needle e i tool di Home Assistant (descrizioni in inglese) il benchmark indica un'accuratezza ancora limitata (tool corretto in 20 passi su 31, argomenti corretti in 17; le domande di stato sono il caso più debole). Misura la tua installazione col benchmark prima di affidarti a Needle.
- Needle non scrive testo: le risposte sono frasi predefinite, in italiano.
- Le frasi condizionali sono bloccate finché il modello non legge lo stato prima di agire
  (vedi [Frasi condizionali](#frasi-condizionali)); non creano mai automazioni.
- La qualità dipende da come Needle interpreta i tool di Home Assistant: misurala col benchmark.
- Non è ancora verificato che HACS accetti questo repository (contiene sia l'add-on sia
  l'integrazione): in caso di problemi installa l'integrazione copiando la cartella.

## Crediti e licenza

- Modello e libreria: [Needle](https://github.com/cactus-compute/needle) di Cactus Compute
  (Apache-2.0).
- Questo progetto è distribuito con licenza [Apache-2.0](LICENSE).
- Progetto indipendente, non affiliato a Cactus Compute, Nabu Casa o Home Assistant.
