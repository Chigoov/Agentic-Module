"""Verification workflow — legal transition table for source states.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §9 — source state machine.
  * WORKFLOW.md — verification is a stage producing validated artifacts.

This module encodes *which* source-state transitions are legal, keeping the
state machine knowledge in one place instead of scattering ad-hoc checks across
the engine. The engine produces a recommended state; this flow validates and
applies it to the :class:`~src.schemas.source.Source`, raising a structured error
on an illegal transition.
"""

from __future__ import annotations

from src.core.errors import StateTransitionError
from src.schemas.source import Source, SourceState

__all__ = ["apply_verification_result", "LEGAL_TRANSITIONS"]


#: Mapping of current state → permitted next states after verification.
#: ``None`` means "any non-terminal state" (the initial DISCOVERED → verified
#: states are the common path).
LEGAL_TRANSITIONS: dict[SourceState, frozenset[SourceState] | None] = {
    SourceState.DISCOVERED: None,
    SourceState.POP_VERIFIED: frozenset({
        SourceState.METADATA_VERIFIED,
        SourceState.DOI_VERIFIED,
        SourceState.CONDITIONAL,
        SourceState.NEEDS_HUMAN_REVIEW,
        SourceState.REJECTED,
    }),
    SourceState.METADATA_VERIFIED: frozenset({
        SourceState.DOI_VERIFIED,
        SourceState.PUBLISHER_VERIFIED,
        SourceState.CONDITIONAL,
        SourceState.NEEDS_HUMAN_REVIEW,
        SourceState.REJECTED,
    }),
    SourceState.DOI_VERIFIED: frozenset({
        SourceState.PUBLISHER_VERIFIED,
        SourceState.FULLTEXT_RETRIEVED,
        SourceState.CONDITIONAL,
        SourceState.NEEDS_HUMAN_REVIEW,
        SourceState.REJECTED,
    }),
    SourceState.PUBLISHER_VERIFIED: frozenset({
        SourceState.FULLTEXT_RETRIEVED,
        SourceState.APPROVED,
        SourceState.CONDITIONAL,
        SourceState.NEEDS_HUMAN_REVIEW,
        SourceState.REJECTED,
    }),
    SourceState.FULLTEXT_RETRIEVED: frozenset({
        SourceState.EVIDENCE_EXTRACTED,
        SourceState.APPROVED,
        SourceState.CONDITIONAL,
        SourceState.NEEDS_HUMAN_REVIEW,
        SourceState.REJECTED,
    }),
    SourceState.EVIDENCE_EXTRACTED: frozenset({
        SourceState.CLAIM_SUPPORTED,
        SourceState.APPROVED,
        SourceState.CONDITIONAL,
        SourceState.NEEDS_HUMAN_REVIEW,
        SourceState.REJECTED,
    }),
    SourceState.CLAIM_SUPPORTED: frozenset({SourceState.APPROVED}),
    SourceState.APPROVED: frozenset(),
    # Non-success states may be re-evaluated or escalated.
    SourceState.CONDITIONAL: frozenset({
        SourceState.METADATA_VERIFIED,
        SourceState.DOI_VERIFIED,
        SourceState.APPROVED,
        SourceState.NEEDS_HUMAN_REVIEW,
        SourceState.REJECTED,
    }),
    SourceState.NEEDS_HUMAN_REVIEW: frozenset({
        SourceState.APPROVED,
        SourceState.REJECTED,
        SourceState.CONDITIONAL,
    }),
    SourceState.REJECTED: frozenset(),
}


def is_legal_transition(current: SourceState, proposed: SourceState) -> bool:
    """Return ``True`` when ``current → proposed`` is permitted."""
    if current is proposed:
        return False
    permitted = LEGAL_TRANSITIONS.get(current)
    if permitted is None:
        # DISCOVERED accepts any non-terminal move; reject terminal resets.
        return proposed not in {SourceState.APPROVED, SourceState.REJECTED}
    return proposed in permitted


def apply_verification_result(
    source: Source,
    recommended_state: SourceState,
    *,
    reason: str,
    actor: str = "verification_engine",
) -> SourceState:
    """Apply a recommended state to ``source``, enforcing legal transitions.

    Returns the (possibly unchanged) resulting state. Raises
    :class:`~src.core.errors.StateTransitionError` when the move is illegal.
    """
    if not is_legal_transition(source.state, recommended_state):
        raise StateTransitionError(
            f"Illegal source transition {source.state} -> {recommended_state}",
            source_id=source.id,
            state=str(source.state),
        )
    source.transition_to(recommended_state, reason=reason, actor=actor)
    return source.state
