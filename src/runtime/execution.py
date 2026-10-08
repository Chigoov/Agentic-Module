"""Execution isolation and readiness checks for every agent workflow."""

from __future__ import annotations

import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from src.core.config import SystemConfig, get_config
from src.core.paths import PathResolutionError, SystemPaths, get_paths
from src.core.project_manager import ProjectManager
from src.runtime.bootstrap import health_check
from src.schemas.project import Project
from src.schemas.task import ResearchMode
from src.core.storage import write_json

__all__ = [
    "WorkflowReadinessError",
    "create_execution_project",
    "ensure_workflow_ready",
]


class WorkflowReadinessError(RuntimeError):
    """Raised when a workflow is missing a required runtime capability."""

    def __init__(self, issues: Iterable[str]) -> None:
        self.issues = tuple(str(issue) for issue in issues if str(issue).strip())
        super().__init__("Workflow preflight failed: " + "; ".join(self.issues))


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", value.strip().lower()).strip("_")
    return cleaned[:48] or "agent_task"


def _execution_name(base: str, command: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{_slug(base)}__{_slug(command)}_{stamp}_{uuid.uuid4().hex[:8]}"


def _copy_source_documents(template: Project, target: Project) -> None:
    source_dir = template.directory / "source_documents"
    if source_dir.is_dir():
        shutil.copytree(source_dir, target.directory / "source_documents", dirs_exist_ok=True)


def create_execution_project(
    *,
    user_request: str,
    command: str,
    workspace: str | None = None,
    template: Project | None = None,
    mode: ResearchMode = ResearchMode.ACADEMIC_WRITING,
    paths: SystemPaths | None = None,
    config: SystemConfig | None = None,
) -> Project:
    """Create a unique project folder for one agent task.

    Existing project artifacts are never reused. Only source documents are
    copied because they are immutable inputs; generated outputs belong to the
    new execution folder.
    """
    resolved_paths = paths or get_paths()
    resolved_config = config or get_config()
    base = template.name if template else (user_request or "agent_task")
    resolved_workspace = workspace or (template.workspace if template else resolved_config.projects.default_workspace)
    name = _execution_name(base, command)

    template_is_external = bool(template and not resolved_paths.is_inside_workspace(template.directory))
    try:
        workspace_path = resolved_paths.workspace_path(
            resolved_workspace,
            allowed_workspaces=resolved_config.projects.allowed_workspaces,
        )
    except PathResolutionError:
        if not template_is_external:
            raise
        resolved_workspace = resolved_config.projects.default_workspace
        workspace_path = resolved_paths.workspace_path(
            resolved_workspace,
            allowed_workspaces=resolved_config.projects.allowed_workspaces,
        )

    project = ProjectManager(config=resolved_config, paths=resolved_paths).create(
        workspace=resolved_workspace,
        name=name,
        user_request=user_request,
        mode=mode,
    )

    if template:
        _copy_source_documents(template, project)
        project.title = template.title
        project.citation_style = template.citation_style
        project.language = template.language
        project.output_type = template.output_type
        project.required_sections = list(template.required_sections)
        project.research_options = dict(template.research_options)
        project.origin_project_path = str(template.directory)
        write_json(project.directory / "project.json", project.model_dump(mode="json"), root=project.directory, overwrite=True)
    return project


def ensure_workflow_ready(
    *,
    project: Project,
    tools: Iterable[Any] = (),
    paths: SystemPaths | None = None,
) -> dict[str, Any]:
    """Verify the system, execution folder, and every requested tool first."""
    resolved_paths = paths or get_paths()
    issues: list[str] = []

    # A caller can provide a deliberately minimal portable root (for example
    # an isolated API test). Run the full system check whenever the root looks
    # like an installed AAI checkout; otherwise the folder/tool checks still
    # protect the execution without inventing a system installation.
    markers = ("00_MASTER_INSTRUCTION.md", "AGENT_CONSTITUTION.md", "ARCHITECTURE.md")
    if any((resolved_paths.system_root / marker).exists() for marker in markers):
        if not health_check(paths=resolved_paths):
            issues.append("system health check failed")
    if resolved_paths.is_inside_system_root(project.directory):
        issues.append("execution folder cannot be inside SYSTEM_ROOT")
    if not project.directory.is_dir():
        issues.append(f"execution folder does not exist: {project.directory}")
    else:
        try:
            probe = project.directory / ".aai_write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            issues.append(f"execution folder is not writable: {exc}")

    tool_report: list[dict[str, str]] = []
    for tool in tools:
        name = str(getattr(tool, "name", type(tool).__name__))
        available = bool(getattr(tool, "is_available", lambda: True)())
        status = getattr(getattr(tool, "status", lambda: "UNKNOWN")(), "value", "UNKNOWN")
        tool_report.append({"tool": name, "status": str(status), "available": str(available).lower()})
        if not available:
            issues.append(f"tool unavailable: {name} (status={status})")

    if issues:
        raise WorkflowReadinessError(issues)

    return {
        "ready": True,
        "python": sys.executable,
        "project_path": str(project.directory),
        "tools": tool_report,
    }


def resolve_source_paths(sources, project: Project) -> None:
    """Keep copied inputs local, recording their original location."""
    from pathlib import Path
    import hashlib
    origin = Path(project.origin_project_path) if project.origin_project_path else project.directory
    for source in sources:
        metadata_artifact = source.metadata.get("verification_artifact", {})
        paths = [(source, "retrieval_path"), (metadata_artifact if isinstance(metadata_artifact, dict) else {}, "path")]
        for owner, key in paths:
            raw = owner.get(key) if isinstance(owner, dict) else getattr(owner, key)
            if not raw:
                continue
            path = Path(raw)
            path = path if path.is_absolute() else origin / path
            try:
                candidate = project.directory / path.relative_to(origin)
            except ValueError:
                candidate = path
            if candidate != path and candidate.is_file() and path.is_file() and hashlib.sha256(candidate.read_bytes()).digest() == hashlib.sha256(path.read_bytes()).digest():
                source.metadata.setdefault("copied_input_origins", {})[key] = str(path)
                path = candidate
            if isinstance(owner, dict):
                owner[key] = str(path.resolve())
            else:
                setattr(owner, key, str(path.resolve()))
