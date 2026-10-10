"""Page-aware PDF parser for academic documents and books (Bagian E).

Specification anchors:
  * AGENT_CONSTITUTION.md §8-9: never fabricate evidence, page numbers, or locations.
  * Bagian E: Output must preserve page numbers and offsets; plain text PDF support;
    mark scanned PDFs as OCR_REQUIRED without guessing text.
"""

from __future__ import annotations

import io
import re
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    if len(sys.argv) > 2:
        sys.path.insert(0, sys.argv[2])
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pydantic import BaseModel, Field
from pypdf import PdfReader
from src.schemas.evidence import EvidenceLocation

MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PDF_PAGES = 1000
MAX_PDF_TEXT = 5_000_000
PDF_TIMEOUT = 30
PDF_MEMORY_BYTES = 512 * 1024 * 1024

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
    text_status: str = "READABLE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "text": self.text,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "page_label": self.page_label or f"p. {self.page}",
            "text_status": self.text_status,
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
    unreadable_pages: list[int] = Field(default_factory=list)
    parser_version: str = Field(default_factory=lambda: sys.modules["pypdf"].__version__)


class PDFParserTool:
    """Extract page-indexed text from PDF without OCR, preserving provenance."""

    def parse(self, source: bytes | str | Path) -> PDFParseResult:
        """Parse a PDF from raw bytes or a file path."""
        process, job = None, None
        try:
            if isinstance(source, (str, Path)):
                with Path(source).open("rb") as stream:
                    content = stream.read(MAX_PDF_BYTES + 1)
            else:
                content = source
            if not content or len(content) > MAX_PDF_BYTES:
                raise ValueError("PDF content is empty or exceeds byte limit")
            # ponytail: one bounded worker per parse; reuse a pool only if measured startup cost matters.
            # Windows venv executables launch a second process; use the base interpreter
            # with this environment's installed packages so the single-process job is enforceable.
            packages = str(Path(sys.modules["pypdf"].__file__).resolve().parents[1])
            process = subprocess.Popen([getattr(sys, "_base_executable", sys.executable), "-I",
                str(Path(__file__).resolve()), "--worker", packages],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                env={k: v for k, v in os.environ.items() if k in {"SystemRoot", "WINDIR", "TEMP", "TMP"}},
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if os.name == "nt":
                job = _limit_windows_worker(process)
            raw, _ = process.communicate(content, timeout=PDF_TIMEOUT)
            if process.returncode or not raw:
                raise ValueError("PDF worker failed or exceeded resource limits")
            return PDFParseResult.model_validate_json(raw)
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            return PDFParseResult(success=False, error_message=f"Failed to parse PDF: {exc}")
        finally:
            if process is not None and process.poll() is None:
                process.kill()
                process.wait()
            if job is not None:
                import ctypes
                kernel = ctypes.WinDLL("kernel32")
                kernel.CloseHandle.argtypes = [ctypes.c_void_p]
                kernel.CloseHandle(job)

    def _parse_local(self, source: bytes) -> PDFParseResult:
        """Worker-only extraction: byte, page and text ceilings are enforced."""
        try:
            content = source
            if not content or len(content) > MAX_PDF_BYTES:
                return PDFParseResult(
                    success=False,
                    error_message="PDF content is empty or exceeds byte limit",
                )

            stream = io.BytesIO(content)
            reader = PdfReader(stream)
            total_pages = len(reader.pages)
            if total_pages > MAX_PDF_PAGES:
                raise ValueError("PDF page limit exceeded")

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
            unreadable = []

            for idx, page in enumerate(reader.pages, start=1):
                raw_text = page.extract_text() or ""
                clean_text = raw_text.strip()
                if offset + len(clean_text) > MAX_PDF_TEXT:
                    raise ValueError("PDF text limit exceeded")
                if clean_text:
                    has_text = True
                else:
                    unreadable.append(idx)

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
                        text_status="READABLE" if clean_text else "OCR_REQUIRED_OR_BLANK",
                    )
                )
                full_parts.append(clean_text)
                # Next page starts after page separator
                offset = char_end + 2

            full_text = "\n\n".join(full_parts) if has_text else ""

            ocr_required = bool(unreadable)
            return PDFParseResult(
                success=True,
                pages=pages,
                total_pages=total_pages,
                full_text=full_text,
                has_text_layer=has_text,
                ocr_required=ocr_required,
                unreadable_pages=unreadable,
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

        match = re.search(r"\s+".join(re.escape(word) for word in norm_needle.split()), p_text)
        if match:
            offset = item.char_start if isinstance(item, PageRecord) else item.get("char_start", 0)
            return EvidenceLocation(
                page=p_num,
                page_label=p_label or (f"p. {p_num}" if p_num else None),
                locator=f"p. {p_num}" if p_num else None,
                char_start=offset + match.start(),
                char_end=offset + match.end(),
            )
    return None


def _limit_windows_worker(process):
    """Native Job Object bounds worker commit memory, CPU time and process count."""
    import ctypes as c
    from ctypes import wintypes as w

    class Basic(c.Structure):
        _fields_ = [("process_time", c.c_int64), ("job_time", c.c_int64), ("flags", w.DWORD),
                    ("min_working_set", c.c_size_t), ("max_working_set", c.c_size_t),
                    ("active_processes", w.DWORD), ("affinity", c.c_size_t),
                    ("priority", w.DWORD), ("scheduling", w.DWORD)]

    class IO(c.Structure):
        _fields_ = [(name, c.c_uint64) for name in ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]

    class Extended(c.Structure):
        _fields_ = [("basic", Basic), ("io", IO), ("process_memory", c.c_size_t),
                    ("job_memory", c.c_size_t), ("peak_process", c.c_size_t), ("peak_job", c.c_size_t)]

    kernel = c.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise OSError(c.get_last_error(), "Cannot create PDF resource job")
    limits = Extended()
    limits.basic.flags = 0x2 | 0x8 | 0x100 | 0x2000  # CPU, process count, memory, kill-on-close
    limits.basic.process_time = PDF_TIMEOUT * 10_000_000
    limits.basic.active_processes = 1
    limits.process_memory = PDF_MEMORY_BYTES
    if (not kernel.SetInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits))
            or not kernel.AssignProcessToJobObject(job, w.HANDLE(int(process._handle)))):
        error = c.get_last_error()
        kernel.CloseHandle(job)
        raise OSError(error, "Cannot enforce PDF worker limits")
    return job


if __name__ == "__main__":
    if os.name != "nt":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (PDF_MEMORY_BYTES, PDF_MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (PDF_TIMEOUT, PDF_TIMEOUT))
    result = PDFParserTool()._parse_local(sys.stdin.buffer.read(MAX_PDF_BYTES + 1))
    sys.stdout.write(result.model_dump_json())
