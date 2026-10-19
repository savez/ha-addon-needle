# Sicurezza

> **English** — Please do not report security vulnerabilities in public issues. Use
> GitHub's private vulnerability reporting: *Security → Report a vulnerability* on this
> repository. You will get an acknowledgement within 7 days.

## Versioni supportate

Il progetto è sperimentale: le correzioni di sicurezza vengono fatte solo sull'ultima
versione pubblicata (branch `main`).

| Versione | Supportata |
|---|---|
| ultima release / `main` | ✅ |
| versioni precedenti | ❌ |

## Come segnalare una vulnerabilità

**Non aprire una issue pubblica.** Usa la segnalazione privata di GitHub:
scheda **Security** del repository → **Report a vulnerability**.

Indica, se possibile:

- componente coinvolto (add-on o integrazione) e versione;
- versione di Home Assistant e architettura;
- passi per riprodurre il problema e impatto (cosa può fare un attaccante);
- eventuale proposta di correzione.

Riceverai una prima risposta entro 7 giorni. Concorderemo insieme i tempi della correzione
e della pubblicazione; chi segnala verrà citato, se lo desidera.

## Ambito

Rientrano nell'ambito, ad esempio:

- azioni su entità **non esposte** ad Assist eseguite tramite Needle;
- accesso a Home Assistant o ai suoi dati a partire dall'add-on (che per progetto non ne ha);
- esecuzione di codice o lettura di file tramite l'API `/v1/infer` dell'add-on;
- invio di dati all'esterno nonostante la telemetria sia disattivata.

Non rientrano nell'ambito:

- interpretazioni sbagliate delle frasi da parte del modello (sono limiti di qualità: apri
  una issue normale);
- vulnerabilità di Home Assistant, della libreria `cactus-needle` o del modello Needle:
  segnalale ai rispettivi progetti.

## Note di sicurezza per chi installa

- L'add-on non espone porte sull'host ed è raggiungibile solo dalla rete interna degli
  add-on; l'API `/v1/infer` non è autenticata, ma l'add-on non può agire su Home Assistant.
- Needle può comandare solo le entità esposte ad Assist: esponi solo ciò che vuoi controllare
  a voce, ed evita di esporre serrature, allarmi e cancelli.
