"""Fast, network-free tests for the SynthesisAgent (Phase 6)."""

from __future__ import annotations

from pathlib import Path

from src.agents.synthesis import SynthesisAgent, SynthesisRequest
from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import Evidence, EvidenceRelationship
from src.schemas.project import Project
from src.schemas.synthesis import SynthesisStatus


def _project(tmp_path: Path) -> Project:
    directory = tmp_path / "proj"
    directory.mkdir()
    return Project(name="proj", workspace="TUGAS 1", path=str(directory), title="Judul")


def _supported_claim(section_hint: str | None = None) -> Claim:
    return Claim(
        claim_text="A supported claim",
        status=ClaimStatus.SUPPORTED,
        support_level=SupportLevel.STRONG,
        confidence=0.9,
        section_hint=section_hint,
    )


def test_synthesis_aggregates_writable_claims(tmp_path: Path) -> None:
    claim = _supported_claim("Pendahuluan")
    evidence = Evidence(
        claim_id=claim.id,
        source_id="src_1",
        evidence_text="passage",
        relationship=EvidenceRelationship.SUPPORTS,
    )
    request = SynthesisRequest(project=_project(tmp_path), claims=[claim], evidence=[evidence])
    response = SynthesisAgent().execute(request)

    assert response.success
    assert response.synthesis is not None
    assert response.finding_count == 1
    assert response.open_gap_count == 0
    assert response.synthesis.status is SynthesisStatus.COMPLETE
    finding = response.synthesis.findings[0]
    assert finding.statement == "A supported claim"
    assert finding.claim_ids == [claim.id]
    assert finding.confidence == 0.9


def test_synthesis_excludes_non_writable_claims(tmp_path: Path) -> None:
    writable = _supported_claim()
    unwritable = Claim(claim_text="Not supported", status=ClaimStatus.REFUTED)
    request = SynthesisRequest(project=_project(tmp_path), claims=[writable, unwritable])
    response = SynthesisAgent().execute(request)

    assert response.success
    assert response.finding_count == 1
    assert response.open_gap_count == 1
    assert response.synthesis is not None
    assert any("REFUTED" in gap for gap in response.synthesis.open_gaps)


def test_synthesis_orders_by_section_hint(tmp_path: Path) -> None:
    first = _supported_claim("Pendahuluan")
    second = _supported_claim("Metode")
    request = SynthesisRequest(project=_project(tmp_path), claims=[second, first])
    response = SynthesisAgent().execute(request)

    assert response.success
    assert response.synthesis is not None
    statements = [f.statement for f in response.synthesis.findings]
    assert statements == ["A supported claim", "A supported claim"]
    # Section ordering is preserved in source_ids mapping via claim order.
    assert response.synthesis.findings[0].claim_ids == [second.id]
    assert response.synthesis.findings[1].claim_ids == [first.id]


def test_synthesis_preserves_conflict_flag(tmp_path: Path) -> None:
    claim = Claim(
        claim_text="Contested claim",
        status=ClaimStatus.CONFLICTED,
        support_level=SupportLevel.MODERATE,
        confidence=0.5,
    )
    claim.attach_support(evidence_id="evd_1", source_id="src_1")
    claim.attach_contradiction(evidence_id="evd_2", source_id="src_2")
    request = SynthesisRequest(project=_project(tmp_path), claims=[claim])
    response = SynthesisAgent().execute(request)

    assert response.success
    assert response.synthesis is not None
    assert response.synthesis.findings[0].conflicts_disclosed is True
