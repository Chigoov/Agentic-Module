"""Fast, network-free tests for the WritingFlow transition tables (Phase 6)."""

from __future__ import annotations

import pytest

from src.core.errors import StateTransitionError
from src.schemas.outline import Outline, OutlineStatus
from src.workflows.writing_flow import (
    LEGAL_OUTLINE_TRANSITIONS,
    LEGAL_WRITING_TRANSITIONS,
    WritingStage,
    apply_outline_result,
    is_legal_outline_transition,
    is_legal_writing_transition,
)


def test_outline_draft_to_approved_is_legal() -> None:
    assert is_legal_outline_transition(OutlineStatus.DRAFT, OutlineStatus.APPROVED)


def test_outline_draft_to_revised_is_legal() -> None:
    assert is_legal_outline_transition(OutlineStatus.DRAFT, OutlineStatus.REVISED)


def test_outline_approved_cannot_roll_back_to_draft() -> None:
    assert not is_legal_outline_transition(OutlineStatus.APPROVED, OutlineStatus.DRAFT)


def test_outline_same_status_is_not_a_transition() -> None:
    assert not is_legal_outline_transition(OutlineStatus.DRAFT, OutlineStatus.DRAFT)


def test_writing_pipeline_is_forward_only() -> None:
    assert is_legal_writing_transition(WritingStage.OUTLINE_DRAFT, WritingStage.OUTLINE_APPROVED)
    assert is_legal_writing_transition(WritingStage.OUTLINE_APPROVED, WritingStage.DRAFT_WRITTEN)
    assert is_legal_writing_transition(WritingStage.DRAFT_WRITTEN, WritingStage.DRAFT_AUDITED)
    assert not is_legal_writing_transition(WritingStage.DRAFT_AUDITED, WritingStage.DRAFT_WRITTEN)
    assert LEGAL_WRITING_TRANSITIONS[WritingStage.DRAFT_AUDITED] == frozenset()


def test_apply_outline_result_applies_legal_move() -> None:
    outline = Outline(title="T")
    status = apply_outline_result(
        outline, OutlineStatus.APPROVED, reason="approved", actor="test"
    )
    assert status is OutlineStatus.APPROVED
    assert outline.status is OutlineStatus.APPROVED
    assert outline.history[-1].to_state == "APPROVED"


def test_apply_outline_result_rejects_illegal_move() -> None:
    outline = Outline(title="T")
    outline.transition_to(OutlineStatus.APPROVED, reason="ok")
    with pytest.raises(StateTransitionError):
        apply_outline_result(outline, OutlineStatus.DRAFT, reason="rollback")


def test_legal_outline_transition_table_shape() -> None:
    assert LEGAL_OUTLINE_TRANSITIONS[OutlineStatus.DRAFT] == frozenset(
        {OutlineStatus.APPROVED, OutlineStatus.REVISED}
    )
