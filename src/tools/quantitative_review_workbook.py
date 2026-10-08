"""Standard workbook writer for quantitative article reviews.

The supplied workbook is the source of truth. This module only fills its data
rows and extends the existing row pattern when more than 40 records exist.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from copy import copy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from openpyxl import load_workbook
from openpyxl.comments import Comment
from openpyxl.formula.translate import Translator
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.cell_range import CellRange

from src.schemas.source import Source, is_verified
from src.tools.source_content import inspect_record, inspect_source, stored_metadata, record_source
from src.tools.source_mapper import normalize_doi, normalize_title

__all__ = [
    "QuantitativeReviewWorkbookError",
    "QuantitativeReviewWorkbookResult",
    "build_quantitative_review_workbook",
    "source_to_review_record",
    "resolve_standard_workbook_template",
]


SHEET_NAMES = (
    "Master 40 Kuantitatif PoPCites",
    "Rubrik & Panduan Skoring",
    "Rekapitulasi & Peringkat 40",
)
MASTER_HEADERS = (
    "No.",
    "Judul penelitian",
    "Sitasi singkat",
    "Tahun",
    "Nama jurnal & publisher",
    "Akreditasi / indeksasi",
    "Populasi dan konteks",
    "Tujuan penelitian",
    "Sampel, metode, dan alat ukur",
    "Temuan utama",
    "Kekuatan artikel",
    "Keterbatasan artikel",
    "Kaitan dengan penelitian ini",
    "DOI",
    "Link halaman artikel",
    "Link PDF / full text legal",
    "Status akses",
)
RANKING_HEADERS = (
    "Peringkat",
    "No. Master",
    "Sitasi penulis & tahun",
    "Nama jurnal & penerbit",
    "Akreditasi / indeksasi",
    "Populasi & sampel (N)",
    "Desain kuantitatif",
    "Total skor",
    "Kategori kelayakan",
    "Rekomendasi bab skripsi",
)
RUBRIC_HEADERS = (
    "Pilar penilaian",
    "Bobot maks.",
    "Kriteria evaluasi",
    "Indikator skor tinggi",
    "Indikator skor sedang",
    "Indikator skor rendah",
    "Fungsi untuk skripsi",
)
MISSING = "[sumber belum lengkap]"


class QuantitativeReviewWorkbookError(ValueError):
    """Raised when the standard template or review records are unsafe."""


@dataclass(frozen=True)
class QuantitativeReviewWorkbookResult:
    workbook_path: str
    report_path: str
    manifest_path: str
    workbook_sha256: str
    workbook_size: int
    article_count: int
    ranked_count: int
    unranked_count: int
    scoring_final: bool
    status: str
    counts: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "workbook_path": self.workbook_path,
            "report_path": self.report_path,
            "manifest_path": self.manifest_path,
            "workbook_sha256": self.workbook_sha256,
            "workbook_size": self.workbook_size,
            "article_count": self.article_count,
            "ranked_count": self.ranked_count,
            "unranked_count": self.unranked_count,
            "scoring_final": self.scoring_final,
            "status": self.status,
            "counts": self.counts,
        }


def resolve_standard_workbook_template(template_path: str | Path | None = None) -> Path:
    """Resolve the user supplied standard workbook without hardcoding a user path."""
    candidates: list[Path] = []
    if template_path:
        return _checked_template(Path(template_path).expanduser())
    env_path = os.environ.get("AUTONOMI_QUANTITATIVE_REVIEW_TEMPLATE")
    if env_path:
        return _checked_template(Path(env_path).expanduser())

    here = Path(__file__).resolve()
    repo_root = here.parents[2]
    candidates.extend(
        [
            repo_root / "templates" / "Standar Baku Hasil Agent.xlsx",
            repo_root / "Standar Baku Hasil Agent.xlsx",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return _checked_template(candidate)

    # The supplied workbook normally lives under Documents/Codex. Search only
    # that bounded directory so startup never scans the whole drive.
    codex_root = Path.home() / "Documents" / "Codex"
    if codex_root.is_dir():
        matches = sorted(
            (p for p in codex_root.rglob("Standar Baku Hasil Agent.xlsx") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if matches:
            return _checked_template(matches[0])
    raise FileNotFoundError(
        "Workbook standar tidak ditemukan. Set AUTONOMI_QUANTITATIVE_REVIEW_TEMPLATE "
        "atau kirim quantitative_review_template dengan path workbook yang diberikan."
    )


def _copy_row_style(ws: Any, source_row: int, target_row: int) -> None:
    source_dim = ws.row_dimensions[source_row]
    target_dim = ws.row_dimensions[target_row]
    target_dim.height = source_dim.height
    target_dim.hidden = source_dim.hidden
    target_dim.outlineLevel = source_dim.outlineLevel
    for col in range(1, ws.max_column + 1):
        source = ws.cell(source_row, col)
        target = ws.cell(target_row, col)
        if source.has_style:
            target._style = copy(source._style)
        target.number_format = source.number_format
        target.protection = copy(source.protection)
        if isinstance(source.value, str) and source.value.startswith("="):
            try:
                target.value = Translator(source.value, origin=source.coordinate).translate_formula(target.coordinate)
            except Exception:
                target.value = source.value


def _clear_row(ws: Any, row: int, *, preserve_formulas: bool = False) -> None:
    for col in range(1, ws.max_column + 1):
        cell = ws.cell(row, col)
        if not (preserve_formulas and cell.data_type == "f"):
            cell.value = None
        cell.comment = None
        cell.hyperlink = None


def _shift_merges_for_insert(ws: Any, start_row: int, amount: int) -> None:
    if amount <= 0:
        return
    affected = list(ws.merged_cells.ranges)
    for merged in affected:
        ws.unmerge_cells(str(merged))
    ws.insert_rows(start_row, amount=amount)
    for merged in affected:
        min_col, min_row, max_col, max_row = merged.bounds
        if min_row >= start_row:
            min_row += amount
            max_row += amount
        elif max_row >= start_row:
            max_row += amount
        ws.merge_cells(start_row=min_row, start_column=min_col, end_row=max_row, end_column=max_col)


def _extend_data_block(ws: Any, *, data_start: int, footer_start: int, count: int, base_rows: tuple[int, int]) -> int:
    capacity = footer_start - data_start
    extra = max(0, count - capacity)
    if extra:
        _shift_merges_for_insert(ws, footer_start, extra)
        for index in range(extra):
            row = footer_start + index
            _copy_row_style(ws, base_rows[index % 2], row)
    for row in range(data_start, data_start + max(capacity, count)):
        if row >= data_start + count:
            _clear_row(ws, row)
    def expanded(ref):
        area = CellRange(str(ref))
        if area.min_row < footer_start and area.max_row >= footer_start - 1:
            area.max_row += extra
        elif area.min_row >= footer_start:
            area.shift(row_shift=extra)
        return str(area)
    if ws.auto_filter.ref:
        ws.auto_filter.ref = expanded(ws.auto_filter.ref)
    for table in ws.tables.values():
        table.ref = expanded(table.ref)
        if table.autoFilter:
            table.autoFilter.ref = table.ref
    for validation in ws.data_validations.dataValidation:
        validation.sqref = " ".join(expanded(area) for area in validation.sqref.ranges)
    if ws.print_area:
        ws.print_area = [expanded(area) for area in ws._print_area.ranges]
    for name in list(ws.parent.defined_names.values()) + list(ws.defined_names.values()):
        try:
            destinations = list(name.destinations)
            if destinations and all(sheet == ws.title for sheet, _ in destinations):
                quoted = ws.title.replace("'", "''")
                name.attr_text = ",".join(f"'{quoted}'!{expanded(ref)}" for _, ref in destinations)
        except (ValueError, TypeError):
            continue  # Formula-valued names are handled as formulas below.
    if extra:
        for row in ws:
            for cell in row:
                if cell.data_type == "f":
                    cell.value = re.sub(r"(\$?[A-Z]+\$?\d+:\$?[A-Z]+\$?)" + str(footer_start - 1) + r"(?!\d)",
                        lambda m: m[1] + str(footer_start - 1 + extra), cell.value)
    return footer_start + extra


def _headers(ws: Any, row: int) -> tuple[str, ...]:
    return tuple(str(ws.cell(row, col).value or "") for col in range(1, len(MASTER_HEADERS) + 1))


def _require_template(wb: Any) -> None:
    if tuple(wb.sheetnames) != SHEET_NAMES:
        raise QuantitativeReviewWorkbookError(
            f"Nama/urutan sheet template berubah: {wb.sheetnames!r}"
        )
    if _headers(wb[SHEET_NAMES[0]], 5) != MASTER_HEADERS:
        raise QuantitativeReviewWorkbookError("Header sheet master tidak sesuai template standar")
    if tuple(str(wb[SHEET_NAMES[1]].cell(4, col).value or "") for col in range(1, 8)) != RUBRIC_HEADERS:
        raise QuantitativeReviewWorkbookError("Header sheet rubrik tidak sesuai template standar")
    if tuple(wb[SHEET_NAMES[2]].cell(4, col).value or "" for col in range(1, 11)) != RANKING_HEADERS:
        raise QuantitativeReviewWorkbookError("Header sheet rekapitulasi tidak sesuai template standar")


def _checked_template(path: Path) -> Path:
    with path.open("rb") as stream:
        wb = load_workbook(stream)
        try:
            _require_template(wb)
        finally:
            wb.close()
    return path.resolve()


def _text(record: Mapping[str, Any], *keys: str, default: str = MISSING) -> Any:
    for key in keys:
        value = record.get(key)
        if value is not None and value != "":
            return value
    return default


def _bool(record: Mapping[str, Any], *keys: str) -> bool:
    return any(bool(record.get(key)) for key in keys)


def _full_text_legal(record: Mapping[str, Any]) -> bool:
    return inspect_record(record)["legal_free"]


def _full_text_read(record: Mapping[str, Any]) -> bool:
    return inspect_record(record)["fully_read"]


def _scientific_eligible(record: Mapping[str, Any]) -> bool:
    return bool(record.get("eligible", False)) and inspect_record(record)["scientific_eligible"]


def _index_row(record: Mapping[str, Any]) -> int:
    index = str(record.get("indexing", "")).casefold()
    return 12 if "sinta" in index else (13 if "q1" in index else (14 if re.search(r"q[23]", index) else 15))


def _access_status(record: Mapping[str, Any]) -> str:
    raw = str(record.get("access_status") or "").strip()
    if _bool(record, "human_review", "needs_human_review"):
        return "perlu review manusia"
    legal = _full_text_legal(record)
    read = _full_text_read(record)
    if raw.casefold() in {"full-text verified", "full text verified", "full-text berhasil dibaca"} and not read:
        return "perlu review manusia"
    if "full-text" in raw.casefold() and "legal" in raw.casefold() and not legal:
        return "perlu review manusia"
    if raw:
        if re.search(r"full[ -]?text", raw.casefold()):
            return "full-text berhasil dibaca" if read else ("full-text legal tersedia" if legal else "perlu review manusia")
        return raw
    if _bool(record, "human_review", "needs_human_review"):
        return "perlu review manusia"
    if read:
        return "full-text berhasil dibaca"
    if legal:
        return "full-text legal tersedia"
    if _bool(record, "abstract_available"):
        return "abstrak tersedia"
    source = record_source(record)
    if source and stored_metadata(source):
        return "metadata saja"
    return "belum diverifikasi"


def _validate_records(records: list[Mapping[str, Any]]) -> None:
    seen_doi: set[str] = set()
    seen_title: set[str] = set()
    for index, record in enumerate(records, 1):
        title = str(record.get("title") or record.get("judul") or "").strip().casefold()
        doi = normalize_doi(record.get("doi")) or ""
        if doi and doi in seen_doi:
            raise QuantitativeReviewWorkbookError(f"DOI duplikat pada record {index}; data tidak dihapus")
        if title and title != MISSING.casefold() and title in seen_title:
            raise QuantitativeReviewWorkbookError(f"Judul duplikat pada record {index}; data tidak dihapus")
        if doi:
            seen_doi.add(doi)
        if title:
            seen_title.add(title)
        source = record_source(record)
        if source:
            findings = []
            if title and normalize_title(title) != normalize_title(source.title):
                findings.append("record title does not match source snapshot")
            if doi and normalize_doi(doi) != normalize_doi(source.doi):
                findings.append("record DOI does not match source snapshot")
            actual_urls = {u for u in (source.url, source.landing_url) if u}
            if record.get("article_url") and actual_urls and record["article_url"] not in actual_urls:
                findings.append("article URL requires identity verification")
            if findings:
                record["needs_human_review"] = True
                record["verification_findings"] = findings


def _select_records(records, *, request_text="", exact_count=None, best_count=None):
    if exact_count is None and best_count is None:
        exact = re.search(r"\btepat\s+(\d+)\s+artikel\b", request_text.casefold())
        best = re.search(r"\b(\d+)\s+artikel\s+terbaik\b|\bartikel\s+terbaik\s+(\d+)\b", request_text.casefold())
        if exact:
            exact_count = int(exact[1])
        elif best:
            best_count = int(best[1] or best[2])
    if exact_count is not None and best_count is not None:
        raise QuantitativeReviewWorkbookError("Gunakan exact_count atau best_count, bukan keduanya")
    target = exact_count if exact_count is not None else best_count
    if target is not None and (not isinstance(target, int) or isinstance(target, bool) or target < 1):
        raise QuantitativeReviewWorkbookError("Jumlah artikel harus bilangan bulat positif")
    # Corpus stays intact; selection is applied only to verified ranking rows.
    return records, target, ({"question": "Berapa jumlah artikel terbaik yang ingin dipilih?", "options": [10, 20, 40]} if target is None and "artikel terbaik" in request_text.casefold() else None)


def source_to_review_record(source: Source) -> dict[str, Any]:
    """Map only source fields that exist; never infer article content."""
    index_names = [name for name, enabled in source.index_status.items() if enabled]
    proof = inspect_source(source)
    verified_metadata = bool(stored_metadata(source))
    legal = proof["legal_free"]
    read = proof["fully_read"]
    metadata = source.metadata or {}
    return {
        "source_snapshot": source.model_dump(mode="json"),
        "assessment": source.metadata.get("assessment"),
        "eligible": proof["scientific_eligible"],
        "version": source.metadata.get("version", "belum diverifikasi"),
        "title": source.title,
        "citation": "; ".join(source.authors) if source.authors else MISSING,
        "year": source.year if source.year is not None else MISSING,
        "journal_publisher": ", ".join(x for x in (source.venue, source.publisher) if x) or MISSING,
        "indexing": ", ".join(index_names) or MISSING,
        "population_context": metadata.get("population_context", MISSING),
        "objective": metadata.get("objective", MISSING),
        "sample_method_measure": metadata.get("sample_method_measure", MISSING),
        "main_findings": metadata.get("main_findings", MISSING),
        "strengths": metadata.get("strengths", MISSING),
        "limitations": metadata.get("limitations", MISSING),
        "relevance": metadata.get("relevance", MISSING),
        "doi": source.doi or MISSING,
        "article_url": source.landing_url or source.url or MISSING,
        "full_text_url": source.download_urls[0] if legal and source.download_urls else MISSING,
        "access_status": "full-text berhasil dibaca" if read else ("full-text legal tersedia" if legal else ("abstrak tersedia" if source.abstract else ("metadata saja" if is_verified(source.state) else "belum diverifikasi"))),
        "metadata_verified": verified_metadata,
        "full_text_legal": legal,
        "full_text_read": read,
        "human_review": source.state == "NEEDS_HUMAN_REVIEW" or (is_verified(source.state) and not verified_metadata),
        "provenance": {
            "source_id": source.id,
            "provider": source.provider,
            "provider_record_id": source.provider_record_id,
            "verification_notes": list(source.verification_notes),
        },
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _counts(records, ranked, summary, unranked_reason, *, require_free_full_text=False):
    status = [_access_status(record) for record in records]
    eligible = sum(_scientific_eligible(r) and (not require_free_full_text or _full_text_legal(r)) for r in records)
    counts = {
        "found": len(records), "deduplicated": len(records), "screened": len(records),
        "eligible": eligible,
        "scientifically_eligible": sum(_scientific_eligible(r) for r in records),
        "access_eligible": sum(_full_text_legal(r) for r in records),
        "metadata_verified": sum(bool(stored_metadata(source)) if (source := record_source(r)) else False for r in records),
        "full_text_legal": sum(_full_text_legal(r) for r in records),
        "full_text_read": sum(_full_text_read(r) for r in records),
        "abstract_only": sum(s == "abstrak tersedia" for s in status),
        "human_review": sum(_bool(r, "human_review", "needs_human_review") or s == "perlu review manusia" for r, s in zip(records, status)),
        "ranked": len(ranked), "not_ranked": len(records) - len(ranked),
        "not_ranked_reason": unranked_reason or "Lihat screening_audit.json untuk alasan tiap artikel",
        "indexing": {}, "reconciliation_findings": [],
    }
    for r in records:
        index = str(r.get("indexing") or MISSING)
        counts["indexing"][index] = counts["indexing"].get(index, 0) + 1
    summary = summary or {}
    if summary.get("search_log_path"):
        try:
            path = Path(summary["search_log_path"])
            if _sha256(path) != summary.get("search_log_sha256"):
                raise ValueError("search log checksum mismatch")
            log = json.loads(path.read_text(encoding="utf-8"))
            stages = log["records_by_stage"]
            keys = ("found", "deduplicated", "screened")
            if not log.get("recorded_at") or not log.get("origin") or any(
                not isinstance(stages[k], list) or any(not isinstance(r, dict) or not r.get("id") or not r.get("title") for r in stages[k]) for k in keys):
                raise ValueError("search stages need traceable records")
            ids = {k: [r["id"] for r in stages[k]] for k in keys}
            if not len(ids["found"]) >= len(ids["deduplicated"]) >= len(ids["screened"]) >= len(records) or any(
                len(set(ids[k])) != len(ids[k]) for k in keys[1:]) or not set(ids["screened"]).issubset(ids["deduplicated"]) or not set(ids["deduplicated"]).issubset(ids["found"]):
                raise ValueError("search stages do not reconcile")
            counts.update({k: len(ids[k]) for k in keys})
        except (OSError, ValueError, TypeError, KeyError) as exc:
            counts["reconciliation_findings"].append({"field": "search_log", "input": summary["search_log_path"], "actual": str(exc)})
    for key, value in summary.items():
        if key in counts and counts[key] != value:
            counts["reconciliation_findings"].append({"field": key, "input": value, "actual": counts[key]})
    return counts


def _verified_score(record, weights):
    assessment = record.get("assessment") or {}
    proof = inspect_record(record)
    source = record_source(record)
    if not source or not stored_metadata(source) or not proof.get("scientific_eligible") or not isinstance(assessment, dict) or assessment.get("artifact_sha256") != proof.get("sha256") or not assessment.get("reviewer") or not assessment.get("reviewed_at"):
        return None
    criteria = assessment.get("criteria", [])
    if len(criteria) != len(weights) or {c.get("pillar") for c in criteria} != set(weights):
        return None
    total = 0
    for c in criteria:
        score = c.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool) or not 0 <= score <= weights[c["pillar"]] or not c.get("locator") or not c.get("evidence_excerpt") or " ".join(c["evidence_excerpt"].split()) not in " ".join(proof["text"].split()):
            return None
        total += score
    provided = record.get("total_score", record.get("score"))
    return total if provided is None or provided == total else None


def _write_report(path: Path, result: Mapping[str, Any], *, created_at: str, runtime_status: str) -> None:
    counts = result["counts"]
    lines = [
        "# Laporan Review Artikel Kuantitatif",
        "",
        f"Status: {result['status']}",
        f"Status runtime: {runtime_status}",
        f"Waktu pembuatan: {created_at}",
        "",
        "## Rekapitulasi aktual",
    ]
    labels = {
        "found": "jumlah artikel yang ditemukan",
        "deduplicated": "jumlah artikel setelah deduplikasi",
        "screened": "jumlah artikel yang ditapis",
        "eligible": "jumlah artikel yang memenuhi kriteria",
        "metadata_verified": "jumlah artikel dengan metadata terverifikasi",
        "full_text_legal": "jumlah artikel dengan full-text legal",
        "full_text_read": "jumlah artikel yang benar-benar dibaca penuh",
        "abstract_only": "jumlah artikel abstrak saja",
        "human_review": "jumlah artikel yang memerlukan review manusia",
        "ranked": "jumlah artikel yang masuk peringkat",
        "not_ranked": "jumlah artikel yang tidak masuk peringkat",
    }
    for key, label in labels.items():
        lines.append(f"- {label}: {counts[key]}")
    lines.append("- Jumlah berdasarkan indeksasi: " + json.dumps(counts["indexing"], ensure_ascii=False))
    lines.append("- Temuan rekonsiliasi: " + json.dumps(counts["reconciliation_findings"], ensure_ascii=False))
    lines.extend(
        [
            f"- Alasan tidak masuk peringkat: {counts['not_ranked_reason']}",
            "",
            "## Validasi",
            "- Urutan peringkat: total skor menurun; tie-break No. Master menaik.",
            "- DOI tidak dipakai sebagai bukti isi artikel.",
            "- Status full-text hanya berasal dari provenance/legal evidence yang diberikan.",
            "",
            "## Artefak",
            f"- Workbook: {result['workbook_path']}",
            f"- SHA-256 workbook: {result['workbook_sha256']}",
            f"- Ukuran workbook: {result['workbook_size']} byte",
            f"- Manifest checksum: {result['manifest_path']}",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_quantitative_review_workbook(
    records: Iterable[Mapping[str, Any]],
    output_path: str | Path,
    *,
    template_path: str | Path | None = None,
    summary: Mapping[str, Any] | None = None,
    request_text: str = "",
    exact_count: int | None = None,
    best_count: int | None = None,
    runtime_status: str = "provisional",
    require_free_full_text: bool = False,
) -> QuantitativeReviewWorkbookResult:
    """Fill the standard workbook, preserving all passing records beyond 40."""
    raw_records = [dict(record) for record in records]
    selected, target, clarification = _select_records(
        raw_records,
        request_text=request_text,
        exact_count=exact_count,
        best_count=best_count,
    )
    _validate_records(selected)
    template = resolve_standard_workbook_template(template_path)
    output = Path(output_path).expanduser().resolve()
    if output == template:
        raise QuantitativeReviewWorkbookError("Tidak boleh menimpa workbook sumber")
    output.parent.mkdir(parents=True, exist_ok=True)
    wb = load_workbook(template)
    _require_template(wb)

    master = wb[SHEET_NAMES[0]]
    master_footer = _extend_data_block(master, data_start=6, footer_start=46, count=len(selected), base_rows=(6, 7))
    for index, record in enumerate(selected, 1):
        row = 5 + index
        _clear_row(master, row, preserve_formulas=True)
        values = [
            index,
            _text(record, "title", "judul"),
            _text(record, "citation", "sitasi", "authors"),
            _text(record, "year"),
            _text(record, "journal_publisher", "venue", "journal"),
            _text(record, "indexing", "accreditation"),
            _text(record, "population_context"),
            _text(record, "objective", "purpose"),
            _text(record, "sample_method_measure", "sample_method_instrument"),
            _text(record, "main_findings", "findings"),
            _text(record, "strengths"),
            _text(record, "limitations"),
            _text(record, "relevance"),
            _text(record, "doi"),
            _text(record, "article_url", "url"),
            _text(record, "full_text_url", "pdf_url"),
            _access_status(record),
        ]
        for col, value in enumerate(values, 1):
            master.cell(row, col).value = value
        for col in (14, 15, 16):
            value = master.cell(row, col).value
            if isinstance(value, str):
                url = f"https://doi.org/{value}" if col == 14 and re.match(r"^10\.\d{4,}/\S+$", value) else value
                if re.match(r"^https?://", url):
                    master.cell(row, col).hyperlink = url
        provenance = record.get("provenance")
        if provenance:
            master.cell(row, 2).comment = Comment(json.dumps(provenance, ensure_ascii=False, default=str), "AAI")

    rubric = wb[SHEET_NAMES[1]]
    weights = {rubric.cell(row, 1).value: rubric.cell(row, 2).value for row in range(5, 8)}
    rubric_final = all(isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0 for value in weights.values()) and all(
        isinstance(rubric.cell(row, col).value, str) and rubric.cell(row, col).value.strip() and not rubric.cell(row, col).value.strip().startswith("[")
        for row in range(5, 8) for col in range(3, 8)) and all(
            isinstance(rubric.cell(row, 3).value, str) and rubric.cell(row, 3).value.strip() and not rubric.cell(row, 3).value.strip().startswith("[")
            for row in range(12, 16))
    eligible_with_master = [(index + 1, record) for index, record in enumerate(selected) if _scientific_eligible(record) and (not require_free_full_text or _full_text_legal(record))]
    eligible = [record for _, record in eligible_with_master]
    scores = {id(record): _verified_score(record, weights) if rubric_final else None for record in eligible}
    assessed = [(no, record) for no, record in eligible_with_master if scores[id(record)] is not None and not _bool(record, "human_review", "needs_human_review")]
    ranked = [record for _, record in sorted(assessed, key=lambda item: (-scores[id(item[1])], item[0]))]
    if clarification:
        ranked = []
    elif target is not None:
        ranked = ranked[:target]
    scored = len(assessed) == len(eligible_with_master)

    ranking = wb[SHEET_NAMES[2]]
    ranking_footer = _extend_data_block(ranking, data_start=5, footer_start=45, count=len(ranked), base_rows=(5, 6))
    master_no_by_identity = {id(record): index + 1 for index, record in enumerate(selected)}
    for rank, record in enumerate(ranked, 1):
        row = 4 + rank
        _clear_row(ranking, row, preserve_formulas=True)
        master_no = master_no_by_identity[id(record)]
        values = [
            rank,
            master_no,
            _text(record, "citation", "sitasi", "authors"),
            _text(record, "journal_publisher", "venue", "journal"),
            _text(record, "indexing", "accreditation"),
            _text(record, "population_sample", "population_context", "sample"),
            _text(record, "quantitative_design", "design"),
            scores[id(record)],
            rubric.cell(_index_row(record), 3).value,
            _text(record, "recommendation", "thesis_recommendation"),
        ]
        for col, value in enumerate(values, 1):
            ranking.cell(row, col).value = value

    counts = _counts(selected, ranked, summary, None, require_free_full_text=require_free_full_text)
    for row in range(12, 16):
        rubric.cell(row, 4).value = sum(_index_row(record) == row for record in eligible)
    counts["clarification"] = clarification
    counts["selection_deficit"] = max(0, target - len(ranked)) if target is not None else 0
    scoring_final = bool(eligible and scored and rubric_final and not counts["human_review"] and not clarification and not counts["reconciliation_findings"] and not counts["selection_deficit"])
    screening_path = output.with_name("screening_audit.json")
    screening = []
    for index, record in enumerate(selected, 1):
        reasons = list(record.get("verification_findings", []))
        if not _scientific_eligible(record): reasons.append("scientific eligibility not established")
        if require_free_full_text and not _full_text_legal(record): reasons.append("legal free readable full-text required")
        if record in eligible and scores.get(id(record)) is None: reasons.append("rubric/assessment not verified")
        if record not in ranked and not reasons: reasons.append("explicit selection or clarification pending")
        screening.append({"master_no": index, "title": record.get("title"), "selected": record in ranked, "reasons": reasons, "record": record})
    screening_path.write_text(json.dumps(screening, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")

    summary_row = ranking_footer + 2
    ranking.merge_cells(start_row=summary_row, start_column=1, end_row=summary_row, end_column=10)
    ranking.cell(summary_row, 1).value = "REKAPITULASI AKTUAL RUN"
    for col in range(1, 11):
        ranking.cell(summary_row, col)._style = copy(ranking.cell(4, min(col, 10))._style)
    summary_labels = [
        ("Jumlah artikel ditemukan", counts["found"]),
        ("Jumlah artikel setelah deduplikasi", counts["deduplicated"]),
        ("Jumlah artikel yang ditapis", counts["screened"]),
        ("Jumlah artikel memenuhi kriteria", counts["eligible"]),
        ("Metadata terverifikasi", counts["metadata_verified"]),
        ("Full-text legal", counts["full_text_legal"]),
        ("Dibaca penuh", counts["full_text_read"]),
        ("Abstrak saja", counts["abstract_only"]),
        ("Perlu review manusia", counts["human_review"]),
        ("Masuk peringkat", counts["ranked"]),
        ("Tidak masuk peringkat", counts["not_ranked"]),
        ("Jumlah berdasarkan indeksasi", json.dumps(counts["indexing"], ensure_ascii=False)),
        ("Alasan tidak masuk peringkat", counts["not_ranked_reason"]),
        ("Status scoring", "final" if scoring_final else "belum final"),
    ]
    for offset, (label, value) in enumerate(summary_labels, 1):
        row = summary_row + offset
        ranking.cell(row, 1).value = label
        ranking.cell(row, 2).value = value
        ranking.cell(row, 1)._style = copy(ranking.cell(5, 1)._style)
        ranking.cell(row, 2)._style = copy(ranking.cell(5, 2)._style)
    if ranking.print_area:
        areas = list(ranking._print_area.ranges)
        for area in areas:
            area.max_row = max(area.max_row, summary_row + len(summary_labels))
        ranking.print_area = [str(area) for area in areas]

    temp = output.with_suffix(output.suffix + ".tmp")
    wb.save(temp)
    with temp.open("rb") as stream:
        reopened = load_workbook(stream)
    _require_template(reopened)
    master_numbers = [reopened[SHEET_NAMES[0]].cell(6 + i, 1).value for i in range(len(selected))]
    rank_numbers = [reopened[SHEET_NAMES[2]].cell(5 + i, 1).value for i in range(len(ranked))]
    master_refs = [reopened[SHEET_NAMES[2]].cell(5 + i, 2).value for i in range(len(ranked))]
    if master_numbers != list(range(1, len(selected) + 1)) or rank_numbers != list(range(1, len(ranked) + 1)) or not set(master_refs).issubset(master_numbers):
        raise QuantitativeReviewWorkbookError("Workbook round-trip reconciliation failed")
    reopened.close()
    temp.replace(output)
    workbook_sha = _sha256(output)
    created_at = datetime.now(timezone.utc).isoformat()
    report_path = output.with_name("quantitative_review_report.md")
    manifest_path = output.with_name("checksum_manifest.json")
    status = "PASS" if scoring_final and not counts["human_review"] else "PARTIAL"
    preliminary = {
        "status": status,
        "workbook_path": str(output),
        "workbook_sha256": workbook_sha,
        "workbook_size": output.stat().st_size,
        "manifest_path": str(manifest_path),
        "counts": counts,
    }
    _write_report(report_path, preliminary, created_at=created_at, runtime_status=runtime_status)
    manifest = {
        "created_at": created_at,
        "workbook": {"path": str(output), "sha256": workbook_sha, "size": output.stat().st_size},
        "report": {"path": str(report_path), "sha256": _sha256(report_path), "size": report_path.stat().st_size},
        "screening": {"path": str(screening_path), "sha256": _sha256(screening_path), "size": screening_path.stat().st_size},
        "zip": None,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return QuantitativeReviewWorkbookResult(
        workbook_path=str(output),
        report_path=str(report_path),
        manifest_path=str(manifest_path),
        workbook_sha256=workbook_sha,
        workbook_size=output.stat().st_size,
        article_count=len(selected),
        ranked_count=len(ranked),
        unranked_count=counts["not_ranked"],
        scoring_final=scoring_final,
        status=status,
        counts=counts,
    )


def update_workflow_report(result: dict, run_summary: dict) -> None:
    """Replace provisional workbook report with actual whole-run status."""
    report = Path(result["report_path"])
    payload = dict(result)
    payload["status"] = run_summary["result_status"]
    _write_report(report, payload, created_at=run_summary["finished_at"], runtime_status="processed" if run_summary["execution_success"] else "failed")
    with report.open("a", encoding="utf-8") as handle:
        handle.write("\n## Status keseluruhan workflow\n```json\n" + json.dumps({
            key: run_summary.get(key) for key in ("run_id", "execution_success", "result_status", "finalization_allowed", "needs_human_review", "document_quality", "citation_audit_passed", "fact_audit_passed", "human_style_audit_passed", "review_findings", "blocking_review_items", "references")
        }, ensure_ascii=False, indent=2) + "\n```\n")
    manifest_path = Path(result["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["run_id"] = run_summary["run_id"]
    manifest["report"] = {"path": str(report), "sha256": _sha256(report), "size": report.stat().st_size}
    for artifact in run_summary["artifacts"]:
        artifact_path = Path(artifact["path"])
        artifact.update(sha256=_sha256(artifact_path), size=artifact_path.stat().st_size)
    manifest["artifacts"] = run_summary["artifacts"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_path = Path(run_summary["quantitative_workbook_path"]).parent.parent / "run_summary.json"
    summary_path.write_text(json.dumps(run_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
