"""Schema foundation: identifiers, timestamps, provenance, and base records.

ARCHITECTURE.md §8 requires every important object to have a stable ID, a
schema, provenance, a status, timestamps, and error information where useful.
This module supplies those building blocks so each concrete schema only has to
declare its own domain fields.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Iterable, Iterator, Self, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_serializer

from src.core.errors import SchemaValidationError

__all__ = [
    "utc_now",
    "new_id",
    "SchemaModel",
    "Provenance",
    "StateTransition",
    "ErrorInfo",
    "BaseRecord",
    "validate_record",
    "dump_jsonl",
    "load_jsonl",
]

_T = TypeVar("_T", bound="SchemaModel")


def utc_now() -> datetime:
    """Timezone-aware current time. All timestamps in the system are UTC."""
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    """Generate a stable, sortable-ish, human-inspectable identifier.

    Format: ``<prefix>_<utc compact timestamp>_<8 hex chars>``, e.g.
    ``src_20260902T211500_1f3c9ab2``. The prefix makes IDs self-describing in
    logs and audit reports; the random suffix avoids collisions.
    """
    cleaned = prefix.strip().lower().replace(" ", "-")
    if not cleaned:
        raise ValueError("ID prefix must not be empty")
    stamp = utc_now().strftime("%Y%m%dT%H%M%S")
    return f"{cleaned}_{stamp}_{uuid.uuid4().hex[:8]}"


class SchemaModel(BaseModel):
    """Base for every contract in the system.

    Unknown fields are rejected so that a renamed or misspelled field fails at
    the boundary instead of silently vanishing.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True, use_enum_values=False)

    def to_dict(self) -> dict[str, Any]:
        """JSON-compatible dictionary (enums become strings, datetimes ISO-8601)."""
        return self.model_dump(mode="json")

    def to_json(self, *, indent: int | None = 2) -> str:
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_dict(cls, data: Any) -> Self:
        """Validate ``data`` into this model, raising :class:`SchemaValidationError`."""
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            raise SchemaValidationError(
                f"{cls.__name__} validation failed",
                errors=exc.errors(include_url=False),
            ) from exc


class Provenance(SchemaModel):
    """Where a piece of data came from.

    Required by SYSTEM_RULES.md §C.24 (record provenance and search history) and
    §H.50 (preserve raw external results when useful for auditability).
    """

    #: Logical origin, e.g. ``"crossref"``, ``"publish_or_perish"``, ``"user"``.
    origin: str
    #: Tool or adapter that produced the record, when applicable.
    tool: str | None = None
    #: Query or request that produced the record.
    query: str | None = None
    retrieved_at: datetime = Field(default_factory=utc_now)
    #: Pointer to the preserved raw payload (path or cache key), not the payload itself.
    raw_reference: str | None = None
    notes: str | None = None

    @field_serializer("retrieved_at")
    def _ser_retrieved_at(self, value: datetime) -> str:
        return value.isoformat()


class StateTransition(SchemaModel):
    """A single audited state change.

    00_MASTER_INSTRUCTION.md §8: "A task state change must be explainable and
    logged." The reason field is therefore mandatory.
    """

    from_state: str | None
    to_state: str
    reason: str
    at: datetime = Field(default_factory=utc_now)
    actor: str | None = None

    @field_serializer("at")
    def _ser_at(self, value: datetime) -> str:
        return value.isoformat()


class ErrorInfo(SchemaModel):
    """Structured error attached to a record instead of a bare log line."""

    code: str
    message: str
    at: datetime = Field(default_factory=utc_now)
    context: dict[str, Any] = Field(default_factory=dict)
    recoverable: bool = True

    @field_serializer("at")
    def _ser_at(self, value: datetime) -> str:
        return value.isoformat()


class BaseRecord(SchemaModel):
    """Persistent record with identity, timestamps, provenance, and history.

    Subclasses set :attr:`id_prefix` so identifiers stay self-describing.
    """

    #: Overridden by subclasses; used by :meth:`make_id`.
    id_prefix: str = Field(default="rec", exclude=True, repr=False)

    id: str = ""
    schema_version: str = "1.0"
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    provenance: Provenance | None = None
    history: list[StateTransition] = Field(default_factory=list)
    errors: list[ErrorInfo] = Field(default_factory=list)

    def model_post_init(self, _context: Any) -> None:
        if not self.id:
            # Assign lazily so callers may supply their own stable ID.
            object.__setattr__(self, "id", new_id(self.id_prefix))

    @field_serializer("created_at", "updated_at")
    def _ser_timestamps(self, value: datetime) -> str:
        return value.isoformat()

    def touch(self) -> None:
        """Mark the record as modified now."""
        self.updated_at = utc_now()

    def record_transition(
        self,
        *,
        from_state: str | None,
        to_state: str,
        reason: str,
        actor: str | None = None,
    ) -> StateTransition:
        """Append an audited transition and refresh ``updated_at``."""
        transition = StateTransition(
            from_state=from_state, to_state=to_state, reason=reason, actor=actor
        )
        self.history.append(transition)
        self.touch()
        return transition

    def record_error(
        self,
        *,
        code: str,
        message: str,
        recoverable: bool = True,
        **context: Any,
    ) -> ErrorInfo:
        """Attach a structured error to this record."""
        error = ErrorInfo(
            code=code, message=message, recoverable=recoverable, context=dict(context)
        )
        self.errors.append(error)
        self.touch()
        return error


def validate_record(model: type[_T], data: Any) -> _T:
    """Functional alias of :meth:`SchemaModel.from_dict` for registries."""
    return model.from_dict(data)


def dump_jsonl(records: Iterable[SchemaModel]) -> str:
    """Serialize records to JSON Lines (the format used by ``*.jsonl`` artifacts)."""
    return "".join(f"{record.model_dump_json()}\n" for record in records)


def load_jsonl(model: type[_T], text: str) -> Iterator[_T]:
    """Parse JSON Lines text into validated records, skipping blank lines."""
    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            yield model.from_dict(__import__("json").loads(stripped))
        except SchemaValidationError as exc:
            raise SchemaValidationError(
                f"{model.__name__} validation failed on JSONL line {line_number}",
                **exc.context,
            ) from exc
        except ValueError as exc:
            raise SchemaValidationError(
                f"Malformed JSON on JSONL line {line_number}", error=str(exc)
            ) from exc
