"""Claim registry — persist and query the claim set for a project.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §14 — claim registry minimum fields.
  * SYSTEM_RULES.md §E.31 — writer works from approved claims only.

A claim registry is scoped to one project. It loads the canonical
``claims.json`` artifact (see :class:`~src.schemas.project.ProjectArtifact`),
holds the claims in memory, and persists atomically through the storage layer.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from src.core.errors import ProjectError
from src.core.logging import get_logger
from src.core.storage import read_json, write_json
from src.schemas.claim import Claim
from src.schemas.project import Project, ProjectArtifact

__all__ = ["ClaimRegistry"]

_logger = get_logger(__name__)


class ClaimRegistry:
    """In-memory registry for a project's claims, backed by ``claims.json``.

    Attributes
    ----------
    project:
        The project this registry serves; defines where claims are stored.
    claims:
        Ordered map of ``claim_id -> Claim``.
    """

    def __init__(self, project: Project, *, claims: Iterable[Claim] | None = None) -> None:
        self.project = project
        self.claims: dict[str, Claim] = {}
        for claim in claims or ():
            self.claims[claim.id] = claim

    # ---------------------------------------------------------------- path
    def _artifact_path(self) -> Path:
        return self.project.artifact_path(ProjectArtifact.CLAIMS)

    # ---------------------------------------------------------------- access
    def add(self, claim: Claim) -> Claim:
        """Register ``claim``. Re-adding the same ID is an error (no silent overwrite)."""
        if claim.id in self.claims:
            raise ProjectError(
                f"Claim {claim.id} already registered",
                claim_id=claim.id,
                path=str(self._artifact_path()),
            )
        self.claims[claim.id] = claim
        return claim

    def get(self, claim_id: str) -> Claim | None:
        return self.claims.get(claim_id)

    def all(self) -> list[Claim]:
        return list(self.claims.values())

    def writable(self) -> list[Claim]:
        """Claims the WriterAgent may use (see :meth:`Claim.is_writable`)."""
        return [claim for claim in self.claims.values() if claim.is_writable]

    def unsupported_important(self) -> list[Claim]:
        """Important claims that still lack adequate support (audit focus)."""
        return [
            claim
            for claim in self.claims.values()
            if claim.is_important and claim.status != "SUPPORTED"
        ]

    # ---------------------------------------------------------------- persist
    def save(self) -> None:
        """Persist every claim atomically to ``claims.json``."""
        write_json(
            self._artifact_path(),
            [claim.to_dict() for claim in self.claims.values()],
            root=self.project.directory,
            overwrite=True,
        )
        _logger.debug(
            "Claim registry saved",
            extra={"project_id": self.project.id, "claims": len(self.claims)},
        )

    @classmethod
    def load(cls, project: Project) -> "ClaimRegistry":
        """Load a registry from disk. A missing file yields an empty registry."""
        path = project.artifact_path(ProjectArtifact.CLAIMS)
        if not path.is_file():
            _logger.debug("No claims.json; starting empty", extra={"project_id": project.id})
            return cls(project)

        try:
            raw = read_json(path)
            claims = [Claim.from_dict(item) for item in raw]
        except Exception as exc:
            raise ProjectError(
                f"Failed to load claims from {path}",
                path=str(path),
                error=str(exc),
            ) from exc
        return cls(project, claims=claims)
