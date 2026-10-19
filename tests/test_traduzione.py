"""Test della traduzione delle chiamate di Needle in intent di HA."""
import pytest
import yaml

from custom_components.needle.strumenti import (
    MISURE,
    Entita,
    genera_strumenti,
)
from custom_components.needle.traduzione import (
    LETTURE,
    e_lettura,
    filtra_misura,
    traduci,
)

INTENT = {
    "HassTurnOn",
    "HassTurnOff",
    "HassLightSet",
    "HassClimateSetTemperature",
    "HassSetPosition",
    "HassMediaPause",
    "HassMediaUnpause",
    "HassMediaNext",
    "HassMediaPrevious",
    "HassSetVolumeRelative",
    "HassVacuumStart",
    "HassVacuumReturnToBase",
    "GetLiveContext",
    "GetDateTime",
}
AREE = {"Bagno", "Cucina", "Camera"}


def _e(entity_id, nome, area, dominio, dc=None):
    return Entita(entity_id, nome, (area,) if area else (), dominio, dc)


CASA = [
    _e("light.a", "Luce bagno", "Bagno", "light"),
    _e("light.b", "Luce cucina", "Cucina", "light"),
    _e("climate.a", "Clima", "Camera", "climate"),
    _e("cover.a", "Tapparella", "Camera", "cover"),
    _e("media_player.a", "TV", "Camera", "media_player"),
    _e("switch.a", "Macchina caffè", None, "switch"),
    _e("vacuum.a", "Robot", None, "vacuum"),
    _e("vacuum.b", "Mocio", None, "vacuum"),
    _e("sensor.t", "Temp bagno", "Bagno", "sensor", "temperature"),
    _e("sensor.u", "Umidità", "Bagno", "sensor", "humidity"),
    _e("sensor.p", "Presa potenza", None, "sensor", "power"),
]
STRUMENTI = genera_strumenti(CASA, INTENT)


def _t(tool_name, /, **arguments):
    return traduci({"name": tool_name, "arguments": arguments}, STRUMENTI, INTENT, AREE)


def _uno(tool, /, **args):
    return [{"tool": tool, "args": args}]


@pytest.mark.parametrize(
    ("name", "arguments", "atteso"),
    [
        ("lights", {"room": "Bagno", "state": "on"},
         _uno("HassTurnOn", area="Bagno", domain=["light"])),
        ("lights", {"room": "Bagno", "state": "off"},
         _uno("HassTurnOff", area="Bagno", domain=["light"])),
        ("lights", {"room": "all", "state": "off"},
         _uno("HassTurnOff", domain=["light"])),
        ("lights", {"room": "Cucina", "brightness": 50},
         _uno("HassLightSet", area="Cucina", brightness=50)),
        ("lights", {"room": "Cucina", "state": "on", "brightness": 50},
         _uno("HassLightSet", area="Cucina", brightness=50)),
        ("air_conditioner", {"room": "Camera", "state": "on"},
         _uno("HassTurnOn", area="Camera", domain=["climate"])),
        ("air_conditioner", {"room": "Camera", "state": "off"},
         _uno("HassTurnOff", area="Camera", domain=["climate"])),
        ("air_conditioner", {"room": "Camera", "temperature": 22},
         _uno("HassClimateSetTemperature", area="Camera", temperature=22)),
        ("air_conditioner", {"room": "Camera", "state": "on", "temperature": 22},
         _uno("HassClimateSetTemperature", area="Camera", temperature=22)),
        ("blinds", {"room": "Camera", "action": "open"},
         _uno("HassTurnOn", area="Camera", domain=["cover"])),
        ("blinds", {"room": "Camera", "action": "close"},
         _uno("HassTurnOff", area="Camera", domain=["cover"])),
        ("blinds", {"room": "Camera", "position": 30},
         _uno("HassSetPosition", area="Camera", position=30, domain=["cover"])),
        ("blinds", {"room": "Camera", "action": "open", "position": 30},
         _uno("HassSetPosition", area="Camera", position=30, domain=["cover"])),
        ("media", {"action": "pause"}, _uno("HassMediaPause")),
        ("media", {"action": "resume"}, _uno("HassMediaUnpause")),
        ("media", {"action": "next"}, _uno("HassMediaNext")),
        ("media", {"action": "previous"}, _uno("HassMediaPrevious")),
        ("media", {"action": "louder"}, _uno("HassSetVolumeRelative", volume_step="up")),
        ("media", {"action": "quieter"}, _uno("HassSetVolumeRelative", volume_step="down")),
        ("device", {"name": "Macchina caffè", "state": "on"},
         _uno("HassTurnOn", name="Macchina caffè", domain=["switch", "fan", "input_boolean"])),
        ("device", {"name": "Macchina caffè", "state": "off"},
         _uno("HassTurnOff", name="Macchina caffè", domain=["switch", "fan", "input_boolean"])),
        ("vacuum", {"action": "start"}, _uno("HassVacuumStart")),
        ("vacuum", {"action": "return_to_base", "name": "Robot"},
         _uno("HassVacuumReturnToBase", name="Robot")),
        ("get_temperature", {"room": "Bagno"}, _uno("GetLiveContext", area="Bagno")),
        ("get_power", {"room": "Presa potenza"},
         _uno("GetLiveContext", name="Presa potenza")),
        ("get_humidity", {}, _uno("GetLiveContext")),
        ("get_time", {}, _uno("GetDateTime")),
    ],
)
def test_mappa(name, arguments, atteso):
    assert _t(name, **arguments) == atteso


