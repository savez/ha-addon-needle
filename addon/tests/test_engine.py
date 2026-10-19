"""Test del motore Needle con agenti finti."""
import threading

import pytest

from app.engine import NeedleEngine

TOOLS_A = [{"name": "HassTurnOn", "description": "accende", "parameters": {"type": "object"}}]
TOOLS_B = [{"name": "HassTurnOff", "description": "spegne", "parameters": {"type": "object"}}]


class FakeAgent:
    def __init__(self, tools):
        self.tools = tools
        self.calls: list[str] = []
        self.resets = 0
        self.closed = False

    def reset(self):
        self.resets += 1
        self.calls.clear()

    def complete(self, text):
        self.calls.append(text)
        return {
            "type": "call",
            "function_calls": [{"name": self.tools[0]["name"], "arguments": {"turno": len(self.calls)}}],
            "confidence": 0.5,
            "validation": {"ungrounded": [f"turno{len(self.calls)}.x"]},
        }

    def close(self):
        self.closed = True


class Factory:
    def __init__(self):
        self.created: list[FakeAgent] = []

    def __call__(self, tools):
        agent = FakeAgent(tools)
        self.created.append(agent)
        return agent


def test_single_turn_returns_response_with_validation():
    factory = Factory()
    engine = NeedleEngine(factory)
    result = engine.infer(TOOLS_A, ["accendi la luce"])
    assert result["function_calls"] == [{"name": "HassTurnOn", "arguments": {"turno": 1}}]
    assert result["validation"] == {"ungrounded": ["turno1.x"]}
    assert isinstance(result["durata_ms"], int)


def test_multi_turn_replays_all_turns_after_reset():
    factory = Factory()
    engine = NeedleEngine(factory)
    result = engine.infer(TOOLS_A, ["frase", "[risultato]"])
    agent = factory.created[0]
    assert agent.resets == 1
    assert agent.calls == ["frase", "[risultato]"]
    assert result["function_calls"][0]["arguments"] == {"turno": 2}
    assert result["validation"] == {"ungrounded": []}


def test_same_tools_reuse_instance():
    factory = Factory()
    engine = NeedleEngine(factory)
    engine.infer(TOOLS_A, ["uno"])
    engine.infer([dict(TOOLS_A[0])], ["due"])
    assert len(factory.created) == 1
    assert factory.created[0].resets == 2


def test_cache_evicts_oldest_and_closes_it():
    factory = Factory()
    engine = NeedleEngine(factory, max_cached=1)
    engine.infer(TOOLS_A, ["uno"])
    engine.infer(TOOLS_B, ["due"])
    assert len(factory.created) == 2
    assert factory.created[0].closed is True
    assert factory.created[1].closed is False


def test_empty_turns_rejected():
    engine = NeedleEngine(Factory())
    with pytest.raises(ValueError):
        engine.infer(TOOLS_A, [])


def test_inference_is_serialized():
    active = 0
    max_active = 0
    lock = threading.Lock()

    class SlowAgent(FakeAgent):
        def complete(self, text):
            nonlocal active, max_active
            with lock:
                active += 1
                max_active = max(max_active, active)
            threading.Event().wait(0.02)
            with lock:
                active -= 1
            return super().complete(text)

    engine = NeedleEngine(lambda tools: SlowAgent(tools))
    threads = [threading.Thread(target=engine.infer, args=(TOOLS_A, ["x"])) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert max_active == 1


def test_risolutore_applied_with_entities():
    class R:
        def __init__(self):
            self.seen = None

        def risolvi(self, response, frase, entita):
            self.seen = (frase, entita)
            return {**response, "risolto": True}

    r = R()
    engine = NeedleEngine(Factory(), risolutore=r)
    assert "risolto" not in engine.infer(TOOLS_A, ["ciao"])
    result = engine.infer(TOOLS_A, ["ciao", "risultato"], [{"nome": "x"}])
    assert result["risolto"] is True
    assert r.seen == ("ciao", [{"nome": "x"}])
