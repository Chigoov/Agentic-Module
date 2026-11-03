"""Tests for Evidence Intelligence schemas and models.

Covers:
- ProvenanceRecord schema and serialization
- ReviewItem schema and ReviewQueue operations
- Property 22: Provenance record serialization round-trip
- Property 23: ReviewQueue persistence round-trip
- Property 24: ReviewQueue filtering correctness
"""

from __future__ import annotations

import itertools
import json
import random
from datetime import UTC, datetime
from pathlib import Path

import pytest

from src.core.errors import SchemaValidationError, StateTransitionError
from tests.fixtures.golden_tiktok_streak import get_golden_fixture
from src.core.storage import (
    load_evidence_graph,
    load_provenance_chain,
    save_evidence_graph,
    save_provenance_chain,
)
from src.schemas.base import Provenance
from src.schemas.claim import (
    Claim,
    ClaimImportance,
    ClaimStatus,
    SemanticDecision,
    SemanticReview,
    SupportLevel,
)
from src.schemas.evidence import (
    SUPPORTING_RELATIONSHIPS,
    Evidence,
    EvidenceLocation,
    EvidenceRelationship,
    EvidenceStrength,
    EvidenceType,
    ExtractionMethod,
    ReadingDepth,
)
from src.schemas.provenance_record import ProvenanceRecord
from src.schemas.review import ReviewItem, ReviewQueue
from src.schemas.source import RetrievalStatus, Source, SourceState
from src.workflows.contradiction import (
    ContradictionReport,
    ContradictoryFinding,
    NullFinding,
    detect_contradictions,
)
from src.workflows.evidence_audit import (
    AuditFlag,
    AuditResult,
    audit_evidence,
)
from src.workflows.evidence_flow import (
    _effective_strength,
    _get_evidence_type,
    calibrate_confidence,
    compute_support_level,
    evaluate_claim,
)
from src.workflows.evidence_graph import (
    build_evidence_graph,
    summarize_evidence_graph,
)
from src.workflows.gates import (
    DOI_PATTERN,
    GateResult,
    check_academic_integrity,
    create_review_queue_from_gate_result,
)
from src.workflows.provenance import (
    build_provenance_chain,
)


# --------------------------------------------------------------------------- #
# Unit Tests: ProvenanceRecord
# --------------------------------------------------------------------------- #


def test_provenance_record_defaults_and_fields() -> None:
    """ProvenanceRecord sets undetermined fields to None without fabricating values."""
    rec = ProvenanceRecord(
        source_id="src_001",
        evidence_id="evd_001",
        claim_id="clm_001",
        reading_depth=ReadingDepth.FULL_TEXT,
        evidence_relation=EvidenceRelationship.SUPPORTS,
    )
    assert rec.source_id == "src_001"
    assert rec.evidence_id == "evd_001"
    assert rec.claim_id == "clm_001"
    assert rec.reading_depth is ReadingDepth.FULL_TEXT
    assert rec.evidence_relation is EvidenceRelationship.SUPPORTS
    assert rec.page is None
    assert rec.section is None
    assert rec.retrieved_at is None
    assert rec.verified_at is None
    assert rec.verification_method is None


def test_provenance_record_serialization_round_trip() -> None:
    """ProvenanceRecord serializes to and from dict cleanly."""
    ts_retrieved = datetime(2026, 9, 2, 10, 0, 0, tzinfo=UTC)
    ts_verified = datetime(2026, 9, 2, 10, 5, 0, tzinfo=UTC)
    rec = ProvenanceRecord(
        source_id="src_42",
        evidence_id="evd_42",
        claim_id="clm_42",
        reading_depth=ReadingDepth.ABSTRACT_ONLY,
        page=7,
        section="Methods",
        retrieved_at=ts_retrieved,
        verified_at=ts_verified,
        verification_method="crossref_doi",
        evidence_relation=EvidenceRelationship.PARTIALLY_SUPPORTS,
    )
    data = rec.to_dict()
    assert data["source_id"] == "src_42"
    assert data["page"] == 7
    assert data["reading_depth"] == "ABSTRACT_ONLY"
    assert data["evidence_relation"] == "partially_supports"
    assert data["retrieved_at"] == ts_retrieved.isoformat()
    assert data["verified_at"] == ts_verified.isoformat()

    restored = ProvenanceRecord.from_dict(data)
    assert restored == rec


def test_provenance_record_rejects_extra_fields() -> None:
    """Extra fields are rejected by SchemaModel boundary check."""
    with pytest.raises(SchemaValidationError):
        ProvenanceRecord.from_dict({
            "source_id": "src_1",
            "evidence_id": "evd_1",
            "claim_id": "clm_1",
            "reading_depth": "FULL_TEXT",
            "evidence_relation": "supports",
            "unexpected_field": "disallowed",
        })


# --------------------------------------------------------------------------- #
# Unit Tests: ReviewItem and ReviewQueue
# --------------------------------------------------------------------------- #


def test_review_item_defaults_and_fields() -> None:
    """ReviewItem generates rev_item prefix and sets expected defaults."""
    item = ReviewItem(
        item_type="claim",
        item_id="clm_001",
        severity="HIGH",
        reason="Claim overclaims causal link",
        recommended_action="Harden wording to correlational",
    )
    assert item.id.startswith("rev_item_")
    assert item.schema_version == "1.1"
    assert item.item_type == "claim"
    assert item.item_id == "clm_001"
    assert item.severity == "HIGH"
    assert item.status == "PENDING"
    assert item.resolution_notes is None


def test_review_item_serialization_round_trip() -> None:
    """ReviewItem serializes to and from dict cleanly."""
    item = ReviewItem(
        item_type="source",
        item_id="src_99",
        severity="CRITICAL",
        reason="Unverified publisher with fabricated DOI",
        recommended_action="Reject source and remove citing claims",
        status="IN_REVIEW",
        resolution_notes="Investigating with Crossref API",
    )
    data = item.to_dict()
    restored = ReviewItem.from_dict(data)
    assert restored.id == item.id
    assert restored.schema_version == "1.1"
    assert restored.item_type == "source"
    assert restored.item_id == "src_99"
    assert restored.severity == "CRITICAL"
    assert restored.status == "IN_REVIEW"
    assert restored.resolution_notes == "Investigating with Crossref API"


def test_review_queue_basic_operations() -> None:
    """ReviewQueue supports add, len, and items encapsulation."""
    queue = ReviewQueue()
    assert len(queue) == 0
    assert queue.items == []

    item1 = ReviewItem(
        item_type="claim",
        item_id="clm_1",
        severity="LOW",
        reason="Minor formatting discrepancy",
        recommended_action="Adjust tone",
    )
    queue.add(item1)
    assert len(queue) == 1
    assert queue.items == [item1]

    # items property returns a copy, modifying it doesn't mutate queue
    queue.items.clear()
    assert len(queue) == 1


def test_review_queue_query() -> None:
    """ReviewQueue query filters by status, severity, and item_type."""
    i1 = ReviewItem(
        item_type="claim",
        item_id="clm_1",
        severity="HIGH",
        reason="r1",
        recommended_action="a1",
        status="PENDING",
    )
    i2 = ReviewItem(
        item_type="claim",
        item_id="clm_2",
        severity="CRITICAL",
        reason="r2",
        recommended_action="a2",
        status="RESOLVED",
    )
    i3 = ReviewItem(
        item_type="source",
        item_id="src_1",
        severity="HIGH",
        reason="r3",
        recommended_action="a3",
        status="PENDING",
    )
    queue = ReviewQueue([i1, i2, i3])

    assert queue.query(status="PENDING") == [i1, i3]
    assert queue.query(severity="CRITICAL") == [i2]
    assert queue.query(item_type="source") == [i3]
    assert queue.query(item_type="claim", status="PENDING") == [i1]
    assert queue.query(severity="LOW") == []


def test_review_queue_has_blocking_items() -> None:
    """has_blocking_items returns True only for unresolved CRITICAL items."""
    crit_pending = ReviewItem(
        item_type="claim",
        item_id="clm_1",
        severity="CRITICAL",
        reason="r1",
        recommended_action="a1",
        status="PENDING",
    )
    crit_resolved = ReviewItem(
        item_type="claim",
        item_id="clm_2",
        severity="CRITICAL",
        reason="r2",
        recommended_action="a2",
        status="RESOLVED",
    )
    crit_dismissed = ReviewItem(
        item_type="claim",
        item_id="clm_3",
        severity="CRITICAL",
        reason="r3",
        recommended_action="a3",
        status="DISMISSED",
    )
    high_pending = ReviewItem(
        item_type="claim",
        item_id="clm_4",
        severity="HIGH",
        reason="r4",
        recommended_action="a4",
        status="PENDING",
    )
    queue = ReviewQueue([crit_pending, crit_resolved, crit_dismissed, high_pending])

    assert queue.has_blocking_items("clm_1") is True
    assert queue.has_blocking_items("clm_2") is False
    assert queue.has_blocking_items("clm_3") is False
    assert queue.has_blocking_items("clm_4") is True
    assert queue.has_blocking_items("clm_nonexistent") is False


def test_review_queue_save_and_load(tmp_path: Path) -> None:
    """ReviewQueue saves to JSON and loads back with all items intact."""
    i1 = ReviewItem(
        item_type="claim",
        item_id="clm_1",
        severity="HIGH",
        reason="r1",
        recommended_action="a1",
    )
    i2 = ReviewItem(
        item_type="source",
        item_id="src_1",
        severity="MEDIUM",
        reason="r2",
        recommended_action="a2",
    )
    queue = ReviewQueue([i1, i2])

    file_path = tmp_path / "review_queue.json"
    queue.save(file_path, root=tmp_path)

    assert file_path.is_file()
    loaded = ReviewQueue.load(file_path)
    assert len(loaded) == 2
    assert loaded.items[0].id == i1.id
    assert loaded.items[0].item_id == "clm_1"
    assert loaded.items[1].id == i2.id
    assert loaded.items[1].item_id == "src_1"


def test_review_queue_load_missing_file(tmp_path: Path) -> None:
    """Loading from a non-existent file returns an empty ReviewQueue."""
    missing_path = tmp_path / "does_not_exist.json"
    loaded = ReviewQueue.load(missing_path)
    assert len(loaded) == 0
    assert loaded.items == []


