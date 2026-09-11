"""Academic audit trail — per-run provenance recording for Phase R4.

Specification anchors:
  * SYSTEM_RULES.md §E — academic workflow integrity.
  * AGENTS.md — evidence-controlled execution; no fabricated outputs.
  * Audit R4 — per-run audit trail proving input, sources, claims, evidence,
    outline, citation audit, fact audit, and output provenance.

Every academic run records a timestamped audit trail under:
  ``<project_directory>/runs/<run_id>/``

Snapshots created:
  - ``input_snapshot.json``
  - ``sources_snapshot.json``
  - ``claims_snapshot.json``
  - ``evidence_snapshot.json``
  - ``outline_snapshot.json``
  - ``citation_audit_snapshot.json`` (when available)
  - ``fact_audit_snapshot.json`` (when available)
  - ``run_summary.json``
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

from src.core.storage import write_json
from src.schemas.claim import Claim
from src.schemas.evidence import Evidence
from src.schemas.outline import Outline
from src.schemas.project import Project, ProjectArtifact
from src.schemas.source import Source

__all__ = [
    "AcademicRunAudit",
    "sanitize_snapshot",
]

_EXCLUDED_KEYS = frozenset({"internal_tokens", "tokens"})
_SENSITIVE_KEY_SUBSTRINGS = (
    "api_token",
    "access_token",
    "auth_token",
    "monitor_token",
    "secret",
    "password",
    "api_key",
    "authorization",
    "autonomi_token",
)


def _is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    if normalized in _EXCLUDED_KEYS:
        return False
    if normalized == "token":
        return True
    return any(sub in normalized for sub in _SENSITIVE_KEY_SUBSTRINGS)


def _get_known_secrets() -> list[str]:
    """Gather current active secrets (e.g. monitor token) to scrub from snapshots."""
    secrets: list[str] = []
    env_token = os.environ.get("AUTONOMI_API_TOKEN")
    if env_token and len(env_token) >= 8:
        secrets.append(env_token)

    try:
        from src.core.paths import get_paths

        token_path = get_paths().state_dir / "monitor_token.txt"
        if token_path.exists():
            val = token_path.read_text(encoding="utf-8").strip()
            if val and len(val) >= 8:
                secrets.append(val)
    except Exception:  # noqa: BLE001
        pass
    return secrets


def sanitize_snapshot(data: Any, *, known_secrets: list[str] | None = None) -> Any:
    """Recursively scrub sensitive keys and secret values from snapshot data."""
    if known_secrets is None:
        known_secrets = _get_known_secrets()

    if isinstance(data, dict):
        cleaned: dict[str, Any] = {}
        for k, v in data.items():
            if _is_sensitive_key(str(k)):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = sanitize_snapshot(v, known_secrets=known_secrets)
        return cleaned

    if isinstance(data, list):
        return [sanitize_snapshot(item, known_secrets=known_secrets) for item in data]

    if isinstance(data, str):
        result = data
        for secret in known_secrets:
            if secret and secret in result:
                result = result.replace(secret, "[REDACTED]")
        return result

    return data


def _compute_relpath(path_str: str | None, root: Path) -> str | None:
    """Compute relative path string to project directory, or None if path does not exist."""
    if not path_str:
        return None
    try:
        p = Path(path_str).resolve()
        if not p.exists():
            return None
        r = root.resolve()
        try:
            return p.relative_to(r).as_posix()
        except ValueError:
            return p.name
    except Exception:
        return None


class AcademicRunAudit:
    """Coordinates recording of per-run snapshots and summary."""

    def __init__(
        self,
        *,
        project: Project,
        run_id: str,
        run_dir: Path,
        started_at: str,
        command: str = "run-academic",
        input_path: str | None = None,
    ) -> None:
        self.project = project
        self.run_id = run_id
        self.run_dir = run_dir
        self.started_at = started_at
        self.command = command
        self.input_path = input_path
        self._root = project.directory

    @classmethod
    def start(
        cls,
        *,
        project: Project,
        claims: list[Claim],
        evidence: list[Evidence],
        sources: list[Source],
        outline: Outline | None = None,
        command: str = "run-academic",
        input_path: str | None = None,
    ) -> AcademicRunAudit:
        """Initialize run folder and immediately write input snapshots."""
        now = datetime.now(timezone.utc)
        started_at = now.isoformat()
        timestamp_slug = now.strftime("%Y%m%dT%H%M%SZ")
        short_id = uuid.uuid4().hex[:8]
        run_id = f"run_{timestamp_slug}_{short_id}"

        run_dir = project.directory / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        audit = cls(
            project=project,
            run_id=run_id,
            run_dir=run_dir,
            started_at=started_at,
            command=command,
            input_path=input_path,
        )

        audit._record_input_snapshots(
            claims=claims,
            evidence=evidence,
            sources=sources,
            outline=outline,
        )
        return audit

    def _record_input_snapshots(
        self,
        *,
        claims: list[Claim],
        evidence: list[Evidence],
        sources: list[Source],
        outline: Outline | None,
    ) -> None:
        """Write sanitized JSON snapshots of all input components."""
        known_secrets = _get_known_secrets()

        # 1. input_snapshot.json
        input_meta = {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "command": self.command,
            "input_path": self.input_path,
            "project": self.project.model_dump(mode="json"),
            "sources_count": len(sources),
            "claims_count": len(claims),
            "evidence_count": len(evidence),
            "has_outline": outline is not None,
        }
        write_json(
            self.run_dir / "input_snapshot.json",
            sanitize_snapshot(input_meta, known_secrets=known_secrets),
            root=self._root,
            overwrite=True,
        )

        # 2. sources_snapshot.json
        sources_payload = [s.model_dump(mode="json") for s in sources]
        write_json(
            self.run_dir / "sources_snapshot.json",
            sanitize_snapshot(sources_payload, known_secrets=known_secrets),
            root=self._root,
            overwrite=True,
        )

        # 3. claims_snapshot.json
        claims_payload = [c.model_dump(mode="json") for c in claims]
        write_json(
            self.run_dir / "claims_snapshot.json",
            sanitize_snapshot(claims_payload, known_secrets=known_secrets),
            root=self._root,
            overwrite=True,
        )

        # 4. evidence_snapshot.json
        evidence_payload = [e.model_dump(mode="json") for e in evidence]
        write_json(
            self.run_dir / "evidence_snapshot.json",
            sanitize_snapshot(evidence_payload, known_secrets=known_secrets),
            root=self._root,
            overwrite=True,
        )

        # 5. outline_snapshot.json
        outline_payload = outline.model_dump(mode="json") if outline else None
        write_json(
            self.run_dir / "outline_snapshot.json",
            sanitize_snapshot(outline_payload, known_secrets=known_secrets),
            root=self._root,
            overwrite=True,
        )

    def finish(
        self,
        *,
        success: bool,
        stages: list[str] | None = None,
        draft_path: str | None = None,
        docx_path: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        """Finalize the run, snapshot audit reports if present, and write run_summary.json."""
        finished_at = datetime.now(timezone.utc).isoformat()
        stages = list(stages or [])

        # Snapshot citation audit if artifact exists
        citation_audit_file = self.project.artifact_path(ProjectArtifact.CITATION_AUDIT)
        citation_audit_path: str | None = None
        if citation_audit_file.exists():
            try:
                cit_data = json.loads(citation_audit_file.read_text(encoding="utf-8"))
                write_json(
                    self.run_dir / "citation_audit_snapshot.json",
                    sanitize_snapshot(cit_data),
                    root=self._root,
                    overwrite=True,
                )
                citation_audit_path = str(citation_audit_file)
            except Exception:  # noqa: BLE001
                pass

        # Snapshot fact audit if artifact exists
        fact_audit_file = self.project.artifact_path(ProjectArtifact.FACT_AUDIT)
        fact_audit_path: str | None = None
        if fact_audit_file.exists():
            try:
                fact_data = json.loads(fact_audit_file.read_text(encoding="utf-8"))
                write_json(
                    self.run_dir / "fact_audit_snapshot.json",
                    sanitize_snapshot(fact_data),
                    root=self._root,
                    overwrite=True,
                )
                fact_audit_path = str(fact_audit_file)
            except Exception:  # noqa: BLE001
                pass

        # Resolve verified draft/docx paths
        resolved_draft = draft_path or (
            str(self.project.artifact_path(ProjectArtifact.DRAFT))
            if self.project.artifact_path(ProjectArtifact.DRAFT).exists()
            else None
        )
        resolved_docx = docx_path or (
            str(self.project.artifact_path(ProjectArtifact.FINAL_DOCX))
            if self.project.artifact_path(ProjectArtifact.FINAL_DOCX).exists()
            else None
        )

        final_draft_path = resolved_draft if success else None
        final_docx_path = resolved_docx if success else None

        draft_relpath = _compute_relpath(final_draft_path, self._root)
        docx_relpath = _compute_relpath(final_docx_path, self._root)
        citation_audit_relpath = _compute_relpath(citation_audit_path, self._root)
        fact_audit_relpath = _compute_relpath(fact_audit_path, self._root)

        run_summary = {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": finished_at,
            "success": success,
            "command": self.command,
            "input_path": self.input_path,
            "draft_path": final_draft_path,
            "draft_relpath": draft_relpath,
            "docx_path": final_docx_path,
            "docx_relpath": docx_relpath,
            "citation_audit_path": citation_audit_path,
            "citation_audit_relpath": citation_audit_relpath,
            "fact_audit_path": fact_audit_path,
            "fact_audit_relpath": fact_audit_relpath,
            "stages": stages,
            "error_message": error_message,
        }

        write_json(
            self.run_dir / "run_summary.json",
            sanitize_snapshot(run_summary),
            root=self._root,
            overwrite=True,
        )

        return run_summary
