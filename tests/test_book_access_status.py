"""Tests for book access status and rights classification (Bagian C)."""

from __future__ import annotations

import pytest

from src.schemas.source import AccessMode, RightsStatus, Source, SourceState, SourceType
from src.tools.source_mapper import classify_rights_and_access, source_from_dict


def test_approved_source_does_not_imply_download_allowed() -> None:
    """SourceState.APPROVED does NOT automatically grant download permission."""
    source = Source(
        title="Sample Book",
        authors=["Author, A."],
        year=2020,
        source_type=SourceType.BOOK,
        access_mode=AccessMode.UNKNOWN,
        rights_status=RightsStatus.UNKNOWN,
        download_urls=[],
    )
    source.approve(reason="Metadata verified by human")
    assert source.state is SourceState.APPROVED
    assert source.download_allowed is False


def test_missing_download_urls_not_downloadable() -> None:
    """Source with open license but no download URLs is not downloadable."""
    source = Source(
        title="Open Book Without Download",
        authors=["Author, A."],
        year=2021,
        access_mode=AccessMode.READ_ONLINE,
        rights_status=RightsStatus.OPEN_LICENSE,
        download_urls=[],
    )
    assert source.download_allowed is False


def test_license_unknown_blocks_download() -> None:
    """Even if a direct URL exists, UNKNOWN rights blocks automatic download."""
    rights, access = classify_rights_and_access(
        download_urls=["https://example.com/file.pdf"],
        license_text=None,
        rights_status_hint=None,
    )
    assert rights is RightsStatus.UNKNOWN
    assert access is AccessMode.UNKNOWN

    source = source_from_dict(
        {
            "title": "Mystery PDF",
            "download_urls": ["https://example.com/file.pdf"],
            "rights_status": "UNKNOWN",
        },
        origin="test",
    )
    assert source.download_allowed is False


def test_borrow_only_cannot_be_downloaded() -> None:
    """Borrow-only ebooks must have access_mode BORROW_ONLY and download_allowed False."""
    rights, access = classify_rights_and_access(
        ebook_access="borrowable",
        download_urls=["https://archive.org/borrow/12345"],
        license_text="Copyrighted Library Loan",
    )
    assert access is AccessMode.BORROW_ONLY
    assert rights is RightsStatus.RESTRICTED

    source = source_from_dict(
        {
            "title": "Borrowable Book",
            "ebook_access": "borrowable",
            "download_urls": ["https://archive.org/borrow/12345"],
        },
        origin="open_library",
    )
    assert source.access_mode is AccessMode.BORROW_ONLY
    assert source.download_allowed is False


def test_preview_only_cannot_be_downloaded() -> None:
    """Preview-only books are PREVIEW_ONLY and not downloadable."""
    rights, access = classify_rights_and_access(
        ebook_access="preview",
        is_preview=True,
        download_urls=["https://books.google.com/books/content?id=123&preview=1"],
    )
    assert access is AccessMode.PREVIEW_ONLY
    assert rights is RightsStatus.UNKNOWN


def test_open_download_with_cc_license() -> None:
    """Open license + download URL yields OPEN_DOWNLOAD and download_allowed True."""
    rights, access = classify_rights_and_access(
        download_urls=["https://directory.doabooks.org/rest/bitstreams/123/retrieve"],
        license_text="Creative Commons Attribution (CC BY 4.0)",
    )
    assert rights is RightsStatus.OPEN_LICENSE
    assert access is AccessMode.OPEN_DOWNLOAD

    source = source_from_dict(
        {
            "title": "Open Book",
            "download_urls": ["https://directory.doabooks.org/rest/bitstreams/123/retrieve"],
            "license": "Creative Commons Attribution (CC BY 4.0)",
        },
        origin="doab",
        source_type_hint=SourceType.BOOK,
    )
    assert source.access_mode is AccessMode.OPEN_DOWNLOAD
    assert source.rights_status is RightsStatus.OPEN_LICENSE
    assert source.download_allowed is True


def test_public_domain_allows_download() -> None:
    """Public domain books with download links allow download."""
    rights, access = classify_rights_and_access(
        download_urls=["https://archive.org/download/book/book.pdf"],
        license_text="Public Domain Mark 1.0",
    )
    assert rights is RightsStatus.PUBLIC_DOMAIN
    assert access is AccessMode.OPEN_DOWNLOAD

    source = source_from_dict(
        {
            "title": "Classic 1900 Book",
            "download_urls": ["https://archive.org/download/book/book.pdf"],
            "license": "Public Domain Mark 1.0",
        },
        origin="open_library",
    )
    assert source.download_allowed is True


def test_pdf_extension_alone_does_not_imply_open_download() -> None:
    """Merely having .pdf in the URL does not confer open access rights."""
    rights, access = classify_rights_and_access(
        download_urls=["https://publisher.com/article.pdf"],
        license_text="All rights reserved. Unauthorized copying prohibited.",
    )
    assert rights is RightsStatus.RESTRICTED
    assert access is not AccessMode.OPEN_DOWNLOAD

    source = source_from_dict(
        {
            "title": "Commercial PDF",
            "download_urls": ["https://publisher.com/article.pdf"],
            "license": "All rights reserved. Unauthorized copying prohibited.",
        },
        origin="web",
    )
    assert source.download_allowed is False
