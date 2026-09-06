"""Model routing package.

ARCHITECTURE.md §6: the model router belongs at the provider/routing layer,
NOT inside agent business logic or the research-tools layer. This package
holds the capability vocabulary and the router abstraction that dispatch
LLM calls by capability.

Phase 1 creates the interface (status is PENDING_CONFIGURATION). Phase 2
wires real providers once API keys are configured.
"""

from __future__ import annotations

from src.routing import model_router, telemetry  # noqa: F401

__all__ = ["model_router", "telemetry"]
