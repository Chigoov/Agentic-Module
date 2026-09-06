"""Fast tests for roadmap Phase 8 orchestration."""

from __future__ import annotations

from pathlib import Path

from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import Evidence, EvidenceLocation
from src.schemas.outline import Outline, OutlineSection
from src.schemas.project import Project
from src.schemas.source import Source, SourceState
from src.workflows.orchestrator import OrchestratorAgent, OrchestratorRequest


def _project(tmp_path: Path) -> Project:
    path = tmp_path / "project"
    path.mkdir()
    return Project(name="project", workspace="tmp", path=str(path), title="Test")


def test_orchestrator_writes_and_audits_supported_claim(tmp_path: Path) -> None:
    project = _project(tmp_path)
    source = Source(title="Paper", authors=["Smith, J."], year=2024, state=SourceState.APPROVED)
    claim = Claim(
        claim_text="The program improved attendance.",
        supporting_sources=[source.id],
        supporting_evidence=["evd_1"],
        status=ClaimStatus.SUPPORTED,
        support_level=SupportLevel.STRONG,
    )
    evidence = Evidence(
        id="evd_1",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="The program improved attendance.",
        location=EvidenceLocation(locator="abstract"),
        quote_verified=True,
    )
    outline = Outline(
        title="Test",
        sections=[OutlineSection(title="Findings", claim_ids=[claim.id])],
    )
    response = OrchestratorAgent().execute(
        OrchestratorRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
        )
    )
    assert response.success is True
    assert response.stages == ["synthesis", "outline", "writing", "citation_audit", "fact_audit"]
    assert (project.directory / "draft.md").is_file()
    assert (project.directory / "citation_audit.json").is_file()
    assert (project.directory / "fact_audit.json").is_file()
