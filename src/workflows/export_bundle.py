"""Academic output export bundle tool for Roadmap R4.

Packs a single academic run into a self-contained, portable .zip archive
under ``<project_directory>/exports/bundle_<run_id>.zip``.

Portable ZIP internal structure:
  academic_output/final.docx
  academic_output/draft.md
  audits/citation_audit.json
  audits/fact_audit.json
  run/run_summary.json
  run/input_snapshot.json
  run/sources_snapshot.json
  run/claims_snapshot.json
  run/evidence_snapshot.json
  run/outline_snapshot.json
  run/citation_audit_snapshot.json (if present)
  run/fact_audit_snapshot.json (if present)

Security and provenance constraints:
  * No external dependencies (uses standard library zipfile).
  * Enforces path safety via `ensure_within`.
  * Absolute paths are NEVER used as archive names.
  * Excludes .env, state tokens, logs, caches, and pytest files.
  * Rejects failed runs unless `--include-failed` is explicitly requested.
  * Failed runs with `--include-failed` only package snapshots and run summary,
    never invented academic outputs.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import zipfile

from src.core.storage import ensure_within

__all__ = ["export_bundle"]

_RUN_SNAPSHOT_FILES = (
    "run_summary.json",
    "input_snapshot.json",
    "sources_snapshot.json",
    "claims_snapshot.json",
    "evidence_snapshot.json",
    "outline_snapshot.json",
    "citation_audit_snapshot.json",
    "fact_audit_snapshot.json",
)


def export_bundle(
    project_dir: Path,
    *,
    run_id: str | None = None,
    include_failed: bool = False,
) -> dict[str, Any]:
    """Package an academic run into a portable .zip archive."""
    resolved_proj = project_dir.resolve()
    if not resolved_proj.exists() or not resolved_proj.is_dir():
        return {
            "success": False,
            "error": f"Project directory does not exist: {project_dir}",
        }

    runs_dir = resolved_proj / "runs"
    if not runs_dir.exists() or not runs_dir.is_dir():
        return {
            "success": False,
            "error": "No runs found for project",
        }

    run_dirs = [d for d in runs_dir.iterdir() if d.is_dir()]
    if not run_dirs:
        return {
            "success": False,
            "error": "No runs found for project",
        }

    # Sort runs newest to oldest
    runs_with_meta: list[tuple[Path, str, dict[str, Any] | None]] = []
    for d in run_dirs:
        summary_file = d / "run_summary.json"
        summary_data: dict[str, Any] | None = None
        started_at = d.name
        if summary_file.exists():
            try:
                summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
                started_at = str(summary_data.get("started_at") or d.name)
            except Exception:  # noqa: BLE001
                pass
        runs_with_meta.append((d, started_at, summary_data))

    runs_with_meta.sort(key=lambda x: x[1], reverse=True)

    # Select target run directory
    target_run_tuple: tuple[Path, str, dict[str, Any] | None] | None = None
    if run_id:
        target_run_tuple = next(
            (item for item in runs_with_meta if item[0].name == run_id or item[0].name.endswith(run_id)),
            None,
        )
        if not target_run_tuple:
            return {
                "success": False,
                "error": f"Run {run_id} not found",
            }
    else:
        target_run_tuple = runs_with_meta[0]

    selected_run_dir, _, selected_summary = target_run_tuple
    selected_run_id = selected_run_dir.name

    if selected_summary is None:
        summary_file = selected_run_dir / "run_summary.json"
        if not summary_file.exists():
            return {
                "success": False,
                "error": f"Run summary not found in {selected_run_id}",
            }
        try:
            selected_summary = json.loads(summary_file.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return {
                "success": False,
                "error": f"Failed to parse run_summary.json: {exc}",
            }

    is_success = bool(selected_summary.get("success", False))
    if not is_success and not include_failed:
        return {
            "success": False,
            "error": f"Run {selected_run_id} failed. Pass --include-failed to bundle failed runs.",
        }

    # Prepare files to package: list of (source_path, arcname)
    files_to_pack: list[tuple[Path, str]] = []

    if is_success:
        # Require academic outputs for successful runs
        docx_file = resolved_proj / "final.docx"
        draft_file = resolved_proj / "draft.md"

        if not docx_file.exists() or not draft_file.exists():
            return {
                "success": False,
                "error": "Required academic output (final.docx or draft.md) not found",
            }

        files_to_pack.append((docx_file, "academic_output/final.docx"))
        files_to_pack.append((draft_file, "academic_output/draft.md"))

        # Audits if present in project
        citation_audit_file = resolved_proj / "citation_audit.json"
        if citation_audit_file.exists():
            files_to_pack.append((citation_audit_file, "audits/citation_audit.json"))

        fact_audit_file = resolved_proj / "fact_audit.json"
        if fact_audit_file.exists():
            files_to_pack.append((fact_audit_file, "audits/fact_audit.json"))

    # Add snapshots from selected run directory
    for filename in _RUN_SNAPSHOT_FILES:
        snap_file = selected_run_dir / filename
        if snap_file.exists():
            files_to_pack.append((snap_file, f"run/{filename}"))

    # Prepare destination exports directory
    exports_dir = resolved_proj / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = exports_dir / f"bundle_{selected_run_id}.zip"

    # Enforce path safety
    safe_bundle_path = ensure_within(bundle_path, resolved_proj)

    # Write archive
    try:
        with zipfile.ZipFile(safe_bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for src_path, arcname in files_to_pack:
                safe_src = ensure_within(src_path, resolved_proj)
                zf.write(safe_src, arcname=arcname)
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "error": f"Failed to create bundle archive: {exc}",
        }

    return {
        "success": True,
        "project_directory": str(resolved_proj),
        "run_id": selected_run_id,
        "bundle_path": str(safe_bundle_path),
        "included_files": [arcname for _, arcname in files_to_pack],
    }
