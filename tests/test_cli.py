"""CLI tests for AI-agent entry points."""

from __future__ import annotations

import json
from pathlib import Path

from src.runtime.cli import main
from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import Evidence, EvidenceLocation
from src.schemas.outline import Outline, OutlineSection
from src.schemas.project import Project
from src.schemas.source import Source, SourceState


def test_cli_plan_outputs_json(capsys) -> None:
    assert main(["plan", "dampak perceraian orang tua terhadap remaja"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    assert out["plan"]["citation_style"] == "APA7"


def test_cli_check_passes() -> None:
    assert main(["check"]) == 0


def test_cli_run_academic_writes_outputs(tmp_path: Path, capsys) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project = Project(name="project", workspace="tmp", path=str(project_dir), title="Test")
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
    payload = {
        "project": project.to_dict(),
        "sources": [source.to_dict()],
        "claims": [claim.to_dict()],
        "evidence": [evidence.to_dict()],
        "outline": outline.to_dict(),
    }
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(payload), encoding="utf-8")

    assert main(["run-academic", "--input-json", str(input_path)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["success"] is True
    assert Path(out["draft_path"]).is_file()
    assert Path(out["docx_path"]).is_file()
