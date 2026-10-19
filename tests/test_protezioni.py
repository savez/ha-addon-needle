"""Tests for protezioni module."""

import pytest
from custom_components.needle.protezioni import (
    INTERROGATIVE_IT,
    SINONIMI_IT,
    e_domanda,
    dispositivo_nominato,
)


class TestInterrogativeIT:
    """Test INTERROGATIVE_IT constant."""

    def test_interrogative_tuple_exists(self):
        """Test that INTERROGATIVE_IT is a tuple."""
        assert isinstance(INTERROGATIVE_IT, tuple)

    def test_interrogative_contains_expected_words(self):
        """Test that INTERROGATIVE_IT contains expected Italian interrogative words."""
        expected = {"è", "e'", "sono", "c'è", "ce", "che", "quale", "quali",
                    "quanto", "quanta", "quanti", "quante", "com'è", "come",
                    "dimmi", "dove"}
        assert set(INTERROGATIVE_IT) == expected


class TestSinonimiIT:
    """Test SINONIMI_IT constant."""

    def test_sinonimi_is_dict(self):
        """Test that SINONIMI_IT is a dict."""
        assert isinstance(SINONIMI_IT, dict)

    def test_sinonimi_has_required_keys(self):
        """Test that SINONIMI_IT has required tool keys."""
        assert "vacuum" in SINONIMI_IT
        assert "device" in SINONIMI_IT

    def test_sinonimi_vacuum_values(self):
        """Test vacuum synonyms."""
        vacuum_syns = SINONIMI_IT["vacuum"]
        assert isinstance(vacuum_syns, tuple)
        expected = {"robot", "aspirapolvere", "aspira", "pulisci", "pulizia"}
        assert set(vacuum_syns) == expected

    def test_sinonimi_device_values(self):
        """Test device synonyms."""
        device_syns = SINONIMI_IT["device"]
        assert isinstance(device_syns, tuple)
        expected = {"presa", "interruttore", "spina", "ventilatore"}
        assert set(device_syns) == expected


class TestEDomanda:
    """Test e_domanda function."""

    def test_question_with_question_mark(self):
        """Test phrase ending with question mark."""
        assert e_domanda("accendi la luce?") is True
        assert e_domanda("la luce del bagno è accesa?") is True
        assert e_domanda("accendi la luce? ") is True  # spaces after ?

    def test_question_starting_with_interrogative(self):
        """Test phrase starting with interrogative word."""
        assert e_domanda("che temperatura c'è") is True
        assert e_domanda("quanti gradi ci sono in camera") is True
        assert e_domanda("dimmi la temperatura") is True
        assert e_domanda("come stai") is True
        assert e_domanda("dove sei") is True
        assert e_domanda("c'è qualcuno") is True

    def test_interrogative_with_apostrophes(self):
        """Test interrogative words with apostrophes."""
        assert e_domanda("c'è la luce") is True
        assert e_domanda("com'è il tempo") is True
        assert e_domanda("e' accesa la luce") is True

    def test_non_question_statement(self):
        """Test non-question statements."""
        assert e_domanda("accendi la luce del bagno") is False
        assert e_domanda("spegni tutte le luci") is False
        assert e_domanda("metti il termostato a 21") is False
        assert e_domanda("accendi il ventilatore") is False

    def test_case_insensitive(self):
        """Test that check is case insensitive."""
        assert e_domanda("CHE temperatura c'è") is True
        assert e_domanda("DIMMI la temperatura") is True
        assert e_domanda("SONO accesa") is True

    def test_empty_string(self):
        """Test empty string."""
        assert e_domanda("") is False

    def test_typographic_apostrophes(self):
        """Test different apostrophe characters (typographic variants)."""
        # Regular apostrophe
        assert e_domanda("c'è la luce") is True
        # Typographic apostrophes (U+2019 right single quotation mark)
        assert e_domanda("c’è la luce") is True
        # Modifier letter apostrophe (U+02BC)
        assert e_domanda("cʼè la luce") is True
        # Backtick
        assert e_domanda("c`è la luce") is True
        # With E' (capital E with U+2019 apostrophe)
        assert e_domanda("E’ accesa") is True
        # With com'è (U+2019)
        assert e_domanda("com’è la temperatura") is True

    def test_trailing_punctuation_in_first_word(self):
        """Test that trailing punctuation is stripped from first word."""
        assert e_domanda("dimmi, la temperatura") is True
        assert e_domanda("che? temperatura") is True
        assert e_domanda("quale: nome") is True


