"""Machine-readable data contracts.

Every important object carries a stable ID, schema, provenance, status, and
timestamps as required by ARCHITECTURE.md §8. Contracts live here — never
inline inside agents — so that workflow boundaries stay stable across phases.
"""

from __future__ import annotations

from src.schemas import (  # noqa: F401
    citation,
    outline,
    provenance_record,
    review,
    source,
    synthesis,
)
from src.schemas.provenance_record import ProvenanceRecord
from src.schemas.review import ReviewItem, ReviewQueue
from src.schemas.source import AccessMode, RetrievalStatus, RightsStatus, Source, SourceState, SourceType

__all__: list[str] = [
    "citation",
    "outline",
    "provenance_record",
    "review",
    "source",
    "synthesis",
    "AccessMode",
    "ProvenanceRecord",
    "RetrievalStatus",
    "ReviewItem",
    "ReviewQueue",
    "RightsStatus",
    "Source",
    "SourceState",
    "SourceType",
]
