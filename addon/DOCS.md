# Needle Local AI

Agente conversazionale **locale** per Assist, basato sul modello
[Needle 3](https://cactuscompute.com/needle) di Cactus Compute.

Il progetto è composto da due parti, **entrambe necessarie**:

- **questo add-on**: fa solo inferenza. Riceve la frase e i tool di Assist e restituisce le
  chiamate ai tool. Non ha accesso a Home Assistant e la telemetria della libreria è
  disattivata;
- **l'integrazione `needle`** (custom component): è l'agente di Assist. Passa le frasi
  all'add-on e fa eseguire a Home Assistant le azioni sulle entità esposte ad Assist.

## 1. Avvia l'add-on

1. Avvia l'add-on e attiva **Avvio all'accensione**.
2. Al primo avvio l'add-on scarica il modello (~35 MB) in `/data`: serve internet solo questa
   volta. Attendi nel **Log** il messaggio `Modello Needle pronto`.
3. Annota il **Nome host** dell'add-on (in questa pagina, scheda *Informazioni*): serve per
   configurare l'integrazione. Se l'add-on è installato in locale è `local-needle`; se è
   installato dal repository GitHub ha la forma `xxxxxxxx-needle`.

## 2. Installa l'integrazione

L'integrazione non viene installata dall'add-on: va aggiunta a parte, in uno di questi modi.

**Con HACS**

1. HACS → ⋮ → **Repository personalizzati**.
2. Repository: `https://github.com/savez/ha-addon-needle`, tipo **Integrazione**.
3. Cerca **Needle Local AI** in HACS, scaricala e **riavvia Home Assistant**.

Se HACS non accetta il repository (contiene anche l'add-on), usa il metodo a mano.

**A mano**

1. Scarica il repository da `https://github.com/savez/ha-addon-needle`.
2. Copia la cartella `custom_components/needle/` in `/config/custom_components/needle/`
   (ad esempio con l'add-on *Samba share* o *File editor*).
3. **Riavvia Home Assistant**.

## 3. Configura l'integrazione

1. Impostazioni → Dispositivi e servizi → **Aggiungi integrazione** → **Needle Local AI**.
2. URL: `http://<nome host dell'add-on>:8765`, ad esempio `http://local-needle:8765`.
   Se compare "Impossibile raggiungere l'add-on", il modello non è ancora pronto: attendi il
   messaggio nel log dell'add-on e riprova.

## 4. Usala con Assist

1. Impostazioni → Assistenti vocali → scegli (o crea) un assistente.
2. **Agente di conversazione**: **Needle Local AI**.
3. Lascia **disattivato** "Preferisci gestire i comandi localmente": così ogni frase passa da
   Needle.
4. Nella scheda **Esponi** scegli le entità che Needle può leggere e comandare: solo quelle
   sono raggiungibili. Evita di esporre serrature, allarmi e cancelli.

Prova con frasi come "accendi la luce del bagno", "spegni la cucina e accendi il salotto"
o "la luce del bagno è accesa?".

Le frasi condizionali ("se la luce del bagno è spenta accendi la camera") per ora sono
**bloccate per sicurezza**: Needle propone l'azione senza verificare la condizione, quindi
l'integrazione non esegue nulla e risponde "Non riesco ancora a verificare le condizioni".
Dettagli nel README del progetto.

## Opzioni dell'add-on

- `log_level`: `debug`, `info`, `warning`, `error`.

## Opzioni dell'integrazione

Impostazioni → Dispositivi e servizi → Needle Local AI → **Configura**:

| Opzione | Default | |
|---|---|---|
| API di Home Assistant | Assist | intent usati per eseguire le azioni |
| Strumenti mostrati a Needle (`strumenti`) | `generati` | `generati`: l'integrazione crea per Needle pochi tool dalle tue entità esposte (luci, clima, tapparelle, media, prese, aspirapolvere, sensori), con aree e nomi reali. `assist`: i tool dell'API Assist di Home Assistant, come nelle versioni precedenti (confronto o ripiego) |
| Mostra avviso di ripiego | sì | se l'add-on non risponde, la frase passa all'agente standard e la risposta inizia con "⚠️ Needle non risponde…" (in voce viene letto) |
| Passi massimi | 5 | limite di letture per richiesta (frasi condizionali e domande) |
| Timeout | 10 s | per chiamata all'add-on |

## Problemi comuni

| Problema | Causa probabile |
|---|---|
| "Impossibile raggiungere l'add-on" durante la configurazione | add-on fermo o modello ancora in download; URL con nome host sbagliato |
| Le risposte iniziano con "⚠️ Needle non risponde" | add-on fermo, in caricamento o troppo lento: controlla il log o aumenta il timeout |
| "Non trovo il dispositivo o non è esposto ad Assist" | entità non esposta, oppure Needle ha scelto un nome sbagliato |
| "Non ho capito, posso aiutarti solo con i dispositivi di casa" | Needle non ha proposto nessun tool per la frase, o ha scartato un'azione perché poco sicuro: riformula con un verbo ("dimmi la temperatura della camera") |
| "Non ho capito se è una domanda o un comando: puoi riformulare?" | protezione: la frase sembra una domanda ma Needle ha proposto un'azione, che non viene eseguita. Riformula ("com'è la temperatura in camera?" oppure "accendi la luce") |
| "Non sono sicuro del dispositivo: puoi dirmi il nome?" | protezione: la frase non nomina il dispositivo scelto (prese, ventilatori, aspirapolvere), oppure Needle ha scelto un tipo di dispositivo diverso da quello della frase (es. condizionatore per "luce"): dì il nome, ad esempio "accendi la presa del balcone"; la sola parola "presa" non basta se ce n'è più di una |
| "Non riesco ancora a verificare le condizioni" | frase condizionale ("se … allora …") bloccata per sicurezza: dai il comando direttamente |

### Log di debug

All'avvio l'add-on scrive nel log l'URL da usare nell'integrazione
(`URL da usare nell'integrazione: http://…:8765`): se l'hai installato dal
repository il nome host non è `local-needle`.

Per vedere ogni richiesta imposta **`log_level: debug`** nella configurazione
di questo add-on e riavvialo. Per ogni frase il log mostra i tool ricevuti, i
turni (la frase e i risultati delle letture), la risposta di Needle e i tempi.
Con `info` (default) questi dettagli non vengono scritti.

Se il log resta vuoto quando parli ad Assist, la richiesta non arriva
all'add-on: di solito l'URL dell'integrazione è sbagliato. Per i dettagli lato
Home Assistant usa **Attiva il debug** nella pagina dell'integrazione.

Le protezioni valgono solo per l'italiano e sono temporanee, in attesa del fine-tuning.

Se alleghi la diagnostica dell'integrazione a una segnalazione, ricorda che contiene i tool
generati, quindi i nomi delle tue entità e delle tue aree: controllala prima di pubblicarla.

Il progetto è sperimentale: con il modello base l'accuratezza è ancora bassa. Documentazione
completa, benchmark e segnalazioni: <https://github.com/savez/ha-addon-needle>.