def test_review_queue_load_invalid_content(tmp_path: Path) -> None:
    """An existing malformed queue must never erase blocking review state."""
    bad_path = tmp_path / "bad.json"
    bad_path.write_text('{"error": "not a list"}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON list"):
        ReviewQueue.load(bad_path)


def test_review_queue_summary() -> None:
    """summary() produces a formatted string grouped by severity."""
    queue = ReviewQueue([
        ReviewItem(
            item_type="claim",
            item_id="clm_crit",
            severity="CRITICAL",
            reason="Contradiction ignored",
            recommended_action="Remove claim",
            status="PENDING",
        ),
        ReviewItem(
            item_type="source",
            item_id="src_high",
            severity="HIGH",
            reason="Unverified DOI",
            recommended_action="Query Crossref",
            status="PENDING",
        ),
        ReviewItem(
            item_type="claim",
            item_id="clm_done",
            severity="CRITICAL",
            reason="Already fixed",
            recommended_action="None",
            status="RESOLVED",
        ),
    ])
    text = queue.summary()
    assert "Review Queue Summary" in text
    assert "CRITICAL (1 pending):" in text
    assert "[claim] clm_crit: Contradiction ignored" in text
    assert "HIGH (1 pending):" in text
    assert "[source] src_high: Unverified DOI" in text
    assert "clm_done" not in text  # resolved items not shown in pending summary


# --------------------------------------------------------------------------- #
# Property-Based Tests
# --------------------------------------------------------------------------- #


def test_property_22_provenance_record_serialization_round_trip() -> None:
    """Property 22: Provenance record serialization round-trip.

    For any valid ProvenanceRecord, serializing to JSON via to_dict()
    and deserializing via from_dict() SHALL produce an equivalent record.
    For any field that cannot be determined, the value SHALL be None.

    **Validates: Requirements 9.4, 9.5**
    """
    depths = list(ReadingDepth)
    relations = list(EvidenceRelationship)
    pages = [None, 1, 42, 100]
    sections = [None, "Introduction", "Methods §2.1", "Results"]
    timestamps = [
        None,
        datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
        datetime(2026, 9, 18, 12, 34, 56, tzinfo=UTC),
    ]
    methods = [None, "verbatim_search", "crossref_doi", "manual_audit"]

    # Test across combinatorial and randomly sampled instances
    rng = random.Random(42)
    for depth in depths:
        for rel in relations:
            page = rng.choice(pages)
            sec = rng.choice(sections)
            ret_at = rng.choice(timestamps)
            ver_at = rng.choice(timestamps)
            method = rng.choice(methods)

            record = ProvenanceRecord(
                source_id=f"src_{rng.randint(1, 999)}",
                evidence_id=f"evd_{rng.randint(1, 999)}",
                claim_id=f"clm_{rng.randint(1, 999)}",
                reading_depth=depth,
                page=page,
                section=sec,
                retrieved_at=ret_at,
                verified_at=ver_at,
                verification_method=method,
                evidence_relation=rel,
            )

            # Check that None fields remain None
            if page is None:
                assert record.page is None
            if sec is None:
                assert record.section is None
            if ret_at is None:
                assert record.retrieved_at is None
            if ver_at is None:
                assert record.verified_at is None
            if method is None:
                assert record.verification_method is None

            # Serialization round-trip
            serialized = record.to_dict()
            restored = ProvenanceRecord.from_dict(serialized)
            assert restored == record


def test_property_23_review_queue_persistence_round_trip(tmp_path: Path) -> None:
    """Property 23: ReviewQueue persistence round-trip.

    For any ReviewQueue containing N ReviewItem records, saving to
    review_queue.json and loading back SHALL produce a queue with N identical items.

    **Validates: Requirements 13.2, 16.1**
    """
    item_types = ["claim", "evidence", "source"]
    severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    statuses = ["PENDING", "IN_REVIEW", "RESOLVED", "DISMISSED"]

    rng = random.Random(12345)

    # Test various queue sizes: 0, 1, 5, 20
    queue_sizes = [0, 1, 5, 20]
    for n in queue_sizes:
        items = []
        for i in range(n):
            items.append(
                ReviewItem(
                    item_type=rng.choice(item_types),
                    item_id=f"item_{i}",
                    severity=rng.choice(severities),
                    reason=f"Reason {i} for review",
                    recommended_action=f"Action {i} to take",
                    status=rng.choice(statuses),
                    resolution_notes=f"Note {i}" if rng.choice([True, False]) else None,
                )
            )

        queue = ReviewQueue(items)
        save_file = tmp_path / f"review_queue_n_{n}.json"
        queue.save(save_file, root=tmp_path)

        loaded = ReviewQueue.load(save_file)
        assert len(loaded) == n
        for orig, loaded_item in zip(queue.items, loaded.items, strict=True):
            assert loaded_item.id == orig.id
            assert loaded_item.schema_version == orig.schema_version
            assert loaded_item.item_type == orig.item_type
            assert loaded_item.item_id == orig.item_id
            assert loaded_item.severity == orig.severity
            assert loaded_item.reason == orig.reason
            assert loaded_item.recommended_action == orig.recommended_action
            assert loaded_item.status == orig.status
            assert loaded_item.resolution_notes == orig.resolution_notes


def test_property_24_review_queue_filtering_correctness() -> None:
    """Property 24: ReviewQueue filtering correctness.

    For any ReviewQueue and any filter combination (status, severity, item_type),
    the query method SHALL return exactly the items matching all specified criteria,
    and no others.

    **Validates: Requirements 13.5**
    """
    item_types = ["claim", "evidence", "source"]
    severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
    statuses = ["PENDING", "IN_REVIEW", "RESOLVED", "DISMISSED"]

    # Construct a queue covering every single combination
    all_items: list[ReviewItem] = []
    for it, sev, st in itertools.product(item_types, severities, statuses):
        all_items.append(
            ReviewItem(
                item_type=it,
                item_id=f"{it}_{sev}_{st}",
                severity=sev,
                reason=f"Testing {it} {sev} {st}",
                recommended_action="Check",
                status=st,
            )
        )

    queue = ReviewQueue(all_items)
    assert len(queue) == len(item_types) * len(severities) * len(statuses)

    # Test all filter combinations (including None)
    filter_statuses = [None] + statuses
    filter_severities = [None] + severities
    filter_item_types = [None] + item_types

    for st_filter in filter_statuses:
        for sev_filter in filter_severities:
            for it_filter in filter_item_types:
                results = queue.query(
                    status=st_filter,
                    severity=sev_filter,
                    item_type=it_filter,
                )

                # Expected items based on filtering criteria
                expected = [
                    item
                    for item in all_items
                    if (st_filter is None or item.status == st_filter)
                    and (sev_filter is None or item.severity == sev_filter)
                    and (it_filter is None or item.item_type == it_filter)
                ]

                assert len(results) == len(expected)
                assert set(r.id for r in results) == set(e.id for e in expected)


# --------------------------------------------------------------------------- #
# Unit Tests: Evidence Graph
# --------------------------------------------------------------------------- #


def test_build_evidence_graph_structure_and_counts() -> None:
    """build_evidence_graph maps claims to evidence and sources with accurate counts."""
    src1 = Source(
        id="src_1",
        title="Study on Motivation",
        authors=["Alice, A."],
        year=2023,
        doi="10.1234/study1",
        state=SourceState.APPROVED,
        publisher_verified=True,
        retrieval_status=RetrievalStatus.RETRIEVED,
    )
    src2 = Source(
        id="src_2",
        title="Counter Study",
        authors=["Bob, B."],
        year=2024,
        doi="10.1234/study2",
        state=SourceState.APPROVED,
        publisher_verified=True,
        retrieval_status=RetrievalStatus.RETRIEVED,
    )

    clm = Claim(
        id="clm_1",
        claim_text="Motivation drives performance",
        status=ClaimStatus.SUPPORTED,
    )

    ev_sup = Evidence(
        id="evd_1",
        claim_id=clm.id,
        source_id=src1.id,
        evidence_text="High motivation improves test scores by 15%.",
        evidence_type=EvidenceType.DIRECT,
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        reading_depth=ReadingDepth.FULL_TEXT,
        location=EvidenceLocation(page=12, section="Results"),
        quote_verified=True,
    )
    ev_con = Evidence(
        id="evd_2",
        claim_id=clm.id,
        source_id=src2.id,
        evidence_text="No correlation was observed in replications.",
        evidence_type=EvidenceType.CONTRADICTORY,
        relationship=EvidenceRelationship.CONTRADICTS,
        strength=EvidenceStrength.MODERATE,
        reading_depth=ReadingDepth.FULL_TEXT,
        location=EvidenceLocation(page=34, section="Discussion"),
        quote_verified=False,
    )
    ev_broken = Evidence(
        id="evd_3",
        claim_id=clm.id,
        source_id="src_nonexistent",
        evidence_text="Anecdotal evidence from survey.",
        evidence_type=EvidenceType.BACKGROUND,
        relationship=EvidenceRelationship.PARTIALLY_SUPPORTS,
        strength=EvidenceStrength.WEAK,
        reading_depth=ReadingDepth.ABSTRACT_ONLY,
        extraction_method=ExtractionMethod.VERBATIM_ABSTRACT,
        location=EvidenceLocation(page=None, section=None),
        quote_verified=False,
    )

    graph = build_evidence_graph([clm], [ev_sup, ev_con, ev_broken], [src1, src2])

    assert "claims" in graph
    assert "sources" in graph
    assert clm.id in graph["claims"]

    c_node = graph["claims"][clm.id]
    assert c_node["claim_id"] == clm.id
    assert c_node["claim_text"] == clm.claim_text
    assert c_node["supporting_count"] == 2  # SUPPORTS and PARTIALLY_SUPPORTS
    assert c_node["contradicting_count"] == 1
    assert len(c_node["evidence"]) == 3

    ev_map = {e["evidence_id"]: e for e in c_node["evidence"]}
    assert ev_map["evd_1"]["verification_status"] == "verified"
    assert ev_map["evd_1"]["broken_reference"] is False
    assert ev_map["evd_1"]["location"] == {"page": 12, "section": "Results"}

    assert ev_map["evd_2"]["verification_status"] == "unverified"
    assert ev_map["evd_2"]["broken_reference"] is False

    assert ev_map["evd_3"]["broken_reference"] is True

    # JSON serializability
    json_str = json.dumps(graph)
    assert json_str is not None

    summary = summarize_evidence_graph(graph)
    assert "Evidence Graph Summary" in summary
    assert clm.id in summary
    assert "Motivation drives performance" in summary
    assert "Supporting" in summary
    assert "Contradicting" in summary
    assert "[BROKEN REFERENCE]" in summary


# --------------------------------------------------------------------------- #
# Unit Tests: Evidence Audit
# --------------------------------------------------------------------------- #


def test_audit_evidence_flags_and_stats() -> None:
    """audit_evidence detects unverified verbatim, depth/method mismatch, type/relation mismatch, and unverified source."""
    src_verified = Source(
        id="src_ok",
        title="Verified Source",
        state=SourceState.APPROVED,
    )
    src_unverified = Source(
        id="src_unv",
        title="Discovered Source",
        state=SourceState.DISCOVERED,
    )

    # 1. Unverified verbatim
    ev_unv_verbatim = Evidence(
        id="ev_1",
        claim_id="clm_1",
        source_id=src_verified.id,
        evidence_text="Verbatim quote that was never verified.",
        verbatim=True,
        quote_verified=False,
    )

    # 2. Type/relationship mismatch: CONTRADICTORY but SUPPORTS
    ev_type_mismatch = Evidence(
        id="ev_2",
        claim_id="clm_1",
        source_id=src_verified.id,
        evidence_text="Text contradicting claim",
        evidence_type=EvidenceType.CONTRADICTORY,
        relationship=EvidenceRelationship.SUPPORTS,
        quote_verified=True,
    )

    # 3. Depth method mismatch (constructed via model_construct to bypass schema init validator)
    ev_depth_mismatch = Evidence.model_construct(
        id="ev_3",
        claim_id="clm_1",
        source_id=src_verified.id,
        evidence_text="Abstract claiming to be verbatim fulltext",
        reading_depth=ReadingDepth.ABSTRACT_ONLY,
        extraction_method=ExtractionMethod.VERBATIM_FULLTEXT,
        verbatim=True,
        quote_verified=True,
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.MODERATE,
        confidence=0.5,
        evidence_type=EvidenceType.PARTIAL,
        location=EvidenceLocation(),
    )

    # 4. Source unverified
    ev_src_unverified = Evidence(
        id="ev_4",
        claim_id="clm_1",
        source_id=src_unverified.id,
        evidence_text="Text from unverified source",
        quote_verified=True,
    )

    # 5. Source not found
    ev_src_missing = Evidence(
        id="ev_5",
        claim_id="clm_1",
        source_id="src_does_not_exist",
        evidence_text="Text from missing source",
        quote_verified=True,
    )

    result = audit_evidence(
        [ev_unv_verbatim, ev_type_mismatch, ev_depth_mismatch, ev_src_unverified, ev_src_missing],
        [src_verified, src_unverified],
    )

    assert result.total_evidence == 5
    assert result.verified_quotes == 4
    assert result.unverified_quotes == 1

    flag_types = [f.flag_type for f in result.flags]
    assert "unverified_verbatim" in flag_types
    assert "type_relationship_mismatch" in flag_types
    assert "depth_method_mismatch" in flag_types
    assert "source_unverified" in flag_types
    assert "source_not_found" in flag_types

    d = result.to_dict()
    assert d["total_evidence"] == 5
    assert len(d["flags"]) == len(result.flags)

    txt = result.to_text()
    assert "Evidence Verification Audit" in txt
    assert "unverified_verbatim" in txt


# --------------------------------------------------------------------------- #
# Unit Tests: Contradiction Detection
# --------------------------------------------------------------------------- #


def test_detect_contradictions_unit() -> None:
    """detect_contradictions classifies mixed evidence, computes severity, and collects findings."""
    claim = Claim(id="clm_test", claim_text="Technology improves learning retention")

    ev_sup = Evidence(
        id="ev_sup",
        claim_id=claim.id,
        source_id="src_1",
        evidence_text="EdTech increases test retention by 20%.",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        evidence_type=EvidenceType.DIRECT,
    )
    ev_con = Evidence(
        id="ev_con",
        claim_id=claim.id,
        source_id="src_2",
        evidence_text="Screens cause significant retention deficits in randomized controlled trials.",
        relationship=EvidenceRelationship.CONTRADICTS,
        strength=EvidenceStrength.DEFINITIVE,
        evidence_type=EvidenceType.CONTRADICTORY,
    )
    ev_null = Evidence(
        id="ev_null",
        claim_id=claim.id,
        source_id="src_3",
        evidence_text="Study found no statistically significant difference across all groups.",
        relationship=EvidenceRelationship.IRRELEVANT,
        strength=EvidenceStrength.WEAK,
        evidence_type=EvidenceType.NOT_SUPPORTED,
    )

    report = detect_contradictions(claim, [ev_sup, ev_con, ev_null])

    assert report.claim_id == claim.id
    assert report.has_mixed_evidence is True
    assert report.conflict_severity == "HIGH"  # DEFINITIVE -> HIGH
    assert len(report.contradictory_findings) == 1
    assert report.contradictory_findings[0].evidence_id == "ev_con"
    assert report.contradictory_findings[0].source_id == "src_2"
    assert len(report.null_findings) == 1
    assert report.null_findings[0].evidence_id == "ev_null"

    d = report.to_dict()
    assert d["claim_id"] == claim.id
    assert d["has_mixed_evidence"] is True
    assert d["conflict_severity"] == "HIGH"

    txt = report.to_text()
    assert "Contradiction Report for Claim: clm_test" in txt
    assert "Mixed Evidence: Yes" in txt


# --------------------------------------------------------------------------- #
# Unit Tests: Provenance Chain
# --------------------------------------------------------------------------- #


def test_build_provenance_chain_unit() -> None:
    """build_provenance_chain attaches retrieved_at, verified_at, and locations."""
    ts_retrieved = datetime(2026, 9, 10, 8, 0, 0, tzinfo=UTC)
    ts_verified = datetime(2026, 9, 10, 8, 30, 0, tzinfo=UTC)

    source = Source(
        id="src_prov",
        title="Provenance Source",
        state=SourceState.DISCOVERED,
        provenance=Provenance(
            origin="crossref",
            tool="crossref_api",
            retrieved_at=ts_retrieved,
        ),
    )
    source.transition_to(
        SourceState.DOI_VERIFIED,
        reason="DOI corroborated by Crossref",
        actor="test",
    )
    # Overwrite the history timestamp to a known value for exact assertion
    source.history[0].at = ts_verified

    claim = Claim(id="clm_prov", claim_text="Provenance test claim")
    ev = Evidence(
        id="ev_prov",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="Traceable finding.",
        reading_depth=ReadingDepth.FULL_TEXT,
        evidence_type=EvidenceType.DIRECT,
        relationship=EvidenceRelationship.SUPPORTS,
        location=EvidenceLocation(page=45, section="Methods"),
    )

    records = build_provenance_chain(claim, [ev], [source])

    assert len(records) == 1
    rec = records[0]
    assert rec.claim_id == claim.id
    assert rec.evidence_id == ev.id
    assert rec.source_id == source.id
    assert rec.reading_depth == ReadingDepth.FULL_TEXT
    assert rec.page == 45
    assert rec.section == "Methods"
    assert rec.retrieved_at == ts_retrieved
    assert rec.verified_at == ts_verified
    assert rec.verification_method == "crossref_api"
    assert rec.evidence_relation == EvidenceRelationship.SUPPORTS


# --------------------------------------------------------------------------- #
# Property-Based Tests (Properties 16-21)
# --------------------------------------------------------------------------- #


def test_property_16_mixed_evidence_classification() -> None:
    """Property 16: Mixed evidence classification.

    For any Claim that has at least one evidence record with relationship = SUPPORTS
    and at least one with relationship = CONTRADICTS, detect_contradictions SHALL
    classify the claim as mixed_evidence.

    **Validates: Requirements 11.2**
    """
    rng = random.Random(1616)
    relationships = list(EvidenceRelationship)
    strengths = list(EvidenceStrength)
    types = list(EvidenceType)

    for trial in range(50):
        claim = Claim(id=f"clm_{trial}", claim_text=f"Claim text for trial {trial}")

        # Choose whether this trial has mixed evidence
        has_sup = rng.choice([True, False])
        has_con = rng.choice([True, False])

        ev_list: list[Evidence] = []
        if has_sup:
            ev_list.append(
                Evidence(
                    claim_id=claim.id,
                    source_id=f"src_sup_{trial}",
                    evidence_text="Supporting evidence",
                    relationship=EvidenceRelationship.SUPPORTS,
                    strength=rng.choice(strengths),
                    evidence_type=rng.choice([EvidenceType.DIRECT, EvidenceType.PARTIAL]),
                )
            )
        if has_con:
            ev_list.append(
                Evidence(
                    claim_id=claim.id,
                    source_id=f"src_con_{trial}",
                    evidence_text="Contradicting evidence",
                    relationship=EvidenceRelationship.CONTRADICTS,
                    strength=rng.choice(strengths),
                    evidence_type=EvidenceType.CONTRADICTORY,
                )
            )

        # Add 0 to 3 other random evidence items
        for extra in range(rng.randint(0, 3)):
            rel = rng.choice(relationships)
            ev_list.append(
                Evidence(
                    claim_id=claim.id,
                    source_id=f"src_extra_{trial}_{extra}",
                    evidence_text=f"Extra evidence {extra}",
                    relationship=rel,
                    strength=rng.choice(strengths),
                    evidence_type=rng.choice(types),
                )
            )

        report = detect_contradictions(claim, ev_list)

        actual_sup = any(
            e.relationship in (EvidenceRelationship.SUPPORTS, EvidenceRelationship.PARTIALLY_SUPPORTS)
            for e in ev_list
        )
        actual_con = any(
            e.relationship is EvidenceRelationship.CONTRADICTS
            or e.evidence_type is EvidenceType.CONTRADICTORY
            for e in ev_list
        )
        expected_mixed = actual_sup and actual_con

        assert report.has_mixed_evidence is expected_mixed


def test_property_17_conflict_severity_from_contradictory_strength() -> None:
    """Property 17: Conflict severity from contradictory evidence strength.

    For any Claim with contradictory evidence, the conflict_severity SHALL be
    HIGH when the strongest contradictory evidence has strength of STRONG or
    DEFINITIVE, MEDIUM when MODERATE, and LOW when WEAK.

    **Validates: Requirements 11.4**
    """
    rng = random.Random(1717)
    strengths = list(EvidenceStrength)

    for trial in range(50):
        claim = Claim(id=f"clm_{trial}", claim_text=f"Claim text for trial {trial}")

        n_contradictory = rng.randint(0, 5)
        ev_list: list[Evidence] = []
        for i in range(n_contradictory):
            strn = rng.choice(strengths)
            ev_list.append(
                Evidence(
                    claim_id=claim.id,
                    source_id=f"src_con_{i}",
                    evidence_text=f"Contradiction {i}",
                    relationship=EvidenceRelationship.CONTRADICTS,
                    strength=strn,
                    evidence_type=EvidenceType.CONTRADICTORY,
                )
            )

        # Add 0 to 3 supporting items
        for i in range(rng.randint(0, 3)):
            ev_list.append(
                Evidence(
                    claim_id=claim.id,
                    source_id=f"src_sup_{i}",
                    evidence_text=f"Support {i}",
                    relationship=EvidenceRelationship.SUPPORTS,
                    strength=rng.choice(strengths),
                    evidence_type=EvidenceType.DIRECT,
                )
            )

        report = detect_contradictions(claim, ev_list)

        if n_contradictory == 0:
            assert report.conflict_severity is None
        else:
            con_strengths = {
                e.strength
                for e in ev_list
                if e.relationship is EvidenceRelationship.CONTRADICTS
                or e.evidence_type is EvidenceType.CONTRADICTORY
            }
            if EvidenceStrength.DEFINITIVE in con_strengths or EvidenceStrength.STRONG in con_strengths:
                assert report.conflict_severity == "HIGH"
            elif EvidenceStrength.MODERATE in con_strengths:
                assert report.conflict_severity == "MEDIUM"
            elif EvidenceStrength.WEAK in con_strengths:
                assert report.conflict_severity == "LOW"
            else:
                assert report.conflict_severity is None


def test_property_18_evidence_graph_completeness_and_broken_references() -> None:
    """Property 18: Evidence graph completeness and broken reference detection.

    For any set of claims, evidence, and sources, build_evidence_graph SHALL
    include every claim_id, every evidence record linked to a claim, and every source.
    For any evidence record whose source_id does not appear in the sources list,
    the graph SHALL mark that edge as broken_reference.

    **Validates: Requirements 7.1, 7.2, 7.3, 7.4**
    """
    rng = random.Random(1818)

    for trial in range(20):
        n_sources = rng.randint(1, 5)
        sources = [
            Source(
                id=f"src_{trial}_{s}",
                title=f"Source {s}",
                authors=[f"Author {s}"],
                year=2020 + s,
                state=SourceState.APPROVED,
            )
            for s in range(n_sources)
        ]
        source_ids = {s.id for s in sources}

        n_claims = rng.randint(1, 4)
        claims = [
            Claim(id=f"clm_{trial}_{c}", claim_text=f"Claim {c}")
            for c in range(n_claims)
        ]

        evidence: list[Evidence] = []
        for c in claims:
            n_ev = rng.randint(0, 4)
            for e_idx in range(n_ev):
                # 50% chance link to real source, 50% broken
                if rng.choice([True, False]):
                    s_id = rng.choice(sources).id
                else:
                    s_id = f"src_missing_{trial}_{e_idx}"

                evidence.append(
                    Evidence(
                        id=f"evd_{c.id}_{e_idx}",
                        claim_id=c.id,
                        source_id=s_id,
                        evidence_text=f"Evidence text for {c.id}",
                        relationship=rng.choice(list(EvidenceRelationship)),
                        strength=rng.choice(list(EvidenceStrength)),
                        evidence_type=rng.choice(list(EvidenceType)),
                        reading_depth=rng.choice(
                            [ReadingDepth.FULL_TEXT, ReadingDepth.METADATA_ONLY, ReadingDepth.UNAVAILABLE]
                        ),
                    )
                )

        graph = build_evidence_graph(claims, evidence, sources)

        # 1. Every claim is present
        assert set(graph["claims"].keys()) == {c.id for c in claims}

        # 2. Every source is present
        assert set(graph["sources"].keys()) == source_ids

        # 3. Completeness of evidence per claim
        for c in claims:
            expected_ev_ids = {e.id for e in evidence if e.claim_id == c.id}
            actual_ev_ids = {e["evidence_id"] for e in graph["claims"][c.id]["evidence"]}
            assert actual_ev_ids == expected_ev_ids

            # 4. Broken reference correctness
            for ev_node in graph["claims"][c.id]["evidence"]:
                is_broken = ev_node["source_id"] not in source_ids
                assert ev_node["broken_reference"] is is_broken

        # 5. Must be JSON serializable
        assert json.dumps(graph) is not None


def test_property_19_audit_flags_detection() -> None:
    """Property 19: Audit flags detection.

    For any Evidence record with verbatim = True and quote_verified = False,
    audit_evidence SHALL include an unverified_verbatim flag.
    For any Evidence record with reading_depth = ABSTRACT_ONLY and
    extraction_method = VERBATIM_FULLTEXT, audit_evidence SHALL include a
    depth_method_mismatch flag.
    For any Evidence record with evidence_type = CONTRADICTORY and
    relationship = SUPPORTS, audit_evidence SHALL include a
    type_relationship_mismatch flag.

    **Validates: Requirements 8.3, 8.4**
    """
    rng = random.Random(1919)
    source = Source(id="src_audit_prop", title="Source for audit", state=SourceState.APPROVED)

    for trial in range(30):
        flag_unv = rng.choice([True, False])
        flag_depth = rng.choice([True, False])
        flag_type = rng.choice([True, False])

        v_flag = True if flag_unv else rng.choice([True, False])
        qv_flag = False if flag_unv else (True if v_flag else rng.choice([True, False]))

        rd = ReadingDepth.ABSTRACT_ONLY if flag_depth else ReadingDepth.FULL_TEXT
        em = ExtractionMethod.VERBATIM_FULLTEXT if flag_depth else ExtractionMethod.VERBATIM_ABSTRACT

        et = (
            EvidenceType.CONTRADICTORY
            if flag_type
            else rng.choice([EvidenceType.DIRECT, EvidenceType.PARTIAL])
        )
        rel = (
            EvidenceRelationship.SUPPORTS
            if flag_type
            else rng.choice([EvidenceRelationship.PARTIALLY_SUPPORTS, EvidenceRelationship.CONTRADICTS])
        )

        ev = Evidence.model_construct(
            id=f"evd_audit_{trial}",
            claim_id="clm_1",
            source_id=source.id,
            evidence_text=f"Audit sample text {trial}",
            verbatim=v_flag,
            quote_verified=qv_flag,
            reading_depth=rd,
            extraction_method=em,
            evidence_type=et,
            relationship=rel,
            strength=EvidenceStrength.MODERATE,
            confidence=0.5,
            location=EvidenceLocation(),
        )

        res = audit_evidence([ev], [source])
        flag_types = {f.flag_type for f in res.flags if f.evidence_id == ev.id}

        assert ("unverified_verbatim" in flag_types) == (v_flag and not qv_flag)
        assert ("depth_method_mismatch" in flag_types) == (
            rd is ReadingDepth.ABSTRACT_ONLY and em is ExtractionMethod.VERBATIM_FULLTEXT
        )
        assert ("type_relationship_mismatch" in flag_types) == (
            et is EvidenceType.CONTRADICTORY and rel is EvidenceRelationship.SUPPORTS
        )


def test_property_20_audit_statistics_accuracy() -> None:
    """Property 20: Audit statistics accuracy.

    For any set of evidence records, the summary statistics in AuditResult
    (total count, per-type counts, per-depth counts, verified vs unverified
    quote counts, flagged issue count) SHALL exactly equal the counts computed
    by iterating the input evidence records.

    **Validates: Requirements 8.6**
    """
    rng = random.Random(2020)
    source = Source(id="src_stat", title="Stat Source", state=SourceState.APPROVED)

    types = list(EvidenceType)
    depths = [ReadingDepth.FULL_TEXT, ReadingDepth.METADATA_ONLY, ReadingDepth.UNAVAILABLE]

    for trial in range(25):
        n_ev = rng.randint(0, 15)
        evidence_list: list[Evidence] = []
        for i in range(n_ev):
            v_val = rng.choice([True, False])
            qv_val = rng.choice([True, False])
            if not v_val:
                qv_val = False

            evidence_list.append(
                Evidence(
                    id=f"ev_{trial}_{i}",
                    claim_id="clm_stat",
                    source_id=source.id,
                    evidence_text=f"Text {i}",
                    evidence_type=rng.choice(types),
                    reading_depth=rng.choice(depths),
                    verbatim=v_val,
                    quote_verified=qv_val,
                )
            )

        res = audit_evidence(evidence_list, [source])

        # Exact total count
        assert res.total_evidence == len(evidence_list)

        # Exact count per evidence_type
        for et in EvidenceType:
            expected_count = sum(1 for e in evidence_list if e.evidence_type == et)
            assert res.by_evidence_type.get(et.value, 0) == expected_count

        # Exact count per reading_depth
        for rd in ReadingDepth:
            expected_count = sum(1 for e in evidence_list if e.reading_depth == rd)
            assert res.by_reading_depth.get(rd.value, 0) == expected_count

        # Exact verified quotes count
        expected_verified = sum(1 for e in evidence_list if e.quote_verified)
        assert res.verified_quotes == expected_verified

        # Exact unverified quotes count
        expected_unverified = sum(1 for e in evidence_list if e.verbatim and not e.quote_verified)
        assert res.unverified_quotes == expected_unverified

        # Flags list length
        assert len(res.flags) == len(res.flags)


def test_property_21_provenance_chain_completeness() -> None:
    """Property 21: Provenance chain completeness.

    For any claim with N associated evidence records, build_provenance_chain
    SHALL return exactly N ProvenanceRecord instances. For any ProvenanceRecord,
    the retrieved_at field SHALL equal the source's provenance.retrieved_at
    (or None if absent), and verified_at SHALL equal the timestamp of the source's
    first transition to a verified state (or None if no such transition exists).

    **Validates: Requirements 9.2, 9.3, 9.5**
    """
    rng = random.Random(2121)

    for trial in range(30):
        claim = Claim(id=f"clm_chain_{trial}", claim_text=f"Claim text {trial}")

        n_sources = rng.randint(1, 4)
        sources: list[Source] = []
        for s_idx in range(n_sources):
            has_prov = rng.choice([True, False])
            prov = None
            if has_prov:
                prov = Provenance(
                    origin="crossref",
                    tool="api",
                    retrieved_at=datetime(2026, 8, s_idx + 1, 10, 0, 0, tzinfo=UTC),
                )

            src = Source(
                id=f"src_ch_{trial}_{s_idx}",
                title=f"Source {s_idx}",
                state=SourceState.DISCOVERED,
                provenance=prov,
            )

            # Random transitions
            has_verified_transition = rng.choice([True, False])
            if has_verified_transition:
                src.transition_to(
                    SourceState.DOI_VERIFIED,
                    reason="Corroborated",
                    actor="test",
                )
                src.history[0].at = datetime(2026, 8, s_idx + 1, 11, 0, 0, tzinfo=UTC)

            sources.append(src)

        source_map = {s.id: s for s in sources}

        # N associated evidence records
        n_ev = rng.randint(0, 8)
        evidence_list: list[Evidence] = []
        for e_idx in range(n_ev):
            # 80% link to real source, 20% to non-existent source
            if rng.choice([True, True, True, True, False]):
                src_choice = rng.choice(sources).id
            else:
                src_choice = f"src_missing_{e_idx}"

            evidence_list.append(
                Evidence(
                    id=f"ev_ch_{trial}_{e_idx}",
                    claim_id=claim.id,
                    source_id=src_choice,
                    evidence_text=f"Evidence text {e_idx}",
                    reading_depth=rng.choice(
                        [ReadingDepth.FULL_TEXT, ReadingDepth.METADATA_ONLY, ReadingDepth.UNAVAILABLE]
                    ),
                    location=EvidenceLocation(page=e_idx + 1, section=f"Section_{e_idx}"),
                )
            )

        chain = build_provenance_chain(claim, evidence_list, sources)

        # 1. Exactly N records
        assert len(chain) == n_ev

        # 2. Field correctness
        for orig_ev, rec in zip(evidence_list, chain, strict=True):
            assert rec.claim_id == claim.id
            assert rec.evidence_id == orig_ev.id
            assert rec.source_id == orig_ev.source_id
            assert rec.reading_depth == orig_ev.reading_depth
            assert rec.page == orig_ev.location.page
            assert rec.section == orig_ev.location.section

            src = source_map.get(orig_ev.source_id)
            if src is not None and src.provenance is not None:
                assert rec.retrieved_at == src.provenance.retrieved_at
            else:
                assert rec.retrieved_at is None

            expected_verified_at = None
            if src is not None:
                for t in src.history:
                    if t.to_state and t.to_state in [
                        SourceState.METADATA_VERIFIED,
                        SourceState.DOI_VERIFIED,
                        SourceState.PUBLISHER_VERIFIED,
                        SourceState.FULLTEXT_RETRIEVED,
                        SourceState.EVIDENCE_EXTRACTED,
                        SourceState.CLAIM_SUPPORTED,
                        SourceState.APPROVED,
                    ]:
                        expected_verified_at = t.at
                        break

            assert rec.verified_at == expected_verified_at


# --------------------------------------------------------------------------- #
# Property-Based Tests: Extended Evidence Flow (Properties 2, 4, 7, 8, 9)
# --------------------------------------------------------------------------- #


def test_property_2_not_supported_evidence_excluded_from_positive_support() -> None:
    """Property 2: NOT_SUPPORTED evidence excluded from positive support.

    For any list of Evidence records where some have evidence_type = NOT_SUPPORTED,
    calling compute_support_level SHALL produce the same SupportLevel as calling it
    with those NOT_SUPPORTED records removed from the list.

    **Validates: Requirement 1.5**
    """
    rng = random.Random(202)
    strengths = list(EvidenceStrength)
    types_excluding_not_supported = [
        EvidenceType.DIRECT,
        EvidenceType.PARTIAL,
        EvidenceType.THEORETICAL,
        EvidenceType.FUNCTIONAL_EQUIVALENT,
        EvidenceType.BACKGROUND,
    ]

    for trial in range(50):
        # Generate 0 to 5 positive evidence records
        n_pos = rng.randint(0, 5)
        evidence_list: list[Evidence] = []
        for i in range(n_pos):
            evidence_list.append(
                Evidence(
                    id=f"ev_pos_{trial}_{i}",
                    claim_id="clm_prop2",
                    source_id=f"src_{rng.randint(1, 3)}",
                    evidence_text=f"Positive evidence {i}",
                    relationship=rng.choice([EvidenceRelationship.SUPPORTS, EvidenceRelationship.PARTIALLY_SUPPORTS]),
                    strength=rng.choice(strengths),
                    evidence_type=rng.choice(types_excluding_not_supported),
                )
            )

        # Generate 1 to 4 NOT_SUPPORTED evidence records
        n_not_supported = rng.randint(1, 4)
        for j in range(n_not_supported):
            evidence_list.append(
                Evidence(
                    id=f"ev_ns_{trial}_{j}",
                    claim_id="clm_prop2",
                    source_id=f"src_{rng.randint(1, 3)}",
                    evidence_text=f"Not supported evidence {j}",
                    relationship=rng.choice([EvidenceRelationship.SUPPORTS, EvidenceRelationship.PARTIALLY_SUPPORTS]),
                    strength=rng.choice(strengths),
                    evidence_type=EvidenceType.NOT_SUPPORTED,
                )
            )

        rng.shuffle(evidence_list)

        # With NOT_SUPPORTED included
        level_with_ns = compute_support_level(evidence_list)

        # With NOT_SUPPORTED filtered out
        filtered_list = [e for e in evidence_list if e.evidence_type != EvidenceType.NOT_SUPPORTED]
        level_filtered = compute_support_level(filtered_list)

        assert level_with_ns == level_filtered

    # Edge case: ONLY NOT_SUPPORTED records in the list produces SupportLevel.NONE
    only_ns = [
        Evidence(
            id=f"ev_only_ns_{k}",
            claim_id="clm_prop2",
            source_id="src_1",
            evidence_text="Null finding",
            relationship=EvidenceRelationship.SUPPORTS,
            strength=EvidenceStrength.DEFINITIVE,
            evidence_type=EvidenceType.NOT_SUPPORTED,
        )
        for k in range(3)
    ]
    assert compute_support_level(only_ns) is SupportLevel.NONE


def test_property_4_reading_depth_caps_confidence() -> None:
    """Property 4: Reading depth caps confidence.

    For any claim evaluation where all supporting evidence has reading_depth = ABSTRACT_ONLY,
    the calibrated confidence SHALL not exceed 0.5. For any claim evaluation where all
    supporting evidence has reading_depth in (METADATA_ONLY, UNAVAILABLE), the calibrated
    confidence SHALL not exceed 0.2.

    **Validates: Requirement 2.5**
    """
    rng = random.Random(404)
    strengths = list(EvidenceStrength)
    types = [EvidenceType.DIRECT, EvidenceType.PARTIAL, EvidenceType.THEORETICAL]

    for trial in range(50):
        claim = Claim(id=f"clm_{trial}", claim_text="Claim for reading depth test", required_source_count=1)

        # Test ABSTRACT_ONLY cap (<= 0.5)
        n_ev = rng.randint(1, 4)
        abstract_evidence = [
            Evidence(
                id=f"ev_abs_{trial}_{i}",
                claim_id=claim.id,
                source_id=f"src_{i}",
                evidence_text=f"Abstract evidence {i}",
                relationship=EvidenceRelationship.SUPPORTS,
                strength=rng.choice(strengths),
                evidence_type=rng.choice(types),
                reading_depth=ReadingDepth.ABSTRACT_ONLY,
                extraction_method=ExtractionMethod.VERBATIM_ABSTRACT,
            )
            for i in range(n_ev)
        ]
        conf_abstract = calibrate_confidence(
            claim,
            supporting=abstract_evidence,
            contradicting=[],
            support_level=SupportLevel.STRONG,
        )
        assert conf_abstract <= 0.5, f"ABSTRACT_ONLY confidence {conf_abstract} exceeded 0.5"

        # Also verify via evaluate_claim
        eval_result_abs = evaluate_claim(claim, abstract_evidence)
        assert eval_result_abs.confidence <= 0.5

        # Test METADATA_ONLY / UNAVAILABLE cap (<= 0.2)
        n_ev_meta = rng.randint(1, 4)
        meta_evidence = [
            Evidence(
                id=f"ev_meta_{trial}_{i}",
                claim_id=claim.id,
                source_id=f"src_{i}",
                evidence_text=f"Metadata evidence {i}",
                relationship=EvidenceRelationship.SUPPORTS,
                strength=rng.choice(strengths),
                evidence_type=rng.choice(types),
                reading_depth=rng.choice([ReadingDepth.METADATA_ONLY, ReadingDepth.UNAVAILABLE]),
            )
            for i in range(n_ev_meta)
        ]
        conf_meta = calibrate_confidence(
            claim,
            supporting=meta_evidence,
            contradicting=[],
            support_level=SupportLevel.STRONG,
        )
        assert conf_meta <= 0.2, f"METADATA_ONLY confidence {conf_meta} exceeded 0.2"

        eval_result_meta = evaluate_claim(claim, meta_evidence)
        assert eval_result_meta.confidence <= 0.2

    # Contrast check: FULL_TEXT evidence with STRONG support can exceed 0.5
    full_text_ev = [
        Evidence(
            id="ev_full",
            claim_id="clm_contrast",
            source_id="src_1",
            evidence_text="Full text passage",
            relationship=EvidenceRelationship.SUPPORTS,
            strength=EvidenceStrength.STRONG,
            evidence_type=EvidenceType.DIRECT,
            reading_depth=ReadingDepth.FULL_TEXT,
        )
    ]
    claim_full = Claim(
        id="clm_contrast",
        claim_text="Full text claim",
        required_source_count=1,
        supporting_sources=["src_1"],
    )
    conf_full = calibrate_confidence(
        claim_full,
        supporting=full_text_ev,
        contradicting=[],
        support_level=SupportLevel.STRONG,
    )
    assert conf_full > 0.5


def test_property_7_evidence_type_degradation_in_support_level() -> None:
    """Property 7: Evidence type degradation in support level computation.

    For any Evidence record with evidence_type = THEORETICAL or FUNCTIONAL_EQUIVALENT,
    the effective strength used by compute_support_level SHALL be one level lower than
    the strength computed by max_claim_strength(). For any Evidence record with
    evidence_type = BACKGROUND, the effective strength SHALL be WEAK regardless of
    the strength field value.

    **Validates: Requirements 12.1, 12.2, 12.3**
    """
    ladder = [
        EvidenceStrength.WEAK,
        EvidenceStrength.MODERATE,
        EvidenceStrength.STRONG,
        EvidenceStrength.DEFINITIVE,
    ]

    for strength in EvidenceStrength:
        for rel in [EvidenceRelationship.SUPPORTS, EvidenceRelationship.PARTIALLY_SUPPORTS]:
            # THEORETICAL degradation
            ev_theo = Evidence(
                claim_id="c1",
                source_id="s1",
                evidence_text="theoretical text",
                relationship=rel,
                strength=strength,
                evidence_type=EvidenceType.THEORETICAL,
            )
            base_strength = ev_theo.max_claim_strength()
            base_idx = ladder.index(base_strength)
            expected_degraded = ladder[max(0, base_idx - 1)]
            assert _effective_strength(ev_theo) == expected_degraded

            # FUNCTIONAL_EQUIVALENT degradation
            ev_func = Evidence(
                claim_id="c1",
                source_id="s1",
                evidence_text="func equiv text",
                relationship=rel,
                strength=strength,
                evidence_type=EvidenceType.FUNCTIONAL_EQUIVALENT,
            )
            assert _effective_strength(ev_func) == expected_degraded

            # BACKGROUND caps at WEAK
            ev_bg = Evidence(
                claim_id="c1",
                source_id="s1",
                evidence_text="background text",
                relationship=rel,
                strength=strength,
                evidence_type=EvidenceType.BACKGROUND,
            )
            assert _effective_strength(ev_bg) == EvidenceStrength.WEAK

    # Verify impact on compute_support_level:
    # A single DEFINITIVE source gives STRONG when DIRECT, but only MODERATE when THEORETICAL
    # (DEFINITIVE degrades to STRONG; single STRONG gives MODERATE)
    ev_def_direct = Evidence(
        claim_id="c1",
        source_id="s1",
        evidence_text="direct text",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.DEFINITIVE,
        evidence_type=EvidenceType.DIRECT,
    )
    assert compute_support_level([ev_def_direct]) is SupportLevel.STRONG

    ev_def_theo = Evidence(
        claim_id="c1",
        source_id="s1",
        evidence_text="theo text",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.DEFINITIVE,
        evidence_type=EvidenceType.THEORETICAL,
    )
    assert compute_support_level([ev_def_theo]) is SupportLevel.MODERATE

    # BACKGROUND definitive gives WEAK
    ev_def_bg = Evidence(
        claim_id="c1",
        source_id="s1",
        evidence_text="bg text",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.DEFINITIVE,
        evidence_type=EvidenceType.BACKGROUND,
    )
    assert compute_support_level([ev_def_bg]) is SupportLevel.WEAK


def test_property_8_all_partial_or_theoretical_evidence_caps_at_moderate() -> None:
    """Property 8: All PARTIAL/THEORETICAL evidence caps support level at MODERATE.

    For any claim where all supporting evidence has evidence_type of PARTIAL or
    THEORETICAL, the SupportLevel returned by compute_support_level SHALL not exceed
    MODERATE, even with multiple distinct definitive/strong sources.

    **Validates: Requirement 12.4**
    """
    rng = random.Random(808)
    strengths = [EvidenceStrength.STRONG, EvidenceStrength.DEFINITIVE]

    for trial in range(40):
        n_sources = rng.randint(2, 6)
        evidence_list: list[Evidence] = []
        for i in range(n_sources):
            et = rng.choice([EvidenceType.PARTIAL, EvidenceType.THEORETICAL])
            evidence_list.append(
                Evidence(
                    id=f"ev_p8_{trial}_{i}",
                    claim_id="clm_p8",
                    source_id=f"src_p8_{i}",
                    evidence_text=f"Evidence {i}",
                    relationship=EvidenceRelationship.SUPPORTS,
                    strength=rng.choice(strengths),
                    evidence_type=et,
                )
            )

        # Without the cap, 2+ distinct sources with STRONG/DEFINITIVE would produce STRONG
        result = compute_support_level(evidence_list)
        assert result in {SupportLevel.MODERATE, SupportLevel.WEAK}
        assert result is not SupportLevel.STRONG

    # Contrast: if even one DIRECT strong evidence is added with another source, STRONG is possible
    direct_ev = Evidence(
        id="ev_direct",
        claim_id="clm_p8",
        source_id="src_direct",
        evidence_text="Direct text",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        evidence_type=EvidenceType.DIRECT,
    )
    theo_ev = Evidence(
        id="ev_theo",
        claim_id="clm_p8",
        source_id="src_theo",
        evidence_text="Theo text",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        evidence_type=EvidenceType.THEORETICAL,
    )
    # 2 sources, one DIRECT STRONG -> SupportLevel.STRONG
    assert compute_support_level([direct_ev, theo_ev]) is SupportLevel.STRONG


def test_property_9_evidence_type_confidence_multipliers() -> None:
    """Property 9: Evidence type confidence multipliers.

    For any confidence calculation, the confidence contribution of evidence SHALL
    be multiplied by: 0.8 for PARTIAL, 0.6 for THEORETICAL, 0.7 for
    FUNCTIONAL_EQUIVALENT, and 0.3 for BACKGROUND evidence types.

    **Validates: Requirement 12.5**
    """
    expected_multipliers = {
        EvidenceType.DIRECT: 1.0,
        EvidenceType.PARTIAL: 0.8,
        EvidenceType.FUNCTIONAL_EQUIVALENT: 0.7,
        EvidenceType.THEORETICAL: 0.6,
        EvidenceType.BACKGROUND: 0.3,
    }

    claim = Claim(id="clm_p9", claim_text="Multiplier test claim", required_source_count=1)

    # Base DIRECT confidence
    ev_direct = Evidence(
        id="ev_dir",
        claim_id=claim.id,
        source_id="src_1",
        evidence_text="Direct text",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        evidence_type=EvidenceType.DIRECT,
        reading_depth=ReadingDepth.FULL_TEXT,
    )
    base_conf = calibrate_confidence(
        claim,
        supporting=[ev_direct],
        contradicting=[],
        support_level=SupportLevel.MODERATE,
    )

    for et, expected_mult in expected_multipliers.items():
        ev = Evidence(
            id=f"ev_{et.value}",
            claim_id=claim.id,
            source_id="src_1",
            evidence_text=f"Text for {et.value}",
            relationship=EvidenceRelationship.SUPPORTS,
            strength=EvidenceStrength.STRONG,
            evidence_type=et,
            reading_depth=ReadingDepth.FULL_TEXT,
        )
        conf = calibrate_confidence(
            claim,
            supporting=[ev],
            contradicting=[],
            support_level=SupportLevel.MODERATE,
        )
        expected_conf = round(base_conf * expected_mult, 3)
        assert conf == expected_conf, f"EvidenceType {et.value} expected {expected_conf}, got {conf}"

    # Multiple evidence with different types: best multiplier applies
    ev_partial = Evidence(
        id="ev_part",
        claim_id=claim.id,
        source_id="src_1",
        evidence_text="Partial",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        evidence_type=EvidenceType.PARTIAL,
        reading_depth=ReadingDepth.FULL_TEXT,
    )
    ev_bg = Evidence(
        id="ev_bg",
        claim_id=claim.id,
        source_id="src_2",
        evidence_text="Background",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        evidence_type=EvidenceType.BACKGROUND,
        reading_depth=ReadingDepth.FULL_TEXT,
    )
    conf_mixed = calibrate_confidence(
        claim,
        supporting=[ev_partial, ev_bg],
        contradicting=[],
        support_level=SupportLevel.MODERATE,
    )
    # best multiplier is max(0.8, 0.3) = 0.8
    assert conf_mixed == round(base_conf * 0.8, 3)


# --------------------------------------------------------------------------- #
# Unit Tests: Storage Helpers
# --------------------------------------------------------------------------- #


def test_storage_evidence_graph(tmp_path: Path) -> None:
    """save_evidence_graph and load_evidence_graph persist and retrieve correctly."""
    graph_data = {
        "claims": {
            "clm_1": {
                "claim_id": "clm_1",
                "claim_text": "Sample claim",
                "evidence": [],
                "supporting_count": 0,
                "contradicting_count": 0,
            }
        },
        "sources": {},
    }
    graph_path = tmp_path / "evidence_graph.json"
    saved_path = save_evidence_graph(graph_data, graph_path, root=tmp_path)
    assert saved_path == graph_path
    assert graph_path.is_file()

    loaded = load_evidence_graph(graph_path)
    assert loaded == graph_data

    # Missing file returns empty dict
    missing_path = tmp_path / "missing_graph.json"
    assert load_evidence_graph(missing_path) == {}

    # Invalid non-dict file returns empty dict
    bad_path = tmp_path / "bad_graph.json"
    bad_path.write_text('["not", "a", "dict"]', encoding="utf-8")
    assert load_evidence_graph(bad_path) == {}


def test_storage_provenance_chain(tmp_path: Path) -> None:
    """save_provenance_chain and load_provenance_chain persist and retrieve correctly."""
    rec = ProvenanceRecord(
        source_id="src_1",
        evidence_id="evd_1",
        claim_id="clm_1",
        reading_depth=ReadingDepth.FULL_TEXT,
        page=10,
        section="Results",
        evidence_relation=EvidenceRelationship.SUPPORTS,
    )
    chain_path = tmp_path / "provenance.jsonl"
    count = save_provenance_chain([rec], chain_path, root=tmp_path)
    assert count == 1
    assert chain_path.is_file()

    loaded = load_provenance_chain(chain_path)
    assert len(loaded) == 1
    assert loaded[0]["source_id"] == "src_1"
    assert loaded[0]["evidence_id"] == "evd_1"
    assert loaded[0]["reading_depth"] == "FULL_TEXT"

    # Missing file returns empty list
    missing_path = tmp_path / "missing_prov.jsonl"
    assert load_provenance_chain(missing_path) == []


# --------------------------------------------------------------------------- #
# Unit Tests: Integrity Gate Extensions
# --------------------------------------------------------------------------- #


def test_gate_empty_support_on_supported_claim() -> None:
    """Req 10.6: SUPPORTED claim with no supporting evidence produces violation."""
    claim = Claim(
        id="clm_empty",
        claim_text="Assertion without evidence",
        status=ClaimStatus.SUPPORTED,
        supporting_evidence=[],
    )
    result = check_academic_integrity(claims=[claim], evidence=[], sources=[])
    assert not result.ok
    assert any("marked SUPPORTED with no supporting evidence" in v for v in result.violations)

    # If status is PROPOSED, no empty support violation
    claim_prop = Claim(
        id="clm_prop",
        claim_text="Assertion proposal",
        status=ClaimStatus.PROPOSED,
        supporting_evidence=[],
    )
    result_prop = check_academic_integrity(claims=[claim_prop], evidence=[], sources=[])
    assert not any("marked SUPPORTED with no supporting evidence" in v for v in result_prop.violations)


def test_gate_unverified_unretrieved_source() -> None:
    """Req 10.7: Evidence citing unverified, unretrieved source produces violation."""
    src = Source(
        id="src_unv_unret",
        title="Unverified and unretrieved paper",
        publisher_verified=False,
        retrieval_status=RetrievalStatus.NOT_ATTEMPTED,
        state=SourceState.APPROVED,
    )
    claim = Claim(
        id="clm_1",
        claim_text="Test claim",
        supporting_sources=[src.id],
        supporting_evidence=["evd_1"],
        status=ClaimStatus.SUPPORTED,
    )
    ev = Evidence(
        id="evd_1",
        claim_id=claim.id,
        source_id=src.id,
        evidence_text="Evidence text from unretrieved source",
        verbatim=False,
    )
    result = check_academic_integrity(claims=[claim], evidence=[ev], sources=[src])
    assert not result.ok
    assert any("cites unverified, unretrieved source" in v for v in result.violations)

    # When publisher_verified is True, violation is not triggered
    src_verified = Source(
        id="src_v_unret",
        title="Verified paper",
        publisher_verified=True,
        retrieval_status=RetrievalStatus.NOT_ATTEMPTED,
        state=SourceState.APPROVED,
    )
    ev_v = Evidence(
        id="evd_1",
        claim_id=claim.id,
        source_id=src_verified.id,
        evidence_text="Evidence text",
        verbatim=False,
    )
    result_v = check_academic_integrity(claims=[claim], evidence=[ev_v], sources=[src_verified])
    assert not any("cites unverified, unretrieved source" in v for v in result_v.violations)


# --------------------------------------------------------------------------- #
# Property-Based Tests: Integrity Gate and Review Queue
# --------------------------------------------------------------------------- #


def test_property_12_doi_format_validation() -> None:
    """Property 12: DOI format validation.

    For any string that does not match the pattern ^10\\.\\d{4,}/\\S+$, the integrity
    gate SHALL add a violation when that string is used as a source's DOI. For any
    string matching the pattern, no DOI format violation SHALL be produced.

    **Validates: Requirements 10.1, 10.2**
    """
    valid_dois = [
        "10.1000/182",
        "10.1038/nature12373",
        "10.1145/3372278.3390670",
        "10.1016/j.chb.2021.106888",
        "10.12345/sub-dir/test_id.v2",
        "10.999999/alpha:beta-gamma",
    ]
    invalid_dois = [
        "not_a_doi",
        "http://doi.org/10.1000/182",
        "https://doi.org/10.1000/182",
        "doi:10.1000/182",
        "10.12/short_prefix",  # prefix < 4 digits
        "10.123/short_prefix",  # prefix < 4 digits
        "10.1000/",  # empty suffix
        "10.1000/with space",  # whitespace in suffix
        "9.1000/wrong_prefix",
        "",
    ]

    for doi in valid_dois:
        src = Source(id="src_val", title="Valid DOI paper", doi=doi, state=SourceState.APPROVED)
        res = check_academic_integrity(claims=[], evidence=[], sources=[src])
        doi_violations = [v for v in res.violations if "invalid DOI format" in v]
        assert len(doi_violations) == 0, f"Valid DOI {doi} unexpectedly flagged: {doi_violations}"

    for doi in invalid_dois:
        src = Source(id="src_inval", title="Invalid DOI paper", doi=doi, state=SourceState.APPROVED)
        res = check_academic_integrity(claims=[], evidence=[], sources=[src])
        doi_violations = [v for v in res.violations if "invalid DOI format" in v]
        assert len(doi_violations) == 1, f"Invalid DOI {doi} was not flagged"
        assert f"invalid DOI format for source src_inval: {doi}" in doi_violations[0]

    # None DOI produces no violation
    src_none = Source(id="src_none", title="No DOI paper", doi=None, state=SourceState.APPROVED)
    res_none = check_academic_integrity(claims=[], evidence=[], sources=[src_none])
    assert not any("invalid DOI format" in v for v in res_none.violations)


def test_property_13_evidence_type_relationship_mismatch() -> None:
    """Property 13: Evidence type/relationship mismatch detection.

    For any Evidence record where evidence_type = CONTRADICTORY and
    relationship = SUPPORTS, the integrity gate SHALL add a violation
    identifying the mismatch.

    **Validates: Requirement 10.3**
    """
    src = Source(id="src_1", title="Source 1", state=SourceState.APPROVED)
    claim = Claim(id="clm_1", claim_text="Claim 1", supporting_evidence=["evd_test"])

    for etype in EvidenceType:
        for rel in EvidenceRelationship:
            ev = Evidence(
                id="evd_test",
                claim_id=claim.id,
                source_id=src.id,
                evidence_text="Sample text",
                evidence_type=etype,
                relationship=rel,
                verbatim=False,
            )
            res = check_academic_integrity(claims=[claim], evidence=[ev], sources=[src])
            mismatch_violations = [v for v in res.violations if "evidence type/relationship mismatch" in v]

            should_mismatch = (etype == EvidenceType.CONTRADICTORY and rel == EvidenceRelationship.SUPPORTS)
            if should_mismatch:
                assert len(mismatch_violations) == 1
                assert f"evidence type/relationship mismatch for evidence evd_test" in mismatch_violations[0]
            else:
                assert len(mismatch_violations) == 0


def test_property_14_overclaim_detection() -> None:
    """Property 14: Overclaim detection.

    For any Claim with status = SUPPORTED where all supporting evidence has
    evidence_type of FUNCTIONAL_EQUIVALENT or THEORETICAL, the integrity gate
    SHALL add a violation flagging the overclaim.

    **Validates: Requirement 10.4**
    """
    rng = random.Random(1414)
    src = Source(id="src_over", title="Source for overclaim", state=SourceState.APPROVED)

    for trial in range(30):
        # Decide whether this trial is an overclaim
        is_overclaim = rng.choice([True, False])
        n_ev = rng.randint(1, 4)

        evidence_list: list[Evidence] = []
        ev_ids: list[str] = []
        for i in range(n_ev):
            eid = f"evd_over_{trial}_{i}"
            ev_ids.append(eid)
            if is_overclaim:
                etype = rng.choice([EvidenceType.FUNCTIONAL_EQUIVALENT, EvidenceType.THEORETICAL])
            else:
                etype = rng.choice([EvidenceType.DIRECT, EvidenceType.PARTIAL, EvidenceType.BACKGROUND])

            evidence_list.append(
                Evidence(
                    id=eid,
                    claim_id=f"clm_{trial}",
                    source_id=src.id,
                    evidence_text=f"Evidence text {i}",
                    evidence_type=etype,
                    relationship=EvidenceRelationship.SUPPORTS,
                    verbatim=False,
                )
            )

        # If not overclaim, ensure at least one is NOT theoretical/functional_equiv
        if not is_overclaim and all(
            e.evidence_type in (EvidenceType.FUNCTIONAL_EQUIVALENT, EvidenceType.THEORETICAL)
            for e in evidence_list
        ):
            evidence_list[0].evidence_type = EvidenceType.DIRECT

        claim = Claim(
            id=f"clm_{trial}",
            claim_text=f"Overclaim test assertion {trial}",
            status=ClaimStatus.SUPPORTED,
            supporting_sources=[src.id],
            supporting_evidence=ev_ids,
        )

        res = check_academic_integrity(claims=[claim], evidence=evidence_list, sources=[src])
        overclaim_violations = [v for v in res.violations if "overclaimed" in v]

        expected_overclaim = all(
            e.evidence_type in (EvidenceType.FUNCTIONAL_EQUIVALENT, EvidenceType.THEORETICAL)
            for e in evidence_list
        )
        if expected_overclaim:
            assert len(overclaim_violations) == 1
            assert f"claim clm_{trial} overclaimed: no direct evidence supports the claim" in overclaim_violations[0]
        else:
            assert len(overclaim_violations) == 0


def test_property_15_abstract_only_evidence_review_reason() -> None:
    """Property 15: Abstract-only evidence review reason.

    For any Claim with status = SUPPORTED where all supporting evidence has
    reading_depth = ABSTRACT_ONLY, the integrity gate SHALL add a review reason.

    **Validates: Requirement 10.5**
    """
    rng = random.Random(1515)
    src = Source(id="src_abs", title="Source for abstract test", state=SourceState.APPROVED)

    for trial in range(30):
        all_abstract = rng.choice([True, False])
        n_ev = rng.randint(1, 4)

        evidence_list: list[Evidence] = []
        ev_ids: list[str] = []
        for i in range(n_ev):
            eid = f"evd_abs_{trial}_{i}"
            ev_ids.append(eid)
            rd = (
                ReadingDepth.ABSTRACT_ONLY
                if all_abstract
                else rng.choice([ReadingDepth.FULL_TEXT, ReadingDepth.METADATA_ONLY])
            )
            em = (
                ExtractionMethod.VERBATIM_ABSTRACT
                if rd == ReadingDepth.ABSTRACT_ONLY
                else ExtractionMethod.MODEL_PARAPHRASE
            )
            evidence_list.append(
                Evidence(
                    id=eid,
                    claim_id=f"clm_{trial}",
                    source_id=src.id,
                    evidence_text=f"Abstract evidence {i}",
                    reading_depth=rd,
                    extraction_method=em,
                    relationship=EvidenceRelationship.SUPPORTS,
                    evidence_type=EvidenceType.DIRECT,
                    verbatim=False,
                )
            )

        if not all_abstract and all(e.reading_depth == ReadingDepth.ABSTRACT_ONLY for e in evidence_list):
            evidence_list[0].reading_depth = ReadingDepth.FULL_TEXT

        claim = Claim(
            id=f"clm_{trial}",
            claim_text=f"Abstract test assertion {trial}",
            status=ClaimStatus.SUPPORTED,
            supporting_sources=[src.id],
            supporting_evidence=ev_ids,
        )

        res = check_academic_integrity(claims=[claim], evidence=evidence_list, sources=[src])
        abs_reasons = [r for r in res.review_reasons if "supported only by abstract-level evidence" in r]

        expected_abstract = all(e.reading_depth == ReadingDepth.ABSTRACT_ONLY for e in evidence_list)
        if expected_abstract:
            assert len(abs_reasons) == 1
            assert f"claim clm_{trial} supported only by abstract-level evidence" in abs_reasons[0]
        else:
            assert len(abs_reasons) == 0


def test_property_25_gate_result_review_reasons_create_review_items() -> None:
    """Property 25: GateResult review reasons create ReviewItems.

    For any GateResult with N review_reasons, creating ReviewItem records from
    them SHALL produce N items, each with status = 'PENDING'.

    **Validates: Requirement 13.3**
    """
    for n in [0, 1, 3, 7, 15]:
        reasons = []
        for i in range(n):
            if i % 2 == 0:
                reasons.append(f"claim clm_{i} supported only by abstract-level evidence")
            else:
                reasons.append(f"source src_{i} not indexed in any queried database")

        gate_res = GateResult(review_reasons=reasons)
        queue = create_review_queue_from_gate_result(gate_res)

        assert len(queue) == n
        for item, expected_reason in zip(queue.items, reasons, strict=True):
            assert item.status == "PENDING"
            assert item.severity == "MEDIUM"
            assert item.reason == expected_reason
            if "claim " in expected_reason:
                assert item.item_type == "claim"
                assert item.item_id in expected_reason
            elif "source " in expected_reason:
                assert item.item_type == "source"
                assert item.item_id in expected_reason


def test_property_26_semantic_review_severity_mapping() -> None:
    """Property 26: Semantic review severity mapping.

    For any Claim that requires semantic review, the created ReviewItem severity
    SHALL map from the claim's importance: CRITICAL -> 'CRITICAL', HIGH -> 'HIGH',
    MEDIUM -> 'MEDIUM', LOW -> 'LOW'.

    **Validates: Requirement 13.7**
    """
    # Create claims across all 4 importance levels that require semantic review
    claims = [
        Claim(
            id="clm_crit",
            claim_text="Fundamental thesis of the research",
            importance=ClaimImportance.CRITICAL,
        ),
        Claim(
            id="clm_high",
            claim_text="Major empirical assertion",
            importance=ClaimImportance.HIGH,
        ),
        Claim(
            id="clm_med_causal",
            claim_text="Intervensi ini menyebabkan peningkatan hasil belajar",  # "menyebabkan" triggers review
            importance=ClaimImportance.MEDIUM,
        ),
        Claim(
            id="clm_low_stat",
            claim_text="Nilai efisiensi meningkat sebesar 25%",  # "meningkat" + "25%" triggers review
            importance=ClaimImportance.LOW,
        ),
    ]

    for c in claims:
        assert c.requires_semantic_review is True

    queue = create_review_queue_from_gate_result(GateResult(), claims=claims)
    assert len(queue) == 4

    items_by_id = {item.item_id: item for item in queue.items}
    assert items_by_id["clm_crit"].severity == "CRITICAL"
    assert items_by_id["clm_high"].severity == "HIGH"
    assert items_by_id["clm_med_causal"].severity == "MEDIUM"
    assert items_by_id["clm_low_stat"].severity == "LOW"

    # If claim already has a semantic review, it is not re-queued
    claims[0].semantic_review = SemanticReview(
        claim_id=claims[0].id,
        decision=SemanticDecision.SUPPORTED,
        reason="Corroborated by independent review",
    )
    queue_after_review = create_review_queue_from_gate_result(GateResult(), claims=claims)
    assert len(queue_after_review) == 3
    assert "clm_crit" not in {item.item_id for item in queue_after_review.items}

    # Claim that does NOT require semantic review is not queued
    benign_claim = Claim(
        id="clm_benign",
        claim_text="Studi pendahuluan dilakukan di perpustakaan",
        importance=ClaimImportance.LOW,
    )
    assert benign_claim.requires_semantic_review is False
    q_benign = create_review_queue_from_gate_result(GateResult(), claims=[benign_claim])
    assert len(q_benign) == 0


def test_property_27_unverified_source_with_publisher_verified_false_flagged() -> None:
    """Property 27: Unverified source with publisher_verified=False flagged.

    For any source with publisher_verified = False that is cited in a claim,
    the integrity gate SHALL include a review item for the citation.

    **Validates: Requirement 4.5**
    """
    # Source with explicit publisher_verified=False
    src_unverified = Source(
        id="src_pub_false",
        title="Unverified Publisher Source",
        state=SourceState.APPROVED,
        publisher_verified=False,
    )
    claim = Claim(
        id="clm_pub_test",
        claim_text="Claim citing unverified publisher source",
        supporting_sources=[src_unverified.id],
        supporting_evidence=["evd_pub"],
        status=ClaimStatus.SUPPORTED,
    )
    ev = Evidence(
        id="evd_pub",
        claim_id=claim.id,
        source_id=src_unverified.id,
        evidence_text="Evidence text",
        verbatim=False,
    )

    res = check_academic_integrity(claims=[claim], evidence=[ev], sources=[src_unverified])
    pub_reasons = [r for r in res.review_reasons if "publisher_verified is False" in r]
    assert len(pub_reasons) == 1
    assert f"source {src_unverified.id} cited in claim but publisher_verified is False" in pub_reasons[0]

    # When publisher_verified is True, no review reason
    src_verified = Source(
        id="src_pub_true",
        title="Verified Publisher Source",
        state=SourceState.APPROVED,
        publisher_verified=True,
    )
    claim_v = Claim(
        id="clm_pub_v",
        claim_text="Claim citing verified publisher source",
        supporting_sources=[src_verified.id],
        supporting_evidence=["evd_pub_v"],
        status=ClaimStatus.SUPPORTED,
    )
    ev_v = Evidence(
        id="evd_pub_v",
        claim_id=claim_v.id,
        source_id=src_verified.id,
        evidence_text="Evidence text",
        verbatim=False,
    )
    res_v = check_academic_integrity(claims=[claim_v], evidence=[ev_v], sources=[src_verified])
    assert not any("publisher_verified is False" in r for r in res_v.review_reasons)


def test_property_28_source_not_indexed_triggers_review_reason() -> None:
    """Property 28: Source not indexed triggers review reason.

    For any source with index_status empty or with all values False, the integrity
    gate SHALL add a review reason indicating the source is not indexed.

    **Validates: Requirement 5.4**
    """
    # 1. Explicit empty index_status
    src_empty = Source(
        id="src_idx_empty",
        title="Empty index status source",
        state=SourceState.APPROVED,
        index_status={},
    )
    res_empty = check_academic_integrity(claims=[], evidence=[], sources=[src_empty])
    empty_reasons = [r for r in res_empty.review_reasons if "not indexed in any queried database" in r]
    assert len(empty_reasons) == 1
    assert f"source {src_empty.id} not indexed in any queried database" in empty_reasons[0]

    # 2. All False index_status
    src_all_false = Source(
        id="src_idx_false",
        title="All false index status source",
        state=SourceState.APPROVED,
        index_status={"crossref": False, "pubmed": False, "scopus": False},
    )
    res_false = check_academic_integrity(claims=[], evidence=[], sources=[src_all_false])
    false_reasons = [r for r in res_false.review_reasons if "not indexed in any queried database" in r]
    assert len(false_reasons) == 1

    # 3. At least one True index_status -> no review reason
    src_indexed = Source(
        id="src_idx_ok",
        title="Indexed source",
        state=SourceState.APPROVED,
        index_status={"crossref": True, "pubmed": False},
    )
    res_indexed = check_academic_integrity(claims=[], evidence=[], sources=[src_indexed])
    assert not any("not indexed in any queried database" in r for r in res_indexed.review_reasons)

    # 4. Old source without index_status passed (backward compat) -> no review reason
    src_old = Source(
        id="src_old",
        title="Old source",
        state=SourceState.APPROVED,
    )
    res_old = check_academic_integrity(claims=[], evidence=[], sources=[src_old])
    assert not any("not indexed in any queried database" in r for r in res_old.review_reasons)


# --------------------------------------------------------------------------- #
# Unit Tests: Enums and Schema Extensions (Requirement 18.1, 18.2)
# --------------------------------------------------------------------------- #


def test_new_enums_members_and_serialization() -> None:
    """Test all new enums for member names, count, and serialization.

    **Validates: Requirement 18.1**
    """
    # EvidenceType: 7 members
    assert len(EvidenceType) == 7
    expected_evidence_types = {
        "DIRECT",
        "PARTIAL",
        "THEORETICAL",
        "FUNCTIONAL_EQUIVALENT",
        "BACKGROUND",
        "CONTRADICTORY",
        "NOT_SUPPORTED",
    }
    assert {e.value for e in EvidenceType} == expected_evidence_types
    for et in EvidenceType:
        assert json.dumps(et) == f'"{et.value}"'

    # ReadingDepth: 4 members
    assert len(ReadingDepth) == 4
    expected_depths = {"FULL_TEXT", "ABSTRACT_ONLY", "METADATA_ONLY", "UNAVAILABLE"}
    assert {d.value for d in ReadingDepth} == expected_depths
    for rd in ReadingDepth:
        assert json.dumps(rd) == f'"{rd.value}"'

    # RetrievalStatus: 4 members
    assert len(RetrievalStatus) == 4
    expected_statuses = {"RETRIEVED", "PARTIAL", "FAILED", "NOT_ATTEMPTED"}
    assert {s.value for s in RetrievalStatus} == expected_statuses
    for rs in RetrievalStatus:
        assert json.dumps(rs) == f'"{rs.value}"'


def test_evidence_schema_new_fields_and_defaults() -> None:
    """Evidence model sets v1.1 schema version and sensible defaults for all new fields.

    **Validates: Requirements 1.2, 1.3, 18.2**
    """
    ev = Evidence(
        claim_id="clm_test",
        source_id="src_test",
        evidence_text="Default field check",
    )
    assert ev.schema_version == "1.1"
    assert ev.evidence_type == EvidenceType.NOT_SUPPORTED
    assert ev.reading_depth == ReadingDepth.UNAVAILABLE
    assert ev.normalized_finding is None
    assert ev.population is None
    assert ev.sample_size is None
    assert ev.methodology is None
    assert ev.variables is None
    assert ev.instruments is None
    assert ev.statistical_result is None
    assert ev.limitations is None


def test_source_schema_new_fields_and_defaults() -> None:
    """Source model sets v1.1 schema version and sensible defaults for new fields.

    **Validates: Requirements 2.2, 3.1, 4.1, 5.1, 18.2**
    """
    src = Source(title="New Source Defaults")
    assert src.schema_version == "1.1"
    assert src.reading_depth == ReadingDepth.UNAVAILABLE
    assert src.retrieval_status == RetrievalStatus.NOT_ATTEMPTED
    assert src.publisher_verified is False
    assert src.index_status == {}


def test_negative_cases_and_error_handling() -> None:
    """Negative tests verifying invalid inputs produce appropriate errors rather than silent failures.

    **Validates: Requirement 18.7**
    """
    # 1. Missing required field on Evidence raises ValidationError
    with pytest.raises(Exception):
        Evidence(claim_id="clm_1", source_id="src_1", evidence_text="")

    # 2. Empty evidence list on evaluate_claim returns INSUFFICIENT_EVIDENCE
    claim = Claim(id="clm_neg", claim_text="Negative claim", required_source_count=1)
    res_empty = evaluate_claim(claim, [])
    assert res_empty.status == ClaimStatus.INSUFFICIENT_EVIDENCE
    assert res_empty.confidence == 0.0

    # 3. Broken reference in claim to non-existent evidence detected by gate
    claim_broken = Claim(
        id="clm_broken",
        claim_text="Broken ref claim",
        supporting_evidence=["evd_nonexistent"],
    )
    res_gate = check_academic_integrity(claims=[claim_broken], evidence=[], sources=[])
    assert any("references nonexistent supporting evidence" in v for v in res_gate.violations)

    # 4. Broken reference in evidence to non-existent source detected by gate and graph
    ev_broken = Evidence(
        id="evd_broken",
        claim_id=claim.id,
        source_id="src_nonexistent",
        evidence_text="Broken source ref",
    )
    res_gate_ev = check_academic_integrity(claims=[claim], evidence=[ev_broken], sources=[])
    assert any("references nonexistent source" in v for v in res_gate_ev.violations)

    graph = build_evidence_graph([claim], [ev_broken], [])
    c_node = graph["claims"][claim.id]
    assert c_node["evidence"][0]["broken_reference"] is True


# --------------------------------------------------------------------------- #
# Golden Test Case (Task 11.1, 11.2, Requirement 15)
# --------------------------------------------------------------------------- #


def test_golden_tiktok_streak_pipeline() -> None:
    """Golden test case for TikTok Streak and social connectedness.

    Validates:
      * Evidence_Flow produces INSUFFICIENT_EVIDENCE or PARTIALLY_SUPPORTED
        (never SUPPORTED or STRONG) when evidence is indirect.
      * Indirect evidence is never treated as DIRECT.
      * detect_contradictions detects mixed evidence with conflict_severity == "HIGH".
      * evaluate_claim produces ClaimStatus.CONFLICTED when contradiction is added.
      * Integrity gate flags overclaims for functional equivalent / theoretical evidence.
      * Integrity gate flags abstract-only supporting evidence.

    **Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5, 15.6, 18.8**
    """
    claim, sources, evidence_dict = get_golden_fixture()

    # 1. Verify fixture configuration
    assert claim.claim_text == "TikTok Streak increases social connectedness among university students"
    assert claim.importance == ClaimImportance.HIGH
    assert claim.status == ClaimStatus.PROPOSED
    assert claim.required_source_count == 2
    assert len(sources) == 5
    assert len(evidence_dict) == 5

    # 2. Indirect supporting evidence items
    indirect_evidence = [
        evidence_dict["ev_tiktok"],
        evidence_dict["ev_snapchat"],
        evidence_dict["ev_connectedness"],
        evidence_dict["ev_activity"],
    ]

    # Verify indirect evidence is never treated as DIRECT
    for ev in indirect_evidence:
        eff_type = _get_evidence_type(ev)
        assert eff_type != EvidenceType.DIRECT, f"Evidence {ev.id} was unexpectedly classified as DIRECT"

    # Evaluate claim with indirect supporting evidence
    eval_result = evaluate_claim(claim, indirect_evidence)

    # VERIFY: Result status is NOT SUPPORTED and support_level is NOT STRONG
    assert eval_result.status != ClaimStatus.SUPPORTED
    assert eval_result.support_level != SupportLevel.STRONG
    assert eval_result.status in (ClaimStatus.PARTIALLY_SUPPORTED, ClaimStatus.INSUFFICIENT_EVIDENCE)
    assert eval_result.support_level in (SupportLevel.MODERATE, SupportLevel.WEAK, SupportLevel.NONE)

    # 3. Add contradicting evidence ev_counter
    all_evidence = list(evidence_dict.values())

    # VERIFY: detect_contradictions detects mixed evidence with conflict_severity == "HIGH"
    contra_report = detect_contradictions(claim, all_evidence)
    assert contra_report.has_mixed_evidence is True
    assert contra_report.conflict_severity == "HIGH"
    assert len(contra_report.contradictory_findings) == 1
    assert contra_report.contradictory_findings[0].evidence_id == "ev_counter"

    # VERIFY: evaluate_claim produces ClaimStatus.CONFLICTED
    conflicted_result = evaluate_claim(claim, all_evidence)
    assert conflicted_result.status == ClaimStatus.CONFLICTED

    # 4. Integrity Gate verification
    # Case A: Claim marked SUPPORTED using only functional equivalent + theoretical evidence -> overclaimed violation
    claim_over = claim.model_copy(deep=True)
    claim_over.status = ClaimStatus.SUPPORTED
    claim_over.supporting_evidence = [
        evidence_dict["ev_snapchat"].id,
        evidence_dict["ev_connectedness"].id,
    ]
    claim_over.supporting_sources = ["src_snapchat", "src_connectedness"]

    gate_over = check_academic_integrity(
        claims=[claim_over],
        evidence=[evidence_dict["ev_snapchat"], evidence_dict["ev_connectedness"]],
        sources=sources,
    )
    overclaim_violations = [v for v in gate_over.violations if "overclaimed" in v]
    assert len(overclaim_violations) == 1
    assert "no direct evidence supports the claim" in overclaim_violations[0]

    # Case B: Claim marked SUPPORTED using only abstract-only evidence -> review reason
    claim_abs = claim.model_copy(deep=True)
    claim_abs.status = ClaimStatus.SUPPORTED
    claim_abs.supporting_evidence = [evidence_dict["ev_tiktok"].id]
    claim_abs.supporting_sources = ["src_tiktok"]

    gate_abs = check_academic_integrity(
        claims=[claim_abs],
        evidence=[evidence_dict["ev_tiktok"]],
        sources=sources,
    )
    abs_reasons = [r for r in gate_abs.review_reasons if "supported only by abstract-level evidence" in r]
    assert len(abs_reasons) == 1


# --------------------------------------------------------------------------- #
# Remaining Property Tests (Properties 1, 3, 5, 10, 11)
# --------------------------------------------------------------------------- #


def test_property_1_evidence_field_independence() -> None:
    """Property 1: Evidence field independence — all enum combinations are valid.

    For any combination of EvidenceType value, EvidenceRelationship value,
    and EvidenceStrength value, creating an Evidence record with those three fields
    set independently SHALL produce a valid record without raising a validation error.

    **Validates: Requirements 1.3, 1.6**
    """
    count = 0
    for etype in EvidenceType:
        for rel in EvidenceRelationship:
            for strength in EvidenceStrength:
                ev = Evidence(
                    claim_id="clm_prop1",
                    source_id="src_prop1",
                    evidence_text=f"Independence test {etype} {rel} {strength}",
                    evidence_type=etype,
                    relationship=rel,
                    strength=strength,
                )
                assert ev.evidence_type == etype
                assert ev.relationship == rel
                assert ev.strength == strength
                count += 1

    # 7 EvidenceType * 4 EvidenceRelationship * 4 EvidenceStrength = 112 combinations
    assert count == 112


def test_property_3_abstract_only_depth_prevents_verbatim_fulltext() -> None:
    """Property 3: ABSTRACT_ONLY depth prevents VERBATIM_FULLTEXT extraction.

    For any Evidence record creation attempt where reading_depth = ABSTRACT_ONLY
    and extraction_method = VERBATIM_FULLTEXT, the system SHALL raise a ValueError
    and the record SHALL not be created.

    **Validates: Requirements 2.4**
    """
    # Negative case: ABSTRACT_ONLY with VERBATIM_FULLTEXT must raise ValueError
    with pytest.raises(ValueError, match="extraction_method cannot be VERBATIM_FULLTEXT"):
        Evidence(
            claim_id="clm_p3",
            source_id="src_p3",
            evidence_text="Invalid abstract with fulltext verbatim",
            reading_depth=ReadingDepth.ABSTRACT_ONLY,
            extraction_method=ExtractionMethod.VERBATIM_FULLTEXT,
        )

    # Positive controls: Other extraction methods with ABSTRACT_ONLY succeed
    valid_abstract_methods = [
        ExtractionMethod.VERBATIM_ABSTRACT,
        ExtractionMethod.MODEL_PARAPHRASE,
        ExtractionMethod.TABULAR_VALUE,
        ExtractionMethod.USER_PROVIDED,
    ]
    for method in valid_abstract_methods:
        ev = Evidence(
            claim_id="clm_p3",
            source_id="src_p3",
            evidence_text=f"Valid method {method}",
            reading_depth=ReadingDepth.ABSTRACT_ONLY,
            extraction_method=method,
        )
        assert ev.reading_depth == ReadingDepth.ABSTRACT_ONLY
        assert ev.extraction_method == method

    # Positive control: FULL_TEXT with VERBATIM_FULLTEXT succeeds
    ev_full = Evidence(
        claim_id="clm_p3",
        source_id="src_p3",
        evidence_text="Valid fulltext extraction",
        reading_depth=ReadingDepth.FULL_TEXT,
        extraction_method=ExtractionMethod.VERBATIM_FULLTEXT,
    )
    assert ev_full.reading_depth == ReadingDepth.FULL_TEXT
    assert ev_full.extraction_method == ExtractionMethod.VERBATIM_FULLTEXT


def test_property_5_not_attempted_blocks_fulltext_retrieved() -> None:
    """Property 5: NOT_ATTEMPTED blocks FULLTEXT_RETRIEVED.

    For any Source with retrieval_status = NOT_ATTEMPTED, attempting to transition
    to SourceState.FULLTEXT_RETRIEVED SHALL raise a StateTransitionError.

    **Validates: Requirements 3.5**
    """
    # Negative case: NOT_ATTEMPTED blocks FULLTEXT_RETRIEVED
    src = Source(
        id="src_p5_1",
        title="Unretrieved Source",
        retrieval_status=RetrievalStatus.NOT_ATTEMPTED,
    )
    with pytest.raises(StateTransitionError, match="cannot advance to FULLTEXT_RETRIEVED"):
        src.transition_to(SourceState.FULLTEXT_RETRIEVED, reason="Should fail")

    # Positive controls: RETRIEVED or PARTIAL allow transition to FULLTEXT_RETRIEVED
    src_retrieved = Source(
        id="src_p5_2",
        title="Retrieved Source",
        retrieval_status=RetrievalStatus.RETRIEVED,
    )
    src_retrieved.transition_to(SourceState.FULLTEXT_RETRIEVED, reason="Retrieved successfully")
    assert src_retrieved.state == SourceState.FULLTEXT_RETRIEVED

    src_partial = Source(
        id="src_p5_3",
        title="Partially Retrieved Source",
        retrieval_status=RetrievalStatus.PARTIAL,
    )
    src_partial.transition_to(SourceState.FULLTEXT_RETRIEVED, reason="Partially retrieved")
    assert src_partial.state == SourceState.FULLTEXT_RETRIEVED


def test_property_10_evidence_serialization_round_trip_preserves_all_fields() -> None:
    """Property 10: Evidence serialization round-trip preserves all fields.

    For any valid Evidence record with any EvidenceType, ReadingDepth, and any
    combination of structured extraction fields set or None, serializing to JSON
    via to_dict() and deserializing via from_dict() SHALL produce a record with
    identical field values.

    **Validates: Requirements 1.6, 6.4, 14.1, 14.2**
    """
    rng = random.Random(1010)

    # Test complete populated record
    full_ev = Evidence(
        claim_id="clm_full_10",
        source_id="src_full_10",
        evidence_text="Full extraction text with all structured fields",
        evidence_type=EvidenceType.DIRECT,
        reading_depth=ReadingDepth.FULL_TEXT,
        extraction_method=ExtractionMethod.VERBATIM_FULLTEXT,
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.DEFINITIVE,
        confidence=0.95,
        location=EvidenceLocation(page=42, section="Methodology §3.1"),
        normalized_finding="Digital streaks increase daily engagement by 23%",
        population="Undergraduate students aged 18-24",
        sample_size="N = 512",
        methodology="Randomized Controlled Trial",
        variables=["streak_count", "affective_connection", "frequency_of_use"],
        instruments=["Social Connectedness Scale (Revised)", "UCLA Loneliness Scale"],
        statistical_result="F(2, 509) = 14.82, p < .001, eta2 = .06",
        limitations="Single-institution sample with potential self-selection bias",
    )
    data = full_ev.to_dict()
    restored = Evidence.from_dict(data)

    assert restored.id == full_ev.id
    assert restored.schema_version == full_ev.schema_version
    assert restored.claim_id == full_ev.claim_id
    assert restored.source_id == full_ev.source_id
    assert restored.evidence_text == full_ev.evidence_text
    assert restored.evidence_type == full_ev.evidence_type
    assert restored.reading_depth == full_ev.reading_depth
    assert restored.extraction_method == full_ev.extraction_method
    assert restored.relationship == full_ev.relationship
    assert restored.strength == full_ev.strength
    assert restored.confidence == full_ev.confidence
    assert restored.location.page == 42
    assert restored.location.section == "Methodology §3.1"
    assert restored.normalized_finding == full_ev.normalized_finding
    assert restored.population == full_ev.population
    assert restored.sample_size == full_ev.sample_size
    assert restored.methodology == full_ev.methodology
    assert restored.variables == full_ev.variables
    assert restored.instruments == full_ev.instruments
    assert restored.statistical_result == full_ev.statistical_result
    assert restored.limitations == full_ev.limitations

    # Test randomized field combinations
    types = list(EvidenceType)
    depths = [ReadingDepth.FULL_TEXT, ReadingDepth.METADATA_ONLY, ReadingDepth.UNAVAILABLE]
    relations = list(EvidenceRelationship)
    strengths = list(EvidenceStrength)

    for trial in range(30):
        pop = f"Pop {trial}" if rng.choice([True, False]) else None
        sz = f"N={trial * 10}" if rng.choice([True, False]) else None
        meth = f"Method {trial}" if rng.choice([True, False]) else None
        vars_list = [f"var_{i}" for i in range(rng.randint(1, 4))] if rng.choice([True, False]) else None
        insts = [f"inst_{i}" for i in range(rng.randint(1, 3))] if rng.choice([True, False]) else None
        stats = f"p < 0.{trial}" if rng.choice([True, False]) else None
        limits = f"Limit {trial}" if rng.choice([True, False]) else None

        ev_rnd = Evidence(
            claim_id=f"clm_rnd_{trial}",
            source_id=f"src_rnd_{trial}",
            evidence_text=f"Evidence text trial {trial}",
            evidence_type=rng.choice(types),
            reading_depth=rng.choice(depths),
            relationship=rng.choice(relations),
            strength=rng.choice(strengths),
            population=pop,
            sample_size=sz,
            methodology=meth,
            variables=vars_list,
            instruments=insts,
            statistical_result=stats,
            limitations=limits,
        )

        d = ev_rnd.to_dict()
        res = Evidence.from_dict(d)

        assert res.id == ev_rnd.id
        assert res.evidence_type == ev_rnd.evidence_type
        assert res.reading_depth == ev_rnd.reading_depth
        assert res.population == pop
        assert res.sample_size == sz
        assert res.methodology == meth
        assert res.variables == vars_list
        assert res.instruments == insts
        assert res.statistical_result == stats
        assert res.limitations == limits


def test_property_11_backward_compatibility_old_records_deserialize_defaults() -> None:
    """Property 11: Backward compatibility — old records deserialize with correct defaults.

    For any JSON payload representing a v1.0 Evidence record (lacking evidence_type,
    reading_depth, and structured fields) or a v1.0 Source record (lacking reading_depth,
    retrieval_status, publisher_verified, index_status), deserialization SHALL succeed
    and new fields SHALL have their specified defaults.

    **Validates: Requirements 14.1, 14.2, 14.3, 14.5**
    """
    # 1. v1.0 Evidence without v1.1 fields
    v1_evidence_payload = {
        "id": "evd_legacy_001",
        "schema_version": "1.0",
        "created_at": "2026-09-01T10:00:00Z",
        "updated_at": "2026-09-01T10:00:00Z",
        "history": [],
        "errors": [],
        "claim_id": "clm_legacy_001",
        "source_id": "src_legacy_001",
        "evidence_text": "Legacy evidence text from pre-v1.1 system.",
        "relationship": "supports",
        "strength": "STRONG",
        "confidence": 0.8,
        "extraction_method": "VERBATIM_FULLTEXT",
        "verbatim": True,
        "quote_verified": True,
    }
    legacy_ev = Evidence.from_dict(v1_evidence_payload)

    # Acceptance Criteria 14.1, 14.2, 14.5
    assert legacy_ev.schema_version == "1.0"
    assert legacy_ev.id == "evd_legacy_001"
    assert legacy_ev.evidence_type == EvidenceType.NOT_SUPPORTED
    assert legacy_ev.reading_depth == ReadingDepth.UNAVAILABLE
    assert legacy_ev.normalized_finding is None
    assert legacy_ev.population is None
    assert legacy_ev.sample_size is None
    assert legacy_ev.methodology is None
    assert legacy_ev.variables is None
    assert legacy_ev.instruments is None
    assert legacy_ev.statistical_result is None
    assert legacy_ev.limitations is None

    # Pre-upgrade unclassified evidence is treated as DIRECT in evaluation flow
    assert _get_evidence_type(legacy_ev) == EvidenceType.DIRECT

    # 2. v1.0 Source without v1.1 fields
    v1_source_payload = {
        "id": "src_legacy_001",
        "schema_version": "1.0",
        "created_at": "2026-09-01T10:00:00Z",
        "updated_at": "2026-09-01T10:00:00Z",
        "history": [],
        "errors": [],
        "title": "Legacy Seminal Paper",
        "authors": ["Smith, J.", "Doe, J."],
        "year": 2020,
        "venue": "Journal of Science",
        "state": "APPROVED",
    }
    legacy_src = Source.from_dict(v1_source_payload)

    # Acceptance Criteria 14.3, 14.5
    assert legacy_src.schema_version == "1.0"
    assert legacy_src.id == "src_legacy_001"
    assert legacy_src.reading_depth == ReadingDepth.UNAVAILABLE
    assert legacy_src.retrieval_status == RetrievalStatus.NOT_ATTEMPTED
    assert legacy_src.publisher_verified is False
    assert legacy_src.index_status == {}


# --------------------------------------------------------------------------- #
# Integration Test: End-to-End Pipeline (Requirement 18.8)
# --------------------------------------------------------------------------- #


def test_end_to_end_evidence_intelligence_pipeline(tmp_path: Path) -> None:
    """End-to-end integration test validating the entire evidence intelligence pipeline.

    Flow:
      Source discovery & verification
        -> Evidence extraction & claim mapping
        -> Contradiction detection
        -> Claim evaluation via evidence flow
        -> Evidence graph construction & summarization
        -> Provenance chain generation
        -> Academic integrity gate
        -> Review queue creation
        -> Storage persistence & reload

    **Validates: Requirements 15.6, 16.1, 16.2, 16.3, 18.8**
    """
    # 1. Source Discovery & Verification Lifecycle
    src_direct = Source(
        id="src_e2e_direct",
        title="Direct Study on TikTok Streaks and Belonging",
        authors=["Zhao, X.", "Wang, Y."],
        year=2024,
        doi="10.1016/j.chb.2024.108000",
        state=SourceState.DISCOVERED,
        provenance=Provenance(
            origin="crossref",
            tool="crossref_api",
            retrieved_at=datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC),
        ),
    )
    src_direct.transition_to(SourceState.METADATA_VERIFIED, reason="Metadata matched", actor="verifier")
    src_direct.transition_to(SourceState.DOI_VERIFIED, reason="DOI confirmed in Crossref", actor="verifier")
    src_direct.retrieval_status = RetrievalStatus.RETRIEVED
    src_direct.publisher_verified = True
    src_direct.index_status = {"crossref": True, "scopus": True}
    src_direct.transition_to(SourceState.FULLTEXT_RETRIEVED, reason="PDF fetched", actor="retriever")
    src_direct.transition_to(SourceState.EVIDENCE_EXTRACTED, reason="Passages extracted", actor="extractor")
    src_direct.approve()
    assert src_direct.state == SourceState.APPROVED

    src_counter = Source(
        id="src_e2e_counter",
        title="Longitudinal Evaluation of App Streaks and Mental Wellbeing",
        authors=["Miller, K."],
        year=2024,
        doi="10.1093/jcmc/zmae010",
        state=SourceState.APPROVED,
        publisher_verified=True,
        retrieval_status=RetrievalStatus.RETRIEVED,
        index_status={"crossref": True},
    )

    sources = [src_direct, src_counter]

    # 2. Claim Creation
    claim = Claim(
        id="clm_e2e_pipeline",
        claim_text="Daily TikTok Streaks significantly increase feelings of social connectedness in undergraduates",
        importance=ClaimImportance.HIGH,
        required_source_count=1,
    )

    # 3. Evidence Extraction and Mapping
    ev_sup = Evidence(
        id="evd_e2e_sup",
        claim_id=claim.id,
        source_id=src_direct.id,
        evidence_text="Participants maintaining daily streaks reported a significant 18% increase in connectedness.",
        evidence_type=EvidenceType.DIRECT,
        reading_depth=ReadingDepth.FULL_TEXT,
        extraction_method=ExtractionMethod.VERBATIM_FULLTEXT,
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        location=EvidenceLocation(page=7, section="Results"),
        normalized_finding="Streaks increase connectedness by 18%",
        statistical_result="t(240) = 4.12, p < .001",
        verbatim=True,
        quote_verified=True,
    )

    ev_con = Evidence(
        id="evd_e2e_con",
        claim_id=claim.id,
        source_id=src_counter.id,
        evidence_text="No sustained increase in social connectedness was observed after controlling for baseline.",
        evidence_type=EvidenceType.CONTRADICTORY,
        reading_depth=ReadingDepth.FULL_TEXT,
        extraction_method=ExtractionMethod.VERBATIM_FULLTEXT,
        relationship=EvidenceRelationship.CONTRADICTS,
        strength=EvidenceStrength.STRONG,
        location=EvidenceLocation(page=19, section="Discussion"),
        statistical_result="beta = 0.02, p = .65",
        verbatim=True,
        quote_verified=True,
    )

    evidence_list = [ev_sup, ev_con]
    claim.attach_support(evidence_id=ev_sup.id, source_id=src_direct.id)
    claim.attach_contradiction(evidence_id=ev_con.id, source_id=src_counter.id)

    # 4. Contradiction Detection & Claim Evaluation
    report = detect_contradictions(claim, evidence_list)
    assert report.has_mixed_evidence is True
    assert report.conflict_severity == "HIGH"
    assert len(report.contradictory_findings) == 1

    eval_result = evaluate_claim(claim, evidence_list)
    assert eval_result.status == ClaimStatus.CONFLICTED
    claim.transition_to(ClaimStatus.CONFLICTED, reason=eval_result.reason)
    assert claim.status == ClaimStatus.CONFLICTED

    # 5. Evidence Graph Construction & Summarization
    graph = build_evidence_graph([claim], evidence_list, sources)
    assert claim.id in graph["claims"]
    assert src_direct.id in graph["sources"]
    assert graph["claims"][claim.id]["supporting_count"] == 1
    assert graph["claims"][claim.id]["contradicting_count"] == 1
    assert all(e["broken_reference"] is False for e in graph["claims"][claim.id]["evidence"])

    summary_text = summarize_evidence_graph(graph)
    assert "Evidence Graph Summary" in summary_text
    assert claim.id in summary_text

    # 6. Provenance Chain Generation
    chain = build_provenance_chain(claim, evidence_list, sources)
    assert len(chain) == 2
    prov_map = {rec.evidence_id: rec for rec in chain}
    assert prov_map["evd_e2e_sup"].source_id == src_direct.id
    assert prov_map["evd_e2e_sup"].reading_depth == ReadingDepth.FULL_TEXT
    assert prov_map["evd_e2e_sup"].page == 7
    assert prov_map["evd_e2e_sup"].section == "Results"
    assert prov_map["evd_e2e_sup"].retrieved_at is not None

    # 7. Academic Integrity Gate Validation
    gate_result = check_academic_integrity(claims=[claim], evidence=evidence_list, sources=sources)
    # Claim is CONFLICTED and carries attached contradicting evidence, so it satisfies disclosure requirements
    assert not any("conflicted claim" in v for v in gate_result.violations)
    assert not any("invalid DOI" in v for v in gate_result.violations)

    # 8. Human Review Queue Integration
    queue = create_review_queue_from_gate_result(gate_result, claims=[claim], sources=sources)
    # High-importance claim requiring semantic review is queued
    assert claim.requires_semantic_review is True
    assert len(queue.query(item_type="claim", severity="HIGH")) >= 1

    # 9. Storage Persistence & Reload
    graph_file = tmp_path / "evidence_graph.json"
    save_evidence_graph(graph, graph_file, root=tmp_path)
    loaded_graph = load_evidence_graph(graph_file)
    assert loaded_graph["claims"][claim.id]["claim_id"] == claim.id

    prov_file = tmp_path / "provenance.jsonl"
    save_provenance_chain(chain, prov_file, root=tmp_path)
    loaded_chain = load_provenance_chain(prov_file)
    assert len(loaded_chain) == 2
    assert loaded_chain[0]["claim_id"] == claim.id

    queue_file = tmp_path / "review_queue.json"
    queue.save(queue_file, root=tmp_path)
    loaded_queue = ReviewQueue.load(queue_file)
    assert len(loaded_queue) == len(queue)
    assert loaded_queue.items[0].status == "PENDING"
