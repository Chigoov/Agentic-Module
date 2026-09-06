"""Deep Research Mode workflow for roadmap Phase 15."""

from __future__ import annotations

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.agents.research import ResearchPlannerAgent, ResearchPlannerRequest, TaskAnalyzerAgent, TaskAnalyzerRequest
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence
from src.schemas.outline import Outline
from src.schemas.project import Project
from src.schemas.source import Source
from src.schemas.task import ResearchMode
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow

__all__ = ["DeepResearchRequest", "DeepResearchResponse", "DeepResearchWorkflow"]


class DeepResearchRequest(AgentRequest):
    project: Project
    user_request: str
    claims: list[Claim] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    outline: Outline | None = None


class DeepResearchResponse(AgentResponse):
    plan: dict[str, object] = Field(default_factory=dict)
    stages: list[str] = Field(default_factory=list)
    draft_path: str | None = None
    docx_path: str | None = None


class DeepResearchWorkflow(BaseAgent[DeepResearchRequest, DeepResearchResponse]):
    agent_name = "deep_research_workflow"

    def _make_error_response(self, *, error_message: str, **extra: object) -> DeepResearchResponse:
        return DeepResearchResponse(success=False, error_message=error_message)

    def _execute(self, request: DeepResearchRequest) -> DeepResearchResponse:
        task = TaskAnalyzerAgent().execute(
            TaskAnalyzerRequest(
                user_request=f"deep research {request.user_request}",
                workspace=request.project.workspace,
            )
        ).task
        task.mode = ResearchMode.DEEP_RESEARCH
        task.project_dir = request.project.path
        plan = ResearchPlannerAgent().execute(ResearchPlannerRequest(task=task)).plan
        plan["queries"] = list(dict.fromkeys([*plan.get("queries", []), request.user_request]))
        plan["mode"] = ResearchMode.DEEP_RESEARCH.value

        academic = AcademicWritingWorkflow().execute(
            AcademicWritingRequest(
                project=request.project,
                claims=request.claims,
                evidence=request.evidence,
                sources=request.sources,
                outline=request.outline,
                generate_docx=True,
            )
        )
        return DeepResearchResponse(
            success=academic.success,
            error_message=academic.error_message,
            plan=plan,
            stages=["deep_plan", *academic.stages],
            draft_path=academic.draft_path,
            docx_path=academic.docx_path,
        )
