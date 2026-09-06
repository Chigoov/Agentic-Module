"""Citation and fact audit agents for roadmap Phase 12."""

from __future__ import annotations

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.core.storage import write_json
from src.schemas.claim import Claim
from src.schemas.project import Project, ProjectArtifact
from src.tools.citation_manager import detect_orphan_citations
from src.tools.reference_formatter import citation_key_for
from src.schemas.source import Source

__all__ = [
    "CitationAuditRequest",
    "CitationAuditResponse",
    "CitationAuditAgent",
    "FactAuditRequest",
    "FactAuditResponse",
    "FactAuditAgent",
]


class CitationAuditRequest(AgentRequest):
    project: Project
    draft: str
    sources: list[Source] = Field(default_factory=list)


class CitationAuditResponse(AgentResponse):
    passed: bool = False
    orphan_citations: list[str] = Field(default_factory=list)
    audit_path: str | None = None


class CitationAuditAgent(BaseAgent[CitationAuditRequest, CitationAuditResponse]):
    agent_name = "citation_audit_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> CitationAuditResponse:
        return CitationAuditResponse(success=False, error_message=error_message)

    def _execute(self, request: CitationAuditRequest) -> CitationAuditResponse:
        known = {citation_key_for(source) for source in request.sources}
        orphan = detect_orphan_citations(request.draft, known)
        payload = {"passed": not orphan, "orphan_citations": orphan}
        path = request.project.artifact_path(ProjectArtifact.CITATION_AUDIT)
        write_json(path, payload, root=request.project.directory, overwrite=True)
        return CitationAuditResponse(passed=not orphan, orphan_citations=orphan, audit_path=str(path))


class FactAuditRequest(AgentRequest):
    project: Project
    claims: list[Claim] = Field(default_factory=list)


class FactAuditResponse(AgentResponse):
    passed: bool = False
    unsupported_claims: list[str] = Field(default_factory=list)
    audit_path: str | None = None


class FactAuditAgent(BaseAgent[FactAuditRequest, FactAuditResponse]):
    agent_name = "fact_audit_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> FactAuditResponse:
        return FactAuditResponse(success=False, error_message=error_message)

    def _execute(self, request: FactAuditRequest) -> FactAuditResponse:
        unsupported = [claim.id for claim in request.claims if claim.is_important and not claim.is_writable]
        payload = {"passed": not unsupported, "unsupported_claims": unsupported}
        path = request.project.artifact_path(ProjectArtifact.FACT_AUDIT)
        write_json(path, payload, root=request.project.directory, overwrite=True)
        return FactAuditResponse(passed=not unsupported, unsupported_claims=unsupported, audit_path=str(path))
