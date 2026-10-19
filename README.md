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
- **Integrazione Needle Local AI**: è l'agente di Assist. Legge le entità esposte ad Assist,
  genera per Needle un piccolo insieme di tool pensati per lui (vedi sotto), traduce la
  chiamata scelta negli intent di Home Assistant, che li esegue, e costruisce la risposta in
  italiano.
- Se l'add-on non risponde, la frase passa all'agente standard di Home Assistant (con un
  avviso, disattivabile).

### Tool generati dalla casa

I tool dell'API Assist (20-30, generici, con nomi e aree come testo libero) sono pensati per
LLM grandi: con i pesi base Needle li usa male. L'integrazione genera invece, **da ogni
installazione e a ogni richiesta**, pochi tool concreti con descrizioni in inglese ed esempi,
solo per i domini presenti tra le entità esposte. Aree e nomi reali diventano i valori
ammessi (`enum`) dei parametri: Needle sceglie fra nomi veri, non ne inventa.

| Tool per Needle | Se ci sono | Si traduce in |
|---|---|---|
| `lights` (stanza o `all`, acceso/spento, luminosità) | luci | `HassTurnOn`/`HassTurnOff`, `HassLightSet` |
| `air_conditioner` (stanza, acceso/spento, temperatura) | `climate` | `HassTurnOn`/`HassTurnOff`, `HassClimateSetTemperature` |
| `blinds` (stanza, apri/chiudi, posizione) | tapparelle | `HassTurnOn`/`HassTurnOff`, `HassSetPosition` |
| `media` (pausa, riprendi, avanti, indietro, volume) | media player | `HassMedia*`, `HassSetVolumeRelative` |
| `device` (nome, acceso/spento) | prese, ventilatori, interruttori | `HassTurnOn`/`HassTurnOff` per nome |
| `vacuum` (avvia, torna alla base) | aspirapolvere | `HassVacuumStart`, `HassVacuumReturnToBase` |
| `get_<misura>` (`get_temperature`, `get_humidity`…) | sensori con quella `device_class` | `GetLiveContext` + filtro per `device_class` |
| `get_time` | intent `GetDateTime` | `GetDateTime` |

Un tool esiste solo se ci sono entità del dominio **e** l'intent di Home Assistant su cui si
traduce. Le entità non esposte ad Assist restano irraggiungibili: le azioni passano sempre
dagli intent. Con l'opzione `strumenti` puoi tornare ai tool di Assist (vedi sotto).

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
| API di Home Assistant | Assist | intent usati per eseguire le azioni |
| Strumenti mostrati a Needle (`strumenti`) | `generati` | `generati`: tool generati dalla casa (consigliato). `assist`: i tool dell'API Assist di Home Assistant, come nelle versioni precedenti: serve per confronto o ripiego |
| Mostra avviso di ripiego | sì | se l'add-on non risponde, la risposta inizia con "⚠️ Needle non risponde…" (in voce viene letto) |
| Passi massimi | 5 | limite di letture per richiesta |
| Timeout | 10 s | per chiamata all'add-on |

L'add-on ha una sola opzione, `log_level` (`debug`, `info`, `warning`, `error`).

## Privacy e sicurezza

- Tutto gira in locale; nessuna frase lascia la tua rete.
- La telemetria della libreria `cactus-needle` è disattivata (`NEEDLE_TELEMETRY=0`).
- L'add-on non ha accesso a Home Assistant: può solo proporre chiamate ai tool.
- Le azioni passano dagli intent di Home Assistant: le entità non esposte ad Assist non sono
  raggiungibili.
- Le frasi condizionali non eseguono azioni se lo stato non è stato letto prima (vedi sotto).

## Domande sullo stato

Per le domande ("quanto è la temperatura in camera?", "com'è l'umidità in bagno?") Needle
sceglie il tool `get_<misura>` giusto (`get_temperature`, `get_humidity`…) e la stanza, o il
nome del sensore se non ha un'area, fra i valori reali della casa. Non c'è nessuna ricerca a
parole: i nomi li risolve Needle con gli `enum`. L'integrazione poi:

- **legge e filtra**: esegue `GetLiveContext` per quell'area o nome e tiene solo le entità
  con la `device_class` richiesta. È un filtro deterministico su un argomento strutturato,
  non un'interpretazione della frase;
