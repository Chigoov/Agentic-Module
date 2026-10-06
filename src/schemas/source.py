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
from src.schemas.evidence import ReadingDepth

__all__ = [
    "SourceState",
    "SourceType",
    "RetrievalStatus",
    "AccessMode",
    "RightsStatus",
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


class RetrievalStatus(StrEnum):
    """Outcome of full-text retrieval for a source."""

    RETRIEVED = "RETRIEVED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"


class AccessMode(StrEnum):
    """Availability and interaction mode for source full text."""

    OPEN_DOWNLOAD = "OPEN_DOWNLOAD"
    READ_ONLINE = "READ_ONLINE"
    BORROW_ONLY = "BORROW_ONLY"
    PREVIEW_ONLY = "PREVIEW_ONLY"
    UNKNOWN = "UNKNOWN"


class RightsStatus(StrEnum):
    """Legal rights and licensing classification for a source."""

    PUBLIC_DOMAIN = "PUBLIC_DOMAIN"
    OPEN_LICENSE = "OPEN_LICENSE"
    PROVIDER_STATED_FREE = "PROVIDER_STATED_FREE"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


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
    volume:
        Volume number (integer or string) when available.
    issue:
        Issue / number (integer or string) when available.
    pages:
        Page range string, e.g. "1269–1287" or "52-64".
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
    reading_depth:
        How deeply the source was read during evidence extraction.
    retrieval_status:
        Outcome of full-text retrieval for the source.
    publisher_verified:
        Whether the source was verified against the publisher's records.
    index_status:
        Academic database indexing status mapping.
    """

    id_prefix: str = Field(default="src", exclude=True, repr=False)
    schema_version: str = "1.1"

    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    venue: str | None = None
    volume: int | str | None = None
    issue: int | str | None = None
    pages: str | None = None
    doi: str | None = None
    url: str | None = None
    abstract: str | None = None
    source_type: SourceType = SourceType.OTHER
    state: SourceState = SourceState.DISCOVERED
    verification_notes: list[str] = Field(default_factory=list)
    citation_count: int | None = None
    retrieval_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    # --- Evidence Intelligence fields (schema v1.1) ---
    reading_depth: ReadingDepth = ReadingDepth.UNAVAILABLE
    retrieval_status: RetrievalStatus = RetrievalStatus.NOT_ATTEMPTED
    publisher_verified: bool = False
    index_status: dict[str, bool] = Field(default_factory=dict)

    # --- Book, Access & Rights fields ---
    publisher: str | None = None
    isbn: str | None = None
    language: str | None = None
    landing_url: str | None = None
    download_urls: list[str] = Field(default_factory=list)
    license: str | None = None
    license_url: str | None = None
    rights_status: RightsStatus = RightsStatus.UNKNOWN
    access_mode: AccessMode = AccessMode.UNKNOWN
    provider: str | None = None
    provider_record_id: str | None = None

    @property
    def download_allowed(self) -> bool:
        """True only if access_mode is OPEN_DOWNLOAD, rights are clear, and download_urls exist."""
        if self.access_mode != AccessMode.OPEN_DOWNLOAD:
            return False
        if self.rights_status not in {
            RightsStatus.PUBLIC_DOMAIN,
            RightsStatus.OPEN_LICENSE,
            RightsStatus.PROVIDER_STATED_FREE,
        }:
            return False
        return bool(self.download_urls)

    def model_dump(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        data = super().model_dump(*args, **kwargs)
        for field_name in (
            "reading_depth",
            "retrieval_status",
            "publisher_verified",
            "index_status",
            "publisher",
            "isbn",
            "language",
            "landing_url",
            "download_urls",
            "license",
            "license_url",
            "rights_status",
            "access_mode",
            "provider",
            "provider_record_id",
        ):
            if field_name not in self.model_fields_set:
                data.pop(field_name, None)
        return data

    def transition_to(
        self, new_state: SourceState, *, reason: str, actor: str | None = None
    ) -> None:
        """Transition to ``new_state``, recording the change."""
        # Guard: NOT_ATTEMPTED blocks FULLTEXT_RETRIEVED
        if (
            new_state == SourceState.FULLTEXT_RETRIEVED
            and self.retrieval_status == RetrievalStatus.NOT_ATTEMPTED
        ):
            raise StateTransitionError(
                f"Source {self.id} cannot advance to FULLTEXT_RETRIEVED "
                "with retrieval_status NOT_ATTEMPTED",
                source_id=self.id,
                state=str(self.state),
            )
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

    def update_reading_depth(
        self, new_depth: ReadingDepth, *, reason: str, actor: str | None = None
    ) -> None:
        """Update reading_depth with history recording."""
        old_depth = self.reading_depth
        self.record_transition(
            from_state=str(old_depth),
            to_state=str(new_depth),
            reason=reason,
            actor=actor,
        )
        self.reading_depth = new_depth

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
