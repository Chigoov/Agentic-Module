"""Offline unit tests for PDFParserTool and page-based evidence extraction."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

from src.schemas.evidence import EvidenceLocation
from src.tools.evidence_extractor import EvidenceExtractor
from src.tools.pdf_parser import PDFParserTool, find_passage_page_location, parse_pdf_pages


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    writer = PdfWriter()
    # Page 1
    writer.add_blank_page(width=300, height=300)
    # Page 2
    writer.add_blank_page(width=300, height=300)
    stream = io.BytesIO()
    writer.write(stream)
    return stream.getvalue()


@pytest.fixture
def text_pdf_path(tmp_path: Path) -> Path:
    """Create a minimal 2-page PDF with extractable text."""
    # We can write a PDF using pypdf or minimal raw PDF syntax
    # Minimal PDF syntax with 2 pages and stream text:
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >> endobj\n"
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 5 0 R /Resources << /Font << /F1 7 0 R >> >> >> endobj\n"
        b"4 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 6 0 R /Resources << /Font << /F1 7 0 R >> >> >> endobj\n"
        b"5 0 obj << /Length 44 >> stream\nBT /F1 12 Tf 50 250 Td (First page intro evidence.) Tj ET\nendstream endobj\n"
        b"6 0 obj << /Length 45 >> stream\nBT /F1 12 Tf 50 250 Td (Second page statistical finding.) Tj ET\nendstream endobj\n"
        b"7 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n"
        b"xref\n0 8\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \n0000000236 00000 n \n0000000357 00000 n \n0000000452 00000 n \n0000000548 00000 n \n"
        b"trailer << /Size 8 /Root 1 0 R >>\nstartxref\n628\n%%EOF\n"
    )
    file_path = tmp_path / "sample_doc.pdf"
    file_path.write_bytes(pdf_content)
    return file_path


def test_pdf_parser_extracts_page_records(text_pdf_path: Path) -> None:
    tool = PDFParserTool()
    result = tool.parse(text_pdf_path)

    assert result.success is True
    assert result.total_pages == 2
    assert result.has_text_layer is True
    assert result.ocr_required is False

    pages = result.pages
    assert len(pages) == 2
    assert pages[0].page == 1
    assert "First page intro evidence." in pages[0].text
    assert pages[1].page == 2
    assert "Second page statistical finding." in pages[1].text


def test_parse_pdf_pages_dict_contract(text_pdf_path: Path) -> None:
    page_dicts = parse_pdf_pages(text_pdf_path)
    assert len(page_dicts) == 2
    assert page_dicts[0]["page"] == 1
    assert "char_start" in page_dicts[0]
    assert "char_end" in page_dicts[0]
    assert "page_label" in page_dicts[0]
    assert "First page intro evidence." in page_dicts[0]["text"]


def test_find_passage_page_location_locates_correct_page(text_pdf_path: Path) -> None:
    pages = parse_pdf_pages(text_pdf_path)

    loc1 = find_passage_page_location("First page intro evidence.", pages)
    assert loc1 is not None
    assert loc1.page == 1
    assert loc1.page_label == "p. 1"
    assert loc1.locator == "p. 1"

    loc2 = find_passage_page_location("Second page statistical finding.", pages)
    assert loc2 is not None
    assert loc2.page == 2
    assert loc2.page_label == "p. 2"
    assert loc2.locator == "p. 2"

    # Non-existent passage returns None, never guesses page number
    loc_missing = find_passage_page_location("Non-existent text here", pages)
    assert loc_missing is None


def test_scanned_pdf_flags_ocr_required_without_faking_text(sample_pdf_bytes: bytes) -> None:
    tool = PDFParserTool()
    result = tool.parse(sample_pdf_bytes)

    assert result.success is True
    assert result.total_pages == 2
    assert result.has_text_layer is False
    assert result.ocr_required is True
    assert result.full_text == ""
    assert "OCR_REQUIRED" in (result.error_message or "")


def test_empty_bytes_fails_gracefully() -> None:
    tool = PDFParserTool()
    result = tool.parse(b"")
    assert result.success is False
    assert "empty" in (result.error_message or "").lower()


def test_blank_page_preserves_following_page_offsets(text_pdf_path):
    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    for page in PdfReader(text_pdf_path).pages:
        writer.add_page(page)
    stream = io.BytesIO(); writer.write(stream)
    result = PDFParserTool().parse(stream.getvalue())
    assert result.success and result.total_pages == 3
    for page in result.pages:
        assert result.full_text[page.char_start:page.char_end] == page.text
