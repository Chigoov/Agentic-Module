"""Tests for ModelRouter safe failure, capability routing, and OpenAI provider client (Bagian F).

Validates: Requirements 6.2, 6.3, 6.5
"""

from __future__ import annotations

import json

import pytest

from src.core.config import reset_config_cache
from src.core.paths import reset_paths_cache
from src.core.status import IntegrationStatus
from src.core.storage import read_jsonl
from src.routing.model_router import (
    ModelCapability,
    ModelRequest,
    ModelResponse,
    ModelRouterTool,
    resolve_model_for_capability,
)


def test_unconfigured_model_router_safe_failure() -> None:
    """Test unconfigured router fails safely with structured response.

    Validates: Requirements 6.2, 6.3, 6.5
    Verifies:
      - Integration status is PENDING_CONFIGURATION when unconfigured.
      - Execution returns structured failure with error_code="PENDING_CONFIGURATION".
      - Empty completion string (no fabricated text).
      - 0 tokens used.
      - No unhandled exception raised.
    """
    tool = ModelRouterTool()
    assert tool.status() is IntegrationStatus.PENDING_CONFIGURATION

    # Must fail safely without raising unhandled exceptions
    response = tool.execute(ModelRequest(prompt="Say hi", capability=ModelCapability.REASONING))
    assert response.success is False
    assert response.error_code == "PENDING_CONFIGURATION"
    assert response.completion == ""
    assert response.tokens_used == 0
    assert "requires configuration" in response.error_message


def test_conceptual_capability_resolution() -> None:
    """Test conceptual capability resolution to operational models.

    Validates: Requirements 6.2, 6.5
    Verifies:
      - Operational mapping across reasoning, planning, writing, and auditing.
      - Direct operational lookup for REASONING, FAST_COMPLETION, STRUCTURED_OUTPUT.
      - Conceptual fallback mapping:
          PLANNING -> REASONING
          RESEARCH -> REASONING
          WRITING -> FAST_COMPLETION
          AUDITING -> STRUCTURED_OUTPUT
      - Resolution via uppercase enum names.
      - Unmapped capabilities safely resolve to None.
    """
    cap_map = {
        "reasoning": "gpt-4o",
        "fast_completion": "gpt-4o-mini",
        "structured_output": "gpt-4o",
    }

    # Direct operational lookup (reasoning)
    assert resolve_model_for_capability(ModelCapability.REASONING, cap_map) == "gpt-4o"
    assert resolve_model_for_capability(ModelCapability.FAST_COMPLETION, cap_map) == "gpt-4o-mini"
    assert resolve_model_for_capability(ModelCapability.STRUCTURED_OUTPUT, cap_map) == "gpt-4o"

    # Conceptual capabilities fall back to appropriate operational models
    assert resolve_model_for_capability(ModelCapability.PLANNING, cap_map) == "gpt-4o"
    assert resolve_model_for_capability(ModelCapability.WRITING, cap_map) == "gpt-4o-mini"
    assert resolve_model_for_capability(ModelCapability.AUDITING, cap_map) == "gpt-4o"
    assert resolve_model_for_capability(ModelCapability.RESEARCH, cap_map) == "gpt-4o"

    # Mapping with uppercase enum names
    upper_map = {
        "REASONING": "o3-mini",
        "FAST_COMPLETION": "gpt-4o-mini",
        "STRUCTURED_OUTPUT": "o3-mini",
    }
    assert resolve_model_for_capability(ModelCapability.REASONING, upper_map) == "o3-mini"
    assert resolve_model_for_capability(ModelCapability.PLANNING, upper_map) == "o3-mini"
    assert resolve_model_for_capability(ModelCapability.WRITING, upper_map) == "gpt-4o-mini"
    assert resolve_model_for_capability(ModelCapability.AUDITING, upper_map) == "o3-mini"

    # Unmapped capability returns None
    assert resolve_model_for_capability(ModelCapability.EMBEDDING, cap_map) is None


