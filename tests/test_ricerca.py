"""Ricerca a parole nel contesto della casa."""

import yaml

from custom_components.needle.ricerca import filtra_live_context, parole

HEADER = "Live Context: An overview of the areas and the devices in this smart home:"
ENTITIES = [
    {"names": "cameretta Umidità, studio umidità", "domain": "sensor", "state": "48", "attributes": {"device_class": "humidity"}},
    {"names": "Sensore 2", "domain": "sensor", "state": "21", "areas": "Cameretta", "attributes": {"device_class": "temperature"}},
    {"names": "Luce cameretta", "domain": "light", "state": "off", "areas": "Cameretta"},
]


def data(entities=ENTITIES):
    return {"result": f"{HEADER}\n{yaml.safe_dump(entities, allow_unicode=True)}"}


def names(result):
    return [e["names"] for e in yaml.safe_load(result["result"].partition("\n")[2])]


def test_parole_senza_accenti_e_parole_corte():
    assert parole("Qual è l'umidità DELLA cameretta?") == {"qual", "umidita", "della", "cameretta"}


def test_needle_terms_win_then_phrase_breaks_ties():
    result = filtra_live_context(data(), {"cameretta"}, parole("temperatura cameretta"))
    assert names(result) == ["Sensore 2"]


def test_alias_matches():
    result = filtra_live_context(data(), set(), parole("studio umidità"))
    assert names(result) == ["cameretta Umidità, studio umidità"]


def test_domain_label_matches():
    result = filtra_live_context(data(), {"cameretta"}, parole("la luce della cameretta è accesa?"))
    assert names(result) == ["Luce cameretta"]


def test_no_match_keeps_everything():
    original = data()
    assert filtra_live_context(original, set(), parole("che ore sono")) is original
