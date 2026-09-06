"""Smoke tests for the routing layer (R-exec / L4).

These verify the model router contract: the capability vocabulary is present,
an unconfigured router reports ``PENDING_CONFIGURATION``, its ``execute``
returns an honest structured failure, and the routing package imports cleanly.
"""

from __future__ import annotations

from src.core.status import IntegrationStatus
from src.core.config import reset_config_cache
from src.core.paths import reset_paths_cache
from src.core.storage import read_jsonl
from src.routing.model_router import (
    ModelCapability,
    ModelRequest,
    ModelResponse,
    ModelRouterTool,
    resolve_model_for_capability,
)


def test_model_router_has_capability_vocabulary() -> None:
    """The capability vocabulary drives dispatch and must be non-empty."""
    assert len(ModelCapability) >= 1


def test_model_router_status_is_pending_configuration() -> None:
    """Without configured providers, the router is honest about its state."""
    tool = ModelRouterTool()
    assert tool.status() is IntegrationStatus.PENDING_CONFIGURATION


def test_model_router_execute_returns_structured_failure() -> None:
    """An unconfigured router must not fabricate a response."""
    tool = ModelRouterTool()
    request = ModelRequest(prompt="test", capability=ModelCapability.REASONING)
    response = tool.execute(request)

    assert isinstance(response, ModelResponse)
    assert response.success is False
    assert response.error_code == "PENDING_CONFIGURATION"


def test_routing_package_imports() -> None:
    """Importing the routing package must be side-effect free."""
    import src.routing as routing

    assert hasattr(routing, "model_router")


def test_model_router_requires_configured_api_key(monkeypatch) -> None:
    """A configured provider without its declared key is still pending."""
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__STATUS", "CONFIGURED")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__PROVIDER", "9router")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__API_KEY_ENV", "MISSING_ROUTER_KEY")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__CAPABILITY_MAP", '{"REASONING":"9router:test"}')
    monkeypatch.delenv("MISSING_ROUTER_KEY", raising=False)
    reset_paths_cache()
    reset_config_cache()

    try:
        assert ModelRouterTool().status() is IntegrationStatus.PENDING_CONFIGURATION
    finally:
        reset_config_cache()
        reset_paths_cache()


def test_model_router_configured_failure_is_structured(monkeypatch, tmp_path) -> None:
    """Configured routing fails explicitly until a real provider client exists."""
    monkeypatch.setenv("AUTONOMI_SYSTEM_ROOT", str(tmp_path))
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__STATUS", "CONFIGURED")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__PROVIDER", "9router")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__API_KEY_ENV", "ROUTER_KEY")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__CAPABILITY_MAP", '{"REASONING":"9router:test"}')
    monkeypatch.setenv("ROUTER_KEY", "secret")
    reset_paths_cache()
    reset_config_cache()

    try:
        response = ModelRouterTool().execute(ModelRequest(prompt="test", capability=ModelCapability.REASONING))

        assert response.success is False
        assert response.error_code == "PROVIDER_CLIENT_NOT_IMPLEMENTED"
        assert response.model_used == "9router:test"
        assert read_jsonl(tmp_path / "model_telemetry.jsonl")[0]["error_code"] == "PROVIDER_CLIENT_NOT_IMPLEMENTED"
    finally:
        reset_config_cache()
        reset_paths_cache()


def test_resolve_model_for_capability_accepts_name_or_value() -> None:
    assert resolve_model_for_capability(ModelCapability.REASONING, {"REASONING": "model-a"}) == "model-a"
    assert resolve_model_for_capability(ModelCapability.REASONING, {"reasoning": "model-b"}) == "model-b"
