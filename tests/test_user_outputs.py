from pathlib import Path
import json
import zipfile

from openpyxl import load_workbook

from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow
from src.workflows.export_bundle import export_bundle
from src.workflows.user_outputs import plan_outputs, work_report
from src.schemas.source import Source
from src.workflows.deep_research import DeepResearchRequest, DeepResearchWorkflow
from test_workflow_audit_repairs import bundle, project_at


def test_two_outputs_and_export(tmp_path):
    project = project_at(tmp_path)
    sources, claims, evidence, outline = bundle(project.directory)
    response = AcademicWritingWorkflow().execute(AcademicWritingRequest(
        project=project, sources=sources, claims=claims, evidence=evidence, outline=outline))
    assert response.success
    first = Path(response.metadata["findings_workbook_path"])
    second = Path(response.metadata["work_report_path"])
    assert first.is_file() and second.is_file()
    wb = load_workbook(first, data_only=True)
    assert wb.worksheets[0].cell(6, 2).value == sources[0].title
    wb.close()
    report = load_workbook(second, data_only=True)
    assert report.active.cell(3, 2).value in {"Selesai", "Sebagian selesai"}
    report.close()
    summary = json.loads((Path(response.run_dir) / "run_summary.json").read_text(encoding="utf-8"))
    assert summary["work_report_path"] == str(second)
    exported = export_bundle(project.directory, run_id=response.run_id)
    assert exported["success"]
    with zipfile.ZipFile(exported["bundle_path"]) as archive:
        assert {"review_output/hasil_temuan.xlsx", "review_output/laporan_pekerjaan.xlsx"} <= set(archive.namelist())


def test_plan_without_sources_and_formula_text(tmp_path):
    project = project_at(tmp_path)
    outputs = plan_outputs(project, {"queries": ["contoh"]})
    wb = load_workbook(outputs["findings_workbook_path"])
    assert "Belum ada sumber" in wb.worksheets[0].cell(2, 1).value
    wb.close()


def test_research_partial_preserves_all_found_sources(tmp_path):
    project = project_at(tmp_path)
    sources = [Source(title=f"Artikel uji {index}") for index in range(3)]
    response = DeepResearchWorkflow().execute(DeepResearchRequest(
        project=project, user_request="uji", sources=sources, min_sources=2, max_sources=1))
    assert response.metadata["result_status"] == "PARTIAL"
    wb = load_workbook(response.metadata["findings_workbook_path"], data_only=True)
    assert {wb.worksheets[0].cell(row, 2).value for row in range(6, 9)} == {s.title for s in sources}
    wb.close()
    report = load_workbook(response.metadata["work_report_path"], data_only=True)
    assert report.active.cell(3, 2).value == "Sebagian selesai"
    report.close()
    path = work_report(tmp_path / "report.xlsx", purpose="=2+2", status="PARTIAL",
                       stages=[], findings=0, problems=["Belum selesai"], outputs=[])
    wb = load_workbook(path)
    assert wb.active.cell(2, 2).value == "=2+2" and wb.active.cell(2, 2).data_type == "s"
    assert wb.active.cell(3, 2).value == "Sebagian selesai"
    wb.close()
