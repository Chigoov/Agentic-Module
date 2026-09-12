"""Fast tests for roadmap Phase 12 audit agents."""

from __future__ import annotations

from pathlib import Path

from src.agents.audit import (
    CitationAuditAgent,
    CitationAuditRequest,
    FactAuditAgent,
    FactAuditRequest,
)
from src.schemas.claim import (
    Claim,
    ClaimImportance,
    ClaimStatus,
    SemanticDecision,
    SemanticReview,
)
from src.schemas.evidence import (
    Evidence,
    EvidenceLocation,
    ExtractionMethod,
)
from src.schemas.project import Project
from src.schemas.source import Source, SourceState


def _project(tmp_path: Path) -> Project:
    path = tmp_path / "project"
    path.mkdir()
    return Project(name="project", workspace="tmp", path=str(path), title="Test")


def test_citation_audit_detects_orphan_key(tmp_path: Path) -> None:
    response = CitationAuditAgent().execute(
        CitationAuditRequest(project=_project(tmp_path), draft="Unsupported fake2024", sources=[])
    )
    assert response.passed is False
    assert response.orphan_citations == ["fake2024"]


def test_citation_audit_passes_known_key(tmp_path: Path) -> None:
    source = Source(title="Paper", authors=["Smith, J."], year=2024)
    response = CitationAuditAgent().execute(
        CitationAuditRequest(project=_project(tmp_path), draft="smith2024", sources=[source])
    )
    assert response.passed is True


def test_fact_audit_blocks_unsupported_important_claim(tmp_path: Path) -> None:
    claim = Claim(claim_text="Important", importance=ClaimImportance.HIGH)
    response = FactAuditAgent().execute(
        FactAuditRequest(project=_project(tmp_path), claims=[claim])
    )
    assert response.passed is False
    assert response.unsupported_claims == [claim.id]


def test_fact_audit_passes_writable_claim(tmp_path: Path) -> None:
    source = Source(
        id="src_1",
        title="Research on learning",
        authors=["Smith, J."],
        year=2024,
        venue="Journal of Learning",
        state=SourceState.APPROVED,
        abstract="Supported empirical finding in education.",
    )
    evidence = Evidence(
        id="evd_1",
        claim_id="clm_1",
        source_id="src_1",
        evidence_text="Supported empirical finding in education.",
        location=EvidenceLocation(locator="abstract"),
        extraction_method=ExtractionMethod.VERBATIM_ABSTRACT,
        verbatim=True,
    )
    claim = Claim(
        id="clm_1",
        claim_text="Supported empirical finding in education.",
        importance=ClaimImportance.HIGH,
        supporting_sources=["src_1"],
        supporting_evidence=["evd_1"],
        status=ClaimStatus.SUPPORTED,
    )
    review = SemanticReview(
        claim_id="clm_1",
        decision=SemanticDecision.SUPPORTED,
        reason="Evidence directly supports claim meaning.",
        evidence_id="evd_1",
        source_id="src_1",
        evidence_excerpt="Supported empirical finding in education.",
        location="abstract",
        reviewer="antigravity_agent",
        method="semantic_evaluation",
    )
    response = FactAuditAgent().execute(
        FactAuditRequest(
            project=_project(tmp_path),
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            semantic_reviews=[review],
        )
    )
    assert response.passed is True
    assert response.structural_passed is True
    assert response.semantic_passed is True
