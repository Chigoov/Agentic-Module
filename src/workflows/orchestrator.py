"""Minimal orchestrator for roadmap Phase 8.

It wires completed stages without owning their business logic.
"""

from __future__ import annotations

from pydantic import Field

from src.agents.audit import CitationAuditAgent, CitationAuditRequest, FactAuditAgent, FactAuditRequest
from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.agents.outline import OutlineAgent, OutlineRequest
from src.agents.synthesis import SynthesisAgent, SynthesisRequest
from src.agents.writer import WriterAgent, WriterRequest
from src.schemas.citation import ReferenceList
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence
from src.schemas.outline import Outline
from src.schemas.project import Project
from src.schemas.source import Source

__all__ = ["OrchestratorRequest", "OrchestratorResponse", "OrchestratorAgent"]


class OrchestratorRequest(AgentRequest):
    project: Project
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    outline: Outline | None = None


class OrchestratorResponse(AgentResponse):
    stages: list[str] = Field(default_factory=list)
    draft: str = ""
    draft_path: str | None = None
    reference_list: ReferenceList | None = None
    citation_audit_passed: bool = False
    fact_audit_passed: bool = False


class OrchestratorAgent(BaseAgent[OrchestratorRequest, OrchestratorResponse]):
    agent_name = "orchestrator_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> OrchestratorResponse:
        return OrchestratorResponse(success=False, error_message=error_message)

    def _execute(self, request: OrchestratorRequest) -> OrchestratorResponse:
        stages: list[str] = []
        synthesis_response = SynthesisAgent().execute(
            SynthesisRequest(project=request.project, claims=request.claims, evidence=request.evidence)
        )
        if not synthesis_response.success or synthesis_response.synthesis is None:
            return OrchestratorResponse(success=False, error_message=synthesis_response.error_message, stages=stages)
        stages.append("synthesis")

        outline = request.outline
        if outline is None:
            outline_response = OutlineAgent().execute(
                OutlineRequest(project=request.project, claims=request.claims, synthesis=synthesis_response.synthesis)
            )
            if not outline_response.success or outline_response.outline is None:
                return OrchestratorResponse(success=False, error_message=outline_response.error_message, stages=stages)
            outline = outline_response.outline
        stages.append("outline")

        writer_response = WriterAgent().execute(
            WriterRequest(
                project=request.project,
                outline=outline,
                claims=request.claims,
                evidence=request.evidence,
                sources=request.sources,
            )
        )
        if not writer_response.success:
            return OrchestratorResponse(success=False, error_message=writer_response.error_message, stages=stages)
        stages.append("writing")

        citation = CitationAuditAgent().execute(
            CitationAuditRequest(project=request.project, draft=writer_response.draft, sources=request.sources)
        )
        fact = FactAuditAgent().execute(FactAuditRequest(project=request.project, claims=request.claims))
        stages.extend(["citation_audit", "fact_audit"])

        return OrchestratorResponse(
            success=citation.passed and fact.passed,
            stages=stages,
            draft=writer_response.draft,
            draft_path=writer_response.draft_path,
            reference_list=writer_response.reference_list,
            citation_audit_passed=citation.passed,
            fact_audit_passed=fact.passed,
            error_message=None if citation.passed and fact.passed else "Audit failed",
        )
