"""Claim registry schema.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §14 — claim registry minimum fields.
  * 00_MASTER_INSTRUCTION.md §19 — evidence strength rule.
  * AGENT_CONSTITUTION.md §6–§10 — evidence integrity.
  * AGENT_CONSTITUTION.md §29 — unsupported important claims must be revised,
    removed, or escalated.

A :class:`Claim` is a factual assertion the document intends to make. It starts
unsupported and only becomes citable after evidence is attached and classified.
The writer works from approved claims (SYSTEM_RULES.md §E.31), so this registry
is the boundary that prevents fabricated content from reaching the draft.
"""

from __future__ import annotations

from enum import IntEnum, StrEnum

from pydantic import Field

from src.core.errors import StateTransitionError
from src.schemas.base import BaseRecord

__all__ = [
    "ClaimImportance",
    "ClaimStatus",
    "SupportLevel",
    "Claim",
    "MIN_CONFIDENCE",
    "MAX_CONFIDENCE",
]

MIN_CONFIDENCE = 0.0
MAX_CONFIDENCE = 1.0


class ClaimImportance(IntEnum):
    """How consequential the claim is for the document's argument.

    An ``IntEnum`` so that thresholds can be expressed as comparisons, e.g.
    ``claim.importance >= ClaimImportance.HIGH``.
    """

    #: Incidental phrasing; failure to support it does not damage the argument.
    LOW = 1
    #: Ordinary supporting statement.
    MEDIUM = 2
    #: Load-bearing statement; must be traceable (AGENT_CONSTITUTION.md §7).
    HIGH = 3
    #: Central thesis or a claim with real-world consequences.
    CRITICAL = 4


class ClaimStatus(StrEnum):
    """Lifecycle of a claim inside the evidence-control pipeline."""

    #: Registered, no evidence attached yet.
    PROPOSED = "PROPOSED"
    #: Discovery/extraction is in progress.
    INVESTIGATING = "INVESTIGATING"
    #: Evidence attached and sufficient for the claim as worded.
    SUPPORTED = "SUPPORTED"
    #: Evidence attached but only partially supports the claim as worded;
    #: the wording must be qualified (00_MASTER_INSTRUCTION.md §19).
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    #: Evidence exists on both sides and the conflict is material
    #: (AGENT_CONSTITUTION.md §14 — conflict must not be hidden).
    CONFLICTED = "CONFLICTED"
    #: Searched and extracted, but no adequate evidence found.
    #: Preferred over fabrication (AGENT_CONSTITUTION.md §30).
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    #: Evidence contradicts the claim; it must not be written as stated.
    REFUTED = "REFUTED"
    #: Escalated to the user (WORKFLOW.md §3).
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"
    #: Deliberately dropped from the document.
    WITHDRAWN = "WITHDRAWN"


class SupportLevel(StrEnum):
    """Aggregate verdict on how well the collected evidence carries the claim."""

    NONE = "NONE"
    WEAK = "WEAK"
    MODERATE = "MODERATE"
    STRONG = "STRONG"


#: Statuses in which WriterAgent may use the claim in prose.
WRITABLE_STATUSES: frozenset[ClaimStatus] = frozenset(
    {ClaimStatus.SUPPORTED, ClaimStatus.PARTIALLY_SUPPORTED, ClaimStatus.CONFLICTED}
)


