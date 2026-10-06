"""Unit and integration tests for workspace discovery, project paths, and isolation.

Verification anchors:
- Workspace discovery: allowed vs unallowed folders (DATA BASE, scripts, cache, logs).
- Path helpers: source_path, run_path, export_path, artifact_path.
- Security: rejection of path traversal, absolute path escapes, empty filenames.
- Project isolation: project A vs B isolation, strict prohibition of writing into DATA BASE.
- Retrieval routing: deterministic source storage and book PDF filename sanitization.
- Backward compatibility and storage regression.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.core.config import SystemConfig
from src.core.errors import PathSafetyError, ProjectError
from src.core.paths import PathResolutionError, SystemPaths, get_paths, reset_paths_cache
from src.core.project_manager import ProjectManager
from src.core.storage import (
    append_jsonl,
    atomic_write_text,
    backup_file,
    ensure_within,
    read_json,
    read_jsonl,
    write_json,
)
from src.schemas.project import (
    PROJECT_ARTIFACTS,
    PROJECT_MANIFEST_FILENAME,
    Project,
    ProjectArtifact,
)
from src.schemas.source import Source, SourceState, SourceType
from src.tools.retrieval import RetrievalRequest, RetrievalTool, safe_source_filename


# --------------------------------------------------------------------------- #
# 1. Workspace discovery
# --------------------------------------------------------------------------- #
def test_workspace_discovery_filters_reserved_and_unallowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only allowed workspaces are discovered; reserved/system folders are excluded."""
    workspace_root = tmp_path / "workspaces"
    workspace_root.mkdir()
    system_root = workspace_root / "DATA BASE"
    system_root.mkdir()

    # Create allowed workspaces
    (workspace_root / "TUGAS 1").mkdir()
    (workspace_root / "TUGAS 2").mkdir()

    # Create reserved and system folders that MUST NOT be discovered as workspaces
    (workspace_root / "scripts").mkdir()
    (workspace_root / "downloaded_articles").mkdir()
    (workspace_root / "cache").mkdir()
    (workspace_root / "logs").mkdir()
    (workspace_root / "state").mkdir()
    (workspace_root / "random_unregistered_folder").mkdir()
    (workspace_root / ".hidden_folder").mkdir()

    paths = SystemPaths(workspace_root=workspace_root, system_root=system_root)

    # When allowed_workspaces is specified (as in system.yaml)
    discovered = paths.project_workspaces(allowed_workspaces=["TUGAS 1", "TUGAS 2"])
    discovered_names = [p.name for p in discovered]

    assert discovered_names == ["TUGAS 1", "TUGAS 2"]
    assert "DATA BASE" not in discovered_names
    assert "scripts" not in discovered_names
    assert "downloaded_articles" not in discovered_names
    assert "cache" not in discovered_names
    assert "logs" not in discovered_names
    assert "state" not in discovered_names
    assert "random_unregistered_folder" not in discovered_names


