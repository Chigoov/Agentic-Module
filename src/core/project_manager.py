"""Project lifecycle management.

Specification anchors:
  * BUILD_PLAN.md §1 — project manager is a Phase 1 foundation component.
  * 00_MASTER_INSTRUCTION.md §22 — project storage.
  * SYSTEM_RULES.md §A.3 — TUGAS 1/TUGAS 2 are project workspaces.

A project is a folder inside a workspace (e.g. TUGAS 1/my_research) holding all
artifacts for one research task. The project manager creates the folder
structure, writes the ``project.json`` manifest, and provides load/update/list
operations while enforcing path safety (nothing touches DATA BASE).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

from src.core.config import SystemConfig, get_config
from src.core.errors import ProjectError
from src.core.logging import get_logger
from src.core.paths import PathResolutionError, SystemPaths, get_paths
from src.core.storage import PathSafetyError, read_json, write_json
from src.schemas.project import (
    PROJECT_MANIFEST_FILENAME,
    PROJECT_SUBDIRS,
    Project,
)
from src.schemas.task import ResearchMode, Task

__all__ = [
    "ProjectManager",
    "create_project",
    "load_project",
    "list_projects",
]

_logger = get_logger(__name__)

#: Characters disallowed in project folder names.
_NAME_FORBIDDEN = frozenset({'/', '\\', ':', '*', '?', '"', '<', '>', '|', '\x00'})


def _slugify(text: str) -> str:
    """Normalize text into a safe folder name, collapsing whitespace/punctuation."""
    cleaned = "".join(
        char if char not in _NAME_FORBIDDEN and not char.isspace() else "_" for char in text
    )
    # Collapse runs of underscores.
    collapsed = re.sub(r"_{2,}", "_", cleaned.strip("_"))
    return collapsed[:80] if collapsed else "project"


class ProjectManager:
    """Project lifecycle facade with safe path resolution.

    Attributes
    ----------
    config:
        System configuration.
    paths:
        System paths.
    """

    def __init__(
        self,
        *,
        config: SystemConfig | None = None,
        paths: SystemPaths | None = None,
    ) -> None:
        self.config = config or get_config()
        self.paths = paths or get_paths()

    # -------------------------------------------------------------- creation
    def create(
        self,
        *,
        task: Task | None = None,
        workspace: str | None = None,
        name: str | None = None,
        user_request: str = "",
        mode: ResearchMode = ResearchMode.ACADEMIC_WRITING,
        exist_ok: bool = False,
    ) -> Project:
        """Create a new research project in the specified workspace.

        Parameters
        ----------
        task:
            Existing :class:`~src.schemas.task.Task` to bind the project to.
            When supplied, most parameters are taken from the task.
        workspace:
            Name of the project workspace (e.g. ``"TUGAS 1"``). Defaults to
            ``config.projects.default_workspace``.
        name:
            Folder name; slugified from ``user_request`` when absent.
        user_request:
            Original user request text.
        mode:
            Research mode.
        exist_ok:
            When ``True``, a previously existing manifest is loaded instead
            of raising :class:`ProjectError`.

        Returns
        -------
        Project
            The newly created (or loaded) project.

        Raises
        ------
        ProjectError
            When the project already exists and ``exist_ok`` is ``False``,
            or when workspace creation is disabled but the workspace is missing.
        PathSafetyError
            When the resolved path escapes the workspace root.
        """
        if task is not None:
            resolved_workspace = task.workspace
            resolved_name = name or _slugify(task.user_request)
            resolved_request = task.user_request
            resolved_mode = task.mode
            task_id: str | None = task.id
        else:
            resolved_workspace = workspace or self.config.projects.default_workspace
            resolved_name = name or _slugify(user_request)
            resolved_request = user_request
            resolved_mode = mode
            task_id = None

        workspace_path = self._resolve_workspace(resolved_workspace)
        if not workspace_path.exists():
            if not self.config.projects.allow_workspace_creation:
                raise ProjectError(
                    f"Workspace {resolved_workspace!r} does not exist and "
                    "projects.allow_workspace_creation is disabled",
                    workspace=resolved_workspace,
                )
            _logger.info(
                "Creating workspace",
                extra={"workspace": resolved_workspace, "path": str(workspace_path)},
            )
            workspace_path.mkdir(parents=True, exist_ok=True)

        project_dir = workspace_path / resolved_name
        manifest_file = project_dir / PROJECT_MANIFEST_FILENAME

        if manifest_file.is_file():
            if exist_ok:
                _logger.info(
                    "Project already exists, loading",
                    extra={"project": resolved_name, "workspace": resolved_workspace},
                )
                return self.load(workspace=resolved_workspace, name=resolved_name)
            raise ProjectError(
                f"Project {resolved_name!r} already exists in {resolved_workspace!r}",
                workspace=resolved_workspace,
                name=resolved_name,
                path=str(project_dir),
            )

        # Build the manifest before creating any folders.
        project = Project(
            name=resolved_name,
            workspace=resolved_workspace,
            path=str(project_dir.resolve()),
            task_id=task_id,
            title=resolved_request[:120] if resolved_request else resolved_name,
            user_request=resolved_request,
            mode=resolved_mode,
            citation_style=self.config.research.default_citation_style,
            language=self.config.research.default_language,
            schema_version=self.config.system.spec_version,
        )

        # Create the folder structure.
        project_dir.mkdir(parents=True, exist_ok=False)
        for subdir in PROJECT_SUBDIRS:
            (project_dir / subdir).mkdir(parents=False, exist_ok=True)

        # Write the manifest.
        write_json(manifest_file, project, root=workspace_path, overwrite=False)

        _logger.info(
            "Project created",
            extra={
                "project_id": project.id,
                "name": resolved_name,
                "workspace": resolved_workspace,
                "path": self.paths.relative(project_dir),
            },
        )
        return project

    def load(self, *, workspace: str, name: str) -> Project:
        """Load an existing project manifest.

        Raises
        ------
        ProjectError
            When the manifest is missing or invalid.
        """
        workspace_path = self._resolve_workspace(workspace)
        project_dir = workspace_path / name
        manifest_file = project_dir / PROJECT_MANIFEST_FILENAME

        if not manifest_file.is_file():
            raise ProjectError(
                f"Project manifest not found: {manifest_file}",
                workspace=workspace,
                name=name,
            )

        try:
            data = read_json(manifest_file)
            project = Project.from_dict(data)
        except Exception as exc:
            raise ProjectError(
                f"Failed to load project manifest: {manifest_file}",
                workspace=workspace,
                name=name,
                error=str(exc),
            ) from exc

        _logger.debug(
            "Project loaded",
            extra={
                "project_id": project.id,
                "name": name,
                "workspace": workspace,
                "task_state": str(project.task_state),
            },
        )
        return project

    def save(self, project: Project) -> None:
        """Persist changes to a project manifest.

        The project's ``updated_at`` is refreshed automatically.
        """
        project.touch()
        workspace_path = self._resolve_workspace(project.workspace)
        manifest_file = project.directory / PROJECT_MANIFEST_FILENAME
        write_json(manifest_file, project, root=workspace_path, overwrite=True)
        _logger.debug("Project manifest saved", extra={"project_id": project.id})

    def list_workspace(self, workspace: str) -> list[Project]:
        """List every project in the specified workspace, ignoring invalid ones.

        Returns an empty list when the workspace does not exist.
        """
        try:
            workspace_path = self._resolve_workspace(workspace)
        except PathResolutionError:
            return []
        if not workspace_path.is_dir():
            return []

        projects: list[Project] = []
        for entry in workspace_path.iterdir():
            if not entry.is_dir():
                continue
            manifest = entry / PROJECT_MANIFEST_FILENAME
            if not manifest.is_file():
                continue
            try:
                projects.append(self.load(workspace=workspace, name=entry.name))
            except ProjectError as exc:
                _logger.warning("Skipping invalid project", extra={"path": str(entry), "error": str(exc)})
                continue
        return sorted(projects, key=lambda p: p.created_at, reverse=True)

    def list_all(self, *, workspaces: Iterable[str] | None = None) -> list[Project]:
        """List projects across multiple workspaces.

        Parameters
        ----------
        workspaces:
            Workspace names to scan. When ``None``, every available project
            workspace is scanned (discovered via :meth:`~SystemPaths.project_workspaces`).
        """
        if workspaces is None:
            candidates = [ws.name for ws in self.paths.project_workspaces()]
        else:
            candidates = list(workspaces)

        all_projects: list[Project] = []
        for ws_name in candidates:
            all_projects.extend(self.list_workspace(ws_name))
        return sorted(all_projects, key=lambda p: p.created_at, reverse=True)

    # ----------------------------------------------------------- helpers
    def _resolve_workspace(self, name: str) -> Path:
        """Resolve a workspace name to an absolute path inside WORKSPACE_ROOT.

        Raises
        ------
        PathResolutionError
            When the workspace path escapes WORKSPACE_ROOT or targets SYSTEM_ROOT.
        """
        return self.paths.workspace_path(name)


# ---------------------------------------------------------------- module API
_default_manager: ProjectManager | None = None


def _get_manager() -> ProjectManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = ProjectManager()
    return _default_manager


def create_project(
    *,
    task: Task | None = None,
    workspace: str | None = None,
    name: str | None = None,
    user_request: str = "",
    mode: ResearchMode = ResearchMode.ACADEMIC_WRITING,
    exist_ok: bool = False,
) -> Project:
    """Create a new research project. See :meth:`ProjectManager.create`."""
    return _get_manager().create(
        task=task,
        workspace=workspace,
        name=name,
        user_request=user_request,
        mode=mode,
        exist_ok=exist_ok,
    )


def load_project(*, workspace: str, name: str) -> Project:
    """Load an existing project manifest. See :meth:`ProjectManager.load`."""
    return _get_manager().load(workspace=workspace, name=name)


def list_projects(
    *, workspace: str | None = None, workspaces: Iterable[str] | None = None
) -> list[Project]:
    """List projects in one or all workspaces. See :meth:`ProjectManager.list_workspace` / :meth:`ProjectManager.list_all`."""
    manager = _get_manager()
    if workspace is not None:
        return manager.list_workspace(workspace)
    return manager.list_all(workspaces=workspaces)
