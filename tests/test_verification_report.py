"""Tests for the comprehensive verification report and empirical evidence documentation.

Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 6.1, 6.2, 6.3, 6.4
"""

from __future__ import annotations

import re
from pathlib import Path
import pytest

from src.core.paths import get_paths

ALLOWED_STATUSES = {
    "VERIFIED_LIVE",
    "TESTED_OFFLINE",
    "UNVERIFIED",
    "PENDING_CONFIGURATION",
    "NEEDS_HUMAN_REVIEW",
}


def _get_report_path() -> Path:
    system_root = get_paths().system_root
    docs_report = system_root / "docs" / "LAPORAN_VERIFIKASI_LIVE_AND_E2E_2026-09-22.md"
    assert docs_report.is_file(), f"Report file not found at {docs_report}"
    return docs_report


def test_property_8_comprehensive_component_status_classification() -> None:
    """Property 8: Comprehensive Component Status Classification.

    For any entry in the component verification table of LAPORAN_VERIFIKASI_LIVE_AND_E2E_2026-09-22.md,
    its status classification SHALL be exactly one of VERIFIED_LIVE, TESTED_OFFLINE,
    UNVERIFIED, PENDING_CONFIGURATION, or NEEDS_HUMAN_REVIEW.

    Validates: Requirements 5.2
    """
    report_path = _get_report_path()
    content = report_path.read_text(encoding="utf-8")

    # Extract component table from Section 1
    assert "## 1. Status Komponen Berdasarkan Bukti" in content
    table_match = re.search(
        r"## 1\. Status Komponen Berdasarkan Bukti.*?\n(\|.+?\|\n(?:\|.+?\|\n)+)",
        content,
        re.DOTALL,
    )
    assert table_match is not None, "Component status table not found in Section 1"
    table_text = table_match.group(1).strip()

    rows = [r.strip() for r in table_text.splitlines() if r.strip().startswith("|")]
    # Skip header and separator
    data_rows = [r for r in rows[2:] if not set(r.replace("|", "").strip()) <= {"-", ":"}]
    assert len(data_rows) >= 10, f"Expected at least 10 component rows, got {len(data_rows)}"

    for row in data_rows:
        cols = [c.strip() for c in row.split("|")[1:-1]]
        assert len(cols) >= 3, f"Invalid row structure: {row}"
        component_name = cols[0]
        status_col = cols[2]

        # Extract status code inside backticks or plain text
        status_match = re.search(r"`?([A-Z_]+)`?", status_col)
        assert status_match is not None, f"Could not parse status from {status_col} for {component_name}"
        status = status_match.group(1)

        assert status in ALLOWED_STATUSES, (
            f"Component '{component_name}' has invalid status '{status}'. "
            f"Must be one of {ALLOWED_STATUSES}"
        )


def test_verification_report_p0_rights_bypass_and_test_unit_proofs() -> None:
    """Validate documentation of P0 download rights bypass resolution and 10/10 test unit proofs.

    Validates: Requirements 5.1, 1.8
    """
    report_path = _get_report_path()
    content = report_path.read_text(encoding="utf-8")

    # Verify P0 section existence and bypass explanation
    assert "## 2. P0 — Penutupan Celah Kebijakan Hak Unduh" in content
    assert "download_url" in content
    assert "BORROW_ONLY_DOWNLOAD_FORBIDDEN" in content
    assert "PREVIEW_ONLY_DOWNLOAD_FORBIDDEN" in content
    assert "DOWNLOAD_RIGHTS_UNCLEAR" in content
    assert "DOWNLOAD_RIGHTS_RESTRICTED" in content
    assert "_refuse_download" in content
    assert "0 byte" in content or "0 berkas" in content or "Zero Bytes" in content

    # Verify 10/10 test unit proofs are explicitly documented
    expected_unit_tests = [
        "test_unknown_with_explicit_download_url_rejected",
        "test_borrow_only_with_explicit_download_url_rejected",
        "test_preview_only_with_explicit_download_url_rejected",
        "test_open_license_with_valid_download_url_allowed",
        "test_direct_download_open_access_book",
        "test_direct_download_borrow_only_refused",
        "test_direct_download_unknown_rights_refused",
        "test_direct_download_empty_content_rejected",
        "test_direct_download_file_size_limit_exceeded",
        "test_direct_download_backup_on_modified_content",
    ]
    for test_name in expected_unit_tests:
        assert test_name in content, f"Expected unit test proof {test_name} not found in report"


