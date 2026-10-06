"""Human review queue schema and management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from src.schemas.base import BaseRecord

__all__ = ["ReviewItem", "ReviewQueue"]


class ReviewItem(BaseRecord):
    """A case queued for human review."""

    id_prefix: str = Field(default="rev_item", exclude=True, repr=False)
    schema_version: str = "1.1"

    item_type: str  # "claim", "evidence", "source"
    item_id: str
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    reason: str
    recommended_action: str
    status: str = "PENDING"  # "PENDING", "IN_REVIEW", "RESOLVED", "DISMISSED"
    resolution_notes: str | None = None


class ReviewQueue:
    """In-memory queue backed by review_queue.json."""

    def __init__(self, items: list[ReviewItem] | None = None) -> None:
        self._items: list[ReviewItem] = list(items or [])

    @property
    def items(self) -> list[ReviewItem]:
        return list(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def add(self, item: ReviewItem) -> None:
        self._items.append(item)

    def query(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        item_type: str | None = None,
    ) -> list[ReviewItem]:
        result = self._items
        if status is not None:
            result = [i for i in result if i.status == status]
        if severity is not None:
            result = [i for i in result if i.severity == severity]
        if item_type is not None:
            result = [i for i in result if i.item_type == item_type]
        return result

    def has_blocking_items(self, item_id: str) -> bool:
        """Check if item has unresolved CRITICAL review items."""
        return any(
            i.item_id == item_id
            and i.severity == "CRITICAL"
            and i.status not in ("RESOLVED", "DISMISSED")
            for i in self._items
        )

    def to_list(self) -> list[dict[str, Any]]:
        """Serialize all items to a list of dicts."""
        return [item.to_dict() for item in self._items]

    def save(self, path: Path | str, *, root: Path | str) -> None:
        from src.core.storage import write_json

        write_json(
            path,
            [item.to_dict() for item in self._items],
            root=root,
            overwrite=True,
        )

    @classmethod
    def load(cls, path: Path | str) -> "ReviewQueue":
        target = Path(path)
        if not target.is_file():
            return cls()
        from src.core.storage import read_json

        raw = read_json(target)
        if not isinstance(raw, list):
            return cls()
        items = [ReviewItem.from_dict(item) for item in raw]
        return cls(items)

    def summary(self) -> str:
        """Human-readable summary grouped by severity."""
        lines = ["Review Queue Summary", "=" * 40]
        for sev in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            items = self.query(severity=sev, status="PENDING")
            if items:
                lines.append(f"\n{sev} ({len(items)} pending):")
                for item in items:
                    lines.append(f"  - [{item.item_type}] {item.item_id}: {item.reason}")
        return "\n".join(lines)
