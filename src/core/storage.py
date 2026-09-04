"""Safe filesystem storage primitives.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §3 — filesystem safety; never overwrite important
    files silently.
  * SYSTEM_RULES.md §A.6/§A.7 — preserve existing files, avoid destructive
    operations.

Two guarantees are enforced here so that callers cannot forget them:

1. **Boundary checks.** Every write must target a path inside an explicitly
   allowed root. Attempts to escape raise :class:`PathSafetyError`.
2. **Atomic writes.** Content is written to a temporary file in the same
   directory and then replaced into place, so an interrupted run cannot leave a
   half-written artifact behind.

Overwriting an existing file always requires ``overwrite=True``.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from src.core.errors import PathSafetyError
from src.schemas.base import SchemaModel

__all__ = [
    "ensure_within",
    "atomic_write_text",
    "write_json",
    "read_json",
    "append_jsonl",
    "read_jsonl",
    "backup_file",
]


def ensure_within(path: str | os.PathLike[str], root: str | os.PathLike[str]) -> Path:
    """Resolve ``path`` and confirm it lies inside ``root``.

    Returns
    -------
    Path
        The resolved absolute path.

    Raises
    ------
    PathSafetyError
        When the resolved path escapes ``root``.
    """
    resolved_root = Path(root).resolve()
    # ``strict=False`` so not-yet-created files can still be validated.
    resolved_path = Path(path).resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise PathSafetyError(
            "Refusing to operate on a path outside its permitted root",
            path=str(resolved_path),
            root=str(resolved_root),
        ) from exc
    return resolved_path


def atomic_write_text(
    path: str | os.PathLike[str],
    content: str,
    *,
    root: str | os.PathLike[str],
    overwrite: bool = False,
    encoding: str = "utf-8",
) -> Path:
    """Atomically write ``content`` to ``path`` inside ``root``.

    Raises
    ------
    PathSafetyError
        When the target escapes ``root``, or when it exists and ``overwrite``
        is ``False``.
    """
    target = ensure_within(path, root)
    if target.exists() and not overwrite:
        raise PathSafetyError(
            "File already exists; pass overwrite=True to replace it",
            path=str(target),
        )
    target.parent.mkdir(parents=True, exist_ok=True)

    # Write to a sibling temp file, then atomically replace.
    handle, temp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.name}.", suffix=".tmp"
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(handle, "w", encoding=encoding, newline="\n") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, target)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return target


def write_json(
    path: str | os.PathLike[str],
    payload: Any,
    *,
    root: str | os.PathLike[str],
    overwrite: bool = False,
    indent: int = 2,
) -> Path:
    """Serialize ``payload`` to JSON and write it atomically.

    Pydantic models are dumped in JSON mode so enums and datetimes serialize
    predictably.
    """
    if isinstance(payload, SchemaModel):
        data: Any = payload.to_dict()
    else:
        data = payload
    text = json.dumps(data, ensure_ascii=False, indent=indent, default=str) + "\n"
    return atomic_write_text(path, text, root=root, overwrite=overwrite)


def read_json(path: str | os.PathLike[str]) -> Any:
    """Read and parse a JSON file."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def append_jsonl(
    path: str | os.PathLike[str],
    records: Iterable[SchemaModel | dict[str, Any]],
    *,
    root: str | os.PathLike[str],
) -> int:
    """Append records to a JSON Lines artifact, creating it when absent.

    Append-only artifacts (``candidates.jsonl``, ``search_log.jsonl``,
    ``evidence.jsonl``) are how the system keeps an auditable trail, so this
    never rewrites existing lines.

    Returns
    -------
    int
        Number of records appended.
    """
    target = ensure_within(path, root)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for record in records:
        if isinstance(record, SchemaModel):
            lines.append(record.model_dump_json())
        else:
            lines.append(json.dumps(record, ensure_ascii=False, default=str))
    if not lines:
        return 0
    with target.open("a", encoding="utf-8", newline="\n") as stream:
        for line in lines:
            stream.write(line + "\n")
    return len(lines)


def read_jsonl(path: str | os.PathLike[str]) -> list[dict[str, Any]]:
    """Read a JSON Lines file into a list of dictionaries, skipping blanks."""
    source = Path(path)
    if not source.is_file():
        return []
    parsed: list[dict[str, Any]] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            parsed.append(json.loads(stripped))
    return parsed


def backup_file(path: str | os.PathLike[str], *, root: str | os.PathLike[str]) -> Path | None:
    """Copy an existing file next to itself with a UTC timestamp suffix.

    Used before any operation that would otherwise overwrite user-visible work
    (00_MASTER_INSTRUCTION.md §3.5). Returns ``None`` when there is nothing to
    back up.
    """
    source = ensure_within(path, root)
    if not source.is_file():
        return None
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = source.with_name(f"{source.name}.{stamp}.bak")
    destination.write_bytes(source.read_bytes())
    return destination
