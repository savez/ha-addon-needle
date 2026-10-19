"""Test del client HTTP dell'add-on."""
import aiohttp
import pytest

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.needle.client import NeedleBadRequest, NeedleClient, NeedleUnavailable

URL = "http://needle.test:8765"


@pytest.fixture
async def client(hass, aioclient_mock):
    return NeedleClient(async_get_clientsession(hass), URL, 3)


async def test_health_ok(client, aioclient_mock):
    aioclient_mock.get(f"{URL}/health", json={"stato": "ok", "versione": "3.2.7"})
    assert await client.health() == {"stato": "ok", "versione": "3.2.7"}


async def test_health_loading_is_unavailable(client, aioclient_mock):
    aioclient_mock.get(f"{URL}/health", status=503, json={"stato": "caricamento"})
    with pytest.raises(NeedleUnavailable):
        await client.health()


async def test_infer_ok(client, aioclient_mock):
    aioclient_mock.post(f"{URL}/v1/infer", json={"type": "call", "function_calls": []})
    result = await client.infer([{"name": "x"}], ["ciao"])
    assert result["type"] == "call"
    assert aioclient_mock.mock_calls[0][2] == {"tools": [{"name": "x"}], "turni": ["ciao"]}


async def test_infer_503_is_unavailable(client, aioclient_mock):
    aioclient_mock.post(f"{URL}/v1/infer", status=503, json={"errore": "modello non pronto"})
    with pytest.raises(NeedleUnavailable):
        await client.infer([], ["ciao"])


async def test_infer_500_is_unavailable(client, aioclient_mock):
    aioclient_mock.post(f"{URL}/v1/infer", status=500, json={"errore": "boom"})
    with pytest.raises(NeedleUnavailable):
        await client.infer([], ["ciao"])


async def test_infer_400_is_bad_request(client, aioclient_mock):
    aioclient_mock.post(f"{URL}/v1/infer", status=400, json={"errore": "turni"})
    with pytest.raises(NeedleBadRequest):
        await client.infer([], ["ciao"])


async def test_infer_timeout_is_unavailable(client, aioclient_mock):
    aioclient_mock.post(f"{URL}/v1/infer", exc=TimeoutError())
    with pytest.raises(NeedleUnavailable):
        await client.infer([], ["ciao"])


async def test_infer_connection_error_is_unavailable(client, aioclient_mock):
    aioclient_mock.post(f"{URL}/v1/infer", exc=aiohttp.ClientConnectionError())
    with pytest.raises(NeedleUnavailable):
        await client.infer([], ["ciao"])
