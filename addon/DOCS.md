# Needle Local AI

Motore di inferenza locale per l'agente conversazionale Needle di Assist.

Al primo avvio l'add-on scarica il modello Needle 3 (~35 MB) in `/data`: finché il
download non è finito, l'integrazione usa l'agente standard di Home Assistant.

L'add-on non ha accesso a Home Assistant: riceve frase e tool dall'integrazione
`needle` e restituisce le tool call. La telemetria della libreria è disattivata.

## Opzioni

- `log_level`: `debug`, `info`, `warning`, `error`.