class TestDispositivoNominato:
    """Test dispositivo_nominato function."""

    def test_vacuum_entity_name_in_phrase(self):
        """Test vacuum tool with entity name in phrase."""
        # "Robot" should match "robot" when split and lowercased
        assert dispositivo_nominato("avvia il robot", "vacuum", "Roborock") is True
        # Entity name words (>= 3 chars): "Nettino" -> "nettino"
        assert dispositivo_nominato("manda nettino alla base", "vacuum", "Nettino") is True

    def test_vacuum_entity_name_not_in_phrase(self):
        """Test vacuum tool with entity name not in phrase."""
        # "Robot" is entity name but "presa" is in phrase, and no robot in phrase
        assert dispositivo_nominato("accendi la presa dell'albero di natale", "vacuum", "Robot") is False

    def test_device_entity_words_in_phrase(self):
        """Test device tool with entity words in phrase."""
        # "presa-balcone-sala Presa" splits to ["presa", "balcone", "sala", "Presa"]
        # Words >= 3 chars: "presa", "balcone", "sala"
        # Phrase contains "presa"
        assert dispositivo_nominato("accendi la presa del balcone", "device", "presa-balcone-sala Presa") is True

    def test_vacuum_synonym_in_phrase(self):
        """Test vacuum tool with synonym in phrase."""
        # "aspirapolvere" is a synonym of vacuum
        assert dispositivo_nominato("accendi l'aspirapolvere", "vacuum", "VacuumBot") is True
        # "robot" is a synonym of vacuum
        assert dispositivo_nominato("avvia il robot", "vacuum", "AnotherBot") is True
        # "pulisci" is a synonym
        assert dispositivo_nominato("pulisci la stanza", "vacuum", "Cleaner") is True

    def test_device_synonym_in_phrase(self):
        """Test device tool with synonym in phrase."""
        # "interruttore" is a synonym of device
        # device: a synonym alone is NOT enough, the entity name must be nominated
        assert dispositivo_nominato("accendi l'interruttore", "device", "Button") is False
        assert dispositivo_nominato("accendi il ventilatore", "device", "Fan") is False
        assert dispositivo_nominato("accendi il ventilatore dello studio", "device", "Ventilatore studio") is True

    def test_device_nome_fatto_solo_di_sinonimi(self):
        """Fallback: se il nome non ha parole distintive basta il sinonimo."""
        assert dispositivo_nominato("accendi la presa", "device", "Presa") is True
        assert dispositivo_nominato("accendi la luce", "device", "Presa") is False

    def test_device_presa_va_nominata(self):
        """Una presa nominata solo con "presa" non basta."""
        frase = "accendi la presa dell'albero di natale"
        assert dispositivo_nominato(frase, "device", "presa-balcone Presa") is False
        assert dispositivo_nominato(frase, "device", "Presa albero di Natale") is True
        assert dispositivo_nominato("spegni la presa del balcone", "device", "presa-balcone Presa") is True
        assert dispositivo_nominato("accendi la presa", "device", "Presa albero di Natale") is False

    def test_non_special_tool_always_true(self):
        """Test that non-special tools always return True."""
        assert dispositivo_nominato("accendi la luce", "lights", None) is True
        assert dispositivo_nominato("accendi la luce", "lights", "Kitchen Light") is True
        assert dispositivo_nominato("spegni tutto", "cover", None) is True
        assert dispositivo_nominato("accendi", "unknown_tool", "Something") is True

    def test_none_entity_name(self):
        """Test with None as entity name."""
        # Without entity name and without synonyms, should return False
        assert dispositivo_nominato("accendi la luce", "vacuum", None) is False
        # With synonym present, should return True even with None entity name
        assert dispositivo_nominato("accendi il robot", "vacuum", None) is True  # robot is synonym
        assert dispositivo_nominato("accendi l'aspirapolvere", "vacuum", None) is True  # aspirapolvere is synonym

    def test_case_insensitive_entity(self):
        """Test that entity name matching is case insensitive."""
        assert dispositivo_nominato("avvia il ROBOT", "vacuum", "Roborock") is True
        assert dispositivo_nominato("avvia il Robot", "vacuum", "roborock") is True

    def test_accents_stripped(self):
        """Test that accents are stripped when comparing."""
        # "caffè" -> "caffe" when accents stripped, not split on accent
        assert dispositivo_nominato("accendi il caffè", "device", "Caffe") is True
        # Also test reverse: entity has accent, phrase doesn't
        assert dispositivo_nominato("accendi il caffe", "device", "Caffè") is True
        # Test with hyphenated entity
        assert dispositivo_nominato("accendi il caffè", "device", "Caffè-bar") is True

    def test_short_words_ignored(self):
        """Test that words with less than 3 characters are ignored."""
        # Entity name "di camera" -> "di" (2 chars, ignored), "camera" (6 chars, kept)
        # Phrase has "camera" but entity name is only matched by "camera"
        assert dispositivo_nominato("accendi la camera", "device", "di camera") is True
        # Entity name "TV di camera" -> "TV" (2 chars, ignored), "di" (2 chars, ignored), "camera" (6 chars)
        # Phrase "accendi di" should NOT match just on "di" (short word)
        assert dispositivo_nominato("accendi di", "device", "TV di camera") is False
        # But should match if "camera" is in phrase
        assert dispositivo_nominato("accendi di camera", "device", "TV di camera") is True

    def test_special_characters_split(self):
        """Test splitting on special characters."""
        # "presa-balcone-sala Presa" splits by non-alphanumeric
        # Should split into: presa, balcone, sala, presa
        assert dispositivo_nominato("accendi la presa", "device", "presa-balcone-sala") is False
        assert dispositivo_nominato("accendi il balcone", "device", "presa-balcone-sala") is True