- **esegue le letture scartate**: quando Needle è poco sicuro scarta la chiamata. Se la
  chiamata scartata è una lettura, l'integrazione la esegue comunque, perché leggere non
  cambia nulla in casa. Le **azioni** scartate restano scartate.

Le misure disponibili dipendono dai sensori esposti: senza sensori di umidità non esiste
`get_humidity`.

## Protezioni

Il modello base commette errori che eseguirebbero un'azione sbagliata. Finché non c'è un
fine-tuning, l'integrazione ne ferma alcuni prima di eseguire (se una chiamata è bloccata non
si esegue nulla di quella frase):

- **Domanda scambiata per comando.** Se la frase è una domanda (finisce con `?` o inizia con
  una parola interrogativa: è, sono, c'è, che, quale, quanto, come, dimmi…) e Needle propone
  un'azione, non viene eseguito nulla e la risposta è:

  > Non ho capito se è una domanda o un comando: puoi riformulare?

- **Dispositivo non nominato.** Per `vacuum` e `device` l'azione viene eseguita solo se la
  frase contiene una parola del nome del dispositivo scelto o una parola del suo tipo (robot,
  aspirapolvere, presa, interruttore…). Altrimenti la risposta è:

  > Non sono sicuro del dispositivo: puoi dirmi il nome?

  Per le prese e i dispositivi va nominato il dispositivo: la sola parola "presa" non basta
  quando ce n'è più di una. Le preposizioni articolate (del, della, nel, sul…) non contano come
  parole del nome.

- **Tipo di dispositivo sbagliato.** Per `lights`, `air_conditioner`, `blinds` e `media`: se la
  frase contiene una parola di un altro tipo (luce, condizionatore, tapparella, volume…) e
  nessuna del tipo scelto, l'azione non viene eseguita e la risposta è la stessa del punto
  precedente. Esempio: "accendi la luce del bagno" interpretata come condizionatore.

Le protezioni sono regole sul testo: valgono **solo per l'italiano** e sono **temporanee**,
da rivedere dopo il fine-tuning (vedi [ROADMAP.md](ROADMAP.md)).

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
| "Non ho capito se è una domanda o un comando: puoi riformulare?" | protezione: la frase sembra una domanda ma Needle ha proposto un'azione; riformula come domanda ("com'è…") o come comando |
| "Non sono sicuro del dispositivo: puoi dirmi il nome?" | protezione: la frase non nomina il dispositivo scelto (prese, ventilatori, aspirapolvere), oppure Needle ha scelto un tipo di dispositivo diverso da quello della frase (es. condizionatore per "luce"); dì il nome ("accendi la presa del balcone") |
| "Non riesco ancora a verificare le condizioni" | frase condizionale ("se … allora …") bloccata per sicurezza: dai il comando direttamente |

Per vedere cosa ha proposto Needle: imposta `log_level: debug` nell'add-on e il logger
`custom_components.needle` a `debug` in Home Assistant.

## Benchmark

Il benchmark misura quante frasi italiane Needle interpreta correttamente. Il default
(`--tools generati`) usa una **casa finta generica** (`benchmark/casa.yaml`), genera i tool
con lo stesso generatore dell'integrazione e applica le stesse protezioni; le 25 frasi sono
in `benchmark/frasi_it.yaml` (`pericolosa: true` = domanda→azione o dominio sbagliato, contate
a parte come "azioni pericolose").

Avvia l'add-on in locale (l'add-on su Home Assistant non espone porte) ed esegui:

```
cd addon && NEEDLE_DATA_DIR=data ../.venv-addon/bin/python -m app &
until curl -sf localhost:8765/health; do sleep 2; done
cd .. && .venv-addon/bin/python -I benchmark/run_benchmark.py --url http://localhost:8765
```

Con Docker: `docker build -t needle-addon addon` e `docker run -d -p 8765:8765 -v "$PWD/addon/data:/data" needle-addon`.
Su macOS serve il motore per Mac (`needle fetch --out <cartella>/engine`), non quello Linux
scaricato per Docker.

Risultato sui pesi base di Needle (nessun fine-tuning), casa finta, tool generati, 25 frasi.
Il modello non dà sempre le stesse risposte da un avvio dell'add-on all'altro (a parità di
tool): dentro lo stesso avvio le esecuzioni sono identiche, tra due avvii cambiano 3 frasi
("accendi la luce del bagno", "accendi la luce del bagnetto", "la luce del bagno è accesa?").
Due avvii:

| Metrica | Avvio A (3 esecuzioni) | Avvio B |
| --- | --- | --- |
| Tool corretti | 22/25 | 21/25 |
| Tool e argomenti corretti | 19/25 | 18/25 |
| Scartate (nessuna chiamata) | 2/25 | 1/25 |
| Azioni pericolose (3 frasi marcate `pericolosa`) | 0 dopo le protezioni (1 prima) | 0 dopo le protezioni (2 prima) |
| Azioni sbagliate eseguite (tutte le 25 frasi) | 1 dopo le protezioni (3 prima) | 1 dopo le protezioni (4 prima) |

"Azioni pericolose" conta, solo sulle frasi marcate (domanda→azione, dominio sbagliato), le
azioni diverse da quelle attese. "Azioni sbagliate eseguite" conta lo stesso su tutte le frasi:
sono azioni non di lettura che passano le protezioni senza corrispondere all'atteso. La
protezione sul tipo di dispositivo ferma la luce interpretata come condizionatore (senza, in
entrambi gli avvii le azioni sbagliate eseguite erano 2). Resta "alza il volume" interpretato
come pausa: è lo stesso tipo di dispositivo, le protezioni non possono fermarlo.

Le prese vanno nominate: per il tool `device` non basta la parola "presa", serve una parola
distintiva del nome (es. "balcone"), altrimenti la chiamata è bloccata.

Il vecchio benchmark sui tool Assist originali resta disponibile con `--tools snapshot`
(`benchmark/tools_snapshot.json` e `benchmark/frasi_assist_it.yaml`): scarica la diagnostica
dell'integrazione (⋮ → Scarica diagnostica) e salvala come `tools_snapshot.json`. La
diagnostica contiene i tool generati, quindi i nomi delle tue entità e delle tue aree: non
pubblicarla senza averla controllata.

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

- Progetto sperimentale: con i pesi base di Needle e i tool generati il benchmark sulla casa
  finta dà 21-22/25 tool corretti e 18-19/25 tool e argomenti corretti, con risposte che
  cambiano un po' da un avvio all'altro (vedi [Benchmark](#benchmark)).
  Misura la tua installazione col benchmark prima di affidarti a Needle.
- **Azioni sbagliate possibili.** Anche con le protezioni il modello può comandare
  l'azione sbagliata: nel benchmark resta 1 azione sbagliata su 25 frasi ("alza il volume"
  mette in pausa): le protezioni non fermano un'azione sbagliata sullo stesso tipo di
  dispositivo. Il rimedio previsto è il fine-tuning ([ROADMAP.md](ROADMAP.md), voce 2). In
  alternativa puoi impostare l'opzione `strumenti` su `assist`: i tool dell'API Assist, senza
  la ricerca a parole delle versioni precedenti.
- Casi ancora deboli: "tutte le luci", "fuori" (esterno), le prese con nomi poco leggibili
  e le domande sì/no sulle luci ("la luce del bagno è accesa?"). Il modello è sensibile alla
  composizione dei tool: aggiungerne o toglierne sposta gli errori.
- Le protezioni (domanda → azione, dispositivo non nominato, tipo di dispositivo sbagliato)
  sono solo per l'italiano e temporanee.
- Needle non scrive testo: le risposte sono frasi predefinite, in italiano.
- Le frasi condizionali sono bloccate finché il modello non legge lo stato prima di agire
  (vedi [Frasi condizionali](#frasi-condizionali)); non creano mai automazioni.
- Non è ancora verificato che HACS accetti questo repository (contiene sia l'add-on sia
  l'integrazione): in caso di problemi installa l'integrazione copiando la cartella.

## Roadmap

Prossimi passi e ragionamenti in [ROADMAP.md](ROADMAP.md): tool generati per Needle dalla
casa, fine-tuning di Needle sui tool di Home Assistant aggiornato a ogni versione, condizioni
verificate dall'integrazione, Needle come tool MCP.

## Crediti e licenza

- Modello e libreria: [Needle](https://github.com/cactus-compute/needle) di Cactus Compute
  (Apache-2.0).
- Questo progetto è distribuito con licenza [Apache-2.0](LICENSE).
- Progetto indipendente, non affiliato a Cactus Compute, Nabu Casa o Home Assistant.
