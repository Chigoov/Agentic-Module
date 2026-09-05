"""Claim verification agent — orchestrates the evidence-control pipeline.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §19 — evidence strength rule.
  * AGENT_CONSTITUTION.md §6–§10/§14 — evidence integrity, conflicts disclosed.
  * AGENT_CONSTITUTION.md §29–§30 — unsupported claims are revised, removed, or
    escalated; never fabricated.

This is the first *real* :class:`~src.agents.base.BaseAgent` subclass. It closes
the Phase 5 debt ("``evaluate_claim`` is pure logic; the integration into an
agent/runtime is Phase 6") by wiring ``ClaimRegistry`` + ``EvidenceRegistry`` +
``evaluate_claim`` into an actual execution path. It is pure logic: no network
I/O and no model — the whole pass is unit-testable offline.

For each claim the agent:
  1. collects the evidence attached to that claim from the registry;
  2. runs the deterministic :func:`~src.workflows.evidence_flow.evaluate_claim`;
  3. syncs the claim's supporting/contradicting bookkeeping from that evidence;
  4. applies the verdict (status/support level/confidence) via
     :meth:`Claim.transition_to`, recording an audited reason.
"""

from __future__ import annotations

from collections import Counter

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.core.claim_registry import ClaimRegistry
from src.core.evidence_registry import EvidenceRegistry
from src.schemas.base import SchemaModel
from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import SUPPORTING_RELATIONSHIPS, EvidenceRelationship
from src.schemas.project import Project
from src.workflows.evidence_flow import evaluate_claim

__all__ = [
    "ClaimOutcome",
    "ClaimVerificationRequest",
    "ClaimVerificationResponse",
    "ClaimVerificationAgent",
]


class ClaimOutcome(SchemaModel):
    """Audited result for one claim after evaluation."""

    claim_id: str
    from_status: ClaimStatus
    to_status: ClaimStatus
    support_level: SupportLevel
    confidence: float
    changed: bool
    reason: str


class ClaimVerificationRequest(AgentRequest):
    """Request: verify every claim in one project's registries."""

    project: Project


class ClaimVerificationResponse(AgentResponse):
    """Summary of the verification pass.

    Counts are computed from final claim states, so they are the authoritative
    source for the synthesis/writing stages downstream.
    """

    outcomes: list[ClaimOutcome] = Field(default_factory=list)
    writable: int = 0
    conflicted: int = 0
    insufficient: int = 0
    refuted: int = 0
    escalated: int = 0


class ClaimVerificationAgent(
    BaseAgent[ClaimVerificationRequest, ClaimVerificationResponse]
):
    """Verify and classify every claim in a project, deterministically."""

    agent_name = "claim_verification_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> ClaimVerificationResponse:
        return ClaimVerificationResponse(success=False, error_message=error_message)

    def _sync_claim_evidence(self, claim: Claim, evidence_list: list) -> None:
        """Mirror registry evidence into the claim's support/conflict bookkeeping.

        ``evaluate_claim`` reasons over the passed evidence list, but the claim's
        own ``supporting_evidence``/``contradicting_evidence`` lists are what the
        transition guards and downstream writer read. This keeps them consistent.
        """
        for evidence in evidence_list:
            if evidence.relationship is EvidenceRelationship.CONTRADICTS:
                claim.attach_contradiction(
                    evidence_id=evidence.id, source_id=evidence.source_id
                )
            elif evidence.relationship in SUPPORTING_RELATIONSHIPS:
                claim.attach_support(evidence_id=evidence.id, source_id=evidence.source_id)
            # IRRELEVANT is intentionally ignored.

    def _execute(self, request: ClaimVerificationRequest) -> ClaimVerificationResponse:
        claims_registry = ClaimRegistry.load(request.project)
        evidence_registry = EvidenceRegistry.load(request.project)

        outcomes: list[ClaimOutcome] = []
        for claim in claims_registry.all():
            evidence_list = evidence_registry.for_claim(claim.id)
            self._sync_claim_evidence(claim, evidence_list)

            result = evaluate_claim(claim, evidence_list)
            from_status = claim.status
            changed = from_status is not result.status

            # Support level and confidence are updated unconditionally (they are
            # a verdict, not a guarded transition).
            claim.support_level = result.support_level
            claim.confidence = result.confidence
            if changed:
                claim.transition_to(
                    result.status,
                    reason=result.reason,
                    actor=self.name,
                    support_level=result.support_level,
                    confidence=result.confidence,
                )

            outcomes.append(
                ClaimOutcome(
                    claim_id=claim.id,
                    from_status=from_status,
                    to_status=claim.status,
                    support_level=claim.support_level,
                    confidence=claim.confidence,
                    changed=changed,
                    reason=result.reason,
                )
            )

        claims_registry.save()

        counts = Counter(claim.status for claim in claims_registry.all())
        response = ClaimVerificationResponse(
            success=True,
            outcomes=outcomes,
            writable=len(claims_registry.writable()),
            conflicted=counts.get(ClaimStatus.CONFLICTED, 0),
            insufficient=counts.get(ClaimStatus.INSUFFICIENT_EVIDENCE, 0),
            refuted=counts.get(ClaimStatus.REFUTED, 0),
            escalated=counts.get(ClaimStatus.NEEDS_HUMAN_REVIEW, 0),
        )
        response.metadata = {
            "project_id": request.project.id,
            "evaluated": len(outcomes),
            "changed": sum(1 for o in outcomes if o.changed),
        }
        return response