class Claim(BaseRecord):
    """A factual assertion together with its evidential status.

    Attributes
    ----------
    claim_text:
        The assertion as it is intended to appear (or its normalized form).
    importance:
        Consequence of the claim for the argument; drives evidence requirements.
    evidence_required:
        Whether traceable evidence is mandatory. Defaults from importance.
    supporting_sources:
        IDs of approved :class:`~src.schemas.source.Source` records.
    supporting_evidence:
        IDs of :class:`~src.schemas.evidence.Evidence` records that support it.
    contradicting_evidence:
        IDs of evidence records that contradict it; never silently dropped.
    support_level:
        Aggregate verdict produced by ClaimVerificationAgent.
    confidence:
        Calibrated confidence in ``[0.0, 1.0]``.
    status:
        Position in the claim lifecycle.
    required_source_count:
        Minimum distinct approved sources required before the claim may be
        marked supported (SYSTEM_RULES.md §C.20, AGENT_CONSTITUTION.md §17).
    qualifier:
        Hedging that must be preserved in prose, e.g. "in a single cohort study".
    section_hint:
        Where the claim is expected to be used in the document.
    """

    id_prefix: str = Field(default="clm", exclude=True, repr=False)

    claim_text: str = Field(min_length=1)
    importance: ClaimImportance = ClaimImportance.MEDIUM
    evidence_required: bool | None = None
    supporting_sources: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    support_level: SupportLevel = SupportLevel.NONE
    confidence: float = Field(default=0.0, ge=MIN_CONFIDENCE, le=MAX_CONFIDENCE)
    status: ClaimStatus = ClaimStatus.PROPOSED
    required_source_count: int = Field(default=1, ge=1)
    qualifier: str | None = None
    section_hint: str | None = None

    def model_post_init(self, _context: object) -> None:
        super().model_post_init(_context)
        # Evidence is mandatory for consequential claims unless explicitly set.
        if self.evidence_required is None:
            object.__setattr__(
                self, "evidence_required", self.importance >= ClaimImportance.HIGH
            )

    # ------------------------------------------------------------------ views
    @property
    def is_important(self) -> bool:
        """Important claims must be auditable (SYSTEM_RULES.md §F.38)."""
        return self.importance >= ClaimImportance.HIGH

    @property
    def has_conflict(self) -> bool:
        return bool(self.supporting_evidence) and bool(self.contradicting_evidence)

    @property
    def is_writable(self) -> bool:
        """Whether WriterAgent may use this claim.

        A claim that requires evidence but has none is never writable, no matter
        what status it carries.
        """
        if self.status not in WRITABLE_STATUSES:
            return False
        if self.evidence_required and not self.supporting_evidence:
            return False
        return True

    def unmet_source_requirement(self) -> int:
        """How many additional distinct approved sources are still needed."""
        return max(0, self.required_source_count - len(set(self.supporting_sources)))

    # -------------------------------------------------------------- mutation
    def attach_support(self, *, evidence_id: str, source_id: str | None = None) -> None:
        """Attach supporting evidence (and its source) without duplicates."""
        if evidence_id not in self.supporting_evidence:
            self.supporting_evidence.append(evidence_id)
        if source_id and source_id not in self.supporting_sources:
            self.supporting_sources.append(source_id)
        self.touch()

    def attach_contradiction(self, *, evidence_id: str, source_id: str | None = None) -> None:
        """Attach contradicting evidence. Conflicts are recorded, never hidden."""
        if evidence_id not in self.contradicting_evidence:
            self.contradicting_evidence.append(evidence_id)
        if source_id and source_id not in self.supporting_sources:
            # The source is still cited: it documents the disagreement.
            self.supporting_sources.append(source_id)
        self.touch()

    def transition_to(
        self,
        new_status: ClaimStatus,
        *,
        reason: str,
        actor: str | None = None,
        support_level: SupportLevel | None = None,
        confidence: float | None = None,
    ) -> None:
        """Move the claim to ``new_status`` with an audited reason.

        Guards the two invariants that matter most:
        a claim requiring evidence cannot become SUPPORTED without evidence, and
        a claim with material contradiction cannot be quietly marked SUPPORTED.
        """
        old_status = self.status
        if old_status == new_status:
            raise StateTransitionError(
                f"Claim {self.id} is already in status {old_status}",
                claim_id=self.id,
                status=str(old_status),
            )
        if new_status is ClaimStatus.SUPPORTED:
            if self.evidence_required and not self.supporting_evidence:
                raise StateTransitionError(
                    "Cannot mark a claim SUPPORTED without supporting evidence",
                    claim_id=self.id,
                    importance=int(self.importance),
                )
            if self.contradicting_evidence:
                raise StateTransitionError(
                    "Claim has contradicting evidence; use CONFLICTED and disclose it",
                    claim_id=self.id,
                    contradicting=len(self.contradicting_evidence),
                )
        self.record_transition(
            from_state=str(old_status), to_state=str(new_status), reason=reason, actor=actor
        )
        self.status = new_status
        if support_level is not None:
            self.support_level = support_level
        if confidence is not None:
            self.confidence = confidence

    def mark_insufficient(self, *, reason: str) -> None:
        """Record that adequate evidence could not be found.

        AGENT_CONSTITUTION.md §30: prefer "insufficient evidence" over fabrication.
        """
        self.transition_to(
            ClaimStatus.INSUFFICIENT_EVIDENCE,
            reason=reason,
            actor="claim_verification_agent",
            support_level=SupportLevel.NONE,
        )

    def request_review(self, *, reason: str) -> None:
        """Escalate the claim to the user (WORKFLOW.md §3)."""
        self.transition_to(
            ClaimStatus.NEEDS_HUMAN_REVIEW, reason=reason, actor="system"
        )
