"""Tools and provider adapters.

Specification anchor: ARCHITECTURE.md §2 — tools are capabilities, agents are
reasoning. This package holds every external integration and deterministic
utility the agents can invoke.
"""

from __future__ import annotations

from src.tools import (  # noqa: F401
    citation_manager,
    crossref,
    dedupe,
    docx_generator,
    evidence_extractor,
    http_client,
    openalex,
    pubmed,
    publish_or_perish,
    reference_formatter,
    research_tool,
    retrieval,
    semantic_scholar,
    source_mapper,
    verification_tool,
)

__all__ = [
    "citation_manager",
    "crossref",
    "dedupe",
    "docx_generator",
    "evidence_extractor",
    "http_client",
    "openalex",
    "pubmed",
    "publish_or_perish",
    "reference_formatter",
    "research_tool",
    "retrieval",
    "semantic_scholar",
    "source_mapper",
    "verification_tool",
]
