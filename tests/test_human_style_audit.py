"""Tests for human-doc-output-guard and HumanStyleAuditAgent."""

from __future__ import annotations

import json
from pathlib import Path

from src.agents.audit import (
    AI_STYLE_CLICHE_PHRASES,
    HumanStyleAuditAgent,
    HumanStyleAuditRequest,
    NaturalStudentOutputGuard,
    sanitize_student_text,
)
from src.schemas.project import Project, ProjectArtifact
from src.schemas.source import Source


def _project(tmp_path: Path) -> Project:
    path = tmp_path / "project"
    path.mkdir(parents=True, exist_ok=True)
    return Project(name="project", workspace="tmp", path=str(path), title="Studi Kasus Pembelajaran")


def test_human_style_audit_passes_clean_draft(tmp_path: Path) -> None:
    project = _project(tmp_path)
    source = Source(title="Media Pembelajaran", authors=["Sari, D."], year=2023)
    draft = (
        "# Studi Kasus Pembelajaran\n\n"
        "## Pendahuluan\n\n"
        "Penggunaan media pembelajaran web membantu interaksi perkuliahan (Sari, 2023).\n"
        "Mahasiswa dapat mengulang materi secara mandiri di rumah.\n\n"
        "| No | Indikator | Nilai |\n"
        "|---|---|---|\n"
        "| 1 | Kehadiran | 92% |\n"
        "| 2 | Ketuntasan | 88% |\n\n"
        "## References\n\n"
        "- Sari, D. (2023). Media Pembelajaran.\n"
    )

    response = HumanStyleAuditAgent().execute(
        HumanStyleAuditRequest(
            project=project,
            draft=draft,
            sources=[source],
            requested_sections=["Pendahuluan"],
        )
    )

    assert response.passed is True
    assert response.ai_style_detected is False
    assert response.unrequested_additions == []
    assert response.excessive_structure is False
    assert response.complex_tables is False
    assert response.fabricated_sources_or_data is False

    audit_file = project.artifact_path(ProjectArtifact.HUMAN_STYLE_AUDIT)
    assert audit_file.is_file()
    payload = json.loads(audit_file.read_text(encoding="utf-8"))
    assert payload["passed"] is True


def test_human_style_audit_detects_ai_cliche_markers(tmp_path: Path) -> None:
    project = _project(tmp_path)
    draft = (
        "# Analisis Kebijakan\n\n"
        "Secara komprehensif, dalam konteks ini penting untuk digarisbawahi bahwa "
        "kebijakan tersebut memiliki peran yang sangat signifikan. "
        "Berdasarkan uraian di atas, inovasi ini sangat krusial.\n"
    )

    response = HumanStyleAuditAgent().execute(
        HumanStyleAuditRequest(project=project, draft=draft)
    )

    assert response.passed is False
    assert response.ai_style_detected is True
    assert "secara komprehensif" in response.ai_style_markers
    assert "dalam konteks ini" in response.ai_style_markers
    assert "penting untuk digarisbawahi" in response.ai_style_markers
    assert len(response.remediation_suggestions) >= 3


def test_human_style_audit_detects_unrequested_additions(tmp_path: Path) -> None:
    project = _project(tmp_path)
    draft = (
        "# Judul Tugas\n\n"
        "## Pendahuluan\n\n"
        "Ini bagian pendahuluan.\n\n"
        "## Bab Tambahan Yang Tidak Diminta Pengguna\n\n"
        "Bagian ini ditambahkan sepihak oleh model.\n"
    )

    response = HumanStyleAuditAgent().execute(
        HumanStyleAuditRequest(
            project=project,
            draft=draft,
            requested_sections=["Pendahuluan"],
        )
    )

    assert response.passed is False
    assert len(response.unrequested_additions) >= 1
    assert any("Bab Tambahan Yang Tidak Diminta Pengguna" in item for item in response.unrequested_additions)


def test_human_style_audit_detects_callout_alerts(tmp_path: Path) -> None:
    project = _project(tmp_path)
    draft = (
        "# Laporan Tugas\n\n"
        "> [!NOTE]\n"
        "> Ini adalah callout box dekoratif ala pamflet.\n"
    )

    response = HumanStyleAuditAgent().execute(
        HumanStyleAuditRequest(project=project, draft=draft)
    )

    assert response.passed is False
    assert any("Callout box dekoratif" in item for item in response.unrequested_additions)