def test_unmapped_capability_safe_failure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Test safe structured failure when a requested capability is not mapped.

    Validates: Requirements 6.2, 6.3, 6.5
    """
    monkeypatch.setenv("AUTONOMI_SYSTEM_ROOT", str(tmp_path))
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__STATUS", "CONFIGURED")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__PROVIDER", "openai")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__API_KEY_ENV", "TEST_OPENAI_KEY")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__CAPABILITY_MAP", '{"reasoning":"gpt-4o"}')
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-mock-key-12345")
    reset_paths_cache()
    reset_config_cache()

    tool = ModelRouterTool()
    assert tool.status() is IntegrationStatus.CONFIGURED

    try:
        response = tool.execute(ModelRequest(prompt="Embed this text", capability=ModelCapability.EMBEDDING))
        assert response.success is False
        assert response.error_code == "CAPABILITY_NOT_MAPPED"
        assert response.completion == ""
        assert response.tokens_used == 0
        assert "No model mapped" in response.error_message

        telemetry = read_jsonl(tmp_path / "model_telemetry.jsonl")
        assert len(telemetry) >= 1
        assert telemetry[-1]["status"] == "CAPABILITY_NOT_MAPPED"
    finally:
        reset_config_cache()
        reset_paths_cache()


def test_unimplemented_provider_safe_failure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Test safe structured failure when provider client is not implemented.

    Validates: Requirements 6.2, 6.3, 6.5
    """
    monkeypatch.setenv("AUTONOMI_SYSTEM_ROOT", str(tmp_path))
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__STATUS", "CONFIGURED")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__PROVIDER", "unsupported_llm_provider")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__API_KEY_ENV", "TEST_OPENAI_KEY")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__CAPABILITY_MAP", '{"reasoning":"custom-model"}')
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-mock-key-12345")
    reset_paths_cache()
    reset_config_cache()

    tool = ModelRouterTool()
    assert tool.status() is IntegrationStatus.CONFIGURED

    try:
        response = tool.execute(ModelRequest(prompt="Analyze this", capability=ModelCapability.REASONING))
        assert response.success is False
        assert response.error_code == "PROVIDER_CLIENT_NOT_IMPLEMENTED"
        assert response.completion == ""
        assert response.tokens_used == 0
        assert "not implemented yet" in response.error_message

        telemetry = read_jsonl(tmp_path / "model_telemetry.jsonl")
        assert len(telemetry) >= 1
        assert telemetry[-1]["status"] == "PROVIDER_CLIENT_NOT_IMPLEMENTED"
    finally:
        reset_config_cache()
        reset_paths_cache()


def test_configured_openai_provider_mock_success(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Test mock successful completion with configured OpenAI client provider.

    Validates: Requirements 6.5
    """
    monkeypatch.setenv("AUTONOMI_SYSTEM_ROOT", str(tmp_path))
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__STATUS", "CONFIGURED")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__PROVIDER", "openai")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__API_KEY_ENV", "TEST_OPENAI_KEY")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__CAPABILITY_MAP", '{"REASONING":"gpt-4o"}')
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-mock-key-12345")
    reset_paths_cache()
    reset_config_cache()

    tool = ModelRouterTool()
    assert tool.status() is IntegrationStatus.CONFIGURED

    mock_resp_body = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "Evidence analysis complete."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"total_tokens": 42},
    }

    class MockHttpResp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def read(self):
            return json.dumps(mock_resp_body).encode("utf-8")

    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: MockHttpResp())

    try:
        response = tool.execute(ModelRequest(prompt="Analyze this", capability=ModelCapability.REASONING))
        assert response.success is True
        assert response.completion == "Evidence analysis complete."
        assert response.model_used == "gpt-4o"
        assert response.tokens_used == 42
        assert response.finish_reason == "stop"

        telemetry = read_jsonl(tmp_path / "model_telemetry.jsonl")
        assert len(telemetry) >= 1
        assert telemetry[-1]["status"] == "SUCCESS"
    finally:
        reset_config_cache()
        reset_paths_cache()


def test_configured_openai_provider_mock_network_failure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Test mock network failure gracefully handled without raising unhandled exception.

    Validates: Requirements 6.2, 6.5
    """
    monkeypatch.setenv("AUTONOMI_SYSTEM_ROOT", str(tmp_path))
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__STATUS", "CONFIGURED")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__PROVIDER", "openai")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__API_KEY_ENV", "TEST_OPENAI_KEY")
    monkeypatch.setenv("AUTONOMI__MODEL_ROUTING__CAPABILITY_MAP", '{"REASONING":"gpt-4o"}')
    monkeypatch.setenv("TEST_OPENAI_KEY", "sk-mock-key-12345")
    reset_paths_cache()
    reset_config_cache()

    tool = ModelRouterTool()

    def mock_fail(req, timeout):
        raise ConnectionResetError("Remote server closed connection")

    monkeypatch.setattr("urllib.request.urlopen", mock_fail)

    try:
        response = tool.execute(ModelRequest(prompt="Analyze this", capability=ModelCapability.REASONING))
        assert response.success is False
        assert response.error_code == "MODEL_CALL_FAILED"
        assert response.completion == ""
        assert response.tokens_used == 0
        assert "ConnectionResetError" in response.error_message

        telemetry = read_jsonl(tmp_path / "model_telemetry.jsonl")
        assert telemetry[-1]["status"] == "MODEL_CALL_FAILED"
    finally:
        reset_config_cache()
        reset_paths_cache()
