"""Fast tests for roadmap Phase 13 DOCX generation."""

from __future__ import annotations

from pathlib import Path

from docx import Document

from src.schemas.citation import ReferenceEntry, ReferenceList
from src.schemas.project import Project
from src.tools.docx_generator import DocxGenerationRequest, DocxGenerationTool


def _project(tmp_path: Path) -> Project:
    path = tmp_path / "project"
    path.mkdir()
    return Project(name="project", workspace="tmp", path=str(path), title="Test")


def test_docx_generation_requires_passed_audits(tmp_path: Path) -> None:
    response = DocxGenerationTool().execute(
        DocxGenerationRequest(
            project=_project(tmp_path),
            draft="# Title",
            citation_audit_passed=False,
            fact_audit_passed=True,
        )
    )
    assert response.success is False
    assert response.error_code == "AUDIT_NOT_PASSED"


def test_docx_generation_writes_readable_docx(tmp_path: Path) -> None:
    refs = ReferenceList(
        entries=[
            ReferenceEntry(
                citation_key="smith2024",
                source_id="src_1",
                formatted="Smith, J. (2024). Paper. Journal. https://doi.org/10.1/x",
            )
        ]
    )
    response = DocxGenerationTool().execute(
        DocxGenerationRequest(
            project=_project(tmp_path),
            draft="# Title\n\n## Findings\n\nThe program improved attendance.",
            reference_list=refs,
            citation_audit_passed=True,
            fact_audit_passed=True,
        )
    )
    assert response.success is True
    assert response.docx_path is not None
    doc = Document(response.docx_path)
    assert [p.text for p in doc.paragraphs if p.text][:2] == ["Title", "Findings"]
