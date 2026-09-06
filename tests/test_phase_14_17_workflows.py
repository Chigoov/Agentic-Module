"""Fast tests for roadmap Phases 14-17."""

from __future__ import annotations

from pathlib import Path

from src.core.storage import append_jsonl
from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import Evidence, EvidenceLocation
from src.schemas.outline import Outline, OutlineSection
from src.schemas.project import Project
from src.schemas.source import Source, SourceState
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow
from src.workflows.deep_research import DeepResearchRequest, DeepResearchWorkflow
from src.workflows.optimization import OptimizationRequest, OptimizationWorkflow
from src.workflows.validation import EndToEndValidationRequest, EndToEndValidator


def _project(tmp_path: Path) -> Project:
    path = tmp_path / "project"
    path.mkdir()
    return Project(name="project", workspace="tmp", path=str(path), title="Test")


def _inputs() -> tuple[list[Claim], list[Evidence], list[Source], Outline]:
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
    outline = Outline(title="Test", sections=[OutlineSection(title="Findings", claim_ids=[claim.id])])
    return [claim], [evidence], [source], outline


def test_academic_writing_workflow_writes_draft_and_docx(tmp_path: Path) -> None:
    project = _project(tmp_path)
    claims, evidence, sources, outline = _inputs()
    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=claims,
            evidence=evidence,
            sources=sources,
            outline=outline,
        )
    )
    assert response.success is True
    assert response.stages[-1] == "docx_generation"
    assert (project.directory / "draft.md").is_file()
    assert (project.directory / "final.docx").is_file()


def test_deep_research_workflow_adds_deep_plan(tmp_path: Path) -> None:
    project = _project(tmp_path)
    claims, evidence, sources, outline = _inputs()
    response = DeepResearchWorkflow().execute(
        DeepResearchRequest(
            project=project,
            user_request="attendance intervention",
            claims=claims,
            evidence=evidence,
            sources=sources,
            outline=outline,
        )
    )
    assert response.success is True
    assert response.plan["mode"] == "DEEP_RESEARCH"
    assert response.stages[0] == "deep_plan"
    assert response.docx_path is not None


def test_end_to_end_validator_records_pass_and_fail(tmp_path: Path) -> None:
    project = _project(tmp_path)
    response = EndToEndValidator().execute(
        EndToEndValidationRequest(
            project=project,
            cases={"simple": lambda: True, "broken": lambda: False},
        )
    )
    assert response.success is False
    assert response.passed == ["simple"]
    assert response.failed == ["broken"]
    assert (project.directory / "e2e_validation.json").is_file()


def test_optimization_workflow_summarizes_telemetry(tmp_path: Path) -> None:
    project = _project(tmp_path)
    telemetry = project.directory / "model_telemetry.jsonl"
    append_jsonl(
        telemetry,
        [{"status": "ok", "tokens_used": 10}, {"status": "FAILED", "tokens_used": 5}],
        root=project.directory,
    )
    response = OptimizationWorkflow().execute(
        OptimizationRequest(project=project, telemetry_path=str(telemetry))
    )
    assert response.success is True
    assert response.report["telemetry_records"] == 2
    assert response.report["total_tokens"] == 15
    assert response.report["failed_runs"] == 1
    assert (project.directory / "optimization_report.json").is_file()
