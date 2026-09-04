"""Tools and provider adapters.

Specification anchor: ARCHITECTURE.md §2 — tools are capabilities, agents are
reasoning. This package holds every external integration and deterministic
utility the agents can invoke.
"""

from __future__ import annotations

from src.tools import (  # noqa: F401
    crossref,
    dedupe,
    http_client,
    openalex,
    pubmed,
    publish_or_perish,
    research_tool,
    semantic_scholar,
    source_mapper,
)

__all__ = [
    "crossref",
    "dedupe",
    "http_client",
    "openalex",
    "pubmed",
    "publish_or_perish",
    "research_tool",
    "semantic_scholar",
    "source_mapper",
]
