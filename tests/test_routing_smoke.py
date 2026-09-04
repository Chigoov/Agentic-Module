"""Smoke tests for the routing layer (R-exec / L4).

These verify the model router contract: the capability vocabulary is present,
an unconfigured router reports ``PENDING_CONFIGURATION``, its ``execute``
returns an honest structured failure, and the routing package imports cleanly.
"""

from __future__ import annotations

from src.core.status import IntegrationStatus
from src.routing.model_router import (
    ModelCapability,
    ModelRequest,
    ModelResponse,
    ModelRouterTool,
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
