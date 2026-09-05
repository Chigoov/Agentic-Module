"""Workflows package — state machines and orchestration.

Specification anchor: ARCHITECTURE.md §4 — "The system operates as a state
machine where each stage produces validated artifacts." This package will hold
the workflow orchestrators that move tasks through their lifecycle.

Phase 1 created only the generic ``StateMachine`` ABC, which was removed
during the architecture refactor (finding M3 / A3): it was a premature
abstraction with no concrete subclasses.

Authoritative transition pattern: ``BaseRecord.record_transition`` /
``transition_to`` on the persisted schemas (``Task``, ``Source``, ``Claim``,
``Evidence``). Concrete orchestration workflows that are pure logic (not
persisted schemas) will subclass an orchestrator here in a later phase, once
there is a real need — not as an empty abstraction.
"""

from __future__ import annotations

from src.workflows import evidence_flow, verification_flow, writing_flow  # noqa: F401

__all__: list[str] = ["evidence_flow", "verification_flow", "writing_flow"]
