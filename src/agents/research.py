"""Concrete research agents for roadmap Phase 7.

These agents are thin coordinators around existing schemas, tools, and flows.
They do not hide provider logic and they do not call models.
"""

from __future__ import annotations

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.agents.claim_verification import ClaimVerificationAgent
from src.core.evidence_registry import EvidenceRegistry
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence, EvidenceLocation
from src.schemas.project import Project
from src.schemas.source import Source
from src.schemas.task import ResearchMode, Task
from src.tools.evidence_extractor import EvidenceExtractor
from src.tools.retrieval import RetrievalRequest, RetrievalTool
from src.tools.verification_tool import VerificationEngine
from src.workflows.verification_flow import apply_verification_result

__all__ = [
    "TaskAnalyzerRequest",
    "TaskAnalyzerResponse",
    "TaskAnalyzerAgent",
    "ResearchPlannerRequest",
    "ResearchPlannerResponse",
    "ResearchPlannerAgent",
    "DiscoveryRequest",
    "DiscoveryResponse",
    "DiscoveryAgent",
    "VerificationRequest",
    "VerificationResponse",
    "VerificationAgent",
    "RetrievalAgentRequest",
    "RetrievalAgentResponse",
    "RetrievalAgent",
    "EvidenceAgentRequest",
    "EvidenceAgentResponse",
    "EvidenceAgent",
    "ClaimAgent",
]


class TaskAnalyzerRequest(AgentRequest):
    user_request: str
    workspace: str = "TUGAS 1"


class TaskAnalyzerResponse(AgentResponse):
    task: Task | None = None
    keywords: list[str] = Field(default_factory=list)


class TaskAnalyzerAgent(BaseAgent[TaskAnalyzerRequest, TaskAnalyzerResponse]):
    agent_name = "task_analyzer_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> TaskAnalyzerResponse:
        return TaskAnalyzerResponse(success=False, error_message=error_message)

    def _execute(self, request: TaskAnalyzerRequest) -> TaskAnalyzerResponse:
        text = request.user_request.strip()
        mode = ResearchMode.DEEP_RESEARCH if "deep" in text.lower() else ResearchMode.ACADEMIC_WRITING
        task = Task(user_request=text, mode=mode, workspace=request.workspace, project_dir="")
        words = [w.strip(".,;:()[]").lower() for w in text.split()]
        keywords = [w for w in words if len(w) > 3][:8]
        return TaskAnalyzerResponse(task=task, keywords=keywords)


class ResearchPlannerRequest(AgentRequest):
    task: Task
    keywords: list[str] = Field(default_factory=list)


class ResearchPlannerResponse(AgentResponse):
    plan: dict[str, object] = Field(default_factory=dict)


class ResearchPlannerAgent(BaseAgent[ResearchPlannerRequest, ResearchPlannerResponse]):
    agent_name = "research_planner_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> ResearchPlannerResponse:
        return ResearchPlannerResponse(success=False, error_message=error_message)

    def _execute(self, request: ResearchPlannerRequest) -> ResearchPlannerResponse:
        queries = [" ".join(request.keywords)] if request.keywords else [request.task.user_request]
        return ResearchPlannerResponse(
            plan={
                "mode": request.task.mode.value,
                "queries": queries,
                "min_sources_per_important_claim": 2,
                "citation_style": "APA7",
                "language": "id",
            }
        )


class DiscoveryRequest(AgentRequest):
    candidates: list[Source] = Field(default_factory=list)


class DiscoveryResponse(AgentResponse):
    sources: list[Source] = Field(default_factory=list)


