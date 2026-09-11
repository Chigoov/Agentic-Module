"""Regression tests for per-run academic audit trail (Roadmap R4).

Checks:
  1. Successful runs produce a timestamped runs/<run_id>/ directory with all 7 snapshots
     (input, sources, claims, evidence, outline, citation audit, fact audit) and run_summary.json.
  2. Failed runs (due to gate failure or output token detection) still produce runs/<run_id>/
     with snapshots and a run_summary.json recording success=False and error_message.
  3. Sensitive values (e.g. monitor tokens or .env secrets) are redacted and never leaked
     into any snapshot file.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import Evidence, EvidenceLocation
from src.schemas.outline import Outline, OutlineSection
from src.schemas.project import Project
from src.schemas.source import Source, SourceState
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow


def _project(tmp_path: Path) -> Project:
    directory = tmp_path / "academic_project"
    directory.mkdir(parents=True, exist_ok=True)
    return Project(
        name="academic_project",
        workspace="test_ws",
        path=str(directory),
        title="Audit Trail Test Project",
    )


def _valid_bundle() -> tuple[Claim, Evidence, Source, Outline]:
    source = Source(
        title="Attention is all you need",
        authors=["Vaswani, A."],
        year=2017,
        state=SourceState.APPROVED,
    )
    claim = Claim(
        claim_text="Transformers rely on attention.",
        supporting_sources=[source.id],
        supporting_evidence=["evd_trail_1"],
        status=ClaimStatus.SUPPORTED,
        support_level=SupportLevel.STRONG,
    )
    evidence = Evidence(
        id="evd_trail_1",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="Transformers rely on attention.",
        location=EvidenceLocation(locator="abstract"),
        quote_verified=True,
    )
    outline = Outline(
        title="Audit Trail Outline",
        sections=[OutlineSection(title="Section 1", claim_ids=[claim.id])],
    )
    return claim, evidence, source, outline


def test_audit_trail_success_creates_runs_and_snapshots(tmp_path: Path) -> None:
    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()

    request = AcademicWritingRequest(
        project=project,
        claims=[claim],
        evidence=[evidence],
        sources=[source],
        outline=outline,
        command="run-academic",
        input_path="input_test.json",
    )

    response = AcademicWritingWorkflow().execute(request)
    assert response.success is True
    assert response.run_id is not None
    assert response.run_dir is not None

    run_dir = Path(response.run_dir)
    assert run_dir.exists()
    assert run_dir.is_dir()
    assert (project.directory / "runs" / response.run_id) == run_dir

    # Required snapshots must exist
    expected_files = [
        "input_snapshot.json",
        "sources_snapshot.json",
        "claims_snapshot.json",
        "evidence_snapshot.json",
        "outline_snapshot.json",
        "citation_audit_snapshot.json",
        "fact_audit_snapshot.json",
        "run_summary.json",
    ]
    for filename in expected_files:
        filepath = run_dir / filename
        assert filepath.exists(), f"Missing required snapshot file: {filename}"
        # Validate that each file parses as valid JSON
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data is not None

    # Validate run_summary.json contents
    summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["run_id"] == response.run_id
    assert summary["success"] is True
    assert summary["command"] == "run-academic"
    assert summary["input_path"] == "input_test.json"
    assert summary["error_message"] is None
    assert summary["draft_path"] is not None and Path(summary["draft_path"]).exists()
    assert summary["docx_path"] is not None and Path(summary["docx_path"]).exists()
    assert summary["citation_audit_path"] is not None
    assert summary["fact_audit_path"] is not None
    assert "started_at" in summary and "finished_at" in summary


def test_audit_trail_failed_gate_creates_run_summary_and_snapshots(tmp_path: Path) -> None:
    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()
    # Forge evidence ID to trigger integrity gate rejection
    forged_claim = claim.model_copy(update={"supporting_evidence": ["evd_nonexistent"]})

    request = AcademicWritingRequest(
        project=project,
        claims=[forged_claim],
        evidence=[evidence],
        sources=[source],
        outline=outline,
        command="run-academic",
        input_path="forged_input.json",
    )

    response = AcademicWritingWorkflow().execute(request)
    assert response.success is False
    assert response.run_id is not None
    assert response.run_dir is not None

    run_dir = Path(response.run_dir)
    assert run_dir.exists()

    # Input snapshots and run_summary.json must still exist
    assert (run_dir / "input_snapshot.json").exists()
    assert (run_dir / "sources_snapshot.json").exists()
    assert (run_dir / "claims_snapshot.json").exists()
    assert (run_dir / "evidence_snapshot.json").exists()
    assert (run_dir / "outline_snapshot.json").exists()
    assert (run_dir / "run_summary.json").exists()

    summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["run_id"] == response.run_id
    assert summary["success"] is False
    assert summary["command"] == "run-academic"
    assert summary["input_path"] == "forged_input.json"
    assert summary["error_message"] is not None
    assert "integrity gate" in summary["error_message"].lower() or "nonexistent" in summary["error_message"].lower()
    assert summary["draft_path"] is None
    assert summary["docx_path"] is None


def test_audit_trail_failed_internal_token_creates_run_summary(tmp_path: Path) -> None:
    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()
    # Add internal token to claim text to trigger output scan failure
    token_claim = claim.model_copy(
        update={"claim_text": "Model analysis revealed turn0search5 token leak."}
    )
    token_evidence = evidence.model_copy(
        update={"evidence_text": "Model analysis revealed turn0search5 token leak."}
    )

    request = AcademicWritingRequest(
        project=project,
        claims=[token_claim],
        evidence=[token_evidence],
        sources=[source],
        outline=outline,
        command="run-academic",
    )

    response = AcademicWritingWorkflow().execute(request)
    assert response.success is False
    assert response.run_id is not None
    assert response.run_dir is not None

    run_dir = Path(response.run_dir)
    assert run_dir.exists()

    summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["success"] is False
    assert summary["error_message"] is not None
    assert "output scan" in summary["error_message"].lower() or "turn0search5" in summary["error_message"].lower()


def test_audit_trail_sanitizes_monitor_token_and_secrets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    secret_token = "secret-token-super-private-998877"
    monkeypatch.setenv("AUTONOMI_API_TOKEN", secret_token)

    project = _project(tmp_path)
    # Inject token into project title to test scrubbing
    project.title = f"Project with secret {secret_token}"
    claim, evidence, source, outline = _valid_bundle()

    request = AcademicWritingRequest(
        project=project,
        claims=[claim],
        evidence=[evidence],
        sources=[source],
        outline=outline,
    )

    response = AcademicWritingWorkflow().execute(request)
    assert response.run_dir is not None
    run_dir = Path(response.run_dir)

    for json_file in run_dir.glob("*.json"):
        text = json_file.read_text(encoding="utf-8")
        assert secret_token not in text, f"Secret leaked in {json_file.name}!"
        if json_file.name == "input_snapshot.json":
            assert "[REDACTED]" in text


def test_cli_cmd_runs_lists_and_inspects(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import argparse
    from src.runtime.cli import _cmd_runs

    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()

    request = AcademicWritingRequest(
        project=project,
        claims=[claim],
        evidence=[evidence],
        sources=[source],
        outline=outline,
    )
    response = AcademicWritingWorkflow().execute(request)
    assert response.success is True

    # 1. Test listing runs
    args_list = argparse.Namespace(project=str(project.directory), input_json=None, run_id=None)
    rc = _cmd_runs(args_list)
    assert rc == 0
    captured = capsys.readouterr().out
    data = json.loads(captured)
    assert data["success"] is True
    assert data["total_runs"] == 1
    assert data["runs"][0]["run_id"] == response.run_id

    # 2. Test inspecting specific run
    args_inspect = argparse.Namespace(project=str(project.directory), input_json=None, run_id=response.run_id)
    rc_inspect = _cmd_runs(args_inspect)
    assert rc_inspect == 0
    captured_inspect = capsys.readouterr().out
    data_inspect = json.loads(captured_inspect)
    assert data_inspect["success"] is True
    assert data_inspect["run"]["run_id"] == response.run_id
    assert data_inspect["run"]["success"] is True


def test_audit_trail_portable_relpaths(tmp_path: Path) -> None:
    """R4: run_summary.json must provide portable relpaths relative to project.directory."""
    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()

    request = AcademicWritingRequest(
        project=project,
        claims=[claim],
        evidence=[evidence],
        sources=[source],
        outline=outline,
    )
    response = AcademicWritingWorkflow().execute(request)
    assert response.success is True
    run_dir = Path(response.run_dir)
    summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))

    # Both absolute and relpath must be populated
    assert summary["draft_path"] is not None and Path(summary["draft_path"]).is_absolute()
    assert summary["docx_path"] is not None and Path(summary["docx_path"]).is_absolute()
    assert summary["citation_audit_path"] is not None and Path(summary["citation_audit_path"]).is_absolute()
    assert summary["fact_audit_path"] is not None and Path(summary["fact_audit_path"]).is_absolute()

    assert summary["draft_relpath"] == "draft.md"
    assert summary["docx_relpath"] == "final.docx"
    assert summary["citation_audit_relpath"] == "citation_audit.json"
    assert summary["fact_audit_relpath"] == "fact_audit.json"


def test_gate_error_clean_ux_without_unhandled_exception(tmp_path: Path) -> None:
    """R4: Integrity gate rejection must return clean response without 'unhandled exception'."""
    project = _project(tmp_path)
    claim, evidence, source, outline = _valid_bundle()
    forged_claim = claim.model_copy(update={"supporting_evidence": ["evd_nonexistent"]})

    request = AcademicWritingRequest(
        project=project,
        claims=[forged_claim],
        evidence=[evidence],
        sources=[source],
        outline=outline,
    )
    response = AcademicWritingWorkflow().execute(request)
    assert response.success is False
    assert response.needs_human_review is True
    assert response.review_prompt is not None
    assert "unhandled exception" not in (response.error_message or "").lower()
    assert "integrity gate" in (response.error_message or "").lower()

    # Final document must not exist
    assert not (project.directory / "final.docx").exists()

    # Audit trail must have run_summary.json with clean error_message
    run_dir = Path(response.run_dir)
    summary = json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["success"] is False
    assert "unhandled exception" not in (summary["error_message"] or "").lower()
    assert summary["draft_relpath"] is None
    assert summary["docx_relpath"] is None


def test_cli_runs_prune_behavior(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """R4: Subcommand 'runs --prune --keep N' retention behavior."""
    import argparse
    from src.runtime.cli import _cmd_runs

    project_dir = tmp_path / "project_with_runs"
    runs_dir = project_dir / "runs"
    runs_dir.mkdir(parents=True)

    # Create 5 dummy run directories with timestamps
    created_runs = []
    for i in range(1, 6):
        run_id = f"run_20260901T00000{i}Z_0000000{i}"
        d = runs_dir / run_id
        d.mkdir()
        summary = {
            "run_id": run_id,
            "started_at": f"2026-09-01T00:00:0{i}.000000+00:00",
            "success": True,
        }
        (d / "run_summary.json").write_text(json.dumps(summary), encoding="utf-8")
        created_runs.append(run_id)

    # 1. Without --prune, nothing is deleted (even if --keep is passed)
    args_no_prune = argparse.Namespace(project=str(project_dir), input_json=None, run_id=None, prune=False, keep=2)
    rc = _cmd_runs(args_no_prune)
    assert rc == 0
    assert len(list(runs_dir.iterdir())) == 5

    # 2. With --prune and --keep 0, command is rejected with exit code 1
    args_keep_zero = argparse.Namespace(project=str(project_dir), input_json=None, run_id=None, prune=True, keep=0)
    rc_zero = _cmd_runs(args_keep_zero)
    assert rc_zero == 1
    err_output = capsys.readouterr().err
    assert "positive integer" in err_output
    assert len(list(runs_dir.iterdir())) == 5

    # 3. With --prune and --keep 2, deletes the 3 oldest runs and keeps the 2 newest runs
    args_prune = argparse.Namespace(project=str(project_dir), input_json=None, run_id=None, prune=True, keep=2)
    rc_prune = _cmd_runs(args_prune)
    assert rc_prune == 0
    captured = capsys.readouterr().out
    prune_res = json.loads(captured)
    assert prune_res["success"] is True
    assert prune_res["total_before"] == 5
    assert prune_res["kept"] == 2
    assert prune_res["deleted"] == 3
    # 3 oldest were run 1, 2, 3
    assert set(prune_res["deleted_run_ids"]) == {created_runs[0], created_runs[1], created_runs[2]}

    remaining = [d.name for d in runs_dir.iterdir() if d.is_dir()]
    assert set(remaining) == {created_runs[3], created_runs[4]}
