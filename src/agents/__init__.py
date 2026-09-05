"""Agents package — reasoning components.

Specification anchor: ARCHITECTURE.md §2 — agents are reasoning, tools are
capabilities. This package holds every autonomous component that makes decisions,
plans multi-step actions, or routes work between tools.
"""

from __future__ import annotations

from src.agents import (  # noqa: F401
    claim_verification,
    outline,
    synthesis,
    writer,
)

__all__: list[str] = [
    "claim_verification",
    "outline",
    "synthesis",
    "writer",
]
