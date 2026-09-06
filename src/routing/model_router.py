"""Model router and LLM capability definitions (Phase 1 stub).

Specification anchors:
  * ARCHITECTURE.md §6 — ``ModelRouter`` belongs at the provider/routing
    layer, not inside agent business logic or the research-tools layer.
  * config/system.yaml — ``model_routing`` section with provider configs.

The model router is how agents abstract away "which LLM" and instead request
capabilities. The router selects a configured provider/model that satisfies
the requirement.

Capabilities
------------
The enumeration below is the *operational* vocabulary the router dispatches
on (``fast_completion``, ``long_context``, ``structured_output``,
``reasoning``, ``embedding``). ``ARCHITECTURE.md`` §6 lists *conceptual*
capabilities (``PLANNING``, ``RESEARCH``, ``REASONING``, ``WRITING``,
``AUDITING``). These are bridged through ``config.model_routing.capability_map``
(conceptual → operational), so the two vocabularies stay coherent without
breaking this contract.

Phase 1 creates the capability vocabulary and the interface. Phase 2 wires
real providers (Claude, GPT, Gemini) once API keys are configured.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any, ClassVar

from pydantic import Field

from src.core.config import get_config
from src.core.paths import get_paths
from src.core.status import IntegrationStatus
from src.routing.telemetry import record_model_telemetry
from src.tools.base import BaseTool, ToolRequest, ToolResponse

__all__ = [
    "ModelCapability",
    "ModelRequest",
    "ModelResponse",
    "ModelRouterTool",
    "resolve_model_for_capability",
]


class ModelCapability(StrEnum):
    """LLM capabilities the system needs.

    The router maps each capability to a configured provider/model in
    ``config/system.yaml``.
    """

    #: Fast, cheap completion for simple transformations.
    FAST_COMPLETION = "fast_completion"
    #: Extended-context window for long-document reasoning.
    LONG_CONTEXT = "long_context"
    #: Structured output with schema validation (JSON mode or similar).
    STRUCTURED_OUTPUT = "structured_output"
    #: High-quality reasoning for complex multi-step decisions.
    REASONING = "reasoning"
    #: Embedding generation for semantic search.
    EMBEDDING = "embedding"


class ModelRequest(ToolRequest):
    """Input contract for an LLM call.

    Attributes
    ----------
    capability:
        Which capability the agent needs.
    prompt:
        User/system prompt text.
    system_prompt:
        Optional system-level instructions.
    output_schema:
        JSON schema when ``capability`` is ``STRUCTURED_OUTPUT``. Named
        ``output_schema`` rather than ``schema`` because ``schema`` shadows a
        reserved attribute on :class:`pydantic.BaseModel`.
    temperature:
        Sampling temperature. Lower = more deterministic.
    max_tokens:
        Maximum completion length.
    """

    capability: ModelCapability
    prompt: str = Field(min_length=1)
    system_prompt: str | None = None
    output_schema: dict[str, Any] | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1)


class ModelResponse(ToolResponse):
    """Output contract for an LLM call.

    Attributes
    ----------
    completion:
        The generated text or structured output.
    model_used:
        Which provider/model actually served the request.
    tokens_used:
        Total token count (prompt + completion).
    finish_reason:
        Why the generation stopped (stop, length, error).
    """

    completion: str | dict[str, Any] = ""
    model_used: str = ""
    tokens_used: int = 0
    finish_reason: str = ""


class ModelRouterTool(BaseTool[ModelRequest, ModelResponse]):
    """Model router that dispatches LLM calls by capability.

    Current implementation:
        Resolves configured capability mappings and fails explicitly when the
        provider client is not present yet. Without provider credentials it
        remains PENDING_CONFIGURATION.

    Notes
    -----
    A concrete provider client still needs to:
    1. Read ``config.model_routing`` to find which provider serves the
       requested capability.
    2. Check that the provider's API key is present and status is not DISABLED.
    3. Construct a provider-specific request (OpenAI, Anthropic, Google format).
    4. Invoke the provider client, applying retries and backoff.
    5. Return the unified :class:`ModelResponse` contract.
    """

    response_model: ClassVar[type[ToolResponse]] = ModelResponse
    tool_name: ClassVar[str] = "model_router"

    def status(self) -> IntegrationStatus:
        """Report the configured status, never claiming more than is proven.

        The declared ``config.model_routing.status`` is the ceiling, but it is
        downgraded to ``PENDING_CONFIGURATION`` whenever the prerequisites for
        actually calling a model are absent (no provider selected, no capability
        map, or no API key). This keeps SYSTEM_RULES.md §H.47-49 enforceable:
        an integration cannot be reported as working just because a YAML file
        says so.
        """
        routing = get_config().model_routing

        declared = routing.status
        if declared is IntegrationStatus.DISABLED:
            return IntegrationStatus.DISABLED

        if not routing.provider or not routing.capability_map or (routing.api_key_env and not routing.api_key):
            return IntegrationStatus.PENDING_CONFIGURATION

        return declared

    def _execute(self, request: ModelRequest) -> ModelResponse:
        """Resolve the configured model and fail safely until a provider client exists."""
        routing = get_config().model_routing
        model = resolve_model_for_capability(request.capability, routing.capability_map)
        system_root = get_paths().system_root
        record_model_telemetry(
            root=system_root,
            path=system_root / "model_telemetry.jsonl",
            capability=request.capability.value,
            status="PROVIDER_CLIENT_NOT_IMPLEMENTED",
            model_used=model or "",
            error_code="PROVIDER_CLIENT_NOT_IMPLEMENTED",
        )
        return ModelResponse.failure(
            error_code="PROVIDER_CLIENT_NOT_IMPLEMENTED",
            error_message="A provider/model is configured, but no provider client is implemented yet",
            model_used=model or "",
        )


def resolve_model_for_capability(capability: ModelCapability, capability_map: dict[str, str]) -> str | None:
    """Return the configured model for a capability, accepting enum names or values."""
    return capability_map.get(capability.value) or capability_map.get(capability.name)
