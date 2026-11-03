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
import hashlib
import os
from pathlib import Path
import tempfile
from typing import Any
import zipfile

from src.core.storage import ensure_within
from src.core.errors import PathSafetyError

__all__ = ["export_bundle"]

_RUN_SNAPSHOT_FILES = (
    "run_summary.json",
    "input_snapshot.json",
    "sources_snapshot.json",
    "findings_sources.json",
    "verified_sources_snapshot.json",
    "claims_snapshot.json",
    "evidence_snapshot.json",
    "outline_snapshot.json",
    "citation_audit_snapshot.json",
    "fact_audit_snapshot.json",
    "workflow_options.json",
    "semantic_reviews.json",
    "access_screening.json",
    "claim_screening.json",
    "search_log.json",
    "verification_reports.json",
    "review_queue.json",
    "human_style_audit.json",
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

    from src.runtime.execution import project_write_lock
    with project_write_lock(resolved_proj):
        return _export_bundle_locked(resolved_proj, run_id=run_id, include_failed=include_failed)


def _export_bundle_locked(resolved_proj: Path, *, run_id: str | None, include_failed: bool) -> dict[str, Any]:
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
                if not isinstance(summary_data, dict):
                    summary_data = None
                    raise ValueError("Run summary must be an object")
                started_at = str(summary_data.get("started_at") or d.name)
            except Exception:  # noqa: BLE001
                pass
        runs_with_meta.append((d, started_at, summary_data))

    runs_with_meta.sort(key=lambda x: x[1], reverse=True)

    # Select target run directory
    target_run_tuple: tuple[Path, str, dict[str, Any] | None] | None = None
    if run_id:
        matches = [item for item in runs_with_meta if item[0].name == run_id or item[0].name.endswith(run_id)]
        if len(matches) > 1:
            return {"success": False, "error": f"Ambiguous run ID {run_id}; provide the full run ID"}
        target_run_tuple = matches[0] if matches else None
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

    if not isinstance(selected_summary, dict):
        return {"success": False, "error": "Run summary must be an object"}
    try:
        ensure_within(selected_run_dir, resolved_proj)
        integrity = json.loads((selected_run_dir / "integrity_manifest.json").read_text(encoding="utf-8"))
        if integrity.get("version") != 1 or integrity.get("run_id") != selected_run_id:
            raise ValueError("unsupported or mismatched run integrity manifest")
        sealed_files = integrity["files"]
        if "run_summary.json" not in sealed_files:
            raise ValueError("run summary is not sealed")
        actual_files = {p.relative_to(selected_run_dir).as_posix() for p in selected_run_dir.rglob("*")
                        if p.is_file() and p.relative_to(selected_run_dir).as_posix() not in {".active", "integrity_manifest.json"}}
        if actual_files != set(sealed_files):
            raise ValueError("run file inventory changed")
        for relative, expected in sealed_files.items():
            if Path(relative).is_absolute():
                raise ValueError("run integrity paths must be relative")
            content = ensure_within(relative, selected_run_dir).read_bytes()
            if len(content) != expected["size"] or hashlib.sha256(content).hexdigest() != expected["sha256"]:
                raise ValueError(f"run integrity mismatch: {relative}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, PathSafetyError) as exc:
        return {"success": False, "error": f"Run integrity validation failed; re-run unsealed legacy runs: {exc}"}

    is_success = bool(selected_summary.get("success", False))
    if not is_success and not include_failed:
        return {
            "success": False,
            "error": f"Run {selected_run_id} failed. Pass --include-failed to bundle failed runs.",
        }

    # Prepare files to package: list of (source_path, arcname)
    files_to_pack: list[tuple[Path, str]] = []

    for artifact in selected_summary.get("artifacts", []) if is_success else []:
        relative = Path(artifact.get("relative_path", ""))
        if not artifact.get("relative_path") or relative.is_absolute():
            return {"success": False, "error": "Run artifact requires a relative path; re-run before export"}
        try:
            source_path = ensure_within(relative, selected_run_dir)
        except (ValueError, PathSafetyError) as exc:
            return {"success": False, "error": str(exc)}
        if not source_path.is_file() or hashlib.sha256(source_path.read_bytes()).hexdigest() != artifact["sha256"]:
            return {"success": False, "error": f"Run artifact integrity mismatch: {source_path}"}
        filename = artifact["name"]
        if filename == "final.docx" and not selected_summary.get("finalization_allowed", False):
            return {"success": False, "error": "Run is not allowed to export a final document"}
        folder = "review_output" if filename.startswith("quantitative_") or filename in {"hasil_temuan.xlsx", "laporan_pekerjaan.xlsx"} else "academic_output"
        files_to_pack.append((source_path, f"{folder}/{filename}"))
    if is_success and not files_to_pack:
        return {"success": False, "error": "Selected run has no immutable output artifacts; re-run before export"}
    for filename in ("citation_audit_snapshot.json", "fact_audit_snapshot.json"):
        path = selected_run_dir / filename
        if is_success and path.is_file():
            files_to_pack.append((path, "audits/" + filename.replace("_snapshot", "")))
    for filename in ("screening_audit.json",):
        path = selected_run_dir / "review" / filename
        if is_success and path.is_file():
            files_to_pack.append((path, "review_output/" + filename))

    # Add snapshots from selected run directory
    for filename in _RUN_SNAPSHOT_FILES:
        snap_file = selected_run_dir / filename
        if snap_file.exists():
            files_to_pack.append((snap_file, f"run/{filename}"))
    for path in (selected_run_dir / "source_artifacts").glob("*"):
        if path.is_file():
            files_to_pack.append((path, "sources/" + path.name))
    files_to_pack.append((selected_run_dir / "integrity_manifest.json", "run/integrity_manifest.json"))

    # Prepare destination exports directory
    exports_dir = resolved_proj / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = exports_dir / f"bundle_{selected_run_id}.zip"

    # Enforce path safety
    safe_bundle_path = ensure_within(bundle_path, resolved_proj)

    # Write archive
    handle, temporary = tempfile.mkstemp(dir=exports_dir, prefix=".bundle_", suffix=".tmp")
    os.close(handle)
    temporary_path = Path(temporary)
    packed_artifacts = []
    try:
        with zipfile.ZipFile(temporary_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for src_path, arcname in files_to_pack:
                safe_src = ensure_within(src_path, selected_run_dir)
                content = safe_src.read_bytes()
                digest = hashlib.sha256(content).hexdigest()
                expected = sealed_files.get(safe_src.relative_to(selected_run_dir).as_posix())
                if expected and (digest != expected["sha256"] or len(content) != expected["size"]):
                    raise ValueError(f"Run changed during export: {safe_src}")
                zf.writestr(arcname, content)
                packed_artifacts.append({"path": str(safe_src), "archive_name": arcname, "sha256": digest, "size": len(content)})
        with zipfile.ZipFile(temporary_path, "r") as zf:
            bad_member = zf.testzip()
            if bad_member is not None:
                return {
                    "success": False,
                    "error": f"ZIP checksum test failed for member {bad_member}",
                }
        temporary_path.replace(safe_bundle_path)
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "error": f"Failed to create bundle archive: {exc}",
        }
    finally:
        temporary_path.unlink(missing_ok=True)

    zip_digest = hashlib.sha256(safe_bundle_path.read_bytes()).hexdigest()
    manifest = {
        "run_id": selected_run_id,
        "artifacts": packed_artifacts,
        "zip": {"path": str(safe_bundle_path), "sha256": zip_digest, "size": safe_bundle_path.stat().st_size},
    }
    manifest_path = safe_bundle_path.with_suffix(".manifest.json")
    try:
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        return {"success": False, "error": f"Checksum manifest write failed: {exc}", "bundle_path": str(safe_bundle_path)}

    return {
        "success": True,
        "project_directory": str(resolved_proj),
        "run_id": selected_run_id,
        "bundle_path": str(safe_bundle_path),
        "included_files": [arcname for _, arcname in files_to_pack],
        "zip_sha256": zip_digest,
        "zip_size": safe_bundle_path.stat().st_size,
        "zip_testzip": "PASS",
        "manifest_path": str(manifest_path),
    }
