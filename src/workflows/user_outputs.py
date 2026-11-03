"""The two user-facing spreadsheets for an AAI execution."""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

from src.schemas.source import Source
from src.tools.quantitative_review_workbook import build_quantitative_review_workbook, source_to_review_record

_STAGES = {
    "deep_plan": "persiapan riset", "task_analysis": "memahami permintaan", "planning": "menyusun rencana",
    "discovery": "mencari sumber", "deduplication": "memeriksa sumber ganda", "ranking": "mengurutkan sumber",
    "verification": "memeriksa metadata", "access_check": "memeriksa akses", "retrieval": "mengambil sumber",
    "evidence_extraction": "mencatat bukti", "claim_verification": "memeriksa klaim", "conflict_detection": "memeriksa perbedaan temuan",
    "synthesis": "merangkum temuan", "outline": "menyusun kerangka", "writing": "menulis draf",
    "humanizer": "merapikan bahasa", "citation_audit": "memeriksa sitasi", "fact_audit": "memeriksa fakta",
    "docx_generation": "membuat dokumen", "quantitative_review_workbook": "menyusun review artikel", "human_review": "meminta pemeriksaan manusia",
}


def findings_workbook(directory: Path, sources: list[dict], *, existing: str | None = None, template: str | None = None) -> str:
    if existing:
        return existing
    records = [source_to_review_record(Source.model_validate(source)) for source in sources]
    result = build_quantitative_review_workbook(records, directory / "hasil_temuan.xlsx", template_path=template)
    return result.workbook_path


def work_report(path: Path, *, purpose: str, status: str, stages: list[str], findings: int,
                problems: list[str], outputs: list[str], plan: str = "") -> str:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Ringkasan"
    rows = [
        ("Tujuan", purpose or "Tidak tercatat"),
        ("Status", {"PASS": "Selesai", "PARTIAL": "Sebagian selesai", "FAILED": "Gagal"}.get(status, status)),
        ("Pekerjaan", ", ".join(_STAGES.get(stage, stage.replace("_", " ")) for stage in stages) or "Belum ada tahapan tercatat"),
        ("Hasil", plan or f"{findings} sumber tercatat. " + (", ".join(outputs) if outputs else "Belum ada hasil lain tercatat.")),
        ("Kendala", "\n".join(problems) if problems else "Tidak ada kendala yang tercatat."),
        ("Langkah berikutnya", "Tinjau dan selesaikan kendala yang tercatat." if problems or status != "PASS" else "Periksa hasil sebelum digunakan."),
    ]
    sheet.append(["Bagian", "Keterangan"])
    for label, value in rows:
        sheet.append([label, str(value)])
        # Treat user- and provider-supplied text as text, never as Excel formulas.
        sheet.cell(sheet.max_row, 2).data_type = "s"
    sheet.column_dimensions["A"].width = 23
    sheet.column_dimensions["B"].width = 90
    sheet.freeze_panes = "B2"
    for cell in sheet[1]:
        cell.font = Font(bold=True)
    for row in sheet.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for index in range(2, len(rows) + 2):
        value = sheet.cell(index, 2).value
        lines = sum(max(1, (len(line) + 85) // 86) for line in value.splitlines())
        sheet.row_dimensions[index].height = min(409, max(30, lines * 16 + 8))
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.xlsx")
    workbook.save(temporary)
    workbook.close()
    temporary.replace(path)
    return str(path)


def plan_outputs(project, plan: dict) -> dict[str, str]:
    directory = project.directory / "hasil"
    first = findings_workbook(directory, [])
    second = work_report(directory / "laporan_pekerjaan.xlsx", purpose=project.user_request,
                         status="PASS", stages=["Menyusun rencana"], findings=0,
                         problems=["Pencarian sumber belum dilakukan pada tahap perencanaan."],
                         outputs=[], plan="Rencana dibuat. Kata kunci pencarian: " + "; ".join(plan.get("queries", [])))
    return {"findings_workbook_path": first, "work_report_path": second}
