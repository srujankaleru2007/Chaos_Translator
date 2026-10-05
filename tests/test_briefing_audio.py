import httpx
import pytest
from dataclasses import replace
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api import routes
from app.main import app


SUMMARY = "The team confirmed the demo deadline and scheduled a rehearsal."


@pytest.fixture
def client():
    return TestClient(app)


def test_missing_text_is_rejected(client):
    response = client.post("/api/v1/briefing/audio", json={})

    assert response.status_code == 422


@pytest.mark.parametrize("text", ["", "   "])
def test_empty_text_is_rejected(client, text):
    response = client.post("/api/v1/briefing/audio", json={"text": text})

    assert response.status_code == 422


def test_missing_api_key_is_an_optional_feature_failure(client):
    with patch("app.api.routes.settings", replace(routes.settings, elevenlabs_api_key="")):
        response = client.post("/api/v1/briefing/audio", json={"text": SUMMARY})

    assert response.status_code == 503
    assert response.json()["detail"] == "Briefing audio is not configured."


def test_success_returns_mp3_and_sends_only_the_summary(client):
    captured = {}

    class MockAsyncClient:
        def __init__(self, **kwargs):
            captured["timeout"] = kwargs["timeout"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, url, *, params, headers, json):
            captured.update(url=url, params=params, headers=headers, body=json)
            return httpx.Response(200, content=b"mock mp3 bytes", request=httpx.Request("POST", url))

    with patch("app.api.routes.settings", replace(routes.settings, elevenlabs_api_key="test-elevenlabs-key")), \
         patch("app.api.routes.httpx.AsyncClient", MockAsyncClient):
        response = client.post("/api/v1/briefing/audio", json={"text": SUMMARY})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/mpeg"
    assert response.content == b"mock mp3 bytes"
    assert captured["body"]["text"] == SUMMARY
    assert captured["body"]["model_id"] == "eleven_flash_v2_5"
    assert "xi-api-key" in captured["headers"]
    assert captured["headers"]["xi-api-key"] == "test-elevenlabs-key"
    assert "conversation" not in captured["body"]


def test_provider_failure_returns_generic_error_without_exposing_provider_body(client):
    class MockAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *args, **kwargs):
            return httpx.Response(
                401,
                json={"detail": "provider response with sensitive info"},
                request=httpx.Request("POST", "https://api.elevenlabs.io/"),
            )

    with patch("app.api.routes.settings", replace(routes.settings, elevenlabs_api_key="test-key")), \
         patch("app.api.routes.httpx.AsyncClient", MockAsyncClient):
        response = client.post("/api/v1/briefing/audio", json={"text": SUMMARY})

    assert response.status_code == 502
    assert response.json()["detail"] == "Briefing audio generation failed."
    assert "sensitive" not in response.text


def test_provider_network_failure_returns_generic_error(client):
    class MockAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def post(self, *args, **kwargs):
            request = httpx.Request("POST", "https://api.elevenlabs.io/")
            raise httpx.ConnectError("network unavailable", request=request)

    with patch("app.api.routes.settings", replace(routes.settings, elevenlabs_api_key="test-key")), \
         patch("app.api.routes.httpx.AsyncClient", MockAsyncClient):
        response = client.post("/api/v1/briefing/audio", json={"text": SUMMARY})

    assert response.status_code == 502
    assert response.json()["detail"] == "Briefing audio is temporarily unavailable."


def test_excessively_long_text_is_rejected(client):
    response = client.post("/api/v1/briefing/audio", json={"text": "x" * 5_001})

    assert response.status_code == 422
