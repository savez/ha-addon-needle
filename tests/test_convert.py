"""Test della conversione dei tool."""
from types import SimpleNamespace

import probatio

from homeassistant.helpers import config_validation as cv, llm

from custom_components.needle.convert import (
    base_name,
    clean_args,
    drop_ungrounded,
    format_tools,
    needle_tools,
    read_only_tools,
)


def _tool(name, read_only=False):
    tool = llm.Tool()
    tool.name = name
    tool.description = f"desc {name}"
    tool.parameters = probatio.Schema(
        {probatio.Optional("name"): cv.string, probatio.Optional("domain"): [cv.string]}
    )
    tool.annotations = llm.ToolAnnotations(read_only=read_only)
    return tool


API = SimpleNamespace(
    tools=[_tool("HassTurnOff"), _tool("homeassistant__GetLiveContext", read_only=True)],
    custom_serializer=llm.selector_serializer,
)

PARAMS = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "domain": {"type": "array", "items": {"type": "string"}},
        "level": {"anyOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
        "brightness": {"type": "integer"},
    },
}


def test_format_tools():
    tools = format_tools(API)
    assert [t["name"] for t in tools] == ["HassTurnOff", "homeassistant__GetLiveContext"]
    assert tools[0]["description"] == "desc HassTurnOff"
    props = tools[0]["parameters"]["properties"]
    assert props["name"]["type"] == "string"
    assert props["domain"]["type"] == "array"


def test_read_only_tools():
    assert read_only_tools(API) == {"homeassistant__GetLiveContext"}


def test_clean_args_drops_empty_and_unknown():
    args = {"name": "Luce", "brightness": None, "level": "", "inventato": 1}
    assert clean_args(args, PARAMS) == {"name": "Luce"}


def test_clean_args_wraps_string_for_array():
    assert clean_args({"domain": "light"}, PARAMS) == {"domain": ["light"]}


def test_clean_args_keeps_string_when_string_allowed():
    assert clean_args({"level": "alto"}, PARAMS) == {"level": "alto"}


def test_drop_ungrounded_matches_snake_case_name():
    args = {"name": "lampada", "device_class": "light_set"}
    result = drop_ungrounded("HassTurnOff", args, ["hass_turn_off.device_class"])
    assert result == {"name": "lampada"}


def test_drop_ungrounded_ignores_other_tools():
    args = {"device_class": "x"}
    assert drop_ungrounded("HassTurnOn", args, ["hass_turn_off.device_class"]) == args


def test_drop_ungrounded_namespaced_tool():
    args = {"area": "bagno", "name": "x"}
    result = drop_ungrounded("homeassistant__GetLiveContext", args, ["get_live_context.name"])
    assert result == {"area": "bagno"}


def test_base_name():
    assert base_name("homeassistant__GetLiveContext") == "GetLiveContext"
    assert base_name("HassTurnOn") == "HassTurnOn"


def test_drop_ungrounded_prefixed_tool_name():
    args = {"name": "x", "device_class": "x"}
    result = drop_ungrounded("intent__HassTurnOff", args, ["intent__HassTurnOff.device_class"])
    assert result == {"name": "x"}


def test_needle_tools_strips_unique_prefixes():
    api = SimpleNamespace(
        tools=[_tool("intent__HassTurnOff"), _tool("homeassistant__GetLiveContext", read_only=True)],
        custom_serializer=llm.selector_serializer,
    )
    tools, real_names = needle_tools(api)
    assert [t["name"] for t in tools] == ["HassTurnOff", "GetLiveContext"]
    assert real_names == {"HassTurnOff": "intent__HassTurnOff", "GetLiveContext": "homeassistant__GetLiveContext"}
    assert tools[0]["parameters"] == format_tools(api)[0]["parameters"]


def test_needle_tools_keeps_prefix_on_collision():
    api = SimpleNamespace(
        tools=[_tool("light__HassTurnOn"), _tool("intent__HassTurnOn"), _tool("intent__HassTurnOff")],
        custom_serializer=llm.selector_serializer,
    )
    tools, real_names = needle_tools(api)
    assert [t["name"] for t in tools] == ["light__HassTurnOn", "intent__HassTurnOn", "HassTurnOff"]
    assert real_names["HassTurnOff"] == "intent__HassTurnOff"
    assert real_names["light__HassTurnOn"] == "light__HassTurnOn"
