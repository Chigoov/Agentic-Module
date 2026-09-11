"""Regression tests for academic output export bundle (Roadmap R4).

Checks:
  1. Successful runs export cleanly to exports/bundle_<run_id>.zip.
  2. ZIP contains the expected portable internal structure:
       academic_output/final.docx
       academic_output/draft.md
       audits/citation_audit.json
       audits/fact_audit.json
       run/run_summary.json
       run/input_snapshot.json
       ...
  3. Exporting a project with no runs produces a clear error.
  4. Exporting a failed run without --include-failed is rejected.
  5. Exporting a failed run with --include-failed succeeds, containing only snapshots
     and run_summary.json, never invented academic outputs.
  6. ZIP entries do not use absolute paths or drive letters.
  7. CLI subcommand export-bundle works via arguments.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import zipfile

import pytest

from src.runtime.cli import _cmd_export_bundle
from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import Evidence, EvidenceLocation
from src.schemas.outline import Outline, OutlineSection
from src.schemas.project import Project
from src.schemas.source import Source, SourceState
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow
from src.workflows.export_bundle import export_bundle


def _project(tmp_path: Path) -> Project:
    directory = tmp_path / "bundle_project"
    directory.mkdir(parents=True, exist_ok=True)
    return Project(
        name="bundle_project",
        workspace="test_ws",
        path=str(directory),
        title="Export Bundle Test Project",
    )


def _valid_bundle() -> tuple[Claim, Evidence, Source, Outline]:
    source = Source(
        title="Attention is all you need",
        authors=["Vaswani, A."],
        year=2017,
        venue="NeurIPS",
        doi="10.48550/arXiv.1706.03762",
        state=SourceState.APPROVED,
    )
    claim = Claim(
        claim_text="Transformers rely on attention mechanisms.",
        supporting_sources=[source.id],
        supporting_evidence=["evd_b_1"],
        status=ClaimStatus.SUPPORTED,
        support_level=SupportLevel.STRONG,
    )
    evidence = Evidence(
        id="evd_b_1",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="Transformers rely on attention mechanisms.",
        location=EvidenceLocation(locator="abstract"),
        quote_verified=True,
    )
    outline = Outline(
        title="Bundle Test Outline",
        sections=[OutlineSection(title="Introduction", claim_ids=[claim.id])],
    )
    return claim, evidence, source, outline


def test_export_bundle_success_and_portable_structure(tmp_path: Path) -> None:
    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
        )
    )
    assert response.success is True
    assert response.run_id is not None

    result = export_bundle(project.directory)
    assert result["success"] is True
    assert result["run_id"] == response.run_id
    assert "bundle_path" in result

    bundle_path = Path(result["bundle_path"])
    assert bundle_path.exists()
    assert bundle_path.name == f"bundle_{response.run_id}.zip"
    assert bundle_path.parent == project.directory / "exports"

    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = zf.namelist()

        # Check required portable paths
        assert "academic_output/final.docx" in names
        assert "academic_output/draft.md" in names
        assert "audits/citation_audit.json" in names
        assert "audits/fact_audit.json" in names
        assert "run/run_summary.json" in names
        assert "run/input_snapshot.json" in names
        assert "run/sources_snapshot.json" in names
        assert "run/claims_snapshot.json" in names
        assert "run/evidence_snapshot.json" in names
        assert "run/outline_snapshot.json" in names
        assert "run/citation_audit_snapshot.json" in names
        assert "run/fact_audit_snapshot.json" in names

        # Verify no absolute paths or drive letters
        for name in names:
            assert not name.startswith(("/", "\\")), f"Entry {name} has leading slash"
            assert ":" not in name, f"Entry {name} contains drive letter or colon"

        # Verify draft content readable
        draft_content = zf.read("academic_output/draft.md").decode("utf-8")
        assert "Transformers rely on attention mechanisms." in draft_content

        # Verify run_summary content readable
        summary_content = json.loads(zf.read("run/run_summary.json").decode("utf-8"))
        assert summary_content["success"] is True
        assert summary_content["run_id"] == response.run_id


def test_export_bundle_no_runs_fails(tmp_path: Path) -> None:
    project = _project(tmp_path)
    # Project exists but runs/ is not created or empty
    result = export_bundle(project.directory)
    assert result["success"] is False
    assert "no runs" in result["error"].lower()


def test_export_bundle_failed_run_without_include_failed_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()
    forged_claim = claim.model_copy(update={"supporting_evidence": ["evd_nonexistent"]})

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[forged_claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
        )
    )
    assert response.success is False

    # Default export without include_failed must be rejected
    result = export_bundle(project.directory, include_failed=False)
    assert result["success"] is False
    assert "failed" in result["error"].lower()
    assert "--include-failed" in result["error"]


def test_export_bundle_failed_run_with_include_failed_snapshots_only(tmp_path: Path) -> None:
    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()
    forged_claim = claim.model_copy(update={"supporting_evidence": ["evd_nonexistent"]})

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[forged_claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
        )
    )
    assert response.success is False

    result = export_bundle(project.directory, include_failed=True)
    assert result["success"] is True
    bundle_path = Path(result["bundle_path"])
    assert bundle_path.exists()

    with zipfile.ZipFile(bundle_path, "r") as zf:
        names = zf.namelist()
        # Snapshots must be present
        assert "run/run_summary.json" in names
        assert "run/input_snapshot.json" in names
        assert "run/sources_snapshot.json" in names
        assert "run/claims_snapshot.json" in names
        assert "run/evidence_snapshot.json" in names
        assert "run/outline_snapshot.json" in names

        # Academic outputs must NOT be present
        assert "academic_output/final.docx" not in names
        assert "academic_output/draft.md" not in names


def test_cli_cmd_export_bundle_integration(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
        )
    )
    assert response.success is True

    # Call CLI export-bundle with --project flag
    args = argparse.Namespace(
        project="",
        project_flag=str(project.directory),
        input_json=None,
        run_id=None,
        include_failed=False,
    )
    rc = _cmd_export_bundle(args)
    assert rc == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["success"] is True
    assert Path(data["bundle_path"]).exists()
    assert "academic_output/final.docx" in data["included_files"]

    # Call with non-existent project directory
    args_bad = argparse.Namespace(
        project=str(tmp_path / "non_existent"),
        project_flag=None,
        input_json=None,
        run_id=None,
        include_failed=False,
    )
    rc_bad = _cmd_export_bundle(args_bad)
    assert rc_bad == 1
    captured_err = capsys.readouterr().err
    assert "not found" in captured_err.lower()
