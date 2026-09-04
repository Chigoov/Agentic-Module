"""Workflows package — state machines and orchestration.

Specification anchor: ARCHITECTURE.md §4 — "The system operates as a state
machine where each stage produces validated artifacts." This package will hold
the workflow orchestrators that move tasks through their lifecycle.

Phase 1 creates only the generic state machine foundation.
"""

from __future__ import annotations

__all__: list[str] = []
