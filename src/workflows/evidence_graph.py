"""Evidence graph module: build and summarize claim-evidence-source mapping.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §14–§15 — claim and evidence registry relationships.
  * AGENT_CONSTITUTION.md §6–§10 — evidence integrity and traceability.
  * Requirement 7 — Claim-Evidence-Source Mapping Graph.
"""

from __future__ import annotations

from typing import Any

from src.schemas.claim import Claim
from src.schemas.evidence import (
    SUPPORTING_RELATIONSHIPS,
    Evidence,
    EvidenceRelationship,
    EvidenceType,
)
from src.schemas.source import Source

__all__ = ["build_evidence_graph", "summarize_evidence_graph"]


def build_evidence_graph(
    claims: list[Claim],
    evidence: list[Evidence],
    sources: list[Source],
) -> dict[str, Any]:
    """Build a structured claim -> evidence -> source mapping graph.

    Parameters
    ----------
    claims:
        List of Claim records.
    evidence:
        List of Evidence records.
    sources:
        List of Source records.

    Returns
    -------
    dict[str, Any]
        Structured dictionary containing claims and sources with only JSON-native types.
    """
    source_map: dict[str, Source] = {s.id: s for s in sources}

    claims_dict: dict[str, Any] = {}
    for claim in claims:
        seen_ev_ids: set[str] = set()
        claim_evidence: list[Evidence] = []
        for e in evidence:
            if (
                e.claim_id == claim.id
                or e.id in claim.supporting_evidence
                or e.id in claim.contradicting_evidence
            ):
                if e.id not in seen_ev_ids:
                    seen_ev_ids.add(e.id)
                    claim_evidence.append(e)

        ev_nodes: list[dict[str, Any]] = []
        supporting_count = 0
        contradicting_count = 0

        for e in claim_evidence:
            broken = e.source_id not in source_map
            page = e.location.page if e.location else None
            section = e.location.section if e.location else None

            if e.relationship in SUPPORTING_RELATIONSHIPS:
                supporting_count += 1
            if (
                e.relationship is EvidenceRelationship.CONTRADICTS
                or e.evidence_type is EvidenceType.CONTRADICTORY
            ):
                contradicting_count += 1

            ev_nodes.append(
                {
                    "evidence_id": e.id,
                    "source_id": e.source_id,
                    "evidence_type": str(e.evidence_type),
                    "relationship": str(e.relationship),
                    "strength": str(e.strength),
                    "reading_depth": str(e.reading_depth),
                    "location": {
                        "page": page,
                        "section": section,
                    },
                    "verification_status": "verified" if e.quote_verified else "unverified",
                    "broken_reference": broken,
                }
            )

        claims_dict[claim.id] = {
            "claim_id": claim.id,
            "claim_text": claim.claim_text,
            "status": str(claim.status),
            "evidence": ev_nodes,
            "supporting_count": supporting_count,
            "contradicting_count": contradicting_count,
        }

    sources_dict: dict[str, Any] = {}
    for source in sources:
        sources_dict[source.id] = {
            "source_id": source.id,
            "title": source.title,
            "authors": list(source.authors),
            "year": source.year,
            "doi": source.doi,
            "state": str(source.state),
            "publisher_verified": bool(source.publisher_verified),
            "index_status": dict(source.index_status),
            "retrieval_status": str(source.retrieval_status),
        }

    return {
        "claims": claims_dict,
        "sources": sources_dict,
    }


def summarize_evidence_graph(graph: dict[str, Any]) -> str:
    """Generate a human-readable summary report from an evidence graph.

    Parameters
    ----------
    graph:
        The graph dictionary returned by :func:`build_evidence_graph`.

    Returns
    -------
    str
        Formatted human-readable summary.
    """
    claims = graph.get("claims", {})
    sources = graph.get("sources", {})
    lines: list[str] = ["Evidence Graph Summary", "=" * 40]

    for claim_id, cdata in claims.items():
        claim_text = cdata.get("claim_text", "")
        status = cdata.get("status", "")
        sup_cnt = cdata.get("supporting_count", 0)
        con_cnt = cdata.get("contradicting_count", 0)
        lines.append(f'\nClaim [{claim_id}] ({status}): "{claim_text}"')
        lines.append(f"  Support: {sup_cnt} supporting | {con_cnt} contradicting")

        evidence_items = cdata.get("evidence", [])
        if not evidence_items:
            lines.append("  (no attached evidence)")
            continue

        for ev in evidence_items:
            ev_id = ev.get("evidence_id")
            src_id = ev.get("source_id")
            etype = ev.get("evidence_type")
            rel = ev.get("relationship")
            depth = ev.get("reading_depth")
            vstatus = ev.get("verification_status")
            broken = ev.get("broken_reference")

            src_info = sources.get(src_id)
            if broken or not src_info:
                src_desc = f"{src_id} [BROKEN REFERENCE]"
            else:
                title = src_info.get("title", "")
                year = src_info.get("year")
                year_str = f" ({year})" if year else ""
                src_desc = f'{src_id} "{title}"{year_str}'

            loc = ev.get("location", {})
            loc_parts: list[str] = []
            if loc.get("page") is not None:
                loc_parts.append(f"p. {loc['page']}")
            if loc.get("section"):
                loc_parts.append(f"§{loc['section']}")
            loc_str = f" [{', '.join(loc_parts)}]" if loc_parts else ""

            branch = (
                "Supporting"
                if rel in ("supports", "partially_supports")
                else (
                    "Contradicting"
                    if rel == "contradicts" or etype == "CONTRADICTORY"
                    else "Other"
                )
            )
            lines.append(
                f"  ├─ {branch}: {ev_id} ({etype}, {depth}, {vstatus}){loc_str} → {src_desc}"
            )

    return "\n".join(lines)
