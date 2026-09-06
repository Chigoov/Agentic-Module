"""Academic Writing Mode workflow for roadmap Phase 14."""

from __future__ import annotations

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence
from src.schemas.outline import Outline
from src.schemas.project import Project
from src.schemas.source import Source
from src.tools.docx_generator import DocxGenerationRequest, DocxGenerationTool
from src.workflows.orchestrator import OrchestratorAgent, OrchestratorRequest

__all__ = ["AcademicWritingRequest", "AcademicWritingResponse", "AcademicWritingWorkflow"]


class AcademicWritingRequest(AgentRequest):
    project: Project
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    outline: Outline | None = None
    generate_docx: bool = True


class AcademicWritingResponse(AgentResponse):
    stages: list[str] = Field(default_factory=list)
    draft_path: str | None = None
    docx_path: str | None = None


class AcademicWritingWorkflow(BaseAgent[AcademicWritingRequest, AcademicWritingResponse]):
    agent_name = "academic_writing_workflow"

    def _make_error_response(self, *, error_message: str, **extra: object) -> AcademicWritingResponse:
        return AcademicWritingResponse(success=False, error_message=error_message)

    def _execute(self, request: AcademicWritingRequest) -> AcademicWritingResponse:
        orchestrated = OrchestratorAgent().execute(
            OrchestratorRequest(
                project=request.project,
                claims=request.claims,
                evidence=request.evidence,
                sources=request.sources,
                outline=request.outline,
            )
        )
        if not orchestrated.success:
            return AcademicWritingResponse(
                success=False,
                error_message=orchestrated.error_message,
                stages=orchestrated.stages,
                draft_path=orchestrated.draft_path,
            )

        stages = list(orchestrated.stages)
        docx_path: str | None = None
        if request.generate_docx:
            docx = DocxGenerationTool().execute(
                DocxGenerationRequest(
                    project=request.project,
                    draft=orchestrated.draft,
                    reference_list=orchestrated.reference_list,
                    citation_audit_passed=orchestrated.citation_audit_passed,
                    fact_audit_passed=orchestrated.fact_audit_passed,
                )
            )
            stages.append("docx_generation")
            if not docx.success:
                return AcademicWritingResponse(
                    success=False,
                    error_message=docx.error_message,
                    stages=stages,
                    draft_path=orchestrated.draft_path,
                )
            docx_path = docx.docx_path

        return AcademicWritingResponse(
            stages=stages,
            draft_path=orchestrated.draft_path,
            docx_path=docx_path,
        )
