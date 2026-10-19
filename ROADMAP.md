# Roadmap

Needle Local AI è sperimentale. Questa pagina raccoglie i prossimi passi e il ragionamento
dietro di essi. Le voci non hanno date.

## 1. Tool pensati per Needle, generati dalla casa (in corso)

**Problema.** Needle riceve oggi i tool dell'API Assist di Home Assistant: 20–30 tool generici,
con nomi e aree come testo libero e descrizioni astratte. Sono pensati per LLM grandi. Con
questi Needle (pesi base) ha confidenza bassissima, scarta molte chiamate e confonde le
domande con i comandi (es. "temperatura bagno" → imposta il termostato).

**Evidenza.** Su 25 frasi italiane reali di una casa vera:

| Tool dati a Needle | Tool e argomenti giusti |
|---|---|
| Tool dell'API Assist | domande sullo stato quasi sempre sbagliate o scartate |
| Pochi tool concreti, descrizioni in inglese con esempi, valori ammessi presi dalla casa | 18/25 (72%), domande su temperatura e umidità 6/6 |

**Soluzione.** L'integrazione genera da ogni installazione un piccolo insieme di tool "alla
Needle" (`lights`, `air_conditioner`, `media`, `device`, `vacuum`, `get_temperature`,
`get_humidity`…), solo per i domini presenti, con aree e nomi reali come `enum`. Poi traduce
la chiamata scelta da Needle negli intent di Home Assistant. Le entità non esposte restano
irraggiungibili.

**Limiti emersi.** Il modello è sensibile alla composizione dei tool: aggiungere o togliere
un tool sposta gli errori. Casi ancora deboli sono "tutte le luci", "fuori", le prese con nomi
poco leggibili e le domande sì/no sulle luci. Una prova con due passaggi (prima la categoria,
poi il tool) è andata peggio (9/25) ed è stata scartata.

## 2. Fine-tuning di Needle sui tool di Home Assistant, aggiornato a ogni versione

**Obiettivo.** Pesi di Needle addestrati sui tool che Home Assistant espone davvero, così che
il modello non dipenda dalla formulazione delle descrizioni e capisca l'italiano (e altre
lingue) senza trucchi.

**Perché va tenuto aggiornato.** I tool cambiano con le versioni di Home Assistant: nuovi
intent, parametri rinominati, descrizioni riscritte. Dei pesi addestrati su una versione
possono peggiorare sulla successiva. Il fine-tuning deve quindi essere un processo ripetibile
e automatico, non un'operazione fatta una volta.

### Strumenti già disponibili

La libreria `cactus-needle` (Apache-2.0) include:

- `needle finetune dati.jsonl`: addestra un adattatore LoRA in locale (JAX; Apple Silicon con
  l'extra `metal`, GPU NVIDIA con `gpu`);
- `needle build --lora adattatore.safetensors`: produce un nuovo file `.cact` della stessa
  taglia dei pesi base;
- `needle platform finetune`: lo stesso sui server di Cactus (a pagamento);
- formato dei dati: una riga JSON per esempio,
  `{"query": "...", "tools": [...], "answers": [{"name": "...", "arguments": {...}}]}`,
  con `answers: []` per le frasi che non devono produrre chiamate.

### Pipeline proposta

```
Nuova versione di Home Assistant
        │
        ▼
1. Snapshot dei tool  ── case finte avviate con pytest-homeassistant-custom-component,
        │                 si legge l'elenco dei tool che l'integrazione darebbe a Needle
        ▼
2. Confronto con lo snapshot precedente
        │  nessun cambiamento → si riusano i pesi esistenti
        ▼  cambiamento
3. Generazione del dataset
        │  - case sintetiche: aree, luci, sensori, clima, media, prese con nomi realistici
        │    e disordinati (alias, maiuscole, nomi tecnici, entità senza area)
        │  - frasi per ogni tool e lingua: comandi, domande, frasi senza verbo, "tutte",
        │    errori di battitura, più azioni nella stessa frase, frasi non domotiche
        │  - risposta attesa calcolata dal generatore, non scritta a mano
        ▼
4. Fine-tuning LoRA + build del .cact
        ▼
5. Valutazione con soglie: benchmark pubblico + frasi tenute fuori dall'addestramento.
        │  Se peggiora rispetto ai pesi in uso → stop, non si pubblica
        ▼
6. Pubblicazione dei pesi (es. Hugging Face), etichettati con la versione di HA
        ▼
7. L'add-on scarica i pesi adatti alla versione di HA che l'integrazione dichiara;
   se non esistono usa i più recenti compatibili o i pesi base
```

### Domande aperte

- **Confidenza.** La libreria dice che i fine-tune fatti sulla piattaforma Cactus mantengono la
  stima di confidenza. Va verificato se un fine-tune locale la mantiene. Senza confidenza
  l'integrazione non può scartare le chiamate incerte e servono altre protezioni.
- **Dove gira l'addestramento.** I runner gratuiti di GitHub Actions (CPU) potrebbero essere
  troppo lenti. Le alternative sono un Mac, un runner con GPU o la piattaforma Cactus.
- **Tool dell'API Assist o tool generati.** Addestrare sui tool nativi segue Home Assistant
  senza traduzioni. Addestrare sui tool generati (voce 1) dà un'interfaccia più stabile tra
  versioni. Da decidere con i primi esperimenti.
- **Lingue.** Si parte dall'italiano. Il generatore di frasi deve permettere di aggiungerne
  altre.
- **Dimensione del dataset** e tempi di addestramento, da misurare.
- **Licenze.** Pesi derivati da Needle (Apache-2.0) e dati sintetici: da verificare se il
  dataset è generato con un LLM esterno (`needle generate-data` usa OpenRouter).

## 3. Condizioni verificate dall'integrazione

Needle scompone "se X allora Y" in condizione (entità e stato atteso) e azione.
L'integrazione legge lo stato da Home Assistant, confronta in modo deterministico ed esegue
l'azione solo se la condizione è vera. Vedi [Frasi condizionali](README.md#frasi-condizionali).

## 4. Needle come tool MCP per agenti AI

Un tool `casa(richiesta)` per gli agenti AI: Needle gestisce il dominio della casa al posto
dell'agente, con meno token e senza dare all'agente un token di Home Assistant.

## 5. Regole e automazioni

Creare automazioni da frasi ("ogni sera alle 22 spegni le luci"). Fuori dalla v1.
