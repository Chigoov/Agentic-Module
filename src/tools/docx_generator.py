"""DOCX generation tool for roadmap Phase 13."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from docx import Document

from src.core.storage import backup_file
from src.schemas.citation import ReferenceList
from src.schemas.project import Project, ProjectArtifact
from src.tools.base import BaseTool, ToolRequest, ToolResponse

__all__ = ["DocxGenerationRequest", "DocxGenerationResponse", "DocxGenerationTool"]


class DocxGenerationRequest(ToolRequest):
    project: Project
    draft: str
    reference_list: ReferenceList | None = None
    citation_audit_passed: bool
    fact_audit_passed: bool


class DocxGenerationResponse(ToolResponse):
    docx_path: str | None = None
    backup_path: str | None = None


class DocxGenerationTool(BaseTool[DocxGenerationRequest, DocxGenerationResponse]):
    response_model = DocxGenerationResponse
    tool_name = "docx_generation"

    def _execute(self, request: DocxGenerationRequest) -> DocxGenerationResponse:
        if not (request.citation_audit_passed and request.fact_audit_passed):
            return DocxGenerationResponse.failure(
                error_code="AUDIT_NOT_PASSED",
                error_message="DOCX generation requires passed citation and fact audits",
            )

        path = request.project.artifact_path(ProjectArtifact.FINAL_DOCX)
        backup = backup_file(path, root=request.project.directory)
        doc = Document()
        self._add_markdown(doc, request.draft)
        if request.reference_list and request.reference_list.entries:
            doc.add_heading("References", level=1)
            for entry in request.reference_list.entries:
                doc.add_paragraph(entry.formatted)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        # Atomic save (audit A05): write to a sibling temp file first, then
        # replace, so a crash mid-save cannot corrupt the previous final.docx.
        # mkstemp opens an fd that must be closed *before* doc.save reuses the
        # name on Windows, and the saved package must be closed before replace.
        fd, temp_name = tempfile.mkstemp(
            dir=str(Path(path).parent), prefix=f".{Path(path).name}.", suffix=".tmp"
        )
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            doc.save(str(temp_path))
            os.replace(temp_path, Path(path))
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
        return DocxGenerationResponse(docx_path=str(path), backup_path=str(backup) if backup else None)

    @staticmethod
    def _add_markdown(doc: Document, text: str) -> None:
        # The draft carries its own "## References" section (single ID→label
        # mapping for the Markdown package). When a structured reference list
        # is supplied, the DOCX appends its own References heading, so the
        # draft's copy is skipped here to avoid a duplicated bibliography.
        in_draft_references = False
        lines = text.splitlines()
        index = 0
        while index < len(lines):
            raw = lines[index]
            line = raw.strip()
            if not line:
                index += 1
                continue
            if line.startswith("## References"):
                in_draft_references = True
                index += 1
                continue
            if in_draft_references:
                if line.startswith("- "):
                    index += 1
                    continue  # draft bibliography bullet; DOCX adds its own
                in_draft_references = False
            if DocxGenerationTool._is_table_start(lines, index):
                index = DocxGenerationTool._add_markdown_table(doc, lines, index)
                continue
            if line.startswith("# "):
                doc.add_heading(line[2:].strip(), level=0)
            elif line.startswith("## "):
                doc.add_heading(line[3:].strip(), level=1)
            elif line.startswith("### "):
                doc.add_heading(line[4:].strip(), level=2)
            elif line.startswith("> "):
                paragraph = doc.add_paragraph(line[2:].strip())
                paragraph.style = "Quote"
            else:
                doc.add_paragraph(line)
            index += 1

    @staticmethod
    def _is_table_start(lines: list[str], index: int) -> bool:
        return (
            index + 1 < len(lines)
            and DocxGenerationTool._is_table_row(lines[index])
            and DocxGenerationTool._is_separator_row(lines[index + 1])
        )

    @staticmethod
    def _add_markdown_table(doc: Document, lines: list[str], index: int) -> int:
        header = DocxGenerationTool._split_table_row(lines[index])
        table = doc.add_table(rows=1, cols=len(header))
        table.style = "Table Grid"
        for cell, value in zip(table.rows[0].cells, header):
            cell.text = value
        index += 2
        while index < len(lines) and DocxGenerationTool._is_table_row(lines[index]):
            values = DocxGenerationTool._split_table_row(lines[index])
            row = table.add_row().cells
            for column, cell in enumerate(row):
                cell.text = values[column] if column < len(values) else ""
            index += 1
        return index

    @staticmethod
    def _is_table_row(line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("|") and stripped.endswith("|") and stripped.count("|") >= 2

    @staticmethod
    def _is_separator_row(line: str) -> bool:
        cells = DocxGenerationTool._split_table_row(line)
        if not cells:
            return False
        for cell in cells:
            marker = cell.strip().replace(":", "")
            if len(marker) < 3 or set(marker) != {"-"}:
                return False
        return True

    @staticmethod
    def _split_table_row(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]