def test_workspace_path_rejects_reserved_and_escapes(tmp_path: Path) -> None:
    """workspace_path() rejects reserved folders, system root, and traversal."""
    workspace_root = tmp_path / "workspaces"
    workspace_root.mkdir()
    system_root = workspace_root / "DATA BASE"
    system_root.mkdir()

    paths = SystemPaths(workspace_root=workspace_root, system_root=system_root)

    # 1. Valid workspace
    tugas1 = paths.workspace_path("TUGAS 1", allowed_workspaces=["TUGAS 1"])
    assert tugas1 == (workspace_root / "TUGAS 1").resolve()

    # 2. SYSTEM_ROOT rejected
    with pytest.raises(PathResolutionError, match="SYSTEM_ROOT is not a project workspace"):
        paths.workspace_path("DATA BASE")

    # 3. Reserved directory rejected
    with pytest.raises(PathResolutionError, match="reserved system directory"):
        paths.workspace_path("scripts")
    with pytest.raises(PathResolutionError, match="reserved system directory"):
        paths.workspace_path("downloaded_articles")
    with pytest.raises(PathResolutionError, match="reserved system directory"):
        paths.workspace_path("cache")

    # 4. Path traversal rejected
    with pytest.raises(PathResolutionError, match="path separators/traversal forbidden"):
        paths.workspace_path("../outside")
    with pytest.raises(PathResolutionError, match="path separators/traversal forbidden"):
        paths.workspace_path("sub/folder")

    # 5. Empty or null byte rejected
    with pytest.raises(PathResolutionError, match="cannot be empty"):
        paths.workspace_path("")
    with pytest.raises(PathResolutionError, match="null bytes forbidden"):
        paths.workspace_path("invalid\x00name")

    # 6. Unallowed workspace rejected
    with pytest.raises(PathResolutionError, match="not an allowed workspace"):
        paths.workspace_path("TUGAS 99", allowed_workspaces=["TUGAS 1", "TUGAS 2"])


# --------------------------------------------------------------------------- #
# 2. Project path helpers
# --------------------------------------------------------------------------- #
def test_project_path_helpers_resolution(tmp_path: Path) -> None:
    """Project helper methods resolve to deterministic locations inside project."""
    project_dir = tmp_path / "my_project"
    project_dir.mkdir()
    (project_dir / "source_documents").mkdir()
    (project_dir / "runs").mkdir()
    (project_dir / "exports").mkdir()

    project = Project(
        name="my_project",
        workspace="TUGAS 1",
        path=str(project_dir),
        title="My Project",
    )

    # 1. source_path
    src_p = project.source_path("paper.pdf")
    assert src_p == (project_dir / "source_documents" / "paper.pdf").resolve()
    assert src_p.parent.name == "source_documents"

    # 2. run_path (directory and file)
    run_dir = project.run_path("run_20260922_abc123")
    assert run_dir == (project_dir / "runs" / "run_20260922_abc123").resolve()

    run_file = project.run_path("run_20260922_abc123", "run_summary.json")
    assert run_file == (project_dir / "runs" / "run_20260922_abc123" / "run_summary.json").resolve()

    # 3. export_path
    export_p = project.export_path("bundle.zip")
    assert export_p == (project_dir / "exports" / "bundle.zip").resolve()
    assert export_p.parent.name == "exports"

    # 4. artifact_path (canonical enum & str)
    docx_p = project.artifact_path(ProjectArtifact.FINAL_DOCX)
    assert docx_p == (project_dir / "final.docx").resolve()

    draft_p = project.artifact_path("draft.md")
    assert draft_p == (project_dir / "draft.md").resolve()


def test_project_path_helpers_reject_traversal_and_malformed(tmp_path: Path) -> None:
    """All path helpers refuse path traversal, external paths, and invalid names."""
    project_dir = tmp_path / "secure_project"
    project_dir.mkdir()
    (project_dir / "source_documents").mkdir()
    (project_dir / "runs").mkdir()
    (project_dir / "exports").mkdir()

    project = Project(
        name="secure_project",
        workspace="TUGAS 1",
        path=str(project_dir),
        title="Secure Project",
    )

    # Path traversal rejection
    for traversal in ("../secret.txt", "..\\secret.txt", "../../etc/passwd", "sub/../../escape.txt"):
        with pytest.raises(PathSafetyError):
            project.source_path(traversal)
        with pytest.raises(PathSafetyError):
            project.export_path(traversal)
        with pytest.raises(PathSafetyError):
            project.artifact_path(traversal)
        with pytest.raises(PathSafetyError):
            project.run_path("run_1", traversal)

    # Traversal in run_id itself
    with pytest.raises(PathSafetyError):
        project.run_path("../evil_run")
    with pytest.raises(PathSafetyError):
        project.run_path("..\\evil_run")

    # Empty or relative pointers
    for empty in ("", "   ", ".", ".."):
        with pytest.raises(PathSafetyError):
            project.source_path(empty)
        with pytest.raises(PathSafetyError):
            project.export_path(empty)
        with pytest.raises(PathSafetyError):
            project.artifact_path(empty)
        with pytest.raises(PathSafetyError):
            project.run_path(empty)

    # Null bytes
    with pytest.raises(PathSafetyError):
        project.source_path("bad\x00file.pdf")
    with pytest.raises(PathSafetyError):
        project.run_path("bad\x00run")
    with pytest.raises(PathSafetyError):
        project.export_path("bad\x00bundle.zip")
    with pytest.raises(PathSafetyError):
        project.artifact_path("bad\x00artifact.json")


