"""Configuration loader.

Sources are merged in increasing order of precedence:

1. built-in defaults (this module);
2. ``SYSTEM_ROOT/config/system.yaml``;
3. an optional local override file (``config/system.local.yaml``);
4. ``SYSTEM_ROOT/.env``;
5. process environment variables prefixed ``AUTONOMI__``.

Environment keys map onto the nested structure with ``__`` as separator, e.g.
``AUTONOMI__LOGGING__LEVEL=DEBUG``.

Every value is validated by Pydantic models, so a malformed configuration fails
at load time rather than in the middle of a research run.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal, Mapping

import yaml
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from src.core.errors import ConfigurationError
from src.core.paths import SystemPaths, get_paths
from src.core.status import IntegrationStatus

__all__ = [
    "ENV_PREFIX",
    "ENV_NESTING_SEPARATOR",
    "SystemSection",
    "LoggingSection",
    "ResearchSection",
    "ProjectsSection",
    "VerificationSection",
    "EvidenceSection",
    "WritingSection",
    "ModelRoutingSection",
    "ToolSection",
    "SystemConfig",
    "load_config",
    "get_config",
    "reset_config_cache",
]

ENV_PREFIX = "AUTONOMI__"
ENV_NESTING_SEPARATOR = "__"

_LOCAL_OVERRIDE_FILENAME = "system.local.yaml"


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #
class _Section(BaseModel):
    """Base for configuration sections: unknown keys are rejected loudly."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class SystemSection(_Section):
    name: str = "AUTONOMI AGENTIC ILMIAH"
    spec_version: str = "1.0"
    build_phase: int = Field(default=1, ge=0)


class LoggingSection(_Section):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    format: Literal["json", "text"] = "json"
    console: bool = True
    file: bool = True
    filename: str = "system.log"
    max_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    backup_count: int = Field(default=5, ge=0)

    @field_validator("level", mode="before")
    @classmethod
    def _upper(cls, value: Any) -> Any:
        return value.upper() if isinstance(value, str) else value

    @field_validator("format", mode="before")
    @classmethod
    def _lower(cls, value: Any) -> Any:
        return value.lower() if isinstance(value, str) else value

    @field_validator("filename")
    @classmethod
    def _bare_filename(cls, value: str) -> str:
        if Path(value).name != value:
            raise ValueError("logging.filename must be a bare filename, not a path")
        return value


class ResearchSection(_Section):
    validation_level: Literal["A", "B", "C"] = "C"
    default_citation_style: str = "APA7"
    default_language: str = "id"
    recent_year_window: int = Field(default=10, ge=1)
    allow_foundational_sources: bool = True
    min_sources_per_important_claim: int = Field(default=2, ge=1)
    max_discovery_retries: int = Field(default=3, ge=0)
    max_verification_retries: int = Field(default=3, ge=0)


class ProjectsSection(_Section):
    default_workspace: str = "TUGAS 1"
    allow_workspace_creation: bool = False


class VerificationSection(_Section):
    """Phase 4 verification-engine tuning.

    ``metadata_match_threshold`` is the Jaccard title-similarity floor below which
    a provider record is not considered to corroborate a candidate (finding: never
    pass a metadata check without real corroboration).
    """

    metadata_match_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    min_metadata_providers: int = Field(default=1, ge=0)
    enabled: bool = True


class EvidenceSection(_Section):
    """Phase 5 evidence/claim-engine tuning.

    ``min_sources_per_important_claim`` mirrors ``ResearchSection`` but is scoped
    to the evidence engine so the claim verdict and the research plan can be
    tuned independently.
    """

    min_sources_per_important_claim: int = Field(default=2, ge=1)
    max_evidence_per_claim: int = Field(default=20, ge=1)
    require_verbatim_quotes: bool = True
    enabled: bool = True


class WritingSection(_Section):
    """Phase 6 writing/synthesis engine tuning.

    ``require_writable_claims`` is the hard gate: the writer only assembles prose
    from claims that are writable (SUPPORTED / PARTIALLY_SUPPORTED / CONFLICTED).
    ``require_citation_backing`` ensures every in-text pointer resolves to a
    verified source (SYSTEM_RULES.md §E.39).
    """

    require_writable_claims: bool = True
    require_citation_backing: bool = True
    enabled: bool = True


class ModelRoutingSection(_Section):
    """Phase 2 configuration. Deliberately inert until a provider is supplied."""

    status: IntegrationStatus = IntegrationStatus.PENDING_CONFIGURATION
    provider: str | None = None
    router_base_url: str | None = None
    api_key_env: str | None = None
    capability_map: dict[str, str] = Field(default_factory=dict)

    @property
    def api_key(self) -> str | None:
        """Read the key from the environment. Secrets are never stored in config."""
        return os.environ.get(self.api_key_env) if self.api_key_env else None


