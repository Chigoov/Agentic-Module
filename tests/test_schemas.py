"""Tests for schema validation, state transitions, and serialization."""

import json

import pytest

from src.core.errors import StateTransitionError
from src.schemas.base import BaseRecord, new_id, utc_now
from src.schemas.claim import Claim, ClaimImportance, ClaimStatus
from src.schemas.evidence import Evidence, EvidenceRelationship, EvidenceStrength, ReadingDepth
from src.schemas.source import RetrievalStatus, Source, SourceState, SourceType
from src.schemas.task import ResearchMode, Task, TaskState


def test_new_id_format() -> None:
    """IDs have the expected prefix_timestamp_hex format."""
    record_id = new_id("test")
    parts = record_id.split("_")
    assert len(parts) == 3
    assert parts[0] == "test"
    assert len(parts[1]) == 15  # YYYYMMDDTHHmmss
    assert len(parts[2]) == 8  # 8 hex chars


def test_base_record_auto_id() -> None:
    """BaseRecord assigns an ID automatically when not supplied."""
    record = BaseRecord()
    assert record.id.startswith("rec_")
    assert record.schema_version == "1.0"
    assert record.created_at <= utc_now()


def test_base_record_touch() -> None:
    """touch() refreshes updated_at."""
    record = BaseRecord()
    original_updated = record.updated_at
    record.touch()
    assert record.updated_at > original_updated


def test_base_record_transition() -> None:
    """record_transition() appends to history and refreshes updated_at."""
    record = BaseRecord()
    original_updated = record.updated_at
    trans = record.record_transition(
        from_state="A", to_state="B", reason="test transition", actor="test"
    )
    assert len(record.history) == 1
    assert record.history[0] == trans
    assert trans.from_state == "A"
    assert trans.to_state == "B"
    assert trans.reason == "test transition"
    assert trans.actor == "test"
    assert record.updated_at > original_updated


def test_base_record_error() -> None:
    """record_error() appends to errors list."""
    record = BaseRecord()
    err = record.record_error(code="TEST_ERROR", message="test error", foo="bar")
    assert len(record.errors) == 1
    assert record.errors[0] == err
    assert err.code == "TEST_ERROR"
    assert err.message == "test error"
    assert err.context["foo"] == "bar"


# --------------------------------------------------------------------------- #
# Task state transitions
# --------------------------------------------------------------------------- #
def test_task_creation() -> None:
    """Task is created in CREATED state."""
    task = Task(user_request="test request", workspace="TUGAS 1", project_dir="/tmp/test")
    assert task.state is TaskState.CREATED
    assert task.mode is ResearchMode.ACADEMIC_WRITING
    assert task.id.startswith("task_")


def test_task_transition_valid() -> None:
    """Transitioning to a new state records history."""
    task = Task(user_request="test", workspace="TUGAS 1", project_dir="/tmp/test")
    task.transition_to(TaskState.PLANNED, reason="plan ready", actor="test")
    assert task.state is TaskState.PLANNED
    assert len(task.history) == 1
    assert task.history[0].to_state == "PLANNED"


def test_task_transition_same_state_rejected() -> None:
    """Transitioning to the same state raises StateTransitionError."""
    task = Task(user_request="test", workspace="TUGAS 1", project_dir="/tmp/test")
    with pytest.raises(StateTransitionError, match="already in state"):
        task.transition_to(TaskState.CREATED, reason="no-op", actor="test")


def test_task_mark_completed() -> None:
    """mark_completed() convenience method works."""
    task = Task(user_request="test", workspace="TUGAS 1", project_dir="/tmp/test")
    task.mark_completed()
    assert task.state is TaskState.COMPLETED


def test_task_mark_failed() -> None:
    """mark_failed() transitions to FAILED and attaches an error."""
    task = Task(user_request="test", workspace="TUGAS 1", project_dir="/tmp/test")
    task.mark_failed(reason="test failure")
    assert task.state is TaskState.FAILED
    assert len(task.errors) == 1
    assert task.errors[0].code == "TASK_FAILED"


# --------------------------------------------------------------------------- #
# Source state transitions
# --------------------------------------------------------------------------- #
def test_source_creation() -> None:
    """Source is created in DISCOVERED state."""
    src = Source(title="Test Paper", authors=["Author A"], year=2023)
    assert src.state is SourceState.DISCOVERED
    assert src.source_type is SourceType.OTHER
    assert src.id.startswith("src_")


def test_source_approve() -> None:
    """approve() transitions to APPROVED."""
    src = Source(title="Test", authors=["A"], year=2023)
    src.approve(reason="verified")
    assert src.state is SourceState.APPROVED


def test_source_reject() -> None:
    """reject() transitions to REJECTED."""
    src = Source(title="Test", authors=["A"], year=2023)
    src.reject(reason="unreliable")
    assert src.state is SourceState.REJECTED


