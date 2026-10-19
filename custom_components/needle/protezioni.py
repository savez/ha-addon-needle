"""Protezioni temporanee, solo per l'italiano, sulle chiamate proposte da Needle.

Modulo puro: solo libreria standard, nessuna dipendenza da Home Assistant né
import relativi (il benchmark lo carica per percorso).
"""

from collections.abc import Collection, Iterable
import re
from typing import Any
import unicodedata


def _strip_accents(text: str) -> str:
    """Toglie gli accenti (normalizzazione NFKD)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def _normalize_apostrophes(text: str) -> str:
    """Riporta gli apostrofi tipografici (U+2019, U+02BC, accento grave) a quello semplice."""
    return text.replace("’", "'").replace("ʼ", "'").replace("`", "'")


# Parole interrogative italiane
INTERROGATIVE_IT = (
    "è",
    "e'",
    "sono",
    "c'è",
    "ce",
    "che",
    "quale",
    "quali",
    "quanto",
    "quanta",
    "quanti",
    "quante",
    "com'è",
    "come",
    "dimmi",
    "dove",
)

# Parole interrogative senza accenti
_INTERROGATIVE_STRIPPED = tuple(_strip_accents(w) for w in INTERROGATIVE_IT)

# Sinonimi dei tool che comandano un dispositivo preciso
SINONIMI_IT = {
    "vacuum": (
        "robot",
        "aspirapolvere",
        "aspira",
        "pulisci",
        "pulizia",
    ),
    "device": (
        "presa",
        "interruttore",
        "spina",
        "ventilatore",
    ),
}

# Preposizioni articolate e altre parole vuote: non nominano nessun dispositivo.
# Le forme elise ("dell'albero") diventano "dell", "nell", ecc.
STOPWORDS_IT = frozenset(
    {
        "del", "dello", "della", "dei", "degli", "delle", "dell",
        "nel", "nello", "nella", "nei", "negli", "nelle", "nell",
        "sul", "sullo", "sulla", "sui", "sugli", "sulle", "sull",
        "al", "allo", "alla", "ai", "agli", "alle", "all",
        "dal", "dallo", "dalla", "dai", "dagli", "dalle", "dall",
        "con", "per", "tra", "fra",
        "una", "uno", "gli",
    }
)

# Parole chiave per tipo di dispositivo (solo i tool che si confondono tra loro).
PAROLE_DOMINIO_IT: dict[str, frozenset[str]] = {
    "lights": frozenset({"luce", "luci", "lampada", "lampadina", "lampade", "faretto"}),
    "air_conditioner": frozenset(
        {
            "condizionatore",
            "clima",
            "climatizzatore",
            "riscaldamento",
            "termostato",
            "gradi",
            "aria",
            "caldo",
            "freddo",
        }
    ),
    "blinds": frozenset(
        {"tapparella", "tapparelle", "tenda", "tende", "persiana", "persiane"}
    ),
    "media": frozenset(
        {
            "musica",
            "canzone",
            "brano",
            "volume",
            "tv",
            "televisione",
            "radio",
            "pausa",
            "riprendi",
            "avanti",
            "indietro",
        }
    ),
}

DOMANDA = "domanda"
DISPOSITIVO = "dispositivo"


def _parole(testo: str) -> list[str]:
    """Parole minuscole, senza accenti, divise sui caratteri non alfanumerici."""
    normalizzato = _strip_accents(_normalize_apostrophes(testo.lower()))
    return [w for w in re.split(r"[^a-z0-9]+", normalizzato) if w]


def _parole_significative(testo: str) -> set[str]:
    """Parole di almeno 3 lettere che non sono preposizioni articolate o parole vuote."""
    return {w for w in _parole(testo) if len(w) >= 3 and w not in STOPWORDS_IT}


def e_domanda(frase: str) -> bool:
    """La frase è una domanda?

    Vero se finisce con '?' (spazi finali ignorati) oppure se la prima parola
    (minuscola, apostrofi normalizzati) è in INTERROGATIVE_IT.
    """
    if not frase:
        return False

    if frase.rstrip().endswith("?"):
        return True

    frase_normalized = _normalize_apostrophes(frase.lower())
    first_word = frase_normalized.split()[0] if frase_normalized.split() else ""
    if not first_word:
        return False

    first_word = first_word.rstrip("?,.;:!")
    if first_word in INTERROGATIVE_IT:
        return True
    return _strip_accents(first_word) in _INTERROGATIVE_STRIPPED


def dispositivo_nominato(
    frase: str,
    tool: str,
    nome_entita: str | None,
) -> bool:
    """Il dispositivo scelto è nominato nella frase?

    Solo per i tool "vacuum" e "device" (per gli altri è sempre vero). Si confrontano
    le parole di almeno 3 lettere, senza accenti e senza preposizioni articolate.

    - device: serve una parola del nome dell'entità che non sia un sinonimo
      ("presa" da sola non basta). Se il nome è fatto solo di sinonimi, vale la
      regola generale.
    - regola generale: basta una parola del nome dell'entità o un sinonimo del tool.
    """
    if tool not in {"vacuum", "device"}:
        return True

    phrase_words = _parole_significative(frase)
    entity_words = _parole_significative(nome_entita) if nome_entita else set()

    if tool == "device" and entity_words:
        sinonimi = {
            _strip_accents(syn.lower()) for syns in SINONIMI_IT.values() for syn in syns
        }
        distintive = entity_words - sinonimi
        if distintive:
            return bool(distintive & phrase_words)

    if any(_strip_accents(s.lower()) in phrase_words for s in SINONIMI_IT.get(tool, ())):
        return True
    return bool(entity_words & phrase_words)


def dominio_coerente(frase: str, tool: str) -> bool:
    """Il tool scelto corrisponde al tipo di dispositivo nominato nella frase?

    Falso se la frase contiene una parola chiave di un ALTRO tool tra luci,
    condizionatore, tapparelle e media, e nessuna parola chiave del tool scelto.
    Per gli altri tool è sempre vero.
    """
    proprie = PAROLE_DOMINIO_IT.get(tool)
    if proprie is None:
        return True
    parole = set(_parole(frase))
    if parole & proprie:
        return True
    altre = set().union(*(p for t, p in PAROLE_DOMINIO_IT.items() if t != tool))
    return not (parole & altre)


def motivo_blocco(
    frase: str,
    chiamate: Iterable[tuple[str, Any, bool]],
    nomi_vacuum: Collection[str],
) -> str | None:
    """Perché le chiamate proposte per questa frase non vanno eseguite (o None).

    `chiamate`: (nome del tool di Needle, argomenti, è una lettura).
    `nomi_vacuum`: nomi degli aspirapolvere della casa; se è uno solo vale come nome
    quando Needle non ne indica uno.

    - DOMANDA: la frase è una domanda e c'è almeno un'azione (si blocca tutto,
      letture comprese: nessuna esecuzione parziale).
    - DISPOSITIVO: per almeno una chiamata il dispositivo non è nominato o il tool
      non corrisponde al tipo di dispositivo della frase (si blocca tutto).
    """
    chiamate = list(chiamate)
    if e_domanda(frase) and any(not lettura for _, _, lettura in chiamate):
        return DOMANDA
    for nome, argomenti, _ in chiamate:
        nome_entita = None
        if isinstance(argomenti, dict) and isinstance(argomenti.get("name"), str):
            nome_entita = argomenti["name"]
        elif nome == "vacuum" and len(nomi_vacuum) == 1:
            nome_entita = next(iter(nomi_vacuum))
        if not dispositivo_nominato(frase, nome, nome_entita):
            return DISPOSITIVO
        if not dominio_coerente(frase, nome):
            return DISPOSITIVO
    return None
