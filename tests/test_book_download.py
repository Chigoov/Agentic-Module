"""Tests for direct download support in RetrievalTool (Bagian D)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from src.schemas.evidence import ReadingDepth
from src.schemas.project import Project
from src.schemas.source import AccessMode, RetrievalStatus, RightsStatus, Source, SourceState, SourceType
from src.tools.retrieval import RetrievedPayload, RetrievalRequest, RetrievalTool


def _make_project(tmp_path: Path) -> Project:
    p_dir = tmp_path / "test_project"
    p_dir.mkdir(parents=True, exist_ok=True)
    return Project(name="test_project", workspace="tmp", path=str(p_dir), title="Test Project")


def test_direct_download_open_access_book(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    sample_content = b"%PDF-1.4 sample content with bytes"
    expected_hash = hashlib.sha256(sample_content).hexdigest()

    source = Source(
        title="Open Access Ecology",
        authors=["Author, Open"],
        year=2023,
        landing_url="https://directory.doabooks.org/handle/20.500.12854/123",
        url="https://directory.doabooks.org/handle/20.500.12854/123",
        download_urls=["https://directory.doabooks.org/rest/bitstreams/123/retrieve"],
        access_mode=AccessMode.OPEN_DOWNLOAD,
        rights_status=RightsStatus.OPEN_LICENSE,
        source_type=SourceType.BOOK,
    )
    assert source.download_allowed is True

    tool = RetrievalTool(
        fetcher=lambda url, timeout: RetrievedPayload(
            content=sample_content,
            content_type="application/pdf",
            final_url="https://directory.doabooks.org/rest/bitstreams/123/retrieve",
        )
    )

    response = tool.execute(RetrievalRequest(project=project, source=source, direct_download=True))
    assert response.success is True
    assert response.retrieval_method == "direct_download"
    assert response.document_path is not None
    assert Path(response.document_path).read_bytes() == sample_content

    # Target strictly inside project
    assert str(Path(project.directory).resolve()) in str(Path(response.document_path).resolve())

    # Check recorded metadata
    meta = source.metadata.get("retrieval")
    assert meta is not None
    assert meta["retrieval_method"] == "direct_download"
    assert meta["content_type"] == "application/pdf"
    assert meta["download_size_bytes"] == len(sample_content)
    assert meta["sha256"] == expected_hash
    assert meta["rights_status"] == "OPEN_LICENSE"
    assert meta["landing_url"] == "https://directory.doabooks.org/handle/20.500.12854/123"
    assert meta["download_url"] == "https://directory.doabooks.org/rest/bitstreams/123/retrieve"


def test_direct_download_borrow_only_refused(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    source = Source(
        id="src_borrow_refused",
        title="Restricted Loan Book",
        authors=["Borrow, Author"],
        year=2020,
        landing_url="https://openlibrary.org/works/OL999W",
        download_urls=["https://archive.org/borrow/999"],
        access_mode=AccessMode.BORROW_ONLY,
        rights_status=RightsStatus.RESTRICTED,
        source_type=SourceType.BOOK,
    )
    tool = RetrievalTool()
    response = tool.execute(RetrievalRequest(project=project, source=source, direct_download=True))

    assert response.success is False
    assert response.error_code == "BORROW_ONLY_DOWNLOAD_FORBIDDEN"
    assert source.state is SourceState.NEEDS_HUMAN_REVIEW
    assert source.retrieval_status is RetrievalStatus.FAILED
    assert any(err.code == "BORROW_ONLY_DOWNLOAD_FORBIDDEN" for err in source.errors)
    docs_dir = project.directory / "source_documents"
    assert not docs_dir.exists() or not any(docs_dir.iterdir())
    queue_file = project.directory / "review_queue.json"
    assert queue_file.is_file()
    import json

    q_data = json.loads(queue_file.read_text(encoding="utf-8"))
    borrow_item = next(item for item in q_data if item["item_id"] == "src_borrow_refused")
    assert borrow_item["severity"] == "HIGH"
    assert borrow_item["recommended_action"] == "Access digital loan from provider site or library catalog"


def test_direct_download_unknown_rights_refused(tmp_path: Path) -> None:
    project = _make_project(tmp_path)
    source = Source(
        id="src_unknown_refused",
        title="Unknown Rights Book",
        authors=["Unknown, Author"],
        year=2021,
        download_urls=["https://example.com/download.pdf"],
        access_mode=AccessMode.UNKNOWN,
        rights_status=RightsStatus.UNKNOWN,
        source_type=SourceType.BOOK,
    )
    tool = RetrievalTool()
    response = tool.execute(RetrievalRequest(project=project, source=source, direct_download=True))

    assert response.success is False
    assert response.error_code == "DOWNLOAD_RIGHTS_UNCLEAR"
    assert source.state is SourceState.NEEDS_HUMAN_REVIEW
    assert source.retrieval_status is RetrievalStatus.FAILED
    assert any(err.code == "DOWNLOAD_RIGHTS_UNCLEAR" for err in source.errors)
    docs_dir = project.directory / "source_documents"
    assert not docs_dir.exists() or not any(docs_dir.iterdir())
    queue_file = project.directory / "review_queue.json"
    assert queue_file.is_file()
    import json

    q_data = json.loads(queue_file.read_text(encoding="utf-8"))
    unknown_item = next(item for item in q_data if item["item_id"] == "src_unknown_refused")
    assert unknown_item["severity"] == "HIGH"
    assert unknown_item["recommended_action"] == "Confirm license and rights from provider landing page before downloading"


def test_direct_download_empty_content_rejected(tmp_path: Path) -> None:
    """Direct download with empty content is rejected with EMPTY_CONTENT and fails safely.

    Validates: Requirements 1.7, 1.8
    """
    project = _make_project(tmp_path)
    source = Source(
        title="Empty File Book",
        authors=["Empty, Author"],
        year=2022,
        download_urls=["https://example.com/empty.pdf"],
        access_mode=AccessMode.OPEN_DOWNLOAD,
        rights_status=RightsStatus.OPEN_LICENSE,
        source_type=SourceType.BOOK,
    )
    tool = RetrievalTool(
        fetcher=lambda url, timeout: RetrievedPayload(content=b"", content_type="application/pdf", final_url=url)
    )
    response = tool.execute(RetrievalRequest(project=project, source=source, direct_download=True))

    assert response.success is False
    assert response.error_code == "EMPTY_CONTENT"
    assert response.document_path is None
    assert source.retrieval_status is RetrievalStatus.FAILED
    assert any(err.code == "EMPTY_CONTENT" for err in source.errors)
    docs_dir = project.directory / "source_documents"
    assert not docs_dir.exists() or not any(docs_dir.iterdir())


def test_direct_download_file_size_limit_exceeded(tmp_path: Path) -> None:
    """Direct download exceeding max_file_size_bytes is rejected with FILE_SIZE_EXCEEDED.

    Validates: Requirements 1.7, 1.8
    """
    project = _make_project(tmp_path)
    source = Source(
        title="Huge File Book",
        authors=["Huge, Author"],
        year=2022,
        download_urls=["https://example.com/huge.pdf"],
        access_mode=AccessMode.OPEN_DOWNLOAD,
        rights_status=RightsStatus.OPEN_LICENSE,
        source_type=SourceType.BOOK,
    )
    oversized = b"X" * 1024
    tool = RetrievalTool(
        fetcher=lambda url, timeout: RetrievedPayload(content=oversized, content_type="application/pdf", final_url=url)
    )
    response = tool.execute(
        RetrievalRequest(project=project, source=source, direct_download=True, max_file_size_bytes=500)
    )

    assert response.success is False
    assert response.error_code == "FILE_SIZE_EXCEEDED"
    assert response.document_path is None
    assert source.retrieval_status is RetrievalStatus.FAILED
    assert any(err.code == "FILE_SIZE_EXCEEDED" for err in source.errors)
    docs_dir = project.directory / "source_documents"
    assert not docs_dir.exists() or not any(docs_dir.iterdir())


def test_direct_download_backup_on_modified_content(tmp_path: Path) -> None:
    """Verifies .bak backup creation when content changes without allow_overwrite.

    Validates: Requirements 1.7, 1.8
    """
    project = _make_project(tmp_path)
    source = Source(
        title="Book Version",
        authors=["Author, V."],
        year=2023,
        download_urls=["https://example.com/version.pdf"],
        access_mode=AccessMode.OPEN_DOWNLOAD,
        rights_status=RightsStatus.OPEN_LICENSE,
        source_type=SourceType.BOOK,
    )

    # First download
    first_tool = RetrievalTool(
        fetcher=lambda url, timeout: RetrievedPayload(content=b"Version 1 content", content_type="application/pdf", final_url=url)
    )
    res1 = first_tool.execute(RetrievalRequest(project=project, source=source, direct_download=True))
    assert res1.success is True
    assert res1.retrieval_method == "direct_download"
    assert source.retrieval_status is RetrievalStatus.RETRIEVED
    assert source.state is SourceState.FULLTEXT_RETRIEVED
    doc_path = Path(res1.document_path)
    assert doc_path.exists()
    assert doc_path.read_bytes() == b"Version 1 content"

    # Second download with different content and allow_overwrite=False
    second_tool = RetrievalTool(
        fetcher=lambda url, timeout: RetrievedPayload(content=b"Version 2 updated content", content_type="application/pdf", final_url=url)
    )
    res2 = second_tool.execute(RetrievalRequest(project=project, source=source, direct_download=True, allow_overwrite=False))
    assert res2.success is True
    assert res2.retrieval_method == "direct_download"
    assert doc_path.read_bytes() == b"Version 2 updated content"
    assert source.retrieval_status is RetrievalStatus.RETRIEVED

    # Backup was created in the directory
    backups = list(doc_path.parent.glob(f"{doc_path.name}.*.bak"))
    assert len(backups) >= 1
    assert backups[0].read_bytes() == b"Version 1 content"

    # Third download with identical content and allow_overwrite=False creates no additional backup
    res3 = second_tool.execute(RetrievalRequest(project=project, source=source, direct_download=True, allow_overwrite=False))
    assert res3.success is True
    backups_after = list(doc_path.parent.glob(f"{doc_path.name}.*.bak"))
    assert len(backups_after) == len(backups)


def test_unknown_with_explicit_download_url_rejected(tmp_path: Path) -> None:
    """Providing explicit download_url CANNOT bypass AccessMode.UNKNOWN or RightsStatus.UNKNOWN.

    Validates: Requirements 1.3, 1.4, 1.8
    """
    import json

    project = _make_project(tmp_path)
    tool = RetrievalTool()
    docs_dir = project.directory / "source_documents"

    # Verify explicit URL cannot bypass AccessMode.UNKNOWN or RightsStatus.UNKNOWN (Requirement 1.3, 1.4)
    cases = [
        ("src_unknown_both", AccessMode.UNKNOWN, RightsStatus.UNKNOWN),
        ("src_unknown_access", AccessMode.UNKNOWN, RightsStatus.OPEN_LICENSE),
        ("src_unknown_rights", AccessMode.OPEN_DOWNLOAD, RightsStatus.UNKNOWN),
    ]

    for source_id, access_mode, rights_status in cases:
        source = Source(
            id=source_id,
            title=f"Unknown Rights Book {source_id}",
            authors=["Author, U."],
            year=2023,
            access_mode=access_mode,
            rights_status=rights_status,
            source_type=SourceType.BOOK,
        )

        response = tool.execute(
            RetrievalRequest(
                project=project,
                source=source,
                download_url=f"https://unauthorized.test/explicit_{source_id}.pdf",
                direct_download=True,
            )
        )

        assert response.success is False
        assert response.error_code == "DOWNLOAD_RIGHTS_UNCLEAR"
        assert source.state is SourceState.NEEDS_HUMAN_REVIEW
        assert source.retrieval_status is RetrievalStatus.FAILED
        assert any(err.code == "DOWNLOAD_RIGHTS_UNCLEAR" for err in source.errors)

    assert not docs_dir.exists() or not any(docs_dir.glob("*.pdf"))

    # Review queue recorded for each unknown variant
    queue_file = project.directory / "review_queue.json"
    assert queue_file.is_file()
    q_data = json.loads(queue_file.read_text(encoding="utf-8"))
    for source_id, _, _ in cases:
        item = next(it for it in q_data if it["item_id"] == source_id)
        assert item["severity"] == "HIGH"
        assert item["recommended_action"] == "Confirm license and rights from provider landing page before downloading"


def test_borrow_only_with_explicit_download_url_rejected(tmp_path: Path) -> None:
    """Providing explicit download_url CANNOT bypass BORROW_ONLY check.

    Validates: Requirements 1.1, 1.8
    """
    project = _make_project(tmp_path)
    source = Source(
        id="src_borrow_only",
        title="Digital Loan Book",
        authors=["Author, B."],
        year=2022,
        access_mode=AccessMode.BORROW_ONLY,
        rights_status=RightsStatus.RESTRICTED,
        source_type=SourceType.BOOK,
    )
    docs_dir = project.directory / "source_documents"

    tool = RetrievalTool()
    response = tool.execute(
        RetrievalRequest(
            project=project,
            source=source,
            download_url="https://archive.org/borrow/direct_bypass.pdf",
            direct_download=True,
        )
    )

    assert response.success is False
    assert response.error_code == "BORROW_ONLY_DOWNLOAD_FORBIDDEN"
    assert source.state is SourceState.NEEDS_HUMAN_REVIEW
    assert source.retrieval_status is RetrievalStatus.FAILED
    assert any(err.code == "BORROW_ONLY_DOWNLOAD_FORBIDDEN" for err in source.errors)
    assert not docs_dir.exists() or not any(docs_dir.glob("*.pdf"))

    queue_file = project.directory / "review_queue.json"
    assert queue_file.is_file()
    import json
    q_data = json.loads(queue_file.read_text(encoding="utf-8"))
    item = next(it for it in q_data if it["item_id"] == "src_borrow_only")
    assert item["severity"] == "HIGH"
    assert item["recommended_action"] == "Access digital loan from provider site or library catalog"


def test_preview_only_with_explicit_download_url_rejected(tmp_path: Path) -> None:
    """Providing explicit download_url CANNOT bypass PREVIEW_ONLY check.

    Validates: Requirements 1.2, 1.8
    """
    project = _make_project(tmp_path)
    source = Source(
        id="src_preview_only",
        title="Preview Only Book",
        authors=["Author, P."],
        year=2021,
        access_mode=AccessMode.PREVIEW_ONLY,
        rights_status=RightsStatus.UNKNOWN,
        source_type=SourceType.BOOK,
    )
    docs_dir = project.directory / "source_documents"

    tool = RetrievalTool()
    response = tool.execute(
        RetrievalRequest(
            project=project,
            source=source,
            download_url="https://books.google.com/preview_bypass.pdf",
            direct_download=True,
        )
    )

    assert response.success is False
    assert response.error_code == "PREVIEW_ONLY_DOWNLOAD_FORBIDDEN"
    assert source.state is SourceState.NEEDS_HUMAN_REVIEW
    assert source.retrieval_status is RetrievalStatus.FAILED
    assert any(err.code == "PREVIEW_ONLY_DOWNLOAD_FORBIDDEN" for err in source.errors)
    assert not docs_dir.exists() or not any(docs_dir.glob("*.pdf"))

    queue_file = project.directory / "review_queue.json"
    assert queue_file.is_file()
    import json
    q_data = json.loads(queue_file.read_text(encoding="utf-8"))
    item = next(it for it in q_data if it["item_id"] == "src_preview_only")
    assert item["severity"] == "MEDIUM"
    assert item["recommended_action"] == "Inspect preview online on provider site"


def test_open_license_with_valid_download_url_allowed(tmp_path: Path) -> None:
    """OPEN_DOWNLOAD + OPEN_LICENSE with valid download_url is permitted, persists content and computes SHA-256 hash.

    Validates: Requirements 1.7, 1.8
    """
    project = _make_project(tmp_path)
    source = Source(
        id="src_open_valid",
        title="Legitimate Open Book",
        authors=["Author, O."],
        year=2024,
        access_mode=AccessMode.OPEN_DOWNLOAD,
        rights_status=RightsStatus.OPEN_LICENSE,
        source_type=SourceType.BOOK,
    )
    content = b"%PDF-1.4 Open Licensed Content"
    expected_hash = hashlib.sha256(content).hexdigest()

    tool = RetrievalTool(
        fetcher=lambda url, timeout: RetrievedPayload(
            content=content,
            content_type="application/pdf",
            final_url=url,
        )
    )
    response = tool.execute(
        RetrievalRequest(
            project=project,
            source=source,
            download_url="https://directory.doabooks.org/rest/bitstreams/valid.pdf",
            direct_download=True,
        )
    )

    assert response.success is True
    assert response.retrieval_method == "direct_download"
    assert response.document_path is not None

    doc_path = Path(response.document_path)
    assert doc_path.exists()
    assert doc_path.read_bytes() == content
    assert str(Path(project.directory).resolve()) in str(doc_path.resolve())
    assert "source_documents" in doc_path.parts

    assert source.retrieval_status is RetrievalStatus.RETRIEVED
    assert source.state is SourceState.FULLTEXT_RETRIEVED

    retrieval_meta = source.metadata.get("retrieval")
    assert retrieval_meta is not None
    assert retrieval_meta["sha256"] == expected_hash
    assert retrieval_meta["download_size_bytes"] == len(content)
    assert retrieval_meta["retrieval_method"] == "direct_download"
    assert retrieval_meta["rights_status"] == "OPEN_LICENSE"
    assert retrieval_meta["download_url"] == "https://directory.doabooks.org/rest/bitstreams/valid.pdf"


def test_direct_download_refuse_when_already_in_needs_human_review(tmp_path: Path) -> None:
    """Refusal on a source already in NEEDS_HUMAN_REVIEW does not raise StateTransitionError."""
    project = _make_project(tmp_path)
    source = Source(
        id="src_already_review",
        title="Flagged Book",
        authors=["Author, F."],
        year=2021,
        access_mode=AccessMode.BORROW_ONLY,
        rights_status=RightsStatus.RESTRICTED,
        state=SourceState.NEEDS_HUMAN_REVIEW,
        source_type=SourceType.BOOK,
    )
    tool = RetrievalTool()
    response = tool.execute(RetrievalRequest(project=project, source=source, direct_download=True))

    assert response.success is False
    assert response.error_code == "BORROW_ONLY_DOWNLOAD_FORBIDDEN"
    assert source.state is SourceState.NEEDS_HUMAN_REVIEW
    assert source.retrieval_status is RetrievalStatus.FAILED
    assert any(err.code == "BORROW_ONLY_DOWNLOAD_FORBIDDEN" for err in source.errors)

    docs_dir = project.directory / "source_documents"
    assert not docs_dir.exists() or not any(docs_dir.iterdir())


def test_direct_download_borrow_only_without_download_urls_refused(tmp_path: Path) -> None:
    """A borrow-only book without any download URLs is refused by policy, not by missing URL."""
    project = _make_project(tmp_path)
    source = Source(
        id="src_borrow_no_url",
        title="Open Library Borrowable Book",
        authors=["Borrow, B."],
        year=2020,
        access_mode=AccessMode.BORROW_ONLY,
        rights_status=RightsStatus.RESTRICTED,
        download_urls=[],
        source_type=SourceType.BOOK,
    )
    tool = RetrievalTool()
    response = tool.execute(RetrievalRequest(project=project, source=source, direct_download=True))

    assert response.success is False
    assert response.error_code == "BORROW_ONLY_DOWNLOAD_FORBIDDEN"
    assert source.state is SourceState.NEEDS_HUMAN_REVIEW
    assert source.retrieval_status is RetrievalStatus.FAILED
    assert any(err.code == "BORROW_ONLY_DOWNLOAD_FORBIDDEN" for err in source.errors)

    docs_dir = project.directory / "source_documents"
    assert not docs_dir.exists() or not any(docs_dir.iterdir())
    queue_file = project.directory / "review_queue.json"
    assert queue_file.is_file()
    import json

    q_data = json.loads(queue_file.read_text(encoding="utf-8"))
    item = next(it for it in q_data if it["item_id"] == "src_borrow_no_url")
    assert item["severity"] == "HIGH"
    assert item["recommended_action"] == "Access digital loan from provider site or library catalog"


def test_zero_byte_writes_and_review_queue_creation_rejected(tmp_path: Path) -> None:
    """Verify zero bytes are written to source_documents/ and review queue records appropriate items across all rejection cases.

    Validates: Requirements 1.5, 1.6, 1.8
    """
    import json

    project = _make_project(tmp_path)
    tool = RetrievalTool()
    docs_dir = project.directory / "source_documents"

    # Exhaustive matrix of policy rejection cases:
    # (id, access_mode, rights_status, use_explicit, expected_code, expected_severity, expected_action)
    rejection_cases = [
        (
            "src_reject_borrow_default",
            AccessMode.BORROW_ONLY,
            RightsStatus.RESTRICTED,
            False,
            "BORROW_ONLY_DOWNLOAD_FORBIDDEN",
            "HIGH",
            "Access digital loan from provider site or library catalog",
        ),
        (
            "src_reject_borrow_explicit",
            AccessMode.BORROW_ONLY,
            RightsStatus.OPEN_LICENSE,
            True,
            "BORROW_ONLY_DOWNLOAD_FORBIDDEN",
            "HIGH",
            "Access digital loan from provider site or library catalog",
        ),
        (
            "src_reject_preview_default",
            AccessMode.PREVIEW_ONLY,
            RightsStatus.UNKNOWN,
            False,
            "PREVIEW_ONLY_DOWNLOAD_FORBIDDEN",
            "MEDIUM",
            "Inspect preview online on provider site",
        ),
        (
            "src_reject_preview_explicit",
            AccessMode.PREVIEW_ONLY,
            RightsStatus.PUBLIC_DOMAIN,
            True,
            "PREVIEW_ONLY_DOWNLOAD_FORBIDDEN",
            "MEDIUM",
            "Inspect preview online on provider site",
        ),
        (
            "src_reject_unknown_both",
            AccessMode.UNKNOWN,
            RightsStatus.UNKNOWN,
            False,
            "DOWNLOAD_RIGHTS_UNCLEAR",
            "HIGH",
            "Confirm license and rights from provider landing page before downloading",
        ),
        (
            "src_reject_unknown_access",
            AccessMode.UNKNOWN,
            RightsStatus.OPEN_LICENSE,
            True,
            "DOWNLOAD_RIGHTS_UNCLEAR",
            "HIGH",
            "Confirm license and rights from provider landing page before downloading",
        ),
        (
            "src_reject_unknown_rights",
            AccessMode.OPEN_DOWNLOAD,
            RightsStatus.UNKNOWN,
            True,
            "DOWNLOAD_RIGHTS_UNCLEAR",
            "HIGH",
            "Confirm license and rights from provider landing page before downloading",
        ),
        (
            "src_reject_restricted_rights",
            AccessMode.OPEN_DOWNLOAD,
            RightsStatus.RESTRICTED,
            False,
            "DOWNLOAD_RIGHTS_RESTRICTED",
            "HIGH",
            "Confirm license and rights from provider landing page before downloading",
        ),
        (
            "src_reject_read_online",
            AccessMode.READ_ONLINE,
            RightsStatus.OPEN_LICENSE,
            True,
            "DOWNLOAD_RIGHTS_RESTRICTED",
            "HIGH",
            "Confirm license and rights from provider landing page before downloading",
        ),
        (
            "src_reject_read_online_restricted",
            AccessMode.READ_ONLINE,
            RightsStatus.RESTRICTED,
            False,
            "DOWNLOAD_RIGHTS_RESTRICTED",
            "HIGH",
            "Confirm license and rights from provider landing page before downloading",
        ),
        (
            "src_reject_read_online_provider_free",
            AccessMode.READ_ONLINE,
            RightsStatus.PROVIDER_STATED_FREE,
            True,
            "DOWNLOAD_RIGHTS_RESTRICTED",
            "HIGH",
            "Confirm license and rights from provider landing page before downloading",
        ),
    ]

    for source_id, access_mode, rights_status, use_explicit, expected_code, expected_severity, expected_action in rejection_cases:
        source = Source(
            id=source_id,
            title=f"Rejection Case {source_id}",
            authors=["Rejection, Author"],
            year=2023,
            access_mode=access_mode,
            rights_status=rights_status,
            download_urls=["https://provider.example.org/download.pdf"] if not use_explicit else [],
            source_type=SourceType.BOOK,
        )

        response = tool.execute(
            RetrievalRequest(
                project=project,
                source=source,
                download_url="https://explicit-bypass.example.org/bypass.pdf" if use_explicit else None,
                direct_download=True,
            )
        )

        # 1. Assert rejection response
        assert response.success is False
        assert response.error_code == expected_code
        assert response.document_path is None

        # 2. Assert source status and state
        assert source.retrieval_status is RetrievalStatus.FAILED
        assert source.state is SourceState.NEEDS_HUMAN_REVIEW
        assert any(err.code == expected_code for err in source.errors)

        # 3. Assert zero bytes written and zero files created in source_documents/
        assert not docs_dir.exists() or len(list(docs_dir.iterdir())) == 0

    # 4. Guarantee review_queue.json records corresponding entries for every rejected source
    queue_file = project.directory / "review_queue.json"
    assert queue_file.is_file()
    q_data = json.loads(queue_file.read_text(encoding="utf-8"))

    queue_by_id = {item["item_id"]: item for item in q_data}
    assert len(queue_by_id) == len(rejection_cases)

    for source_id, _, _, _, _, expected_severity, expected_action in rejection_cases:
        assert source_id in queue_by_id
        item = queue_by_id[source_id]
        assert item["item_type"] == "source"
        assert item["severity"] == expected_severity
        assert item["recommended_action"] == expected_action
        assert item["status"] == "PENDING"
        assert item["reason"] != ""


def test_zero_byte_writes_preserves_existing_directory_rejected(tmp_path: Path) -> None:
    """Verify policy rejection writes zero bytes and does not alter existing documents in source_documents/.

    Validates: Requirements 1.5, 1.6, 1.8
    """
    import json

    project = _make_project(tmp_path)
    tool = RetrievalTool()
    docs_dir = project.directory / "source_documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Pre-populate source_documents/ with an existing file
    existing_file = docs_dir / "existing_doc.pdf"
    existing_content = b"%PDF-1.4 existing file content"
    existing_file.write_bytes(existing_content)

    source = Source(
        id="src_reject_with_existing_dir",
        title="Restricted Book With Existing Dir",
        authors=["Author, R."],
        year=2023,
        access_mode=AccessMode.BORROW_ONLY,
        rights_status=RightsStatus.RESTRICTED,
        download_urls=["https://example.com/borrow.pdf"],
        source_type=SourceType.BOOK,
    )

    response = tool.execute(RetrievalRequest(project=project, source=source, direct_download=True))

    assert response.success is False
    assert response.error_code == "BORROW_ONLY_DOWNLOAD_FORBIDDEN"
    assert source.retrieval_status is RetrievalStatus.FAILED
    assert source.state is SourceState.NEEDS_HUMAN_REVIEW

    # Check directory contents remained completely intact (zero new files, zero modified files)
    files = list(docs_dir.iterdir())
    assert len(files) == 1
    assert files[0].name == "existing_doc.pdf"
    assert files[0].read_bytes() == existing_content

    # Review queue recorded
    queue_file = project.directory / "review_queue.json"
    assert queue_file.is_file()
    q_data = json.loads(queue_file.read_text(encoding="utf-8"))
    item = next(it for it in q_data if it["item_id"] == "src_reject_with_existing_dir")
    assert item["severity"] == "HIGH"
    assert item["recommended_action"] == "Access digital loan from provider site or library catalog"