def test_enum_case_normalized():
    assert _t("lights", room="bagno", state="ON") == _uno(
        "HassTurnOn", area="Bagno", domain=["light"]
    )


def test_value_outside_enum_dropped():
    assert _t("lights", room="Garage", state="on") == []
    assert _t("device", name="Forno", state="on") == []
    assert _t("device", name="Macchina caffè", state="maybe") == []


def test_incomplete_calls_are_empty():
    assert _t("air_conditioner", room="Camera") == []
    assert _t("air_conditioner", room="Garage", state="on") == []
    assert _t("blinds", room="Camera") == []
    assert _t("media", action="dance") == []
    assert _t("lights", state="on") == []


def test_unknown_tool_or_missing_intent():
    assert _t("foo") == []
    assert traduci({"name": "foo"}, STRUMENTI, INTENT, AREE) == []
    senza = INTENT - {"HassVacuumStart"}
    assert traduci({"name": "vacuum", "arguments": {"action": "start"}},
                   STRUMENTI, senza, AREE) == []
    assert traduci({"name": "get_time", "arguments": {}},
                   STRUMENTI, INTENT - {"GetDateTime"}, AREE) == []


def test_house_without_areas():
    casa = [_e("climate.a", "Clima", None, "climate"), _e("cover.a", "Tapp", None, "cover")]
    strumenti = genera_strumenti(casa, INTENT)
    assert traduci({"name": "air_conditioner", "arguments": {"state": "on"}},
                   strumenti, INTENT, set()) == _uno("HassTurnOn", domain=["climate"])
    assert traduci({"name": "blinds", "arguments": {"action": "close"}},
                   strumenti, INTENT, set()) == _uno("HassTurnOff", domain=["cover"])


def test_letture_in_sync_with_strumenti():
    assert set(LETTURE) == {n for n, _ in MISURE.values()} | {"get_time"}
    for device_class, (nome, _) in MISURE.items():
        assert LETTURE[nome] == device_class
    assert LETTURE["get_time"] is None
    assert e_lettura("get_temperature") and e_lettura("get_time")
    assert not e_lettura("lights")


def test_domini_device_in_sync_with_strumenti():
    from custom_components.needle import strumenti, traduzione

    assert tuple(traduzione.DOMINI_DEVICE) == strumenti._DEVICE_DOMINI


LIVE = (
    "Live Context: An overview of the areas and the devices in this smart home:\n"
    + yaml.safe_dump(
        [
            {"names": "Temp bagno", "state": "21",
             "attributes": {"device_class": "temperature", "unit": "°C"}},
            {"names": "Umidità", "state": "50",
             "attributes": {"device_class": "humidity"}},
            {"names": "Luce", "state": "on"},
        ],
        allow_unicode=True,
        sort_keys=False,
    )
)


def test_filtra_misura():
    out = filtra_misura({"success": True, "result": LIVE}, "temperature")
    testa, corpo = out["result"].split("\n", 1)
    assert testa == LIVE.split("\n", 1)[0]
    assert [x["names"] for x in yaml.safe_load(corpo)] == ["Temp bagno"]
    assert out["success"] is True


def test_filtra_misura_unparseable_unchanged():
    for data in ({"result": "Live Context: x\n: [bad"}, {"foo": 1}, {"result": 5}):
        assert filtra_misura(data, "temperature") == data
