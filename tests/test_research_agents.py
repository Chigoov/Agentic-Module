"""Fast tests for roadmap Phase 7 research agents."""

from __future__ import annotations

from pathlib import Path

from src.agents.research import (
    DiscoveryAgent,
    DiscoveryRequest,
    EvidenceAgent,
    EvidenceAgentRequest,
    ResearchPlannerAgent,
    ResearchPlannerRequest,
    RetrievalAgent,
    RetrievalAgentRequest,
    TaskAnalyzerAgent,
    TaskAnalyzerRequest,
)
from src.schemas.claim import Claim
from src.schemas.project import Project
from src.schemas.source import Source


def _project(tmp_path: Path) -> Project:
    path = tmp_path / "project"
    (path / "source_documents").mkdir(parents=True)
    return Project(name="project", workspace="tmp", path=str(path), title="Test")


def test_task_analyzer_and_planner_create_minimal_plan() -> None:
    analyzed = TaskAnalyzerAgent().execute(
        TaskAnalyzerRequest(user_request="Write academic paper about evidence integrity")
    )
    assert analyzed.success is True
    planned = ResearchPlannerAgent().execute(
        ResearchPlannerRequest(task=analyzed.task, keywords=analyzed.keywords)
    )
    assert planned.plan["citation_style"] == "APA7"
    assert planned.plan["queries"]


def test_discovery_agent_dedupes_sources() -> None:
    source = Source(title="Same Paper", doi="10.1/x")
    response = DiscoveryAgent().execute(DiscoveryRequest(candidates=[source, source]))
    assert len(response.sources) == 1


def test_retrieval_and_evidence_agents_connect(tmp_path: Path) -> None:
    project = _project(tmp_path)
    source = Source(title="Paper", abstract="The program improved attendance.")
    claim = Claim(claim_text="The program improved attendance.")
    retrieved = RetrievalAgent().execute(
        RetrievalAgentRequest(project=project, sources=[source])
    )
    assert retrieved.parsed_text_by_source[source.id] == "The program improved attendance."
    evidence = EvidenceAgent().execute(
        EvidenceAgentRequest(
            project=project,
            claim=claim,
            source=source,
            haystack=retrieved.parsed_text_by_source[source.id],
            passage="The program improved attendance.",
            locator="abstract",
        )
    )
    assert evidence.success is True
    assert evidence.evidence is not None
    assert (project.directory / "evidence.jsonl").is_file()
