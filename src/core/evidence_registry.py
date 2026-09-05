"""Evidence registry — persist and query evidence for a project.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §15 — evidence registry minimum fields.
  * AGENT_CONSTITUTION.md §8/§9 — evidence integrity, never fabricate.

One source yields many pieces of evidence; one claim is supported by evidence
from several sources. Evidence is therefore stored append-only in
``evidence.jsonl`` (see :class:`~src.schemas.project.ProjectArtifact`), matching
the auditable JSON-Lines convention used elsewhere.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.core.errors import ProjectError
from src.core.logging import get_logger
from src.core.storage import append_jsonl, read_jsonl
from src.schemas.evidence import Evidence, EvidenceRelationship
from src.schemas.project import Project, ProjectArtifact

__all__ = ["EvidenceRegistry"]

_logger = get_logger(__name__)


class EvidenceRegistry:
    """In-memory registry for a project's evidence, backed by ``evidence.jsonl``.

    Attributes
    ----------
    project:
        The project this registry serves.
    evidence:
        Ordered map of ``evidence_id -> Evidence``.
    """

    def __init__(self, project: Project, *, evidence: Iterable[Evidence] | None = None) -> None:
        self.project = project
        self.evidence: dict[str, Evidence] = {}
        for item in evidence or ():
            self.evidence[item.id] = item

    def _artifact_path(self) -> Path:
        return self.project.artifact_path(ProjectArtifact.EVIDENCE)

    # ---------------------------------------------------------------- access
    def add(self, evidence: Evidence) -> Evidence:
        """Register ``evidence``. Duplicate IDs raise (append-only integrity)."""
        if evidence.id in self.evidence:
            raise ProjectError(
                f"Evidence {evidence.id} already registered",
                evidence_id=evidence.id,
                path=str(self._artifact_path()),
            )
        self.evidence[evidence.id] = evidence
        return evidence

    def get(self, evidence_id: str) -> Evidence | None:
        return self.evidence.get(evidence_id)

    def for_claim(self, claim_id: str) -> list[Evidence]:
        return [e for e in self.evidence.values() if e.claim_id == claim_id]

    def for_source(self, source_id: str) -> list[Evidence]:
        return [e for e in self.evidence.values() if e.source_id == source_id]

    def all(self) -> list[Evidence]:
        return list(self.evidence.values())

    # ---------------------------------------------------------------- persist
    def save(self, *, new_only: bool = True) -> int:
        """Append evidence to ``evidence.jsonl``.

        Because the artifact is append-only, only records not yet on disk are
        written. Pass ``new_only=False`` to rewrite the entire file (used only
        after a load/merge cycle, and never for silent overwrite of history).
        """
        if new_only:
            existing = {item["id"] for item in read_jsonl(self._artifact_path())}
            pending = [e for e in self.evidence.values() if e.id not in existing]
        else:
            pending = list(self.evidence.values())

        if not pending:
            return 0
        written = append_jsonl(
            self._artifact_path(),
            pending,
            root=self.project.directory,
        )
        _logger.debug(
            "Evidence registry saved",
            extra={"project_id": self.project.id, "appended": written},
        )
        return written

    @classmethod
    def load(cls, project: Project) -> "EvidenceRegistry":
        """Load a registry from disk. A missing file yields an empty registry."""
        path = project.artifact_path(ProjectArtifact.EVIDENCE)
        if not path.is_file():
            _logger.debug("No evidence.jsonl; starting empty", extra={"project_id": project.id})
            return cls(project)

        try:
            records = [Evidence.from_dict(item) for item in read_jsonl(path)]
        except Exception as exc:
            raise ProjectError(
                f"Failed to load evidence from {path}",
                path=str(path),
                error=str(exc),
            ) from exc
        return cls(project, evidence=records)
