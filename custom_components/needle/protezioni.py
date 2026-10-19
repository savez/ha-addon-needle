"""Protection functions for Needle conversation handling."""

import re
import unicodedata


def _strip_accents(text: str) -> str:
    """Strip accents from text using NFKD normalization."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def _normalize_apostrophes(text: str) -> str:
    """Normalize different apostrophe characters to the standard one."""
    # Replace all apostrophe variants with the standard apostrophe
    # U+2019 (right single quotation mark), U+02BC (modifier letter apostrophe), backtick
    return text.replace("'", "'").replace("’", "'").replace("ʼ", "'").replace("`", "'")


# Italian interrogative words
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

# Accent-stripped interrogative words (module-level constant)
_INTERROGATIVE_STRIPPED = tuple(_strip_accents(w) for w in INTERROGATIVE_IT)

# Tool synonyms
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


def e_domanda(frase: str) -> bool:
    """
    Determine if a phrase is a question.

    Returns True if:
    - The phrase ends with '?' (ignoring trailing spaces), OR
    - The first word (lowercased, apostrophes normalized) is in INTERROGATIVE_IT

    Args:
        frase: The phrase to check

    Returns:
        True if the phrase is a question, False otherwise
    """
    if not frase:
        return False

    # Check if ends with question mark (ignoring trailing spaces)
    stripped = frase.rstrip()
    if stripped.endswith("?"):
        return True

    # Get first word (whitespace-separated token)
    frase_normalized = _normalize_apostrophes(frase.lower())
    first_word = frase_normalized.split()[0] if frase_normalized.split() else ""

    if not first_word:
        return False

    # Strip trailing punctuation from first word
    first_word = first_word.rstrip("?,.;:!")

    # Check if first word is in INTERROGATIVE_IT
    if first_word in INTERROGATIVE_IT:
        return True

    # Also check accent-stripped version against accent-stripped list
    first_word_stripped = _strip_accents(first_word)

    return first_word_stripped in _INTERROGATIVE_STRIPPED


def dispositivo_nominato(
    frase: str,
    tool: str,
    nome_entita: str | None,
) -> bool:
    """
    Check if a device is properly named in the phrase.

    For "vacuum" and "device" tools:
    - Returns True if any word (≥3 letters, no accents, lowercase) from nome_entita
      appears in the phrase, OR if any synonym of the tool appears in the phrase

    For other tools:
    - Always returns True

    Args:
        frase: The phrase to check
        tool: The tool name ("vacuum", "device", etc.)
        nome_entita: The entity name to look for

    Returns:
        True if device is properly named or tool is not a special tool
    """
    # Only special handling for vacuum and device tools
    if tool not in {"vacuum", "device"}:
        return True

    # Extract words from phrase for comparison
    # Strip accents first, then normalize apostrophes, then lowercase, then split
    frase_lower = frase.lower()
    frase_normalized = _normalize_apostrophes(frase_lower)
    frase_accents_stripped = _strip_accents(frase_normalized)
    # Split on non-alphanumeric characters
    phrase_words = set(
        w
        for w in re.split(r"[^a-z0-9]+", frase_accents_stripped)
        if len(w) >= 3
    )

    if tool == "device" and nome_entita:
        # A synonym alone ("presa") is not enough: a word of the entity name that is
        # not a synonym must be nominated. Names made only of synonyms fall through
        # to the generic rule below.
        sinonimi = {
            _strip_accents(syn.lower()) for syns in SINONIMI_IT.values() for syn in syns
        }
        nome_words = {
            w
            for w in re.split(
                r"[^a-z0-9]+", _strip_accents(_normalize_apostrophes(nome_entita.lower()))
            )
            if len(w) >= 3
        }
        distintive = nome_words - sinonimi
        if distintive:
            return bool(distintive & phrase_words)

    # Check tool synonyms
    if tool in SINONIMI_IT:
        for synonym in SINONIMI_IT[tool]:
            synonym_normalized = _strip_accents(synonym.lower())
            if synonym_normalized in phrase_words:
                return True

    # Check entity name words
    if nome_entita:
        nome_lower = nome_entita.lower()
        nome_normalized = _normalize_apostrophes(nome_lower)
        nome_accents_stripped = _strip_accents(nome_normalized)
        # Split on non-alphanumeric characters
        entity_words = set(
            w
            for w in re.split(r"[^a-z0-9]+", nome_accents_stripped)
            if len(w) >= 3
        )

        # Check if any entity word appears in phrase
        if entity_words & phrase_words:
            return True

    return False
