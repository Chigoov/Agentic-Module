"""Tests for path resolution and workspace boundaries."""

from pathlib import Path

import pytest

from src.core.errors import PathSafetyError
from src.core.paths import PathResolutionError, SystemPaths, get_paths


def test_get_paths_discovers_system_root(real_system_root: Path) -> None:
    """get_paths() discovers this checkout wherever it lives (audit A07: the
    folder name is not the identity — the canonical spec files are)."""
    from src.core.paths import SPEC_FILES

    paths = get_paths()
    assert paths.system_root == real_system_root
    assert all((paths.system_root / name).is_file() for name in SPEC_FILES[:3])


def test_get_paths_derives_workspace_root(real_system_root: Path) -> None:
    """Workspace root is one level above system root, whatever the checkout
    folder is named (audit A07 portability)."""
    paths = get_paths()
    assert paths.workspace_root == real_system_root.parent
    assert paths.system_root.parent == paths.workspace_root


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


def test_project_workspaces_discovered(real_system_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Workspaces are discovered from the workspace root, independent of any
    pre-existing local folders (audit: clean clones must pass without a local
    ``TUGAS 1``). The check runs against an isolated synthetic workspace."""
    from src.core.paths import reset_paths_cache
    monkeypatch.setenv("AUTONOMI_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("AUTONOMI_SYSTEM_ROOT", str(real_system_root))
    reset_paths_cache()
    try:
        (tmp_path / "TUGAS 1").mkdir()
        (tmp_path / "TUGAS 2").mkdir()
        paths = get_paths()
        workspace_names = {ws.name for ws in paths.project_workspaces()}
        assert "TUGAS 1" in workspace_names
        assert "TUGAS 2" in workspace_names
    finally:
        reset_paths_cache()


def test_workspace_path_resolves_correctly(real_system_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """workspace_path() resolves a workspace to workspace_root/<name> without
    requiring it to exist physically beforehand (audit: clean-clone portability)."""
    from src.core.paths import reset_paths_cache
    monkeypatch.setenv("AUTONOMI_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("AUTONOMI_SYSTEM_ROOT", str(real_system_root))
    reset_paths_cache()
    try:
        paths = get_paths()
        tugas1 = paths.workspace_path("TUGAS 1")
        assert tugas1 == tmp_path / "TUGAS 1"
    finally:
        reset_paths_cache()


def test_workspace_path_rejects_system_root() -> None:
    """workspace_path() must refuse the SYSTEM_ROOT folder itself, whatever
    the checkout is named (audit A07 portability)."""
    paths = get_paths()
    with pytest.raises(PathResolutionError, match="SYSTEM_ROOT is not a project workspace"):
        paths.workspace_path(paths.system_root.name)


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
