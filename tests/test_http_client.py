"""Unit tests for the stdlib HTTP client (no real network; monkeypatched)."""

from __future__ import annotations

import json
import urllib.error

import pytest

from src.core.errors import IntegrationError
from src.tools.http_client import HttpClient, build_user_agent


class TestBuildUserAgent:
    def test_with_email(self) -> None:
        assert "mailto:x@y.z" in build_user_agent(contact_email="x@y.z")

    def test_without_email(self) -> None:
        assert "AUTONOMI-AGENTIC-ILMIAH" in build_user_agent(contact_email=None)


class _FakeResponse:
    def __init__(self, status: int, body: bytes, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self.code = status
        self._body = body
        self.headers = headers or {}

    def read(self) -> bytes:
        return self._body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class TestHttpClient:
    def _client(self, *, max_retries: int = 0) -> HttpClient:
        return HttpClient(tool_name="test", max_retries=max_retries, timeout_seconds=5)

    def test_get_json_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        payload = {"ok": True}

        def fake_urlopen(request: object, timeout: int) -> _FakeResponse:
            return _FakeResponse(200, json.dumps(payload).encode("utf-8"), {"Content-Type": "application/json"})

        monkeypatch.setattr("src.tools.http_client.urllib.request.urlopen", fake_urlopen)

        client = self._client()
        result = client.get_json("https://example.org/x", params={"q": "test"})
        assert result.status == 200
        assert result.json() == {"ok": True}

    def test_http_error_raises_structured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_urlopen(request: object, timeout: int) -> _FakeResponse:
            raise urllib.error.HTTPError(
                "https://example.org/x", 404, "Not Found", {}, None  # type: ignore[arg-type]
            )

        monkeypatch.setattr("src.tools.http_client.urllib.request.urlopen", fake_urlopen)

        client = self._client()
        with pytest.raises(IntegrationError) as exc_info:
            client.request("https://example.org/x")
        assert exc_info.value.context.get("error_code") == "HTTP_404"

    def test_network_error_raises_structured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_urlopen(request: object, timeout: int) -> _FakeResponse:
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr("src.tools.http_client.urllib.request.urlopen", fake_urlopen)

        client = self._client()
        with pytest.raises(IntegrationError) as exc_info:
            client.request("https://example.org/x")
        assert exc_info.value.context.get("error_code") == "NETWORK_ERROR"

    def test_invalid_json_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_urlopen(request: object, timeout: int) -> _FakeResponse:
            return _FakeResponse(200, b"not json", {"Content-Type": "application/json"})

        monkeypatch.setattr("src.tools.http_client.urllib.request.urlopen", fake_urlopen)

        client = self._client()
        with pytest.raises(IntegrationError) as exc_info:
            client.get_json("https://example.org/x")
        assert exc_info.value.context.get("error_code") == "INVALID_JSON"

    def test_retries_transient_then_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[int] = []

        def fake_urlopen(request: object, timeout: int) -> _FakeResponse:
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.HTTPError(
                    "https://example.org/x", 429, "Too Many Requests", {}, None  # type: ignore[arg-type]
                )
            return _FakeResponse(200, b"{}", {})

        monkeypatch.setattr("src.tools.http_client.urllib.request.urlopen", fake_urlopen)
        # Avoid real backoff sleeps in the test.
        monkeypatch.setattr("src.tools.http_client.time.sleep", lambda _s: None)

        client = self._client(max_retries=3)
        result = client.request("https://example.org/x")
        assert result.status == 200
        assert len(calls) == 3
