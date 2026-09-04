"""Tests for storage layer boundary checks and atomic writes."""

from pathlib import Path

import pytest

from src.core.errors import PathSafetyError
from src.core.storage import (
    append_jsonl,
    atomic_write_text,
    backup_file,
    ensure_within,
    read_json,
    read_jsonl,
    write_json,
)
from src.schemas.base import BaseRecord


def test_ensure_within_accepts_valid_path(temp_workspace: Path) -> None:
    """ensure_within() returns the resolved path when it's inside root."""
    target = temp_workspace / "subdir" / "file.txt"
    result = ensure_within(target, root=temp_workspace)
    assert result == target.resolve()


def test_ensure_within_rejects_escape(temp_workspace: Path) -> None:
    """ensure_within() raises when path escapes root."""
    with pytest.raises(PathSafetyError, match="outside its permitted root"):
        ensure_within("../../etc/passwd", root=temp_workspace)


def test_atomic_write_text_creates_file(temp_workspace: Path) -> None:
    """atomic_write_text() creates a file with the given content."""
    target = temp_workspace / "test.txt"
    written = atomic_write_text(target, "hello\n", root=temp_workspace)
    assert written == target
    assert target.read_text(encoding="utf-8") == "hello\n"


def test_atomic_write_text_refuses_overwrite_without_flag(temp_workspace: Path) -> None:
    """atomic_write_text() raises when file exists and overwrite=False."""
    target = temp_workspace / "existing.txt"
    target.write_text("original", encoding="utf-8")
    with pytest.raises(PathSafetyError, match="already exists"):
        atomic_write_text(target, "new", root=temp_workspace)


def test_atomic_write_text_overwrites_with_flag(temp_workspace: Path) -> None:
    """atomic_write_text() replaces existing file when overwrite=True."""
    target = temp_workspace / "existing.txt"
    target.write_text("original", encoding="utf-8")
    atomic_write_text(target, "replaced", root=temp_workspace, overwrite=True)
    assert target.read_text(encoding="utf-8") == "replaced"


def test_write_json_serializes_dict(temp_workspace: Path) -> None:
    """write_json() serializes a dict to JSON."""
    target = temp_workspace / "data.json"
    payload = {"key": "value", "count": 42}
    write_json(target, payload, root=temp_workspace)
    assert target.is_file()
    loaded = read_json(target)
    assert loaded == payload


def test_write_json_serializes_pydantic_model(temp_workspace: Path) -> None:
    """write_json() serializes a Pydantic model via to_dict()."""
    target = temp_workspace / "record.json"
    record = BaseRecord()
    write_json(target, record, root=temp_workspace)
    loaded = read_json(target)
    assert loaded["id"] == record.id


def test_append_jsonl_creates_new_file(temp_workspace: Path) -> None:
    """append_jsonl() creates a new file with the given records."""
    target = temp_workspace / "log.jsonl"
    records = [{"event": "A"}, {"event": "B"}]
    count = append_jsonl(target, records, root=temp_workspace)
    assert count == 2
    assert target.is_file()


def test_append_jsonl_appends_to_existing(temp_workspace: Path) -> None:
    """append_jsonl() adds records without rewriting existing lines."""
    target = temp_workspace / "log.jsonl"
    append_jsonl(target, [{"event": "A"}], root=temp_workspace)
    append_jsonl(target, [{"event": "B"}], root=temp_workspace)
    loaded = read_jsonl(target)
    assert len(loaded) == 2
    assert loaded[0]["event"] == "A"
    assert loaded[1]["event"] == "B"


def test_read_jsonl_returns_empty_when_missing(temp_workspace: Path) -> None:
    """read_jsonl() returns an empty list when the file doesn't exist."""
    target = temp_workspace / "missing.jsonl"
    loaded = read_jsonl(target)
    assert loaded == []


def test_backup_file_copies_with_timestamp(temp_workspace: Path) -> None:
    """backup_file() creates a timestamped .bak copy."""
    original = temp_workspace / "important.txt"
    original.write_text("data", encoding="utf-8")
    backup = backup_file(original, root=temp_workspace)
    assert backup is not None
    assert backup.suffix == ".bak"
    assert backup.read_text(encoding="utf-8") == "data"
    # Original is unchanged
    assert original.read_text(encoding="utf-8") == "data"


def test_backup_file_returns_none_when_missing(temp_workspace: Path) -> None:
    """backup_file() returns None when there is nothing to back up."""
    nonexistent = temp_workspace / "missing.txt"
    result = backup_file(nonexistent, root=temp_workspace)
    assert result is None
