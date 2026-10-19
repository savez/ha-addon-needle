"""Test del generatore dei tool per Needle."""
import json
import logging

from custom_components.needle.strumenti import (
    MAX_ENUM,
    MISURE,
    Entita,
    entita_da_esposte,
    genera_strumenti,
)

ON_OFF = {"HassTurnOn", "HassTurnOff"}


def _by_name(tools):
    return {t["name"]: t for t in tools}


def _enum(tool, param):
    return tool["parameters"]["properties"][param]["enum"]


def _luce(i, area):
    return Entita(f"light.l{i}", f"Luce {i}", (area,) if area else (), "light", None)


def _sensore(i, nome, area, dc):
    return Entita(f"sensor.s{i}", nome, (area,) if area else (), "sensor", dc)


def _all_enums(tools):
    for tool in tools:
        for prop in tool["parameters"]["properties"].values():
            if "enum" in prop:
                yield tool["name"], prop["enum"]


def test_lights_rooms_and_all():
    ent = [_luce(1, "Cucina"), _luce(2, "Bagno"), _luce(3, "Bagno")]
    tools = _by_name(genera_strumenti(ent, ON_OFF | {"HassLightSet"}))
    assert _enum(tools["lights"], "room") == ["Bagno", "Cucina", "all"]
    assert "brightness" in tools["lights"]["parameters"]["properties"]
    assert tools["lights"]["parameters"]["required"] == ["state"]
    assert tools["lights"]["description"].startswith("Turn lights on or off")


def test_tool_only_when_domain_and_intent():
    ent = [_luce(1, "Bagno"), Entita("climate.c", "Clima", ("Bagno",), "climate", None)]
    tools = _by_name(genera_strumenti(ent, ON_OFF))
    assert "blinds" not in tools
    assert "temperature" not in tools["air_conditioner"]["parameters"]["properties"]
    assert "brightness" not in tools["lights"]["parameters"]["properties"]
    tools = _by_name(genera_strumenti(ent, {"HassClimateSetTemperature"}))
    assert "air_conditioner" not in tools
    assert "lights" not in tools
    tools = _by_name(genera_strumenti(ent, ON_OFF | {"HassClimateSetTemperature"}))
    assert "temperature" in tools["air_conditioner"]["parameters"]["properties"]


def test_measures_from_device_class():
    ent = [
        _sensore(1, "Temp bagno", "Bagno", "temperature"),
        _sensore(2, "Umidità esterna", None, "humidity"),
        _sensore(3, "Senza classe", "Bagno", None),
    ]
    tools = _by_name(genera_strumenti(ent, {"GetLiveContext"}))
    assert _enum(tools["get_temperature"], "room") == ["Bagno"]
    assert _enum(tools["get_humidity"], "room") == ["Umidità esterna"]
    assert set(tools) == {"get_temperature", "get_humidity"}
    assert {"temperature", "humidity", "illuminance", "power", "battery"} <= set(MISURE)
    assert genera_strumenti(ent, set()) == []


def test_no_areas_house():
    tools = genera_strumenti([_luce(1, None), _luce(2, None)], ON_OFF)
    assert _enum(_by_name(tools)["lights"], "room") == ["all"]
    assert all(values for _, values in _all_enums(tools))


def test_empty_enum_omits_param_or_tool():
    # sensore senza area né nome utilizzabile non esiste; solo media senza azioni
    ent = [Entita("media_player.m", "TV", (), "media_player", None)]
    assert genera_strumenti(ent, ON_OFF) == []
    tools = _by_name(genera_strumenti(ent, {"HassMediaPause", "HassSetVolumeRelative"}))
    assert _enum(tools["media"], "action") == ["pause", "louder", "quieter"]


def test_vacuum_name_only_when_several():
    one = [Entita("vacuum.a", "Robo", (), "vacuum", None)]
    tools = _by_name(genera_strumenti(one, {"HassVacuumStart"}))
    assert "name" not in tools["vacuum"]["parameters"]["properties"]
    assert _enum(tools["vacuum"], "action") == ["start"]
    two = one + [Entita("vacuum.b", "Aspira", (), "vacuum", None)]
    tools = _by_name(genera_strumenti(two, {"HassVacuumStart", "HassVacuumReturnToBase"}))
    assert _enum(tools["vacuum"], "name") == ["Aspira", "Robo"]
    assert _enum(tools["vacuum"], "action") == ["start", "return_to_base"]


def test_get_time_and_order():
    ent = [
        _sensore(1, "T", "Bagno", "temperature"),
        Entita("switch.p", "Presa", (), "switch", None),
        _luce(1, "Bagno"),
    ]
    tools = genera_strumenti(ent, ON_OFF | {"GetLiveContext", "GetDateTime"})
    assert [t["name"] for t in tools] == ["lights", "device", "get_temperature", "get_time"]
    assert tools[-1]["parameters"]["properties"] == {}
    assert _by_name(tools)["device"]["parameters"]["required"] == ["name", "state"]


def test_enum_limit(caplog):
    ent = [Entita(f"switch.s{i}", f"Presa {i:02d}", (), "switch", None) for i in range(45)]
    ent.reverse()
    with caplog.at_level(logging.WARNING):
        tools = _by_name(genera_strumenti(ent, ON_OFF))
    values = _enum(tools["device"], "name")
    assert len(values) == MAX_ENUM == 40
    assert values == sorted(values)
    assert "device" in caplog.text


def test_deterministic():
    ent = [
        _luce(1, "Cucina"),
        _luce(2, "Bagno"),
        _sensore(3, "T", "Bagno", "temperature"),
        Entita("switch.x", "Presa", (), "switch", None),
    ]
    intents = ON_OFF | {"GetLiveContext", "GetDateTime"}
    a = json.dumps(genera_strumenti(ent, intents))
    b = json.dumps(genera_strumenti(list(reversed(ent)), set(reversed(sorted(intents)))))
    assert a == b


def test_entita_da_esposte():
    esposte = {
        "light.a": {"names": "Luce, Lampada", "domain": "light", "areas": "Bagno, Corridoio"},
        "sensor.t": {
            "names": "Temp",
            "domain": "sensor",
            "attributes": {"device_class": "temperature"},
        },
    }
    assert sorted(entita_da_esposte(esposte), key=lambda e: e.entity_id) == [
        Entita("light.a", "Luce", ("Bagno", "Corridoio"), "light", None),
        Entita("sensor.t", "Temp", (), "sensor", "temperature"),
    ]
