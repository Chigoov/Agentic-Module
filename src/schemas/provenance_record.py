"""Provenance record schema for claim-evidence-source traceability."""

from __future__ import annotations

from datetime import datetime

from pydantic import field_serializer

from src.schemas.base import SchemaModel
from src.schemas.evidence import EvidenceRelationship, ReadingDepth

__all__ = ["ProvenanceRecord"]


class ProvenanceRecord(SchemaModel):
    """Full traceability record for one piece of evidence.

    Links source, evidence, and claim with retrieval/verification timestamps
    and location info. Fields are None when undetermined — never fabricated.
    """

    source_id: str
    evidence_id: str
    claim_id: str
    reading_depth: ReadingDepth
    page: int | None = None
    section: str | None = None
    retrieved_at: datetime | None = None
    verified_at: datetime | None = None
    verification_method: str | None = None
    evidence_relation: EvidenceRelationship

    @field_serializer("retrieved_at", "verified_at")
    def _ser_timestamps(self, value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None
