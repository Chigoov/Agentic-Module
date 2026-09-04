"""Tests for project lifecycle management."""

from pathlib import Path

import pytest

from src.core.config import SystemConfig
from src.core.errors import ProjectError
from src.core.paths import SystemPaths
from src.core.project_manager import ProjectManager, create_project, list_projects, load_project
from src.schemas.project import PROJECT_MANIFEST_FILENAME, Project
from src.schemas.task import ResearchMode, Task, TaskState


@pytest.fixture
def project_manager(
    manager_with_temp_workspace: tuple[SystemConfig, Path]
) -> tuple[ProjectManager, Path]:
    """ProjectManager instance configured for temp workspace testing."""
    config, temp_workspace = manager_with_temp_workspace
    # Create a SystemPaths that treats temp_workspace.parent as workspace_root
    from src.core.paths import SystemPaths, get_paths
    
    real_paths = get_paths()
    paths = SystemPaths(
        workspace_root=temp_workspace.parent,
        system_root=real_paths.system_root,
    )
    manager = ProjectManager(config=config, paths=paths)
    return manager, temp_workspace


def test_create_project_in_temp_workspace(
    project_manager: tuple[ProjectManager, Path]
) -> None:
    """Creating a project in a temp workspace works."""
    manager, temp_workspace = project_manager
    project = manager.create(
        workspace=temp_workspace.name,
        name="test_project",
        user_request="Test request",
    )
    assert project.name == "test_project"
    assert project.workspace == temp_workspace.name
    assert project.user_request == "Test request"
    assert project.id.startswith("prj_")


def test_create_project_from_task(project_manager: tuple[ProjectManager, Path]) -> None:
    """Creating a project from a Task copies fields."""
    manager, temp_workspace = project_manager
    task = Task(
        user_request="Write a paper about X",
        workspace=temp_workspace.name,
        project_dir=str(temp_workspace / "auto_named"),
        mode=ResearchMode.DEEP_RESEARCH,
    )
    project = manager.create(task=task)
    assert project.task_id == task.id
    assert project.user_request == task.user_request
    assert project.mode is ResearchMode.DEEP_RESEARCH


def test_create_project_slugifies_name(project_manager: tuple[ProjectManager, Path]) -> None:
    """Project name is slugified from user request when not provided."""
    manager, temp_workspace = project_manager
    project = manager.create(
        workspace=temp_workspace.name,
        user_request="How does: deep learning / work?",
    )
    # Forbidden chars replaced with underscores, runs collapsed
    assert "/" not in project.name
    assert ":" not in project.name
    assert "__" not in project.name


def test_create_project_creates_manifest(project_manager: tuple[ProjectManager, Path]) -> None:
    """Project creation writes project.json."""
    manager, temp_workspace = project_manager
    project = manager.create(
        workspace=temp_workspace.name,
        name="test_project",
        user_request="Test",
    )
    manifest_file = project.directory / PROJECT_MANIFEST_FILENAME
    assert manifest_file.is_file()


def test_create_project_creates_subdirs(project_manager: tuple[ProjectManager, Path]) -> None:
    """Project creation creates source_documents/ subdirectory."""
    manager, temp_workspace = project_manager
    project = manager.create(
        workspace=temp_workspace.name,
        name="test_project",
        user_request="Test",
    )
    source_docs = project.directory / "source_documents"
    assert source_docs.is_dir()


def test_create_project_rejects_duplicate_without_exist_ok(
    project_manager: tuple[ProjectManager, Path]
) -> None:
    """Creating a project that already exists raises ProjectError."""
    manager, temp_workspace = project_manager
    manager.create(workspace=temp_workspace.name, name="duplicate", user_request="Test")
    with pytest.raises(ProjectError, match="already exists"):
        manager.create(workspace=temp_workspace.name, name="duplicate", user_request="Test")


def test_create_project_exist_ok_loads_existing(
    project_manager: tuple[ProjectManager, Path]
) -> None:
    """With exist_ok=True, an existing project is loaded instead of erroring."""
    manager, temp_workspace = project_manager
    original = manager.create(workspace=temp_workspace.name, name="existing", user_request="First")
    loaded = manager.create(
        workspace=temp_workspace.name,
        name="existing",
        user_request="Second",
        exist_ok=True,
    )
    # Should load the original, not create a new one
    assert loaded.id == original.id
    assert loaded.user_request == "First"


def test_load_project(project_manager: tuple[ProjectManager, Path]) -> None:
    """Loading a project by workspace+name works."""
    manager, temp_workspace = project_manager
    created = manager.create(workspace=temp_workspace.name, name="loadable", user_request="Test")
    loaded = manager.load(workspace=temp_workspace.name, name="loadable")
    assert loaded.id == created.id
    assert loaded.name == "loadable"


def test_load_project_missing_raises(project_manager: tuple[ProjectManager, Path]) -> None:
    """Loading a non-existent project raises ProjectError."""
    manager, temp_workspace = project_manager
    with pytest.raises(ProjectError, match="manifest not found"):
        manager.load(workspace=temp_workspace.name, name="missing")


def test_save_project(project_manager: tuple[ProjectManager, Path]) -> None:
    """Saving a project persists changes."""
    manager, temp_workspace = project_manager
    project = manager.create(workspace=temp_workspace.name, name="saveable", user_request="Test")
    # Mutate the project
    project.sync_task_state(TaskState.PLANNED, reason="test")
    manager.save(project)
    # Reload and verify
    reloaded = manager.load(workspace=temp_workspace.name, name="saveable")
    assert reloaded.task_state is TaskState.PLANNED


def test_list_workspace(project_manager: tuple[ProjectManager, Path]) -> None:
    """Listing a workspace returns all projects in it."""
    manager, temp_workspace = project_manager
    manager.create(workspace=temp_workspace.name, name="proj1", user_request="A")
    manager.create(workspace=temp_workspace.name, name="proj2", user_request="B")
    projects = manager.list_workspace(temp_workspace.name)
    assert len(projects) == 2
    names = {p.name for p in projects}
    assert names == {"proj1", "proj2"}


def test_list_workspace_empty_when_missing(project_manager: tuple[ProjectManager, Path]) -> None:
    """Listing a non-existent workspace returns an empty list."""
    manager, temp_workspace = project_manager
    projects = manager.list_workspace("nonexistent_workspace")
    assert projects == []
