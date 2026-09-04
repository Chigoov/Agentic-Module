"""Source state schema.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §9 — source state machine.
  * 00_MASTER_INSTRUCTION.md §10 — validation level C.
  * AGENT_CONSTITUTION.md §1–§5 — source integrity rules.

A :class:`Source` is a candidate or verified bibliographic record. Discovery
produces candidates; verification advances them through states until they reach
APPROVED and are safe for citation. Every important claim must cite only
approved sources (SYSTEM_RULES.md §D.40).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from src.core.errors import StateTransitionError
from src.schemas.base import BaseRecord

__all__ = [
    "SourceState",
    "SourceType",
    "Source",
    "is_verified",
    "is_approved",
]


class SourceState(StrEnum):
    """Verification lifecycle from 00_MASTER_INSTRUCTION.md §9."""

    DISCOVERED = "DISCOVERED"
    POP_VERIFIED = "POP_VERIFIED"
    METADATA_VERIFIED = "METADATA_VERIFIED"
    DOI_VERIFIED = "DOI_VERIFIED"
    PUBLISHER_VERIFIED = "PUBLISHER_VERIFIED"
    FULLTEXT_RETRIEVED = "FULLTEXT_RETRIEVED"
    EVIDENCE_EXTRACTED = "EVIDENCE_EXTRACTED"
    CLAIM_SUPPORTED = "CLAIM_SUPPORTED"
    APPROVED = "APPROVED"

    # Non-success states
    REJECTED = "REJECTED"
    CONDITIONAL = "CONDITIONAL"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


class SourceType(StrEnum):
    """Coarse classification for prioritization and validation rules."""

    JOURNAL_ARTICLE = "JOURNAL_ARTICLE"
    CONFERENCE_PAPER = "CONFERENCE_PAPER"
    BOOK = "BOOK"
    BOOK_CHAPTER = "BOOK_CHAPTER"
    THESIS = "THESIS"
    PREPRINT = "PREPRINT"
    TECHNICAL_REPORT = "TECHNICAL_REPORT"
    WEB_RESOURCE = "WEB_RESOURCE"
    OTHER = "OTHER"


def is_verified(state: SourceState | str) -> bool:
    """Return ``True`` when metadata has been corroborated (validation level ≥2)."""
    verified = {
        SourceState.METADATA_VERIFIED,
        SourceState.DOI_VERIFIED,
        SourceState.PUBLISHER_VERIFIED,
        SourceState.FULLTEXT_RETRIEVED,
        SourceState.EVIDENCE_EXTRACTED,
        SourceState.CLAIM_SUPPORTED,
        SourceState.APPROVED,
    }
    return SourceState(state) in verified


def is_approved(state: SourceState | str) -> bool:
    """Return ``True`` only when the source is safe to cite (validation level C)."""
    return SourceState(state) == SourceState.APPROVED


class Source(BaseRecord):
    """Bibliographic record with verification state.

    Attributes
    ----------
    title:
        Work title (never invented; AGENT_CONSTITUTION.md §3).
    authors:
        Normalized author list, e.g. ``["Smith, J.", "Lee, K."]``.
    year:
        Publication year (integer or None for undated works).
    venue:
        Journal, conference, publisher, or None.
    doi:
        DOI (never invented; AGENT_CONSTITUTION.md §2).
    url:
        Canonical URL when available.
    abstract:
        Retrieved abstract text.
    source_type:
        Coarse classification for prioritization.
    state:
        Current position in the verification lifecycle.
    verification_notes:
        Corroboration evidence and ambiguity notes for human review.
    citation_count:
        Citation count when available (used for ranking).
    retrieval_path:
        Local path or cache key for retrieved full text.
    metadata:
        Additional provider-specific fields preserved for auditability.
    """

    id_prefix: str = Field(default="src", exclude=True, repr=False)

    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    source_type: SourceType = SourceType.OTHER
    state: SourceState = SourceState.DISCOVERED
    verification_notes: list[str] = Field(default_factory=list)
    citation_count: int | None = None
    retrieval_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def transition_to(
        self, new_state: SourceState, *, reason: str, actor: str | None = None
    ) -> None:
        """Transition to ``new_state``, recording the change."""
        old_state = self.state
        if old_state == new_state:
            raise StateTransitionError(
                f"Source {self.id} is already in state {old_state}",
                source_id=self.id,
                state=str(old_state),
            )
        self.record_transition(
            from_state=str(old_state), to_state=str(new_state), reason=reason, actor=actor
        )
        self.state = new_state

    def add_verification_note(self, note: str) -> None:
        """Append a corroboration or ambiguity note."""
        self.verification_notes.append(note)
        self.touch()

    def approve(self, *, reason: str = "Validation level C satisfied") -> None:
        """Mark the source as approved for citation."""
        self.transition_to(SourceState.APPROVED, reason=reason, actor="verification_agent")

    def reject(self, *, reason: str) -> None:
        """Mark the source as rejected (will not be cited)."""
        self.record_error(code="SOURCE_REJECTED", message=reason, recoverable=False)
        self.transition_to(SourceState.REJECTED, reason=reason, actor="verification_agent")

    def request_review(self, *, reason: str) -> None:
        """Escalate to human review per WORKFLOW.md §3."""
        self.transition_to(SourceState.NEEDS_HUMAN_REVIEW, reason=reason, actor="system")

    def is_foundational(self, recent_year_threshold: int) -> bool:
        """Check if this source is old enough to be exempt from recency constraints.

        00_MASTER_INSTRUCTION.md §18: foundational sources are allowed when they
        are necessary for original theories, seminal concepts, or canonical
        measurement instruments.
        """
        if self.year is None:
            return False
        # A source is "foundational candidate" if it predates the threshold by
        # a meaningful margin (≥10 years older than the normal window).
        # The actual determination of whether it *should* be kept is made by
        # ResearchPlannerAgent or VerificationAgent based on domain context.
        return self.year < (recent_year_threshold - 10)
