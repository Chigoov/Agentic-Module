"""Fast tests for roadmap Phase 12 audit agents."""

from __future__ import annotations

from pathlib import Path

from src.agents.audit import (
    CitationAuditAgent,
    CitationAuditRequest,
    FactAuditAgent,
    FactAuditRequest,
)
from src.schemas.claim import Claim, ClaimImportance, ClaimStatus
from src.schemas.project import Project
from src.schemas.source import Source


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
    claim = Claim(
        claim_text="Supported",
        importance=ClaimImportance.HIGH,
        supporting_evidence=["evd_1"],
        status=ClaimStatus.SUPPORTED,
    )
    response = FactAuditAgent().execute(
        FactAuditRequest(project=_project(tmp_path), claims=[claim])
    )
    assert response.passed is True
