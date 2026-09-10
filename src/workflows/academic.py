"""Academic Writing Mode workflow for roadmap Phase 14 & Phase R4 audit trail."""

from __future__ import annotations

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence
from src.schemas.outline import Outline
from src.schemas.project import Project
from src.schemas.source import Source
from src.tools.docx_generator import DocxGenerationRequest, DocxGenerationTool
from src.workflows.audit_trail import AcademicRunAudit
from src.workflows.orchestrator import OrchestratorAgent, OrchestratorRequest

__all__ = ["AcademicWritingRequest", "AcademicWritingResponse", "AcademicWritingWorkflow"]


class AcademicWritingRequest(AgentRequest):
    project: Project
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    outline: Outline | None = None
    generate_docx: bool = True
    command: str | None = "run-academic"
    input_path: str | None = None


class AcademicWritingResponse(AgentResponse):
    stages: list[str] = Field(default_factory=list)
    draft_path: str | None = None
    docx_path: str | None = None
    run_id: str | None = None
    run_dir: str | None = None


class AcademicWritingWorkflow(BaseAgent[AcademicWritingRequest, AcademicWritingResponse]):
    agent_name = "academic_writing_workflow"

    def _make_error_response(self, *, error_message: str, **extra: object) -> AcademicWritingResponse:
        return AcademicWritingResponse(
            success=False,
            error_message=error_message,
            run_id=extra.get("run_id") if isinstance(extra.get("run_id"), str) else None,
            run_dir=extra.get("run_dir") if isinstance(extra.get("run_dir"), str) else None,
        )

    def _execute(self, request: AcademicWritingRequest) -> AcademicWritingResponse:
        audit = AcademicRunAudit.start(
            project=request.project,
            claims=request.claims,
            evidence=request.evidence,
            sources=request.sources,
            outline=request.outline,
            command=request.command or "run-academic",
            input_path=request.input_path,
        )

        try:
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
                audit.finish(
                    success=False,
                    stages=orchestrated.stages,
                    draft_path=orchestrated.draft_path,
                    error_message=orchestrated.error_message,
                )
                return AcademicWritingResponse(
                    success=False,
                    error_message=orchestrated.error_message,
                    stages=orchestrated.stages,
                    draft_path=orchestrated.draft_path,
                    run_id=audit.run_id,
                    run_dir=str(audit.run_dir),
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
                    audit.finish(
                        success=False,
                        stages=stages,
                        draft_path=orchestrated.draft_path,
                        error_message=docx.error_message,
                    )
                    return AcademicWritingResponse(
                        success=False,
                        error_message=docx.error_message,
                        stages=stages,
                        draft_path=orchestrated.draft_path,
                        run_id=audit.run_id,
                        run_dir=str(audit.run_dir),
                    )
                docx_path = docx.docx_path

            audit.finish(
                success=True,
                stages=stages,
                draft_path=orchestrated.draft_path,
                docx_path=docx_path,
            )

            return AcademicWritingResponse(
                stages=stages,
                draft_path=orchestrated.draft_path,
                docx_path=docx_path,
                run_id=audit.run_id,
                run_dir=str(audit.run_dir),
            )
        except Exception as exc:
            audit.finish(
                success=False,
                error_message=str(exc),
            )
            raise