# --------------------------------------------------------------------------- #
# 3. Project isolation
# --------------------------------------------------------------------------- #
def test_cross_project_isolation(tmp_path: Path) -> None:
    """Project A and Project B cannot cross-access or overwrite each other."""
    proj_a_dir = tmp_path / "project_a"
    proj_a_dir.mkdir()
    (proj_a_dir / "source_documents").mkdir()

    proj_b_dir = tmp_path / "project_b"
    proj_b_dir.mkdir()
    (proj_b_dir / "source_documents").mkdir()

    proj_a = Project(name="project_a", workspace="TUGAS 1", path=str(proj_a_dir))
    proj_b = Project(name="project_b", workspace="TUGAS 1", path=str(proj_b_dir))

    # Path derivation produces distinct directories
    assert proj_a.source_path("data.pdf") != proj_b.source_path("data.pdf")
    assert proj_a.export_path("out.zip") != proj_b.export_path("out.zip")

    # Project A cannot claim ownership of Project B's path
    path_b_doc = proj_b.source_path("data.pdf")
    with pytest.raises(PathSafetyError):
        ensure_within(path_b_doc, proj_a.directory)

    # Refuse writing into Project B using Project A's root
    with pytest.raises(PathSafetyError):
        atomic_write_text(path_b_doc, "illegal write", root=proj_a.directory)


def test_refuse_project_inside_data_base(tmp_path: Path) -> None:
    """Project creation and saving explicitly refuse targeting SYSTEM_ROOT."""
    workspace_root = tmp_path / "workspaces"
    workspace_root.mkdir()
    system_root = workspace_root / "DATA BASE"
    system_root.mkdir()
    tugas1 = workspace_root / "TUGAS 1"
    tugas1.mkdir()

    paths = SystemPaths(workspace_root=workspace_root, system_root=system_root)
    cfg = SystemConfig()
    manager = ProjectManager(config=cfg, paths=paths)

    # Refuse creating project targeting DATA BASE as workspace
    with pytest.raises(ProjectError):
        manager.create(workspace="DATA BASE", name="sub_proj")

    # Refuse creating project inside DATA BASE directory
    with pytest.raises(ProjectError):
        ProjectManager(config=cfg, paths=paths).create(
            workspace="DATA BASE",
            name="malicious",
        )


# --------------------------------------------------------------------------- #
# 4. Retrieval routing & E-book safe filename
# --------------------------------------------------------------------------- #
def test_retrieval_routes_to_active_project_and_safe_filename(tmp_path: Path) -> None:
    """Retrieval routes strictly to project source_documents with clean filenames."""
    project_dir = tmp_path / "retrieval_proj"
    project_dir.mkdir()
    (project_dir / "source_documents").mkdir()
    project = Project(name="retrieval_proj", workspace="TUGAS 1", path=str(project_dir))

    # 1. Book with title produces kebab-case safe filename
    book_source = Source(
        title="Metodologi Penelitian & Desain Eksperimen: Edisi Ke-2 / Revisi!",
        source_type=SourceType.BOOK,
        abstract="Bab 1 pengantar metodologi.",
    )
    safe_name = safe_source_filename(book_source, "pdf")
    assert "/" not in safe_name
    assert "\\" not in safe_name
    assert ":" not in safe_name
    assert "!" not in safe_name
    assert safe_name.endswith(".pdf")
    assert safe_name.startswith("metodologi-penelitian")

    # 2. Execution routes through project.source_path
    tool = RetrievalTool()
    response = tool.execute(RetrievalRequest(project=project, source=book_source))

    assert response.success is True
    assert response.document_path is not None
    doc_path = Path(response.document_path)
    assert doc_path.is_file()
    assert doc_path.parent == (project_dir / "source_documents").resolve()
    assert doc_path == project.source_path(doc_path.name)
    assert book_source.metadata["file_path"] == f"source_documents/{doc_path.name}"
    assert book_source.metadata["source_type"] == "book"