def test_source_is_foundational() -> None:
    """is_foundational() checks year and type."""
    old_src = Source(title="Old", authors=["A"], year=1990, source_type=SourceType.BOOK)
    recent_src = Source(title="Recent", authors=["B"], year=2023)
    # With a threshold of 2023, anything before 2013 (2023 - 10) is foundational
    assert old_src.is_foundational(recent_year_threshold=2023) is True
    assert recent_src.is_foundational(recent_year_threshold=2023) is False


def test_retrieval_status_enum_members() -> None:
    """RetrievalStatus has exactly the four expected members."""
    expected = {"RETRIEVED", "PARTIAL", "FAILED", "NOT_ATTEMPTED"}
    assert {m.value for m in RetrievalStatus} == expected


def test_source_schema_v1_1_defaults() -> None:
    """Source initializes with schema v1.1 defaults."""
    src = Source(title="Test Paper", authors=["Author A"], year=2023)
    assert src.schema_version == "1.1"
    assert src.reading_depth is ReadingDepth.UNAVAILABLE
    assert src.retrieval_status is RetrievalStatus.NOT_ATTEMPTED
    assert src.publisher_verified is False
    assert src.index_status == {}


def test_source_update_reading_depth() -> None:
    """update_reading_depth() records a state transition in history."""
    src = Source(title="Test", authors=["A"], year=2023)
    src.update_reading_depth(
        ReadingDepth.FULL_TEXT, reason="retrieved and analyzed", actor="test_actor"
    )
    assert src.reading_depth is ReadingDepth.FULL_TEXT
    assert len(src.history) == 1
    trans = src.history[0]
    assert trans.from_state == "UNAVAILABLE"
    assert trans.to_state == "FULL_TEXT"
    assert trans.reason == "retrieved and analyzed"
    assert trans.actor == "test_actor"


def test_source_transition_to_fulltext_retrieved_guard() -> None:
    """transition_to(FULLTEXT_RETRIEVED) requires retrieval_status != NOT_ATTEMPTED."""
    src = Source(title="Test", authors=["A"], year=2023)
    assert src.retrieval_status is RetrievalStatus.NOT_ATTEMPTED

    with pytest.raises(StateTransitionError, match="cannot advance to FULLTEXT_RETRIEVED"):
        src.transition_to(SourceState.FULLTEXT_RETRIEVED, reason="advance attempt")

    # When retrieval_status is RETRIEVED, transition succeeds
    src.retrieval_status = RetrievalStatus.RETRIEVED
    src.transition_to(SourceState.FULLTEXT_RETRIEVED, reason="retrieval succeeded")
    assert src.state is SourceState.FULLTEXT_RETRIEVED


def test_source_backward_compatibility_v1_0() -> None:
    """Source deserializes v1.0 data cleanly with defaults for new fields."""
    legacy_dict = {
        "id": "src_20260101T000000_11223344",
        "schema_version": "1.0",
        "title": "Legacy Title",
        "authors": ["Old Author"],
        "year": 2021,
    }
    restored = Source.from_dict(legacy_dict)
    assert restored.id == "src_20260101T000000_11223344"
    assert restored.schema_version == "1.0"
    assert restored.reading_depth is ReadingDepth.UNAVAILABLE
    assert restored.retrieval_status is RetrievalStatus.NOT_ATTEMPTED
    assert restored.publisher_verified is False
    assert restored.index_status == {}


def test_source_serialization_with_new_fields() -> None:
    """Source serializes and deserializes all new v1.1 fields intact."""
    src = Source(
        title="Modern Study",
        authors=["Modern Researcher"],
        year=2024,
        reading_depth=ReadingDepth.FULL_TEXT,
        retrieval_status=RetrievalStatus.RETRIEVED,
        publisher_verified=True,
        index_status={"crossref": True, "scopus": False},
    )
    data = src.to_dict()
    assert data["schema_version"] == "1.1"
    assert data["reading_depth"] == "FULL_TEXT"
    assert data["retrieval_status"] == "RETRIEVED"
    assert data["publisher_verified"] is True
    assert data["index_status"] == {"crossref": True, "scopus": False}

    restored = Source.from_dict(data)
    assert restored.reading_depth is ReadingDepth.FULL_TEXT
    assert restored.retrieval_status is RetrievalStatus.RETRIEVED
    assert restored.publisher_verified is True
    assert restored.index_status == {"crossref": True, "scopus": False}


# --------------------------------------------------------------------------- #
# Claim state and evidence linkage
# --------------------------------------------------------------------------- #
def test_claim_creation() -> None:
    """Claim starts PROPOSED with no supporting evidence."""
    claim = Claim(claim_text="Test claim")
    assert claim.status is ClaimStatus.PROPOSED
    assert claim.importance is ClaimImportance.MEDIUM
    assert claim.supporting_evidence == []
    assert claim.id.startswith("clm_")


