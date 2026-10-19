"""Test del server HTTP dell'add-on."""
import pytest

from app.server import AppState, create_app, load_model


class FakeEngine:
    def __init__(self, result=None, exc=None):
        self.result = result or {"type": "call", "function_calls": [], "validation": {"ungrounded": []}, "durata_ms": 1}
        self.exc = exc
        self.seen = None

    def infer(self, tools, turni, entita=None):
        self.seen = (tools, turni)
        self.entita = entita
        if self.exc:
            raise self.exc
        return self.result


TOOLS = [{"name": "HassTurnOn", "description": "x", "parameters": {"type": "object"}}]


@pytest.fixture
def make_client(aiohttp_client):
    async def _make(state):
        return await aiohttp_client(create_app(state))
    return _make


async def test_health_loading(make_client):
    client = await make_client(AppState())
    resp = await client.get("/health")
    assert resp.status == 503
    assert (await resp.json())["stato"] == "caricamento"


async def test_health_error(make_client):
    client = await make_client(AppState(errore="download fallito"))
    resp = await client.get("/health")
    assert resp.status == 503
    assert await resp.json() == {"stato": "errore", "errore": "download fallito"}


async def test_health_ok(make_client):
    client = await make_client(AppState(engine=FakeEngine(), versione="3.2.7"))
    resp = await client.get("/health")
    assert resp.status == 200
    assert await resp.json() == {"stato": "ok", "versione": "3.2.7"}


async def test_infer_ok(make_client):
    engine = FakeEngine()
    client = await make_client(AppState(engine=engine))
    resp = await client.post("/v1/infer", json={"tools": TOOLS, "turni": ["accendi"]})
    assert resp.status == 200
    assert (await resp.json())["type"] == "call"
    assert engine.seen == (TOOLS, ["accendi"])


async def test_infer_not_ready(make_client):
    client = await make_client(AppState())
    resp = await client.post("/v1/infer", json={"tools": TOOLS, "turni": ["accendi"]})
    assert resp.status == 503


@pytest.mark.parametrize(
    "body",
    [
        "non json",
        [],
        {"tools": "x", "turni": ["a"]},
        {"tools": [{"description": "senza nome"}], "turni": ["a"]},
        {"tools": TOOLS, "turni": []},
        {"tools": TOOLS, "turni": [1]},
    ],
)
async def test_infer_bad_request(make_client, body):
    client = await make_client(AppState(engine=FakeEngine()))
    if isinstance(body, str):
        resp = await client.post("/v1/infer", data=body, headers={"Content-Type": "application/json"})
    else:
        resp = await client.post("/v1/infer", json=body)
    assert resp.status == 400


async def test_infer_engine_error(make_client):
    client = await make_client(AppState(engine=FakeEngine(exc=RuntimeError("boom"))))
    resp = await client.post("/v1/infer", json={"tools": TOOLS, "turni": ["accendi"]})
    assert resp.status == 500
    assert "boom" in (await resp.json())["errore"]


async def test_load_model_success():
    state = AppState()
    engine = FakeEngine()
    await load_model(state, lambda: (engine, "3.2.7"))
    assert state.engine is engine
    assert state.versione == "3.2.7"
    assert state.errore is None


async def test_load_model_failure():
    state = AppState()

    def broken():
        raise OSError("rete assente")

    await load_model(state, broken)
    assert state.engine is None
    assert "rete assente" in state.errore


async def test_infer_passes_entities(make_client):
    engine = FakeEngine()
    client = await make_client(AppState(engine=engine, versione="t"))
    entita = [{"nome": "Luce bagno", "alias": [], "aree": ["Bagno"]}]
    resp = await client.post("/v1/infer", json={"tools": TOOLS, "turni": ["x"], "entita": entita})
    assert resp.status == 200
    assert engine.entita == entita


async def test_infer_rejects_bad_entities(make_client):
    client = await make_client(AppState(engine=FakeEngine(), versione="t"))
    resp = await client.post("/v1/infer", json={"tools": TOOLS, "turni": ["x"], "entita": "no"})
    assert resp.status == 400
