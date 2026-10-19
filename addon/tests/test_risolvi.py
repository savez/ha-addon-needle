"""Risoluzione dei nomi con un embedder finto (trigrammi di caratteri)."""
import math

from app.risolvi import Risolutore

ENTITA = [
    {"nome": "Luce bagno", "alias": [], "aree": ["Bagno"], "dominio": "light"},
    {"nome": "cameretta Temperatura", "alias": [], "aree": ["Cameretta"], "dominio": "sensor"},
    {"nome": "cameretta Umidità", "alias": ["studio umidità"], "aree": ["Cameretta"], "dominio": "sensor"},
    {"nome": "Tapparella salotto", "alias": [], "aree": ["Salotto"], "dominio": "cover"},
]


class FakeEmbedder:
    """Similarità tra trigrammi: basta per verificare la logica, non il modello."""

    DIM = 512

    def _vec(self, text):
        text = f"  {text.casefold()}  "
        v = [0.0] * self.DIM
        for i in range(len(text) - 2):
            v[hash(text[i:i + 3]) % self.DIM] += 1
        norm = math.sqrt(sum(x * x for x in v)) or 1
        return [x / norm for x in v]

    def query(self, text):
        return self._vec(text)

    def documento(self, text):
        return self._vec(text)


def reply(*calls):
    return {"function_calls": [{"name": n, "arguments": a} for n, a in calls]}


def args(result, i=0):
    return result["function_calls"][i]["arguments"]


def test_typo_resolved_to_real_name():
    r = Risolutore(FakeEmbedder(), soglia=0.3)
    result = r.risolvi(reply(("HassTurnOn", {"name": "luce bagnetto"})), "accendi la luce del bagnetto", ENTITA)
    assert args(result) == {"name": "Luce bagno"}
    assert result["risoluzioni"][0]["da"] == "luce bagnetto"


def test_phrase_picks_between_same_room():
    r = Risolutore(FakeEmbedder(), soglia=0.0)
    result = r.risolvi(reply(("GetLiveContext", {"name": "cameretta"})), "dimmi la temperatura della cameretta", ENTITA)
    assert args(result) == {"name": "cameretta Temperatura"}


def test_area_resolved():
    r = Risolutore(FakeEmbedder(), soglia=0.3)
    result = r.risolvi(reply(("HassTurnOff", {"area": "salotto grande"})), "chiudi il salotto grande", ENTITA)
    assert args(result) == {"area": "Salotto"}


def test_real_names_and_aliases_untouched():
    r = Risolutore(FakeEmbedder(), soglia=0.0)
    result = r.risolvi(reply(("GetLiveContext", {"name": "studio umidità", "area": "bagno"})), "x", ENTITA)
    assert args(result) == {"name": "studio umidità", "area": "bagno"}
    assert result["risoluzioni"] == []


def test_below_threshold_keeps_needle_value():
    r = Risolutore(FakeEmbedder(), soglia=0.99)
    result = r.risolvi(reply(("HassTurnOn", {"name": "garage"})), "accendi il garage", ENTITA)
    assert args(result) == {"name": "garage"}
    assert result["risoluzioni"][0]["similarita"] < 0.99


def test_without_entities_response_unchanged():
    response = reply(("HassTurnOn", {"name": "x"}))
    assert Risolutore(FakeEmbedder(), soglia=0.1).risolvi(response, "x", []) is response


def test_suppressed_calls_resolved_too():
    r = Risolutore(FakeEmbedder(), soglia=0.0)
    response = {"function_calls": [], "suppressed_calls": [{"name": "GetLiveContext", "arguments": {"name": "cameretta"}}]}
    result = r.risolvi(response, "dimmi la temperatura della cameretta", ENTITA)
    assert result["suppressed_calls"][0]["arguments"] == {"name": "cameretta Temperatura"}