class ToolSection(_Section):
    """Configuration shared by every external tool/adapter."""

    status: IntegrationStatus = IntegrationStatus.NOT_IMPLEMENTED
    enabled: bool = False
    base_url: str | None = None
    api_key_env: str | None = None
    contact_email_env: str | None = None
    executable_path: str | None = None
    install_dir: str | None = None
    search_dirs: list[str] = Field(default_factory=list)
    integration_verified: bool = False
    timeout_seconds: int = Field(default=30, ge=1)

    @property
    def api_key(self) -> str | None:
        return os.environ.get(self.api_key_env) if self.api_key_env else None

    @property
    def contact_email(self) -> str | None:
        return os.environ.get(self.contact_email_env) if self.contact_email_env else None


class SystemConfig(_Section):
    """Fully validated system configuration."""

    system: SystemSection = Field(default_factory=SystemSection)
    logging: LoggingSection = Field(default_factory=LoggingSection)
    research: ResearchSection = Field(default_factory=ResearchSection)
    projects: ProjectsSection = Field(default_factory=ProjectsSection)
    verification: VerificationSection = Field(default_factory=VerificationSection)
    evidence: EvidenceSection = Field(default_factory=EvidenceSection)
    writing: WritingSection = Field(default_factory=WritingSection)
    model_routing: ModelRoutingSection = Field(default_factory=ModelRoutingSection)
    tools: dict[str, ToolSection] = Field(default_factory=dict)

    #: Provenance: which files actually contributed to this configuration.
    sources: tuple[str, ...] = ()

    def tool(self, name: str) -> ToolSection:
        """Return a tool section, defaulting to NOT_IMPLEMENTED when absent.

        An unknown tool is never an implicit success: the default section is
        disabled, so callers must still check the status before invoking it.
        """
        return self.tools.get(name, ToolSection())

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def _read_yaml(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigurationError(f"Cannot read configuration file: {path}", error=str(exc)) from exc
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in {path}", error=str(exc)) from exc
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ConfigurationError(f"Configuration root must be a mapping: {path}")
    return parsed


def _deep_merge(base: dict[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge ``overlay`` into ``base`` without mutating either."""
    merged = dict(base)
    for key, value in overlay.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged


def _coerce_scalar(value: str) -> Any:
    """Interpret an environment string as JSON when possible, else keep the text."""
    text = value.strip()
    lowered = text.lower()
    if lowered in {"null", "none", "~"}:
        return None
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return value


def _env_overlay(environ: Mapping[str, str]) -> dict[str, Any]:
    """Build a nested overlay from ``AUTONOMI__A__B=value`` style variables."""
    overlay: dict[str, Any] = {}
    for raw_key, raw_value in environ.items():
        if not raw_key.startswith(ENV_PREFIX):
            continue
        path = [part for part in raw_key[len(ENV_PREFIX) :].split(ENV_NESTING_SEPARATOR) if part]
        if not path:
            continue
        cursor = overlay
        for part in path[:-1]:
            node = cursor.setdefault(part.lower(), {})
            if not isinstance(node, dict):
                node = {}
                cursor[part.lower()] = node
            cursor = node
        cursor[path[-1].lower()] = _coerce_scalar(raw_value)
    return overlay


def load_config(
    paths: SystemPaths | None = None,
    *,
    overrides: Mapping[str, Any] | None = None,
    use_env: bool = True,
) -> SystemConfig:
    """Load, merge, and validate the system configuration.

    Parameters
    ----------
    paths:
        Resolved system paths; defaults to :func:`src.core.paths.get_paths`.
    overrides:
        Highest-precedence nested overlay, used by tests.
    use_env:
        When ``False``, ``.env`` and ``AUTONOMI__*`` variables are ignored.
    """
    resolved_paths = paths or get_paths()
    data: dict[str, Any] = {}
    sources: list[str] = []

    for candidate in (
        resolved_paths.system_config_file,
        resolved_paths.config_dir / _LOCAL_OVERRIDE_FILENAME,
    ):
        if candidate.is_file():
            data = _deep_merge(data, _read_yaml(candidate))
            sources.append(resolved_paths.relative(candidate))

    if use_env:
        dotenv_path = resolved_paths.dotenv_file
        environ: dict[str, str] = {}
        if dotenv_path.is_file():
            environ.update({k: v for k, v in dotenv_values(dotenv_path).items() if v is not None})
            sources.append(resolved_paths.relative(dotenv_path))
        environ.update(os.environ)
        env_layer = _env_overlay(environ)
        if env_layer:
            data = _deep_merge(data, env_layer)
            sources.append("environment")

    if overrides:
        data = _deep_merge(data, overrides)
        sources.append("overrides")

    data["sources"] = tuple(sources)

    try:
        return SystemConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigurationError(
            "System configuration failed validation",
            errors=exc.errors(include_url=False),
            sources=tuple(sources),
        ) from exc


@lru_cache(maxsize=1)
def _cached_config() -> SystemConfig:
    return load_config()


def get_config() -> SystemConfig:
    """Return the process-wide configuration, loading it on first use."""
    return _cached_config()


def reset_config_cache() -> None:
    """Clear the cached configuration (used by tests and after config edits)."""
    _cached_config.cache_clear()
