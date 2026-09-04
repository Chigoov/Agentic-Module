"""Centralized path management.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §23 — ``SYSTEM_ROOT = WORKSPACE_ROOT / "DATA BASE"``.
  * SYSTEM_RULES.md §A.8 — path resolution must be centralized.

Absolutely no user-specific path is hardcoded here. The system root is
discovered from the location of this file, and can be overridden through
environment variables for testing or relocation.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

__all__ = [
    "SYSTEM_ROOT_DIRNAME",
    "ENV_WORKSPACE_ROOT",
    "ENV_SYSTEM_ROOT",
    "SPEC_FILES",
    "SUPPLEMENTARY_DOCS",
    "PathResolutionError",
    "SystemPaths",
    "get_paths",
    "reset_paths_cache",
]

#: Name of the system root directory inside the workspace.
SYSTEM_ROOT_DIRNAME = "DATA BASE"

ENV_WORKSPACE_ROOT = "AUTONOMI_WORKSPACE_ROOT"
ENV_SYSTEM_ROOT = "AUTONOMI_SYSTEM_ROOT"

#: Mandatory specification documents that must remain present in SYSTEM_ROOT.
#: These are the canonical spec set validated by the health check.
SPEC_FILES: tuple[str, ...] = (
    "00_MASTER_INSTRUCTION.md",
    "AGENT_CONSTITUTION.md",
    "ARCHITECTURE.md",
    "SYSTEM_RULES.md",
    "WORKFLOW.md",
    "BUILD_PLAN.md",
)

#: Supplementary/process documents that belong in SYSTEM_ROOT but are not part
#: of the canonical spec set. The health check reports their presence but does
#: not treat their absence as a spec failure.
SUPPLEMENTARY_DOCS: tuple[str, ...] = (
    "SYSTEM_INDEX.md",
    "ENGINEERING_PROTOCOL.md",
    "README.md",
)

#: Directories that hold generated state and may be created at runtime.
#: ``runtime`` was renamed to ``state`` during the architecture refactor
#: (audit finding M1): "runtime" now refers to *code*, not storage.
_STORAGE_DIRS: tuple[str, ...] = ("config", "database", "cache", "state", "logs")


class PathResolutionError(RuntimeError):
    """Raised when the system root cannot be resolved unambiguously."""


def _as_dir(value: str | os.PathLike[str]) -> Path:
    return Path(value).expanduser().resolve()


def _looks_like_system_root(candidate: Path) -> bool:
    """A system root is a directory named ``DATA BASE`` holding the spec files.

    Only one spec file is required for the check so that a partially populated
    test workspace still resolves.
    """
    if candidate.name != SYSTEM_ROOT_DIRNAME or not candidate.is_dir():
        return False
    return True


def _discover_system_root(start: Path) -> Path:
    """Walk upwards from ``start`` looking for the system root."""
    for candidate in (start, *start.parents):
        if _looks_like_system_root(candidate):
            return candidate
        nested = candidate / SYSTEM_ROOT_DIRNAME
        if _looks_like_system_root(nested):
            return nested
    raise PathResolutionError(
        f"Could not locate the {SYSTEM_ROOT_DIRNAME!r} system root starting from {start}. "
        f"Set {ENV_SYSTEM_ROOT} to the absolute path of the system root."
    )


def _resolve_roots(system_root: str | os.PathLike[str] | None = None) -> tuple[Path, Path]:
    """Resolve ``(workspace_root, system_root)``.

    Resolution order: explicit argument, ``AUTONOMI_SYSTEM_ROOT``,
    ``AUTONOMI_WORKSPACE_ROOT``, then discovery from this file's location.
    """
    if system_root is not None:
        resolved = _as_dir(system_root)
    elif os.environ.get(ENV_SYSTEM_ROOT):
        resolved = _as_dir(os.environ[ENV_SYSTEM_ROOT])
    elif os.environ.get(ENV_WORKSPACE_ROOT):
        resolved = _as_dir(os.environ[ENV_WORKSPACE_ROOT]) / SYSTEM_ROOT_DIRNAME
    else:
        resolved = _discover_system_root(Path(__file__).resolve().parent)

    if not resolved.is_dir():
        raise PathResolutionError(f"System root does not exist or is not a directory: {resolved}")

    return resolved.parent, resolved


@dataclass(frozen=True, slots=True)
class SystemPaths:
    """Immutable view of every path the system is allowed to derive.

    Attributes
    ----------
    workspace_root:
        ``AUTONOMI AGENTIC ILMIAH/`` — parent of the system root.
    system_root:
        ``AUTONOMI AGENTIC ILMIAH/DATA BASE/`` — authoritative system root.
    """

    workspace_root: Path
    system_root: Path

    # ------------------------------------------------------------------ source
    @property
    def src_dir(self) -> Path:
        return self.system_root / "src"

    @property
    def tests_dir(self) -> Path:
        return self.system_root / "tests"

    @property
    def docs_dir(self) -> Path:
        return self.system_root / "docs"

    @property
    def prompts_dir(self) -> Path:
        return self.system_root / "prompts"

    # ----------------------------------------------------------------- storage
    @property
    def config_dir(self) -> Path:
        return self.system_root / "config"

    @property
    def database_dir(self) -> Path:
        return self.system_root / "database"

    @property
    def cache_dir(self) -> Path:
        return self.system_root / "cache"

    @property
    def logs_dir(self) -> Path:
        return self.system_root / "logs"

    @property
    def state_dir(self) -> Path:
        """Generated-state directory (renamed from ``runtime`` during refactor M1)."""
        return self.system_root / "state"

    @property
    def runtime_dir(self) -> Path:
        """Backward-compatible alias for :attr:`state_dir`."""
        return self.state_dir

    @property
    def system_config_file(self) -> Path:
        return self.config_dir / "system.yaml"

    @property
    def dotenv_file(self) -> Path:
        return self.system_root / ".env"

    @property
    def project_index_file(self) -> Path:
        """Registry of every project created by the system."""
        return self.state_dir / "project_index.json"

    # ---------------------------------------------------------------- helpers
    def spec_file(self, filename: str) -> Path:
        if filename not in SPEC_FILES:
            raise KeyError(f"{filename!r} is not a known specification file: {SPEC_FILES}")
        return self.system_root / filename

    def missing_spec_files(self) -> list[str]:
        return [name for name in SPEC_FILES if not (self.system_root / name).is_file()]

    def missing_supplementary_docs(self) -> list[str]:
        """Advisory: supplementary docs missing from SYSTEM_ROOT (never a spec failure)."""
        return [name for name in SUPPLEMENTARY_DOCS if not (self.system_root / name).is_file()]

    def project_workspaces(self) -> list[Path]:
        """Project workspaces (e.g. ``TUGAS 1``) — every workspace dir except SYSTEM_ROOT."""
        if not self.workspace_root.is_dir():
            return []
        found = [
            entry
            for entry in self.workspace_root.iterdir()
            if entry.is_dir()
            and entry.resolve() != self.system_root
            and not entry.name.startswith((".", "_", "~"))
        ]
        return sorted(found, key=lambda p: p.name.casefold())

    def workspace_path(self, name: str) -> Path:
        """Resolve a workspace by name, refusing anything outside WORKSPACE_ROOT."""
        candidate = (self.workspace_root / name).resolve()
        if not self.is_inside_workspace(candidate):
            raise PathResolutionError(f"Workspace {name!r} escapes the workspace root: {candidate}")
        if candidate == self.system_root:
            raise PathResolutionError(
                "SYSTEM_ROOT is not a project workspace (SYSTEM_RULES.md §A.2/§A.3)."
            )
        return candidate

    def is_inside_workspace(self, path: str | os.PathLike[str]) -> bool:
        try:
            Path(path).resolve().relative_to(self.workspace_root)
        except ValueError:
            return False
        return True

    def is_inside_system_root(self, path: str | os.PathLike[str]) -> bool:
        try:
            Path(path).resolve().relative_to(self.system_root)
        except ValueError:
            return False
        return True

    def relative(self, path: str | os.PathLike[str]) -> str:
        """Workspace-relative string for logs and reports (keeps logs portable)."""
        resolved = Path(path).resolve()
        try:
            return resolved.relative_to(self.workspace_root).as_posix()
        except ValueError:
            return resolved.as_posix()

    def storage_dirs(self) -> tuple[Path, ...]:
        return tuple(self.system_root / name for name in _STORAGE_DIRS)

    def ensure_storage_dirs(self) -> list[Path]:
        """Create missing generated-state directories. Never touches workspaces."""
        created: list[Path] = []
        for directory in self.storage_dirs():
            if not directory.exists():
                directory.mkdir(parents=True, exist_ok=True)
                created.append(directory)
        return created

    def describe(self) -> dict[str, str]:
        """Flat mapping used by health reports and diagnostics."""
        return {
            "workspace_root": str(self.workspace_root),
            "system_root": str(self.system_root),
            "src_dir": str(self.src_dir),
            "config_dir": str(self.config_dir),
            "database_dir": str(self.database_dir),
            "cache_dir": str(self.cache_dir),
            "logs_dir": str(self.logs_dir),
            "state_dir": str(self.state_dir),
            "runtime_dir": str(self.runtime_dir),
            "docs_dir": str(self.docs_dir),
            "tests_dir": str(self.tests_dir),
        }


@lru_cache(maxsize=8)
def _cached_paths(system_root: str | None) -> SystemPaths:
    workspace_root, resolved_system_root = _resolve_roots(system_root)
    return SystemPaths(workspace_root=workspace_root, system_root=resolved_system_root)


def get_paths(system_root: str | os.PathLike[str] | None = None) -> SystemPaths:
    """Return the cached :class:`SystemPaths` for this process.

    Parameters
    ----------
    system_root:
        Optional explicit override, primarily for tests. When omitted the root
        is taken from the environment or discovered from this file's location.
    """
    key = str(_as_dir(system_root)) if system_root is not None else None
    return _cached_paths(key)


def reset_paths_cache() -> None:
    """Clear the resolution cache (used by tests that relocate the root)."""
    _cached_paths.cache_clear()


def iter_existing(paths: Iterable[str | os.PathLike[str]]) -> list[Path]:
    """Filter an iterable of candidate paths down to the ones that exist.

    Used by adapters that must never assume an executable path exists
    (00_MASTER_INSTRUCTION.md §12).
    """
    result: list[Path] = []
    for candidate in paths:
        if not candidate:
            continue
        try:
            resolved = Path(candidate).expanduser()
        except (OSError, ValueError):
            continue
        if resolved.exists():
            result.append(resolved.resolve())
    return result
