"""Page-aware PDF parser for academic documents and books (Bagian E).

Specification anchors:
  * AGENT_CONSTITUTION.md §8-9: never fabricate evidence, page numbers, or locations.
  * Bagian E: Output must preserve page numbers and offsets; plain text PDF support;
    mark scanned PDFs as OCR_REQUIRED without guessing text.
"""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pypdf import PdfReader

from src.schemas.evidence import EvidenceLocation

__all__ = [
    "PageRecord",
    "PDFParseResult",
    "PDFParserTool",
    "parse_pdf_pages",
    "find_passage_page_location",
]


def _normalize_ws(text: str) -> str:
    return " ".join(text.split())


class PageRecord(BaseModel):
    """Extracted text and character offsets for a single PDF page."""

    page: int = Field(ge=1, description="1-indexed real page number from PDF document")
    text: str = Field(default="")
    char_start: int = Field(ge=0, default=0)
    char_end: int = Field(ge=0, default=0)
    page_label: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "text": self.text,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "page_label": self.page_label or f"p. {self.page}",
        }


class PDFParseResult(BaseModel):
    """Structured result of parsing a PDF document."""

    success: bool = True
    pages: list[PageRecord] = Field(default_factory=list)
    total_pages: int = 0
    full_text: str = ""
    has_text_layer: bool = False
    ocr_required: bool = False
    error_message: str | None = None


class PDFParserTool:
    """Extract page-indexed text from PDF without OCR, preserving provenance."""

    def parse(self, source: bytes | str | Path) -> PDFParseResult:
        """Parse a PDF from raw bytes or a file path."""
        try:
            if isinstance(source, (str, Path)):
                path = Path(source)
                if not path.is_file():
                    return PDFParseResult(
                        success=False,
                        error_message=f"PDF file not found: {path}",
                    )
                content = path.read_bytes()
            else:
                content = source

            if not content:
                return PDFParseResult(
                    success=False,
                    error_message="PDF content is empty (0 bytes)",
                )

            stream = io.BytesIO(content)
            reader = PdfReader(stream)
            total_pages = len(reader.pages)

            if total_pages == 0:
                return PDFParseResult(
                    success=True,
                    total_pages=0,
                    has_text_layer=False,
                    ocr_required=True,
                    error_message="PDF has 0 pages",
                )

            pages: list[PageRecord] = []
            full_parts: list[str] = []
            offset = 0
            has_text = False

            for idx, page in enumerate(reader.pages, start=1):
                raw_text = page.extract_text() or ""
                clean_text = raw_text.strip()
                if clean_text:
                    has_text = True

                char_start = offset
                char_end = char_start + len(clean_text)
                label = f"p. {idx}"

                pages.append(
                    PageRecord(
                        page=idx,
                        text=clean_text,
                        char_start=char_start,
                        char_end=char_end,
                        page_label=label,
                    )
                )
                full_parts.append(clean_text)
                # Next page starts after page separator
                offset = char_end + 2

            full_text = "\n\n".join(full_parts) if has_text else ""

            ocr_required = not has_text
            return PDFParseResult(
                success=True,
                pages=pages,
                total_pages=total_pages,
                full_text=full_text,
                has_text_layer=has_text,
                ocr_required=ocr_required,
                error_message="OCR_REQUIRED: PDF is scanned or has no extractable text layer" if ocr_required else None,
            )
        except Exception as exc:  # noqa: BLE001
            return PDFParseResult(
                success=False,
                error_message=f"Failed to parse PDF: {exc}",
            )


def parse_pdf_pages(source: bytes | str | Path) -> list[dict[str, Any]]:
    """Convenience helper returning the list of page dicts as specified in Bagian E.

    [
        {
            "page": 1,
            "text": "...",
            "char_start": 0,
            "char_end": 500
        }
    ]
    """
    result = PDFParserTool().parse(source)
    if not result.success:
        return []
    return [p.to_dict() for p in result.pages]


def find_passage_page_location(passage: str, pages: list[PageRecord] | list[dict[str, Any]]) -> EvidenceLocation | None:
    """Find exact verbatim passage in a set of parsed PDF pages without guessing.

    Returns an EvidenceLocation with proven page number, or None if passage is absent.
    """
    norm_needle = _normalize_ws(passage)
    if not norm_needle:
        return None

    for item in pages:
        p_num = item.page if isinstance(item, PageRecord) else item.get("page")
        p_text = item.text if isinstance(item, PageRecord) else (item.get("text") or "")
        p_label = item.page_label if isinstance(item, PageRecord) else item.get("page_label")

        norm_hay = _normalize_ws(p_text)
        if norm_needle in norm_hay:
            char_idx = norm_hay.find(norm_needle)
            return EvidenceLocation(
                page=p_num,
                page_label=p_label or (f"p. {p_num}" if p_num else None),
                locator=f"p. {p_num}" if p_num else None,
                char_start=char_idx,
                char_end=char_idx + len(norm_needle),
            )
    return None
