"""CLI tests for AI-agent entry points."""

from __future__ import annotations

import json
import pytest
from pathlib import Path
from conftest import fixture_source

from src.runtime.cli import build_parser, main
from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import Evidence, EvidenceLocation
from src.schemas.outline import Outline, OutlineSection
from src.schemas.project import Project
from src.schemas.source import Source, SourceState


@pytest.fixture(autouse=True)
def portable_cli_workspace(tmp_path, monkeypatch):
    from src.core.paths import reset_paths_cache
    from src.core.config import reset_config_cache
    workspace = tmp_path / "workspaces"
    (workspace / "TUGAS 1").mkdir(parents=True)
    monkeypatch.setenv("AUTONOMI_SYSTEM_ROOT", str(Path(__file__).resolve().parents[1]))
    monkeypatch.setenv("AUTONOMI_WORKSPACE_ROOT", str(workspace))
    monkeypatch.setenv("AUTONOMI__LOGGING__FILE", "false")
    reset_paths_cache(); reset_config_cache()
    yield
    reset_paths_cache(); reset_config_cache()


def test_cli_plan_outputs_json(capsys) -> None:
    assert main(["plan", "dampak perceraian orang tua terhadap remaja"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    assert out["plan"]["citation_style"] == "APA7"


def test_cli_check_passes() -> None:
    assert main(["check"]) == 0


def test_cli_monitor_parser_accepts_host_and_port() -> None:
    args = build_parser().parse_args(["monitor", "--host", "127.0.0.1", "--port", "0"])
    assert args.command == "monitor"
    assert args.port == 0


def test_cli_run_academic_writes_outputs(tmp_path: Path, capsys, monkeypatch) -> None:
    class _FakeCliProvider:
        name = "fake_cli"
        def lookup_by_doi(self, doi: str):
            return None
        def lookup_by_bibliographic(self, title: str, authors=None, year=None):
            return Source(title=title, authors=authors or ["Smith, J."], year=year or 2024)

    from src.tools.verification_tool import VerificationEngine
    monkeypatch.setattr(
        "src.runtime.cli.VerificationEngine",
        lambda *a, **kw: VerificationEngine(providers=[_FakeCliProvider()]),
    )

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project = Project(name="project", workspace="tmp", path=str(project_dir), title="Test")
    source = Source(
        title="Paper",
        authors=["Smith, J."],
        year=2024,
        state=SourceState.APPROVED,
        abstract="The program improved attendance.",
    )
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
    review = {
        "claim_id": claim.id,
        "decision": "SUPPORTED",
        "reason": "Empirical evidence directly supports the assertion.",
        "evidence_id": evidence.id,
        "source_id": source.id,
        "evidence_excerpt": evidence.evidence_text,
        "location": "abstract",
        "reviewer": "antigravity_agent",
        "method": "semantic_evaluation",
    }
    fixture_source(source, evidence.evidence_text, tmp_path / "source_fixture")
    payload = {
        "project": project.to_dict(),
        "sources": [source.to_dict()],
        "claims": [claim.to_dict()],
        "evidence": [evidence.to_dict()],
        "outline": outline.to_dict(),
        "semantic_reviews": [review],
    }
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    assert main(["run-academic", "--input-json", str(input_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    assert Path(out["draft_path"]).is_file()
    assert Path(out["docx_path"]).is_file()


def test_cli_review_queue_inspect_and_resolve(tmp_path: Path, capsys) -> None:
    project_dir = tmp_path / "rq_project"
    project_dir.mkdir()
    from src.schemas.review import ReviewItem, ReviewQueue
    queue_file = project_dir / "review_queue.json"
    item1 = ReviewItem(
        id="rev_test_1",
        item_type="audit",
        item_id="clm_1",
        severity="HIGH",
        reason="Fact audit failed: claim clm_1: consequential claim has no semantic review record",
        recommended_action="Review and resolve audit findings",
    )
    rq = ReviewQueue([item1])
    rq.save(queue_file, root=project_dir)

    # 1. Inspect
    assert main(["review-queue", str(project_dir)]) == 0
    out1 = json.loads(capsys.readouterr().out)
    assert out1["success"] is True
    assert out1["total_items"] == 1
    assert out1["items"][0]["id"] == "rev_test_1"
    assert out1["items"][0]["status"] == "PENDING"

    # Mock fact_audit.json with assessment so resolve can create SemanticReview
    fa_payload = {
        "assessments": [
            {
                "claim_id": "clm_1",
                "evidence_id": "evd_1",
                "source_id": "src_1",
                "evidence_text": "Sample text for clm 1",
                "evidence_location": "abstract",
            }
        ]
    }
    (project_dir / "fact_audit.json").write_text(json.dumps(fa_payload), encoding="utf-8")

    # 2. Resolve
    assert main(["review-queue", str(project_dir), "--resolve", "rev_test_1", "--notes", "Verified by researcher"]) == 0
    out2 = json.loads(capsys.readouterr().out)
    assert out2["success"] is True
    assert out2["resolved_item"]["status"] == "RESOLVED"
    assert out2["resolved_item"]["resolution_notes"] == "Verified by researcher"
    assert out2["semantic_review"] is not None
    assert out2["semantic_review"]["claim_id"] == "clm_1"

    # Verify semantic_reviews.json file created
    sem_file = project_dir / "semantic_reviews.json"
    assert sem_file.is_file()
    sem_data = json.loads(sem_file.read_text(encoding="utf-8"))
    assert len(sem_data) == 1
    assert sem_data[0]["claim_id"] == "clm_1"


def test_cli_finalize_blocks_on_critical_pending_item(tmp_path: Path, capsys) -> None:
    project_dir = tmp_path / "fin_project"
    project_dir.mkdir()
    from src.schemas.review import ReviewItem, ReviewQueue
    queue_file = project_dir / "review_queue.json"
    item = ReviewItem(
        id="rev_crit",
        item_type="source",
        item_id="src_crit",
        severity="CRITICAL",
        reason="Found 0 verified sources, minimum 2 required",
        recommended_action="Broaden search",
    )
    ReviewQueue([item]).save(queue_file, root=project_dir)

    assert main(["finalize", str(project_dir)]) == 1
    err = capsys.readouterr().err
    assert "review items remain pending" in err
