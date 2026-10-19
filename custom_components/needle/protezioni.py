"""Protection functions for Needle conversation handling."""

import re
import unicodedata
from typing import Optional

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


def _strip_accents(text: str) -> str:
    """Strip accents from text using NFKD normalization."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn")


def _normalize_apostrophes(text: str) -> str:
    """Normalize different apostrophe characters to the standard one."""
    # Replace both ' and ' with '
    return text.replace("'", "'").replace("'", "'")


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

    # Check if first word is in INTERROGATIVE_IT
    if first_word in INTERROGATIVE_IT:
        return True

    # Also check accent-stripped version against accent-stripped list
    first_word_stripped = _strip_accents(first_word)
    interrogative_stripped = [_strip_accents(w) for w in INTERROGATIVE_IT]

    return first_word_stripped in interrogative_stripped


def dispositivo_nominato(
    frase: str,
    tool: str,
    nome_entita: Optional[str],
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
    frase_lower = frase.lower()
    frase_normalized = _normalize_apostrophes(frase_lower)
    # Split on non-alphanumeric characters
    phrase_words = set(
        _strip_accents(w)
        for w in re.split(r"[^a-z0-9]", frase_normalized)
        if len(w) >= 3
    )

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
        # Split on non-alphanumeric characters
        entity_words = set(
            _strip_accents(w)
            for w in re.split(r"[^a-z0-9]", nome_normalized)
            if len(w) >= 3
        )

        # Check if any entity word appears in phrase
        if entity_words & phrase_words:
            return True

    return False
