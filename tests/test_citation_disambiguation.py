"""Tests for citation disambiguation (Smith, 2023a vs 2023b) and citation_map.json artifact (Bagian G)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agents.audit import CitationAuditAgent, CitationAuditRequest
from src.agents.writer import WriterAgent, WriterRequest
from src.schemas.claim import Claim, ClaimImportance, ClaimStatus
from src.schemas.evidence import Evidence, EvidenceLocation, EvidenceRelationship, EvidenceStrength
from src.schemas.outline import Outline, OutlineSection
from src.schemas.project import Project, ProjectArtifact
from src.schemas.source import Source, SourceState, SourceType
from src.tools.citation_manager import CitationManager, build_citation_map


def _make_project(tmp_path: Path) -> Project:
    p = tmp_path / "citation_test_proj"
    p.mkdir(parents=True, exist_ok=True)
    return Project(name="citation_test_proj", workspace="tmp", path=str(p), title="Citation Disambiguation")


def test_citation_manager_disambiguates_same_author_and_year() -> None:
    manager = CitationManager()
    source1 = Source(id="src_1", title="Alpha Study", authors=["Smith, J."], year=2023, state=SourceState.APPROVED)
    source2 = Source(id="src_2", title="Beta Study", authors=["Smith, J."], year=2023, state=SourceState.APPROVED)

    manager.register_source(source1)
    # Before second source is registered, label is Smith, 2023
    assert manager.get_citation_label("src_1") == "Smith, 2023"

    manager.register_source(source2)
    # When second source with same author & year is registered, both receive 'a' and 'b' suffixes
    assert manager.get_citation_label("src_1") == "Smith, 2023a"
    assert manager.get_citation_label("src_2") == "Smith, 2023b"

    # A third source with different author remains unaffected
    source3 = Source(id="src_3", title="Gamma Study", authors=["Lee, K."], year=2023, state=SourceState.APPROVED)
    manager.register_source(source3)
    assert manager.get_citation_label("src_3") == "Lee, 2023"


def test_writer_emits_disambiguated_citations_and_references(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    source1 = Source(
        id="src_1",
        title="First Study",
        authors=["Nashrullah, M."],
        year=2023,
        venue="Journal A",
        doi="10.1001/ja.2023.1",
        state=SourceState.APPROVED,
    )
    source2 = Source(
        id="src_2",
        title="Second Study",
        authors=["Nashrullah, M."],
        year=2023,
        venue="Journal B",
        doi="10.1001/jb.2023.2",
        state=SourceState.APPROVED,
    )

    ev1 = Evidence(
        id="evd_1",
        claim_id="clm_1",
        source_id="src_1",
        evidence_text="First finding data.",
        verbatim=True,
        quote_verified=True,
        location=EvidenceLocation(page=10),
    )
    ev2 = Evidence(
        id="evd_2",
        claim_id="clm_2",
        source_id="src_2",
        evidence_text="Second finding data.",
        verbatim=True,
        quote_verified=True,
        location=EvidenceLocation(page=25),
    )

    claim1 = Claim(
        id="clm_1",
        claim_text="Intervention A is effective.",
        status=ClaimStatus.SUPPORTED,
        importance=ClaimImportance.MEDIUM,
        supporting_evidence=["evd_1"],
        supporting_sources=["src_1"],
    )
    claim2 = Claim(
        id="clm_2",
        claim_text="Intervention B is also effective.",
        status=ClaimStatus.SUPPORTED,
        importance=ClaimImportance.MEDIUM,
        supporting_evidence=["evd_2"],
        supporting_sources=["src_2"],
    )

    outline = Outline(
        title="Comparative Analysis",
        sections=[
            OutlineSection(title="Section 1", level=1, claim_ids=["clm_1", "clm_2"]),
        ],
    )

    writer_resp = WriterAgent().execute(
        WriterRequest(
            project=project,
            outline=outline,
            claims=[claim1, claim2],
            evidence=[ev1, ev2],
            sources=[source1, source2],
        )
    )

    assert writer_resp.success is True
    draft = writer_resp.draft

    # Must contain disambiguated in-text labels (Nashrullah, 2023a) and (Nashrullah, 2023b)
    assert "Nashrullah, 2023a" in draft
    assert "Nashrullah, 2023b" in draft
    assert "(Nashrullah, 2023)" not in draft

    # Bibliography in draft must also carry disambiguation suffixes (2023a) and (2023b)
    assert "(2023a)" in draft
    assert "(2023b)" in draft

    # Citation map artifact must exist and match specification
    map_file = Path(project.directory) / "citation_map.json"
    assert map_file.is_file()
    map_data = json.loads(map_file.read_text(encoding="utf-8"))
    assert "citations" in map_data
    citations = map_data["citations"]
    assert len(citations) >= 2

    c1 = next(c for c in citations if c["source_id"] == "src_1")
    assert c1["citation_label"] == "Nashrullah, 2023a"
    assert c1["claim_id"] == "clm_1"
    assert c1["evidence_id"] == "evd_1"
    assert "10" in c1["location"]

    c2 = next(c for c in citations if c["source_id"] == "src_2")
    assert c2["citation_label"] == "Nashrullah, 2023b"
    assert c2["claim_id"] == "clm_2"
    assert c2["evidence_id"] == "evd_2"
    assert "25" in c2["location"]

    # Citation audit passes on the draft with disambiguated forms
    audit_resp = CitationAuditAgent().execute(
        CitationAuditRequest(project=project, draft=draft, sources=[source1, source2])
    )
    assert audit_resp.passed is True
    assert audit_resp.author_year_orphans == []
    assert audit_resp.orphan_citations == []
