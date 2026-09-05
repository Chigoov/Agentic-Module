"""Synthesis agent — deterministic aggregation of writable findings.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §17 — evidence synthesis in deep research.
  * AGENT_CONSTITUTION.md §14 — conflicts disclosed, never hidden.
  * AGENT_CONSTITUTION.md §26–§30 — synthesis works only from supported claims.

This agent consumes writable claims + their evidence and produces a
:class:`~src.schemas.synthesis.Synthesis`: one finding per writable claim
(aggregated in a stable order), plus an explicit ``open_gaps`` list for claims
that could not be written as stated.

The aggregation is fully deterministic — it reads claim text, support level,
confidence, sources, and conflict flags straight off the verified records. The
natural-language *narrative* synthesis (paraphrasing findings into flowing
prose) is deliberately deferred to the Model Router, which is still
``PENDING_CONFIGURATION``; this agent never invents prose (AGENT_CONSTITUTION §24).
"""

from __future__ import annotations

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence
from src.schemas.project import Project
from src.schemas.synthesis import Synthesis, SynthesisFinding, SynthesisStatus

__all__ = [
    "SynthesisRequest",
    "SynthesisResponse",
    "SynthesisAgent",
]


class SynthesisRequest(AgentRequest):
    """Request: aggregate writable claims + evidence into a synthesis."""

    project: Project
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)


class SynthesisResponse(AgentResponse):
    """The resulting synthesis, plus the count of non-writable gaps."""

    synthesis: Synthesis | None = None
    finding_count: int = 0
    open_gap_count: int = 0


class SynthesisAgent(BaseAgent[SynthesisRequest, SynthesisResponse]):
    """Aggregate supported claims into a deterministic ``Synthesis``."""

    agent_name = "synthesis_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> SynthesisResponse:
        return SynthesisResponse(success=False, error_message=error_message)

    @staticmethod
    def _statement(claim: Claim) -> str:
        """Render a claim's statement, preserving any hedging qualifier (§19)."""
        if claim.qualifier:
            return f"{claim.claim_text} ({claim.qualifier})"
        return claim.claim_text

    def _execute(self, request: SynthesisRequest) -> SynthesisResponse:
        findings: list[SynthesisFinding] = []
        open_gaps: list[str] = []

        # Stable order: claims grouped by section hint (None sorts last) so the
        # synthesis mirrors the document structure rather than insertion order.
        ordered = sorted(
            request.claims,
            key=lambda c: (c.section_hint is not None, c.section_hint or ""),
        )

        for claim in ordered:
            if claim.is_writable:
                findings.append(
                    SynthesisFinding(
                        statement=self._statement(claim),
                        claim_ids=[claim.id],
                        source_ids=list(claim.supporting_sources),
                        support_level=claim.support_level,
                        confidence=claim.confidence,
                        conflicts_disclosed=claim.has_conflict,
                    )
                )
            else:
                open_gaps.append(
                    f"{claim.id}: {claim.status.value} — {claim.claim_text}"
                )

        synthesis = Synthesis(
            project_id=request.project.id,
            findings=findings,
            open_gaps=open_gaps,
            status=SynthesisStatus.COMPLETE,
        )

        response = SynthesisResponse(
            success=True,
            synthesis=synthesis,
            finding_count=len(findings),
            open_gap_count=len(open_gaps),
        )
        response.metadata = {
            "project_id": request.project.id,
            "writable": len([c for c in request.claims if c.is_writable]),
            "total": len(request.claims),
        }
        return response