def test_verification_report_doab_live_telemetry() -> None:
    """Validate DOAB live verification telemetry recording.

    Validates: Requirements 5.3
    """
    report_path = _get_report_path()
    content = report_path.read_text(encoding="utf-8")

    assert "2026-09-22T11:11:46.730497+00:00" in content
    assert "https://directory.doabooks.org/rest/search" in content
    assert "climate justice" in content
    assert "200" in content
    assert "Climate Justice for Children: Impacts of Climate Change and Solutions" in content
    assert "bitstreams" in content


def test_verification_report_open_library_live_telemetry() -> None:
    """Validate Open Library live verification telemetry recording.

    Validates: Requirements 5.4
    """
    report_path = _get_report_path()
    content = report_path.read_text(encoding="utf-8")

    assert "2026-09-22T11:11:56.845118+00:00" in content
    assert "https://openlibrary.org/search.json" in content
    assert "climate change" in content
    assert "200" in content
    assert "Climate change" in content
    assert "borrowable" in content.lower() or "borrow_only" in content.lower()


def test_verification_report_cli_research_execution_and_stopping_condition() -> None:
    """Validate CLI research execution, 16 pipeline stages, exit code 1, and stopping condition.

    Validates: Requirements 5.5
    """
    report_path = _get_report_path()
    content = report_path.read_text(encoding="utf-8")

    # Command
    assert "python -m src research" in content
    assert "Dampak perubahan iklim terhadap ketahanan pangan dan strategi adaptasi berbasis komunitas" in content
    assert "TUGAS 1" in content

    # 16 stages
    stages = [
        "deep_plan", "task_analysis", "planning", "discovery", "deduplication",
        "ranking", "verification", "access_check", "retrieval", "evidence_extraction",
        "claim_verification", "conflict_detection", "synthesis", "writing",
        "citation_audit", "fact_audit"
    ]
    for stage in stages:
        assert stage in content, f"Pipeline stage {stage} not documented in report"

    # Exit code 1 and stopping condition
    assert "1" in content  # Exit code 1
    assert "fact_audit.json" in content
    assert "review_queue.json" in content
    assert "final.docx" in content


def test_verification_report_complete_artifact_inventory() -> None:
    """Validate documentation of complete artifact inventory across workspace and runs/.

    Validates: Requirements 5.5, 4.2
    """
    report_path = _get_report_path()
    content = report_path.read_text(encoding="utf-8")

    assert "## 5. P1 — Eksekusi Riset CLI Nyata, 16 Tahap Pipeline, dan Audit Artefak" in content
    assert "### 5.5 Inventaris Lengkap Artefak Riset" in content
    assert "TUGAS 1/dampak_perubahan_iklim_terhada" in content

    # All primary artifacts must be documented
    expected_artifacts = [
        "candidates.jsonl",
        "verified_sources.json",
        "source_documents/",
        "runs/<run_id>/",
        "claims.json",
        "evidence.jsonl",
        "draft.md",
        "citation_map.json",
        "citation_audit.json",
        "fact_audit.json",
        "review_queue.json",
        "final.docx",
    ]
    for artifact in expected_artifacts:
        assert artifact in content, f"Expected artifact {artifact} not found in report"

    # Verify runs snapshot structure documentation
    expected_snapshots = [
        "input_snapshot.json",
        "sources_snapshot.json",
        "claims_snapshot.json",
        "evidence_snapshot.json",
        "outline_snapshot.json",
        "citation_audit_snapshot.json",
        "fact_audit_snapshot.json",
        "run_summary.json",
    ]
    for snapshot in expected_snapshots:
        assert snapshot in content, f"Expected run snapshot file {snapshot} not found in report"


