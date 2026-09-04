"""Tests for path resolution and workspace boundaries."""

from pathlib import Path

import pytest

from src.core.errors import PathSafetyError
from src.core.paths import PathResolutionError, SystemPaths, get_paths


def test_get_paths_discovers_system_root(real_system_root: Path) -> None:
    """Verify that get_paths() discovers DATA BASE from the filesystem."""
    paths = get_paths()
    assert paths.system_root == real_system_root
    assert paths.system_root.name == "DATA BASE"


def test_get_paths_derives_workspace_root(real_system_root: Path) -> None:
    """Workspace root is one level above system root."""
    paths = get_paths()
    assert paths.workspace_root == real_system_root.parent
    assert paths.system_root == paths.workspace_root / "DATA BASE"


def test_system_paths_properties_exist() -> None:
    """All derived path properties are callable and return Path objects."""
    paths = get_paths()
    assert isinstance(paths.src_dir, Path)
    assert isinstance(paths.config_dir, Path)
    assert isinstance(paths.database_dir, Path)
    assert isinstance(paths.logs_dir, Path)
    assert isinstance(paths.cache_dir, Path)
    assert isinstance(paths.state_dir, Path)
    assert isinstance(paths.runtime_dir, Path)
    # runtime_dir is a backward-compatible alias for state_dir (M1).
    assert paths.runtime_dir == paths.state_dir
    assert isinstance(paths.prompts_dir, Path)
    assert isinstance(paths.system_config_file, Path)


def test_spec_files_present(real_system_root: Path) -> None:
    """All six specification files must be present."""
    paths = get_paths()
    missing = paths.missing_spec_files()
    assert missing == [], f"Missing specification files: {missing}"


def test_project_workspaces_discovered() -> None:
    """TUGAS 1 and TUGAS 2 should be discovered as project workspaces."""
    paths = get_paths()
    workspaces = paths.project_workspaces()
    workspace_names = {ws.name for ws in workspaces}
    assert "TUGAS 1" in workspace_names
    assert "TUGAS 2" in workspace_names


def test_workspace_path_resolves_correctly() -> None:
    """workspace_path() should resolve TUGAS 1 to workspace_root/TUGAS 1."""
    paths = get_paths()
    tugas1 = paths.workspace_path("TUGAS 1")
    assert tugas1 == paths.workspace_root / "TUGAS 1"
    assert tugas1.is_dir()


def test_workspace_path_rejects_system_root() -> None:
    """workspace_path() must refuse to return SYSTEM_ROOT (DATA BASE)."""
    paths = get_paths()
    with pytest.raises(PathResolutionError, match="SYSTEM_ROOT is not a project workspace"):
        paths.workspace_path("DATA BASE")


def test_workspace_path_rejects_escape() -> None:
    """workspace_path() must refuse paths that escape WORKSPACE_ROOT."""
    paths = get_paths()
    with pytest.raises(PathResolutionError):
        paths.workspace_path("../../../etc")


def test_relative_path_to_workspace_root() -> None:
    """relative() should compute paths relative to workspace root."""
    paths = get_paths()
    tugas1 = paths.workspace_root / "TUGAS 1"
    rel = paths.relative(tugas1)
    assert rel == "TUGAS 1"


def test_relative_path_outside_workspace_returns_absolute() -> None:
    """relative() returns the absolute path when target is outside workspace."""
    paths = get_paths()
    outside = Path("/some/other/path")
    rel = paths.relative(outside)
    assert rel == outside.resolve().as_posix()
