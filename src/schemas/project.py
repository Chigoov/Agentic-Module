"""Project artifact contract.

Specification anchor: 00_MASTER_INSTRUCTION.md §22 — project storage.

``project.json`` is the manifest that makes a project folder self-describing:
which task it serves, which spec version created it, and which artifacts are
expected. Keeping it as a validated schema (rather than an ad-hoc dict inside
the project manager) means a project written by one version of the system can
be inspected and migrated by a later one.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import Field

from src.schemas.base import BaseRecord
from src.schemas.task import ResearchMode, TaskState

__all__ = [
    "ProjectArtifact",
    "PROJECT_ARTIFACTS",
    "PROJECT_SUBDIRS",
    "PROJECT_MANIFEST_FILENAME",
    "Project",
]

#: Name of the manifest file inside every project folder.
PROJECT_MANIFEST_FILENAME = "project.json"


class ProjectArtifact(StrEnum):
    """Canonical artifact filenames from 00_MASTER_INSTRUCTION.md §22.

    Declared as an enum so that stage implementations in later phases reference
    a shared constant instead of repeating string literals.
    """

    RESEARCH_PLAN = "research_plan.json"
    CANDIDATES = "candidates.jsonl"
    SEARCH_LOG = "search_log.jsonl"
    VERIFIED_SOURCES = "verified_sources.json"
    CLAIMS = "claims.json"
    EVIDENCE = "evidence.jsonl"
    OUTLINE = "outline.json"
    DRAFT = "draft.md"
    CITATION_AUDIT = "citation_audit.json"
    FACT_AUDIT = "fact_audit.json"
    FINAL_DOCX = "final.docx"


#: Ordered tuple of expected artifacts, mirroring the research data flow.
PROJECT_ARTIFACTS: tuple[ProjectArtifact, ...] = tuple(ProjectArtifact)

#: Subdirectories created inside a project folder.
PROJECT_SUBDIRS: tuple[str, ...] = ("source_documents",)


class Project(BaseRecord):
    """Manifest describing one research project on disk.

    Attributes
    ----------
    name:
        Folder name of the project inside its workspace.
    workspace:
        Project workspace that contains it (e.g. ``"TUGAS 1"``).
    path:
        Absolute path to the project folder.
    task_id:
        ID of the :class:`~src.schemas.task.Task` this project serves.
    title:
        Human-readable title, defaults to the folder name.
    user_request:
        Original request, duplicated here so a project folder is
        self-explanatory without loading system state.
    mode:
        Research mode the project was created for.
    task_state:
        Last known task state, mirrored for quick inspection.
    spec_version:
        Specification version that created the project, for future migration.
    citation_style:
        Citation style in effect for this project.
    language:
        Output language for the document.
    """

    id_prefix: str = Field(default="prj", exclude=True, repr=False)

    name: str = Field(min_length=1)
    workspace: str
    path: str
    task_id: str | None = None
    title: str | None = None
    user_request: str = ""
    mode: ResearchMode = ResearchMode.ACADEMIC_WRITING
    task_state: TaskState = TaskState.CREATED
    citation_style: str = "APA7"
    language: str = "id"

    @property
    def directory(self) -> Path:
        """Project folder as a :class:`~pathlib.Path`."""
        return Path(self.path)

    def artifact_path(self, artifact: ProjectArtifact | str) -> Path:
        """Absolute path of a canonical artifact inside this project."""
        filename = artifact.value if isinstance(artifact, ProjectArtifact) else artifact
        return self.directory / filename

    def sync_task_state(self, state: TaskState, *, reason: str) -> None:
        """Mirror a task state change into the manifest with an audit entry."""
        previous = self.task_state
        if previous == state:
            return
        self.record_transition(
            from_state=str(previous), to_state=str(state), reason=reason, actor="project_manager"
        )
        self.task_state = state
