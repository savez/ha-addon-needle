# Changelog

## [0.3.1](https://github.com/savez/ha-addon-needle/compare/v0.3.0...v0.3.1) (2026-10-19)


### Bug Fixes

* usa EmbeddingGemma 300M, la versione 2 non è supportata da llama.cpp ([#14](https://github.com/savez/ha-addon-needle/issues/14)) ([419e60f](https://github.com/savez/ha-addon-needle/commit/419e60f695e2ad596b31a0295927bc9641b50c7b))

## [0.3.0](https://github.com/savez/ha-addon-needle/compare/v0.2.1...v0.3.0) (2026-10-19)


### Features

* risoluzione dei nomi di entità e aree con EmbeddingGemma 2 ([#12](https://github.com/savez/ha-addon-needle/issues/12)) ([b85a1e6](https://github.com/savez/ha-addon-needle/commit/b85a1e68743c88fb3010ded779dbcf7f3e747f11))

## [0.2.1](https://github.com/savez/ha-addon-needle/compare/v0.2.0...v0.2.1) (2026-10-19)


### Bug Fixes

* letture dello stato con ricerca a parole ed esecuzione delle letture scartate ([#10](https://github.com/savez/ha-addon-needle/issues/10)) ([41b7ab5](https://github.com/savez/ha-addon-needle/commit/41b7ab58cbc35843494692850711340b3d10264b))

## [0.2.0](https://github.com/savez/ha-addon-needle/compare/v0.1.3...v0.2.0) (2026-10-19)


### Features

* log di debug delle richieste e URL dell'add-on all'avvio ([#8](https://github.com/savez/ha-addon-needle/issues/8)) ([2ead27c](https://github.com/savez/ha-addon-needle/commit/2ead27c0fd73602361f5751230eb9a7279d3e09e))

## [0.1.3](https://github.com/savez/ha-addon-needle/compare/v0.1.2...v0.1.3) (2026-10-19)


### Bug Fixes

* alza il timeout predefinito verso l'add-on a 10 secondi ([#6](https://github.com/savez/ha-addon-needle/issues/6)) ([45b2e22](https://github.com/savez/ha-addon-needle/commit/45b2e22e09b36f4d5d2800f6b8cee0966eb07642))

## [0.1.2](https://github.com/savez/ha-addon-needle/compare/v0.1.1...v0.1.2) (2026-10-19)


### Bug Fixes

* **integrazione:** nomi dei tool senza prefisso e blocco delle condizionali non verificate ([#4](https://github.com/savez/ha-addon-needle/issues/4)) ([967647c](https://github.com/savez/ha-addon-needle/commit/967647c3b04e3a214fa66f6f716874aff24a3902))

## [0.1.1](https://github.com/savez/ha-addon-needle/compare/v0.1.0...v0.1.1) (2026-10-19)


### Bug Fixes

* **addon:** immagine base nel Dockerfile invece di build.yaml ([#2](https://github.com/savez/ha-addon-needle/issues/2)) ([acb21ca](https://github.com/savez/ha-addon-needle/commit/acb21ca4bc9a6be612a27789b652f37d68e1698a))

## 0.1.0 (2026-10-19)

### Features

* Prima versione: add-on di inferenza locale con Needle 3 e integrazione `needle` come agente conversazionale di Assist.
