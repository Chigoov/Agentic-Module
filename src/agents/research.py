"""Concrete research agents for roadmap Phase 7 & 15.

These agents coordinate research schemas, tools, discovery providers, and retrieval.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from src.agents.base import AgentRequest, AgentResponse, BaseAgent
from src.agents.claim_verification import ClaimVerificationAgent
from src.core.evidence_registry import EvidenceRegistry
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence, EvidenceLocation
from src.schemas.project import Project
from src.schemas.source import Source, SourceState, is_verified
from src.schemas.task import ResearchMode, Task
from src.tools.dedupe import deduplicate
from src.tools.evidence_extractor import EvidenceExtractor
from src.tools.pdf_parser import find_passage_page_location
from src.tools.research_tool import ResearchRequest
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
    "rank_sources",
]


def rank_sources(sources: list[Source]) -> list[Source]:
    """Rank sources deterministically by state, downloadability, citation count, and recency."""
    def sort_key(s: Source) -> tuple[int, int, int, int, str]:
        # 1. State priority (approved=3, verified=2, discovered=1, rejected=0)
        if s.state is SourceState.APPROVED:
            state_score = 3
        elif is_verified(s.state):
            state_score = 2
        elif s.state is SourceState.REJECTED:
            state_score = 0
        else:
            state_score = 1

        # 2. Direct download permitted (open full text is high value for evidence)
        dl_score = 1 if getattr(s, "download_allowed", False) else 0

        # 3. Citation count
        cite_score = s.citation_count if s.citation_count is not None else 0

        # 4. Year
        year_score = s.year if s.year is not None else 0

        # 5. Title for stable sorting
        title_str = (s.title or "").casefold()

        return (state_score, dl_score, cite_score, year_score, title_str)

    return sorted(sources, key=sort_key, reverse=True)


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
    queries: list[str] = Field(default_factory=list)
    providers: list[Any] = Field(default_factory=list)
    max_results_per_query: int = Field(default=5, ge=1, le=50)


class DiscoveryResponse(AgentResponse):
    sources: list[Source] = Field(default_factory=list)
    raw_sources: list[Source] = Field(default_factory=list)


class DiscoveryAgent(BaseAgent[DiscoveryRequest, DiscoveryResponse]):
    agent_name = "discovery_agent"

    def _make_error_response(self, *, error_message: str, **extra: object) -> DiscoveryResponse:
        return DiscoveryResponse(success=False, error_message=error_message)

    def _execute(self, request: DiscoveryRequest) -> DiscoveryResponse:
        all_candidates: list[Source] = list(request.candidates)
        failures = []
        if request.queries and request.providers:
            for query in request.queries:
                for prov in request.providers:
                    try:
                        resp = prov.execute(
                            ResearchRequest(query=query, max_results=request.max_results_per_query)
                        )
                        if resp.success and resp.results:
                            all_candidates.extend(resp.results)
                        if not resp.success:
                            failures.append({"provider": getattr(prov, "name", type(prov).__name__), "query": query,
                                "error": resp.error_message or resp.error_code or "provider search failed"})
                    except Exception as exc:
                        failures.append({"provider": getattr(prov, "name", type(prov).__name__), "query": query, "error": str(exc)})

        # Deduplicate deterministically using the enhanced multi-key deduplicator
        deduped = deduplicate(all_candidates)
        ranked = rank_sources(deduped)
        return DiscoveryResponse(success=bool(all_candidates) or not failures, sources=ranked, raw_sources=all_candidates,
            needs_human_review=bool(failures), error_message="; ".join(f["error"] for f in failures) or None,
            metadata={"deduped": len(all_candidates) - len(ranked), "provider_failures": failures})


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
            from src.tools.source_content import inspect_source
            cached = inspect_source(source, request.project.directory)
            if cached["full_text"]:
                parsed[source.id] = cached["text"]
                continue
            direct_dl = getattr(source, "download_allowed", False)
            response = tool.execute(RetrievalRequest(project=request.project, source=source, direct_download=direct_dl))
            content_proof = source.metadata.get("content_verification")
            if response.success and response.retrieval_method != "abstract" and content_proof and not content_proof["full_text"]:
                failed.append(source.id)
                continue
            if response.success and response.parsed_text:
                parsed[source.id] = response.parsed_text
            elif not response.success:
                # If direct download failed, try regular abstract/url retrieval as fallback
                if direct_dl:
                    fallback_resp = tool.execute(RetrievalRequest(project=request.project, source=source, direct_download=False))
                    if fallback_resp.success and fallback_resp.parsed_text:
                        parsed[source.id] = fallback_resp.parsed_text
                        continue
                failed.append(source.id)
        return RetrievalAgentResponse(sources=request.sources, parsed_text_by_source=parsed, failed=failed, needs_human_review=bool(failed))


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
        # Check if source has page records in metadata (from PDF parsing)
        pdf_pages = request.source.metadata.get("pdf_pages") or []
        location = None
        if pdf_pages:
            loc = find_passage_page_location(request.passage, pdf_pages)
            if loc:
                location = loc

        if location is None:
            location = EvidenceLocation(locator=request.locator)

        result = EvidenceExtractor().extract_verbatim(
            passage=request.passage,
            haystack=request.haystack,
            claim_id=request.claim.id,
            source=request.source,
            location=location,
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
