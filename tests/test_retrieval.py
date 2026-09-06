"""Fast, network-free tests for Phase 6 retrieval."""

from __future__ import annotations

from pathlib import Path

from src.schemas.evidence import EvidenceLocation
from src.schemas.project import Project
from src.schemas.source import Source, SourceState
from src.tools.evidence_extractor import EvidenceExtractor
from src.tools.retrieval import RetrievedPayload, RetrievalRequest, RetrievalTool


def _project(tmp_path: Path) -> Project:
    path = tmp_path / "project"
    (path / "source_documents").mkdir(parents=True)
    return Project(name="project", workspace="tmp", path=str(path), title="Test")


def test_retrieves_existing_abstract(tmp_path: Path) -> None:
    project = _project(tmp_path)
    source = Source(title="Paper", abstract="Important abstract text.")
    response = RetrievalTool().execute(RetrievalRequest(project=project, source=source))
    assert response.success is True
    assert response.parsed_text == "Important abstract text."
    assert Path(response.document_path).read_text(encoding="utf-8") == "Important abstract text."
    assert source.state is SourceState.FULLTEXT_RETRIEVED


def test_retrieves_and_parses_html_url(tmp_path: Path) -> None:
    project = _project(tmp_path)
    source = Source(title="Paper", url="https://example.test/paper")

    def fetcher(url: str, timeout: int) -> RetrievedPayload:
        return RetrievedPayload(
            b"<html><body><h1>Title</h1><p>Evidence paragraph.</p></body></html>",
            "text/html; charset=utf-8",
            url,
        )

    response = RetrievalTool(fetcher=fetcher).execute(
        RetrievalRequest(project=project, source=source)
    )
    assert response.success is True
    assert response.parsed_text == "Title Evidence paragraph."
    assert response.document_path.endswith(".html")
    assert Path(response.document_path).is_file()


def test_pdf_is_saved_without_fake_text_parse(tmp_path: Path) -> None:
    project = _project(tmp_path)
    source = Source(title="Paper", url="https://example.test/paper.pdf")
    tool = RetrievalTool(
        fetcher=lambda url, timeout: RetrievedPayload(b"%PDF-1.4", "application/pdf", url)
    )
    response = tool.execute(RetrievalRequest(project=project, source=source))
    assert response.success is True
    assert response.parsed_text is None
    assert response.metadata["content_parsed"] is False
    assert Path(response.document_path).read_bytes() == b"%PDF-1.4"


def test_retrieval_fails_without_content_pointer(tmp_path: Path) -> None:
    response = RetrievalTool().execute(
        RetrievalRequest(project=_project(tmp_path), source=Source(title="No content"))
    )
    assert response.success is False
    assert response.error_code == "NO_RETRIEVABLE_CONTENT"


def test_retrieval_feeds_verbatim_evidence_extraction(tmp_path: Path) -> None:
    source = Source(title="Paper", abstract="The intervention improved attendance.")
    response = RetrievalTool().execute(
        RetrievalRequest(project=_project(tmp_path), source=source)
    )
    result = EvidenceExtractor().extract_verbatim(
        passage="The intervention improved attendance.",
        haystack=response.parsed_text,
        claim_id="clm_1",
        source=source,
        location=EvidenceLocation(locator="abstract"),
    )
    assert result.found is True
    assert result.evidence.is_citable_quotation is True


def test_retrieval_does_not_regress_approved_source(tmp_path: Path) -> None:
    source = Source(title="Paper", abstract="Text.", state=SourceState.APPROVED)
    response = RetrievalTool().execute(
        RetrievalRequest(project=_project(tmp_path), source=source)
    )
    assert response.success is True
    assert source.state is SourceState.APPROVED


def test_retrieval_refuses_rejected_source(tmp_path: Path) -> None:
    source = Source(title="Paper", abstract="Text.", state=SourceState.REJECTED)
    response = RetrievalTool().execute(
        RetrievalRequest(project=_project(tmp_path), source=source)
    )
    assert response.success is False
    assert response.error_code == "SOURCE_REJECTED"