def test_human_style_audit_detects_excessive_structure(tmp_path: Path) -> None:
    project = _project(tmp_path)
    # 1. Deep headings test
    deep_draft = (
        "# Bab 1\n\n"
        "## Subbab 1.1\n\n"
        "### Sub-subbab 1.1.1\n\n"
        "#### Sub-sub-subbab 1.1.1.1 Terlalu Dalam\n\n"
        "Teks terlalu terpecah-pecah.\n"
    )
    response_deep = HumanStyleAuditAgent().execute(
        HumanStyleAuditRequest(project=project, draft=deep_draft)
    )
    assert response_deep.passed is False
    assert response_deep.excessive_structure is True
    assert any("Heading terlalu dalam" in d for d in response_deep.excessive_structure_details)

    # 2. Bullet overload test (>60% bullets in long text)
    bullet_draft = "\n".join([f"- Poin nomor {i} berisi catatan singkat" for i in range(20)])
    response_bullet = HumanStyleAuditAgent().execute(
        HumanStyleAuditRequest(project=project, draft=bullet_draft)
    )
    assert response_bullet.passed is False
    assert response_bullet.excessive_structure is True
    assert any("didominasi poin-poin" in d for d in response_bullet.excessive_structure_details)


def test_human_style_audit_detects_complex_tables(tmp_path: Path) -> None:
    project = _project(tmp_path)
    # Table with 6 columns (default max 4) and unrequested AI rating column
    table_draft = (
        "# Perbandingan\n\n"
        "| No | Aspek | Model A | Model B | Variabel X | Skor AI (1-10) |\n"
        "|---|---|---|---|---|---|\n"
        "| 1 | Akurasi | 90% | 85% | Signifikan | 9.5 |\n"
    )

    response = HumanStyleAuditAgent().execute(
        HumanStyleAuditRequest(project=project, draft=table_draft, max_table_cols=4)
    )

    assert response.passed is False
    assert response.complex_tables is True
    assert any("melebihi batas wajar" in d for d in response.complex_table_details)
    assert any("analisis subjektif AI tidak diminta" in d for d in response.complex_table_details)


def test_human_style_audit_detects_fabricated_dois_and_tokens(tmp_path: Path) -> None:
    project = _project(tmp_path)
    draft = (
        "# Riset\n\n"
        "Temuan ini merujuk pada https://doi.org/10.9999/fake-paper-doi "
        "dan kutipan turn0search3 yang belum bersih. (Wibowo, 2029)\n"
    )

    response = HumanStyleAuditAgent().execute(
        HumanStyleAuditRequest(project=project, draft=draft, sources=[])
    )

    assert response.passed is False
    assert response.fabricated_sources_or_data is True
    assert any("DOI fiktif" in d for d in response.fabricated_details)
    assert any("Token internal AI" in d for d in response.fabricated_details)
    assert any("Sitasi yatim" in d for d in response.fabricated_details)


def test_sanitize_student_text() -> None:
    raw_text = (
        "Secara komprehensif, dalam konteks ini penting untuk digarisbawahi bahwa "
        "metode ini memiliki peran yang sangat signifikan.\n"
        "> [!NOTE]\n"
        "> Catatan penting ini harus tetap ada."
    )
    cleaned = sanitize_student_text(raw_text)

    assert "Secara komprehensif" not in cleaned
    assert "secara menyeluruh" in cleaned
    assert "dalam konteks ini" not in cleaned
    assert "berperan penting" in cleaned
    assert "[!NOTE]" not in cleaned
    assert "> Catatan penting" in cleaned


def test_natural_student_output_guard_alias() -> None:
    assert NaturalStudentOutputGuard is HumanStyleAuditAgent


def test_skills_and_steering_files_exist() -> None:
    root = Path(__file__).resolve().parent.parent

    skill_file = root / "skills" / "human-doc-output-guard" / "SKILL.md"
    assert skill_file.is_file(), "human-doc-output-guard/SKILL.md must exist"

    content = skill_file.read_text(encoding="utf-8").lower()
    assert "human-doc-output-guard" in content
    assert "ikuti instruksi pengguna secara sempit" in content
    assert "jaga gaya bahasa manusia / mahasiswa" in content
    assert "jangan mengarang" in content
    assert "jaga format dokumen docx" in content
    assert "jaga output tabel & spreadsheet" in content
    assert "jangan seperti ai" in content

    ref_dir = root / "skills" / "human-doc-output-guard" / "references"
    assert (ref_dir / "student-style-guide.md").is_file()
    assert (ref_dir / "docx-and-table-guard.md").is_file()
    assert (ref_dir / "audit-checklist.md").is_file()

    # Workspace steering file
    steering_file = root.parent / ".kiro" / "steering" / "human-doc-output-guard.md"
    assert steering_file.is_file(), ".kiro/steering/human-doc-output-guard.md must exist"
