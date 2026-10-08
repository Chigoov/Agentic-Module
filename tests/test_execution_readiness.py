from pathlib import Path

import pytest

from src.core.config import SystemConfig
from src.core.paths import SystemPaths
from src.runtime.execution import (
    WorkflowReadinessError,
    create_execution_project,
    ensure_workflow_ready,
)


class _UnavailableTool:
    name = "missing_tool"

    def status(self):
        return "NOT_IMPLEMENTED"

    def is_available(self):
        return False


def test_each_execution_gets_a_fresh_folder_and_source_copy(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    system_root = workspace / "DATA BASE"
    workspace.mkdir()
    system_root.mkdir()
    paths = SystemPaths(workspace_root=workspace, system_root=system_root)
    config = SystemConfig()
    (workspace / "TUGAS 1").mkdir()

    template_dir = tmp_path / "template"
    (template_dir / "source_documents").mkdir(parents=True)
    (template_dir / "source_documents" / "paper.pdf").write_bytes(b"pdf")
    from src.schemas.project import Project

    template = Project(name="topic", workspace="TUGAS 1", path=str(template_dir), title="Original title",
        language="en", citation_style="APA7", research_options={"require_free_full_text": True}, output_type="literature_review")
    first = create_execution_project(
        user_request="Topic", command="research", template=template,
        paths=paths, config=config,
    )
    second = create_execution_project(
        user_request="Topic", command="research", template=template,
        paths=paths, config=config,
    )

    assert first.directory != second.directory
    assert first.directory.parent == workspace / "TUGAS 1"
    assert (first.directory / "source_documents" / "paper.pdf").read_bytes() == b"pdf"
    assert first.title == template.title and first.language == "en" and first.citation_style == "APA7"
    assert first.research_options == template.research_options and first.output_type == "literature_review"
    from src.runtime.execution import resolve_source_paths
    from src.schemas.source import Source
    source = Source(title="Copy", retrieval_path=str(template_dir / "source_documents" / "paper.pdf"))
    resolve_source_paths([source], first)
    assert source.retrieval_path == str(first.directory / "source_documents" / "paper.pdf")
    assert source.metadata["copied_input_origins"]["retrieval_path"] == str(template_dir / "source_documents" / "paper.pdf")


def test_preflight_blocks_unavailable_tool(tmp_path: Path) -> None:
    system_root = tmp_path / "DATA BASE"
    system_root.mkdir()
    paths = SystemPaths(workspace_root=tmp_path, system_root=system_root)
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    from src.schemas.project import Project

    project = Project(name="project", workspace="tmp", path=str(project_dir))
    with pytest.raises(WorkflowReadinessError, match="missing_tool"):
        ensure_workflow_ready(project=project, tools=[_UnavailableTool()], paths=paths)
