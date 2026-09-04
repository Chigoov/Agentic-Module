"""Pytest configuration and shared fixtures.

All tests in this suite are integration tests that exercise the real bootstrap,
paths, config, and storage layer. Unit tests for pure functions will be added
later if needed, but Phase 1 focuses on proving the foundation fits together.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest

from src.core.config import SystemConfig, get_config, load_config
from src.core.paths import SystemPaths, get_paths


@pytest.fixture(scope="session")
def real_system_root() -> Path:
    """The actual DATA BASE folder, used by tests that need to read specs."""
    paths = get_paths()
    return paths.system_root


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Generator[Path, None, None]:
    """Isolated temporary workspace for tests that create projects or artifacts."""
    workspace = tmp_path / "test_workspace"
    workspace.mkdir()
    yield workspace


@pytest.fixture
def isolated_config(temp_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> SystemConfig:
    """Load config in an isolated environment, preventing cache pollution.

    Tests that mutate the environment or need a clean config cache should use this.
    """
    # Clear the module-level caches using the provided reset functions.
    from src.core.config import reset_config_cache
    from src.core.logging import reset_logging
    from src.core.paths import reset_paths_cache

    reset_config_cache()
    reset_paths_cache()
    reset_logging()

    # Point logging to a temp directory so tests don't pollute the real logs/.
    monkeypatch.setenv("AUTONOMI__LOGGING__FILE", "false")

    config = get_config()
    return config


@pytest.fixture
def manager_with_temp_workspace(
    temp_workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[SystemConfig, Path]:
    """Config and workspace path with workspace creation enabled for project tests."""
    from src.core.config import reset_config_cache
    from src.core.paths import reset_paths_cache

    reset_config_cache()
    reset_paths_cache()

    # Enable workspace creation and point logging to temp
    monkeypatch.setenv("AUTONOMI__PROJECTS__ALLOW_WORKSPACE_CREATION", "true")
    monkeypatch.setenv("AUTONOMI__LOGGING__FILE", "false")

    config = get_config()
    return config, temp_workspace