def test_verification_report_model_router_fail_safe_and_zero_credentials() -> None:
    """Validate documentation of Model Router PENDING_CONFIGURATION fail-safe behavior and zero-credential boundary audit.

    Validates: Requirements 5.1, 6.1, 6.2, 6.3, 6.4
    """
    report_path = _get_report_path()
    content = report_path.read_text(encoding="utf-8")

    assert "## 6. P2 — Audit Kesiapan Model Router & Batas Nol Kredensial" in content
    assert "PENDING_CONFIGURATION" in content
    assert "tokens_used = 0" in content or "tokens_used=0" in content
    assert 'completion = ""' in content or 'completion=""' in content
    assert "zero unhandled exception" in content.lower() or "tidak memunculkan exception" in content.lower()
    assert "config/system.yaml" in content
    assert "Zero Credentials Boundary" in content or "Batas Nol Kredensial" in content

    # Verify unit test proofs are documented
    expected_unit_tests = [
        "test_unconfigured_model_router_safe_failure",
        "test_conceptual_capability_resolution",
        "test_configured_model_router_success_mock",
        "test_configured_model_router_network_failure",
        "test_zero_credentials_in_repository",
        "test_model_router_property_9_fail_safe_invariant",
    ]
    for test_name in expected_unit_tests:
        assert test_name in content, f"Expected model router unit test {test_name} not found in report"


def test_verification_report_automated_test_metrics_and_system_health_check() -> None:
    """Validate documentation of full offline test suite execution and system health check exit code 0.

    Validates: Requirements 5.6
    """
    report_path = _get_report_path()
    content = report_path.read_text(encoding="utf-8")

    assert "## 7. Rangkuman Metrik Uji Otomatis & Pemeriksaan Kesehatan Sistem" in content
    assert "python -m pytest -q --tb=short" in content
    assert "470 passed" in content
    assert "python -m src check" in content
    assert "Exit Code: 0" in content or "Exit Code: `0`" in content or "exit code 0" in content.lower()
    assert "[OK] System health check passed" in content


def test_both_report_files_exist_and_synchronized() -> None:
    """Validate that both report files exist in docs/ and project root, and contain all required sections.

    Validates: Requirements 5.1, 5.2, 5.3, 5.4, 5.5, 5.6
    """
    system_root = get_paths().system_root
    docs_report = system_root / "docs" / "LAPORAN_VERIFIKASI_LIVE_AND_E2E_2026-09-22.md"
    root_report = system_root / "LAPORAN_VERIFIKASI_LIVE_AND_E2E_2026-09-22.md"

    assert docs_report.is_file(), f"docs report missing at {docs_report}"
    assert root_report.is_file(), f"root report missing at {root_report}"

    docs_content = docs_report.read_text(encoding="utf-8")
    root_content = root_report.read_text(encoding="utf-8")

    required_sections = [
        "## 1. Status Komponen Berdasarkan Bukti",
        "## 2. P0 — Penutupan Celah Kebijakan Hak Unduh",
        "## 3. P0 — Bukti Verifikasi Telemetri Live Provider",
        "## 4. P1 — Sinkronisasi Provider Default",
        "## 5. P1 — Eksekusi Riset CLI Nyata, 16 Tahap Pipeline, dan Audit Artefak",
        "## 6. P2 — Audit Kesiapan Model Router & Batas Nol Kredensial",
        "## 7. Rangkuman Metrik Uji Otomatis & Pemeriksaan Kesehatan Sistem",
        "## 8. Kesimpulan & Rekomendasi Tindak Lanjut",
    ]
    for section in required_sections:
        assert section in docs_content, f"Section '{section}' missing from docs report"
        assert section in root_content, f"Section '{section}' missing from root report"