def test_claim_attach_support() -> None:
    """attach_support() adds evidence without duplicates."""
    claim = Claim(claim_text="Test")
    claim.attach_support(evidence_id="evd_001", source_id="src_001")
    claim.attach_support(evidence_id="evd_001", source_id="src_001")  # duplicate
    assert len(claim.supporting_evidence) == 1
    assert len(claim.supporting_sources) == 1


def test_claim_cannot_mark_supported_without_evidence() -> None:
    """Transitioning to SUPPORTED without evidence raises StateTransitionError."""
    claim = Claim(claim_text="Important claim", importance=ClaimImportance.HIGH)
    with pytest.raises(StateTransitionError, match="without supporting evidence"):
        claim.transition_to(ClaimStatus.SUPPORTED, reason="test")


def test_claim_cannot_mark_supported_with_contradictions() -> None:
    """Marking SUPPORTED when contradictions exist raises StateTransitionError."""
    claim = Claim(claim_text="Test")
    claim.attach_support(evidence_id="evd_001")
    claim.attach_contradiction(evidence_id="evd_002")
    with pytest.raises(StateTransitionError, match="contradicting evidence"):
        claim.transition_to(ClaimStatus.SUPPORTED, reason="test")


def test_claim_mark_insufficient() -> None:
    """mark_insufficient() transitions to INSUFFICIENT_EVIDENCE."""
    claim = Claim(claim_text="Test", importance=ClaimImportance.HIGH)
    claim.mark_insufficient(reason="searched but found nothing")
    assert claim.status is ClaimStatus.INSUFFICIENT_EVIDENCE


# --------------------------------------------------------------------------- #
# Evidence and quote verification
# --------------------------------------------------------------------------- #
def test_evidence_creation() -> None:
    """Evidence record captures claim/source linkage and location."""
    evd = Evidence(
        claim_id="clm_001",
        source_id="src_001",
        evidence_text="According to the study...",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
    )
    assert evd.id.startswith("evd_")
    assert evd.verbatim is True
    assert evd.quote_verified is False


def test_evidence_mark_quote_verified_success() -> None:
    """mark_quote_verified() succeeds when text is found verbatim."""
    evd = Evidence(
        claim_id="clm_001",
        source_id="src_001",
        evidence_text="exact passage",
    )
    haystack = "This document contains the exact passage we are looking for."
    found = evd.mark_quote_verified(haystack=haystack, actor="test")
    assert found is True
    assert evd.quote_verified is True


def test_evidence_mark_quote_verified_failure() -> None:
    """mark_quote_verified() fails and attaches an error when text is not found."""
    evd = Evidence(
        claim_id="clm_001",
        source_id="src_001",
        evidence_text="missing passage",
    )
    haystack = "This document does not contain that text."
    found = evd.mark_quote_verified(haystack=haystack, actor="test")
    assert found is False
    assert evd.quote_verified is False
    assert len(evd.errors) == 1
    assert evd.errors[0].code == "QUOTE_NOT_FOUND"


def test_evidence_max_claim_strength() -> None:
    """max_claim_strength() degrades for partial support."""
    strong_full = Evidence(
        claim_id="clm_001",
        source_id="src_001",
        evidence_text="test",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
    )
    assert strong_full.max_claim_strength() is EvidenceStrength.STRONG

    strong_partial = Evidence(
        claim_id="clm_001",
        source_id="src_001",
        evidence_text="test",
        relationship=EvidenceRelationship.PARTIALLY_SUPPORTS,
        strength=EvidenceStrength.STRONG,
    )
    assert strong_partial.max_claim_strength() is EvidenceStrength.MODERATE


# --------------------------------------------------------------------------- #
# Serialization round-trip
# --------------------------------------------------------------------------- #
def test_task_serialization_round_trip() -> None:
    """Task serializes to JSON and deserializes cleanly."""
    task = Task(user_request="test", workspace="TUGAS 1", project_dir="/tmp/test")
    task.transition_to(TaskState.PLANNED, reason="test", actor="test")
    json_str = task.model_dump_json()
    data = json.loads(json_str)
    restored = Task.from_dict(data)
    assert restored.id == task.id
    assert restored.state is TaskState.PLANNED
    assert len(restored.history) == 1


def test_source_serialization_round_trip() -> None:
    """Source serializes and deserializes with all fields intact."""
    src = Source(title="Test", authors=["A", "B"], year=2023, doi="10.1234/test")
    src.approve(reason="verified")
    json_str = src.model_dump_json()
    data = json.loads(json_str)
    restored = Source.from_dict(data)
    assert restored.id == src.id
    assert restored.state is SourceState.APPROVED
    assert restored.doi == "10.1234/test"