class DiscoveryAgent(BaseAgent[DiscoveryRequest, DiscoveryResponse]):
    agent_name = "discovery_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> DiscoveryResponse:
        return DiscoveryResponse(success=False, error_message=error_message)

    def _execute(self, request: DiscoveryRequest) -> DiscoveryResponse:
        seen: set[tuple[str, str | None]] = set()
        out: list[Source] = []
        for source in request.candidates:
            key = (source.title.casefold(), source.doi.casefold() if source.doi else None)
            if key in seen:
                continue
            seen.add(key)
            out.append(source)
        return DiscoveryResponse(sources=out, metadata={"deduped": len(request.candidates) - len(out)})


class VerificationRequest(AgentRequest):
    sources: list[Source] = Field(default_factory=list)
    engine: object | None = None


class VerificationResponse(AgentResponse):
    sources: list[Source] = Field(default_factory=list)
    reports: list[object] = Field(default_factory=list)


class VerificationAgent(BaseAgent[VerificationRequest, VerificationResponse]):
    agent_name = "verification_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> VerificationResponse:
        return VerificationResponse(success=False, error_message=error_message)

    def _execute(self, request: VerificationRequest) -> VerificationResponse:
        engine = request.engine if isinstance(request.engine, VerificationEngine) else VerificationEngine(providers=[])
        reports: list[object] = []
        for source in request.sources:
            result = engine.verify(source)
            reports.append(result.report)
            try:
                apply_verification_result(source, result.recommended_state, reason="verification agent result", actor=self.name)
            except Exception as exc:  # noqa: BLE001 - keep per-source failure isolated
                source.record_error(code="VERIFICATION_TRANSITION_FAILED", message=str(exc))
        return VerificationResponse(sources=request.sources, reports=reports)


class RetrievalAgentRequest(AgentRequest):
    project: Project
    sources: list[Source] = Field(default_factory=list)
    tool: object | None = None


class RetrievalAgentResponse(AgentResponse):
    sources: list[Source] = Field(default_factory=list)
    parsed_text_by_source: dict[str, str] = Field(default_factory=dict)
    failed: list[str] = Field(default_factory=list)


class RetrievalAgent(BaseAgent[RetrievalAgentRequest, RetrievalAgentResponse]):
    agent_name = "retrieval_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> RetrievalAgentResponse:
        return RetrievalAgentResponse(success=False, error_message=error_message)

    def _execute(self, request: RetrievalAgentRequest) -> RetrievalAgentResponse:
        tool = request.tool if isinstance(request.tool, RetrievalTool) else RetrievalTool()
        parsed: dict[str, str] = {}
        failed: list[str] = []
        for source in request.sources:
            response = tool.execute(RetrievalRequest(project=request.project, source=source))
            if response.success and response.parsed_text:
                parsed[source.id] = response.parsed_text
            elif not response.success:
                failed.append(source.id)
        return RetrievalAgentResponse(sources=request.sources, parsed_text_by_source=parsed, failed=failed)


class EvidenceAgentRequest(AgentRequest):
    project: Project
    claim: Claim
    source: Source
    haystack: str
    passage: str
    locator: str = "retrieved content"


class EvidenceAgentResponse(AgentResponse):
    evidence: Evidence | None = None


class EvidenceAgent(BaseAgent[EvidenceAgentRequest, EvidenceAgentResponse]):
    agent_name = "evidence_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> EvidenceAgentResponse:
        return EvidenceAgentResponse(success=False, error_message=error_message)

    def _execute(self, request: EvidenceAgentRequest) -> EvidenceAgentResponse:
        result = EvidenceExtractor().extract_verbatim(
            passage=request.passage,
            haystack=request.haystack,
            claim_id=request.claim.id,
            source=request.source,
            location=EvidenceLocation(locator=request.locator),
        )
        if not result.found or result.evidence is None:
            return EvidenceAgentResponse(success=False, error_message=result.error)
        registry = EvidenceRegistry.load(request.project)
        registry.add(result.evidence)
        registry.save()
        return EvidenceAgentResponse(evidence=result.evidence)


class ClaimAgent(ClaimVerificationAgent):
    """Phase 7 name for the existing claim-verification execution path."""

    agent_name = "claim_agent"
