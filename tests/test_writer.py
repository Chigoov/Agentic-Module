"""Fast, network-free tests for the WriterAgent (Phase 6)."""

from __future__ import annotations

from pathlib import Path

from src.agents.writer import WriterAgent, WriterRequest
from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import (
    Evidence,
    EvidenceLocation,
    EvidenceRelationship,
    EvidenceStrength,
)
from src.schemas.outline import Outline, OutlineSection
from src.schemas.project import Project
from src.schemas.source import Source, SourceType


def _project(tmp_path: Path) -> Project:
    directory = tmp_path / "proj"
    directory.mkdir()
    return Project(
        name="proj",
        workspace="TUGAS 1",
        path=str(directory),
        title="Document Title",
    )


def _source(*, title: str, authors: list[str], year: int) -> Source:
    return Source(
        title=title,
        authors=authors,
        year=year,
        source_type=SourceType.JOURNAL_ARTICLE,
    )


def _writable_claim(*, source_ids: list[str] | None = None) -> Claim:
    return Claim(
        claim_text="A supported claim",
        status=ClaimStatus.SUPPORTED,
        support_level=SupportLevel.STRONG,
        confidence=0.9,
        supporting_sources=source_ids or [],
    )


def test_writer_assembles_draft_from_writable_claims(tmp_path: Path) -> None:
    project = _project(tmp_path)
    source = _source(title="Alpha", authors=["Smith, J."], year=2012)
    claim = _writable_claim(source_ids=[source.id])
    outline = Outline(
        project_id=project.id,
        title="Document Title",
        sections=[OutlineSection(title="Pendahuluan", claim_ids=[claim.id])],
    )
    request = WriterRequest(
        project=project,
        outline=outline,
        claims=[claim],
        sources=[source],
    )
    response = WriterAgent().execute(request)

    assert response.success
    assert response.draft.startswith("# Document Title")
    assert "## Pendahuluan" in response.draft
    assert "A supported claim" in response.draft
    assert "(Smith, 2012)" in response.draft
    assert response.excluded_claims == []
    assert response.orphan_citations == []
    assert response.reference_list is not None
    assert response.reference_list.entries[0].citation_key == "smith2012"
    assert response.draft_path is not None


def test_writer_excludes_non_writable_claims(tmp_path: Path) -> None:
    project = _project(tmp_path)
    writable = _writable_claim()
    unwritable = Claim(claim_text="Refuted claim", status=ClaimStatus.REFUTED)
    outline = Outline(
        project_id=project.id,
        title="Document Title",
        sections=[
            OutlineSection(title="S", claim_ids=[writable.id, unwritable.id]),
        ],
    )
    request = WriterRequest(
        project=project, outline=outline, claims=[writable, unwritable]
    )
    response = WriterAgent().execute(request)

    assert response.success
    assert "Refuted claim" not in response.draft
    assert response.excluded_claims == [unwritable.id]


def test_writer_includes_citable_quotation(tmp_path: Path) -> None:
    project = _project(tmp_path)
    source = _source(title="Alpha", authors=["Smith, J."], year=2012)
    claim = _writable_claim(source_ids=[source.id])
    evidence = Evidence(
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="The sky is blue.",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.DEFINITIVE,
        location=EvidenceLocation(page=42),
        quote_verified=True,
    )
    outline = Outline(
        project_id=project.id,
        title="Document Title",
        sections=[OutlineSection(title="S", claim_ids=[claim.id])],
    )
    request = WriterRequest(
        project=project,
        outline=outline,
        claims=[claim],
        evidence=[evidence],
        sources=[source],
    )
    response = WriterAgent().execute(request)

    assert response.success
    assert '> "The sky is blue."' in response.draft
    assert "p. 42" in response.draft


def test_writer_never_invents_citations(tmp_path: Path) -> None:
    project = _project(tmp_path)
    # Claim references a source that is NOT in the request.sources list.
    claim = _writable_claim(source_ids=["src_missing"])
    outline = Outline(
        project_id=project.id,
        title="Document Title",
        sections=[OutlineSection(title="S", claim_ids=[claim.id])],
    )
    request = WriterRequest(project=project, outline=outline, claims=[claim])
    response = WriterAgent().execute(request)

    assert response.success
    # No author-year pointer may be synthesized for an unknown source.
    assert "(Smith" not in response.draft
    assert response.reference_list is not None
    assert response.reference_list.entries == []


def test_writer_writes_draft_to_disk(tmp_path: Path) -> None:
    project = _project(tmp_path)
    claim = _writable_claim()
    outline = Outline(
        project_id=project.id,
        title="Document Title",
        sections=[OutlineSection(title="S", claim_ids=[claim.id])],
    )
    request = WriterRequest(project=project, outline=outline, claims=[claim])
    response = WriterAgent().execute(request)

    assert response.success
    assert response.draft_path is not None
    written = Path(response.draft_path)
    assert written.is_file()
    assert "Document Title" in written.read_text(encoding="utf-8")
