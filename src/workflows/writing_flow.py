"""Writing workflow — legal transition tables for outline and draft stages.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §22 — ``outline.json`` and ``draft.md`` artifacts.
  * WORKFLOW.md — writing is a stage producing validated artifacts.

This module encodes *which* writing-stage transitions are legal, mirroring the
pattern in :mod:`src.workflows.verification_flow`. The :class:`Outline` schema
already guards same-status moves; this flow adds the directional rules
(an approved outline may only be reopened for revision, a draft may not regress
into an outline, etc.) so the lifecycle knowledge lives in one place.
"""

from __future__ import annotations

from enum import StrEnum

from src.core.errors import StateTransitionError
from src.schemas.outline import Outline, OutlineStatus

__all__ = [
    "WritingStage",
    "LEGAL_OUTLINE_TRANSITIONS",
    "LEGAL_WRITING_TRANSITIONS",
    "is_legal_outline_transition",
    "is_legal_writing_transition",
    "apply_outline_result",
]


class WritingStage(StrEnum):
    """Coarse lifecycle of the writing pipeline, across outline and draft."""

    OUTLINE_DRAFT = "OUTLINE_DRAFT"
    OUTLINE_APPROVED = "OUTLINE_APPROVED"
    DRAFT_WRITTEN = "DRAFT_WRITTEN"
    DRAFT_AUDITED = "DRAFT_AUDITED"


#: Legal moves for the :class:`~src.schemas.outline.Outline` document status.
LEGAL_OUTLINE_TRANSITIONS: dict[OutlineStatus, frozenset[OutlineStatus]] = {
    OutlineStatus.DRAFT: frozenset({OutlineStatus.APPROVED, OutlineStatus.REVISED}),
    OutlineStatus.REVISED: frozenset({OutlineStatus.APPROVED, OutlineStatus.REVISED}),
    # An approved outline may be reopened, but never silently rolled back to DRAFT.
    OutlineStatus.APPROVED: frozenset({OutlineStatus.REVISED}),
}

#: Legal moves across the whole writing pipeline (outline → draft → audit).
LEGAL_WRITING_TRANSITIONS: dict[WritingStage, frozenset[WritingStage]] = {
    WritingStage.OUTLINE_DRAFT: frozenset({WritingStage.OUTLINE_APPROVED}),
    WritingStage.OUTLINE_APPROVED: frozenset({WritingStage.DRAFT_WRITTEN}),
    WritingStage.DRAFT_WRITTEN: frozenset({WritingStage.DRAFT_AUDITED}),
    WritingStage.DRAFT_AUDITED: frozenset(),
}


def is_legal_outline_transition(current: OutlineStatus, proposed: OutlineStatus) -> bool:
    """Return ``True`` when ``current → proposed`` is a permitted outline move."""
    if current is proposed:
        return False
    return proposed in LEGAL_OUTLINE_TRANSITIONS.get(current, frozenset())


def is_legal_writing_transition(current: WritingStage, proposed: WritingStage) -> bool:
    """Return ``True`` when ``current → proposed`` is a permitted pipeline move."""
    if current is proposed:
        return False
    return proposed in LEGAL_WRITING_TRANSITIONS.get(current, frozenset())


def apply_outline_result(
    outline: Outline,
    new_status: OutlineStatus,
    *,
    reason: str,
    actor: str = "outline_agent",
) -> OutlineStatus:
    """Apply a status to ``outline``, enforcing the legal transition table.

    Returns the resulting status. Raises :class:`StateTransitionError` on an
    illegal move.
    """
    if not is_legal_outline_transition(outline.status, new_status):
        raise StateTransitionError(
            f"Illegal outline transition {outline.status} -> {new_status}",
            outline_id=outline.id,
            status=str(outline.status),
        )
    outline.transition_to(new_status, reason=reason, actor=actor)
    return outline.status