def test_retrieval_refuses_missing_or_invalid_project() -> None:
    """Retrieval fails gracefully when project is missing or points to DATA BASE."""
    from pydantic import ValidationError

    source = Source(title="Sample Paper", abstract="Sample abstract")
    tool = RetrievalTool()

    # 1. Pydantic rejects None project at request validation
    with pytest.raises(ValidationError):
        RetrievalRequest(project=None, source=source)  # type: ignore[arg-type]

    # 2. Even if constructed directly without validation, tool refuses None project
    req_none = RetrievalRequest.model_construct(project=None, source=source)
    res_none = tool.execute(req_none)
    assert res_none.success is False
    assert res_none.error_code == "NO_ACTIVE_PROJECT"

    # 3. Project pointing to DATA BASE is rejected
    real_paths = get_paths()
    bad_project = Project(
        name="evil_in_system_root",
        workspace="DATA BASE",
        path=str(real_paths.system_root / "evil_proj"),
    )
    res_bad = tool.execute(RetrievalRequest(project=bad_project, source=source))
    assert res_bad.success is False
    assert res_bad.error_code == "INVALID_PROJECT_CONTEXT"


# --------------------------------------------------------------------------- #
# 5. Canonical artifacts and storage regression
# --------------------------------------------------------------------------- #
def test_canonical_artifacts_compatibility(tmp_path: Path) -> None:
    """Every standard canonical artifact resolves directly under project root."""
    project_dir = tmp_path / "canonical_proj"
    project_dir.mkdir()
    project = Project(name="canonical_proj", workspace="TUGAS 1", path=str(project_dir))

    expected_names = [
        "research_plan.json",
        "candidates.jsonl",
        "search_log.jsonl",
        "verified_sources.json",
        "claims.json",
        "evidence.jsonl",
        "outline.json",
        "draft.md",
        "citation_audit.json",
        "fact_audit.json",
        "human_style_audit.json",
        "final.docx",
    ]

    for expected_name in expected_names:
        artifact_path = project.artifact_path(expected_name)
        assert artifact_path == project_dir.resolve() / expected_name
        assert artifact_path.parent == project_dir.resolve()

    # Manifest file
    manifest_path = project_dir / PROJECT_MANIFEST_FILENAME
    write_json(manifest_path, project, root=project_dir)
    assert manifest_path.is_file()
    loaded_manifest = read_json(manifest_path)
    assert loaded_manifest["name"] == "canonical_proj"


def test_storage_atomic_write_and_backup_preserved(tmp_path: Path) -> None:
    """Atomic write and backup mechanisms continue functioning safely."""
    target = tmp_path / "important.json"
    data1 = {"v": 1}
    data2 = {"v": 2}

    write_json(target, data1, root=tmp_path)
    assert target.is_file()
    assert read_json(target) == data1

    # Overwrite requires flag or backup
    backup = backup_file(target, root=tmp_path)
    assert backup is not None
    assert backup.is_file()
    assert read_json(backup) == data1

    write_json(target, data2, root=tmp_path, overwrite=True)
    assert read_json(target) == data2
