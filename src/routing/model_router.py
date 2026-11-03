"""Model router and LLM capability definitions (Phase 1/2 + Bagian F).

Specification anchors:
  * ARCHITECTURE.md §6 — ``ModelRouter`` belongs at the provider/routing
    layer, not inside agent business logic or the research-tools layer.
  * config/system.yaml — ``model_routing`` section with provider configs.
  * Bagian F: Capabilities routing, safe fallback (PENDING_CONFIGURATION),
    never fabricate citations/evidence/DOIs.
"""

from __future__ import annotations

import json
import os
import urllib.request
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

    #: Conceptual capabilities (ARCHITECTURE.md §6)
    PLANNING = "planning"
    RESEARCH = "research"
    WRITING = "writing"
    AUDITING = "auditing"


_CONCEPTUAL_FALLBACK: dict[ModelCapability, ModelCapability] = {
    ModelCapability.PLANNING: ModelCapability.REASONING,
    ModelCapability.RESEARCH: ModelCapability.REASONING,
    ModelCapability.WRITING: ModelCapability.FAST_COMPLETION,
    ModelCapability.AUDITING: ModelCapability.STRUCTURED_OUTPUT,
}


class ModelRequest(ToolRequest):
    """Input contract for an LLM call."""

    capability: ModelCapability
    prompt: str = Field(min_length=1)
    system_prompt: str | None = None
    output_schema: dict[str, Any] | None = None
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=1)


class ModelResponse(ToolResponse):
    """Output contract for an LLM call."""

    completion: str | dict[str, Any] = ""
    model_used: str = ""
    tokens_used: int = 0
    finish_reason: str = ""


class ModelRouterTool(BaseTool[ModelRequest, ModelResponse]):
    """Model router that dispatches LLM calls by capability."""

    response_model: ClassVar[type[ToolResponse]] = ModelResponse
    tool_name: ClassVar[str] = "model_router"

    def status(self) -> IntegrationStatus:
        """Report the configured status, never claiming more than is proven."""
        routing = get_config().model_routing

        declared = routing.status
        if declared is IntegrationStatus.DISABLED:
            return IntegrationStatus.DISABLED

        if not routing.provider or not routing.capability_map or (routing.api_key_env and not routing.api_key):
            return IntegrationStatus.PENDING_CONFIGURATION

        return declared

    def _execute(self, request: ModelRequest) -> ModelResponse:
        """Resolve the configured model and dispatch or fail safely."""
        routing = get_config().model_routing
        model = resolve_model_for_capability(request.capability, routing.capability_map)
        system_root = get_paths().system_root

        if not model:
            record_model_telemetry(
                root=system_root,
                path=system_root / "model_telemetry.jsonl",
                capability=request.capability.value,
                status="CAPABILITY_NOT_MAPPED",
                model_used="",
                error_code="CAPABILITY_NOT_MAPPED",
            )
            return ModelResponse.failure(
                error_code="CAPABILITY_NOT_MAPPED",
                error_message=f"No model mapped for capability '{request.capability.value}'",
                model_used="",
            )

        provider = (routing.provider or "").lower()
        if provider in {"openai", "generic_openai"}:
            return self._call_openai_compatible(request, model, routing)

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
            error_message=f"Provider client for '{routing.provider}' is not implemented yet",
            model_used=model or "",
        )

    def _call_openai_compatible(
        self, request: ModelRequest, model: str, routing: Any
    ) -> ModelResponse:
        system_root = get_paths().system_root
        base_url = (routing.router_base_url or routing.environment_value("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
        url = f"{base_url}/chat/completions"
        api_key = routing.api_key or routing.environment_value("OPENAI_API_KEY") or ""

        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload_dict: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.output_schema and request.capability == ModelCapability.STRUCTURED_OUTPUT:
            payload_dict["response_format"] = {"type": "json_object"}

        body_bytes = json.dumps(payload_dict).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "AutonomiAgenticIlmiah/1.0",
        }
        req = urllib.request.Request(url, data=body_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                choice = (resp_data.get("choices") or [{}])[0]
                message = choice.get("message") or {}
                content = message.get("content") or ""
                finish_reason = choice.get("finish_reason") or "stop"
                tokens_used = (resp_data.get("usage") or {}).get("total_tokens") or 0

                record_model_telemetry(
                    root=system_root,
                    path=system_root / "model_telemetry.jsonl",
                    capability=request.capability.value,
                    status="SUCCESS",
                    model_used=model,
                    tokens_used=tokens_used,
                )
                return ModelResponse(
                    success=True,
                    completion=content,
                    model_used=model,
                    tokens_used=tokens_used,
                    finish_reason=finish_reason,
                )
        except Exception as exc:
            record_model_telemetry(
                root=system_root,
                path=system_root / "model_telemetry.jsonl",
                capability=request.capability.value,
                status="MODEL_CALL_FAILED",
                model_used=model,
                error_code="MODEL_CALL_FAILED",
            )
            return ModelResponse.failure(
                error_code="MODEL_CALL_FAILED",
                error_message=f"Model call to {url} failed: {type(exc).__name__}: {exc}",
                model_used=model,
            )


def resolve_model_for_capability(capability: ModelCapability, capability_map: dict[str, str]) -> str | None:
    """Return the configured model for a capability, accepting enum names, values, or conceptual fallbacks."""
    res = capability_map.get(capability.value) or capability_map.get(capability.name)
    if res:
        return res
    fallback = _CONCEPTUAL_FALLBACK.get(capability)
    if fallback:
        return capability_map.get(fallback.value) or capability_map.get(fallback.name)
    return None
