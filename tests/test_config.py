"""Tests for configuration loading and validation."""

import os

import pytest

from src.core.config import SystemConfig, get_config, reset_config_cache
from src.core.status import IntegrationStatus


def test_get_config_loads_successfully() -> None:
    """Configuration loads without validation errors."""
    config = get_config()
    assert isinstance(config, SystemConfig)
    assert config.system.name == "AUTONOMI AGENTIC ILMIAH"
    assert config.system.spec_version == "1.0"


def test_system_section_defaults() -> None:
    """System section has expected defaults."""
    config = get_config()
    assert config.system.build_phase == 6


def test_logging_section_defaults() -> None:
    """Logging section has sensible defaults."""
    config = get_config()
    assert config.logging.level == "INFO"
    assert config.logging.format == "json"
    assert config.logging.console is True
    assert config.logging.file is True


def test_research_section_defaults() -> None:
    """Research section defaults match specification."""
    config = get_config()
    assert config.research.validation_level == "C"
    assert config.research.default_citation_style == "APA7"
    assert config.research.default_language == "id"
    assert config.research.allow_foundational_sources is True


def test_projects_section_defaults() -> None:
    """Projects section defaults to TUGAS 1 and disallows auto-creation."""
    config = get_config()
    assert config.projects.default_workspace == "TUGAS 1"
    assert config.projects.allow_workspace_creation is False


def test_model_routing_not_configured() -> None:
    """Model routing is PENDING_CONFIGURATION in Phase 1."""
    config = get_config()
    assert config.model_routing.status is IntegrationStatus.PENDING_CONFIGURATION


def test_tools_not_implemented() -> None:
    """All tools are NOT_IMPLEMENTED in Phase 1."""
    config = get_config()
    for tool_name, tool_config in config.tools.items():
        assert tool_config.status is IntegrationStatus.NOT_IMPLEMENTED
        assert tool_config.enabled is False


def test_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment variables can override config values."""
    monkeypatch.setenv("AUTONOMI__LOGGING__LEVEL", "DEBUG")
    reset_config_cache()
    config = get_config()
    assert config.logging.level == "DEBUG"


def test_nested_env_var_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nested config keys work with double-underscore separator."""
    monkeypatch.setenv("AUTONOMI__RESEARCH__DEFAULT_CITATION_STYLE", "APA6")
    reset_config_cache()
    config = get_config()
    assert config.research.default_citation_style == "APA6"
