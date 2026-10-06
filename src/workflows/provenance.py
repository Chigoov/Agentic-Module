"""Provenance chain construction workflow.

Specification anchors:
  * AGENT_CONSTITUTION.md §6–§10 — full traceability of evidence to source.
  * Requirement 9 — Research Provenance Record.
"""

from __future__ import annotations

from datetime import datetime

from src.schemas.claim import Claim
from src.schemas.evidence import Evidence
from src.schemas.provenance_record import ProvenanceRecord
from src.schemas.source import Source, is_verified

__all__ = ["build_provenance_chain"]


def build_provenance_chain(
    claim: Claim,
    evidence: list[Evidence],
    sources: list[Source],
) -> list[ProvenanceRecord]:
    """Build a complete traceability chain linking claim, evidence, and sources.

    Parameters
    ----------
    claim:
        The Claim to trace.
    evidence:
        Evidence records associated with the claim.
    sources:
        Source records referenced by the evidence.

    Returns
    -------
    list[ProvenanceRecord]
        List of provenance records, one per associated evidence. Undetermined
        fields are set to None without fabricating values.
    """
    source_map: dict[str, Source] = {s.id: s for s in sources}

    relevant_evidence = [
        e
        for e in evidence
        if (
            e.claim_id == claim.id
            or e.id in claim.supporting_evidence
            or e.id in claim.contradicting_evidence
        )
    ]
    # Fallback if caller passed pre-associated evidence where claim_id is not set
    if not relevant_evidence and evidence and all(not e.claim_id for e in evidence):
        relevant_evidence = list(evidence)

    records: list[ProvenanceRecord] = []
    for e in relevant_evidence:
        source = source_map.get(e.source_id)

        retrieved_at: datetime | None = None
        verification_method: str | None = None
        verified_at: datetime | None = None

        if source is not None:
            if source.provenance is not None:
                retrieved_at = source.provenance.retrieved_at
                verification_method = source.provenance.tool or source.provenance.origin

            for transition in source.history:
                if transition.to_state and is_verified(transition.to_state):
                    verified_at = transition.at
                    break

        page = e.location.page if e.location else None
        section = e.location.section if e.location else None

        records.append(
            ProvenanceRecord(
                source_id=e.source_id,
                evidence_id=e.id,
                claim_id=claim.id,
                reading_depth=e.reading_depth,
                page=page,
                section=section,
                retrieved_at=retrieved_at,
                verified_at=verified_at,
                verification_method=verification_method,
                evidence_relation=e.relationship,
            )
        )

    return records
