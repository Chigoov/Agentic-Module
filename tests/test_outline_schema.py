"""Fast, network-free tests for the Outline schema (Phase 6)."""

from __future__ import annotations

import pytest

from src.core.errors import StateTransitionError
from src.schemas.outline import Outline, OutlineSection, OutlineStatus


def test_outline_section_defaults() -> None:
    section = OutlineSection(title="Pendahuluan")
    assert section.level == 1
    assert section.claim_ids == []
    assert section.subsections == []
    assert section.order == 0


def test_outline_rejects_duplicate_claim_ids() -> None:
    section = OutlineSection(title="X", claim_ids=["c1", "c2"])
    other = OutlineSection(title="Y", claim_ids=["c2"])
    with pytest.raises(ValueError):
        Outline(title="T", sections=[section, other])


def test_outline_claim_ids_walks_nested() -> None:
    inner = OutlineSection(title="Sub", claim_ids=["c2"])
    outer = OutlineSection(title="Top", claim_ids=["c1"], subsections=[inner])
    outline = Outline(title="T", sections=[outer])
    assert outline.claim_ids == ["c1", "c2"]


def test_outline_transition_records_history() -> None:
    outline = Outline(title="T")
    outline.transition_to(OutlineStatus.APPROVED, reason="ok", actor="test")
    assert outline.status is OutlineStatus.APPROVED
    assert outline.history[-1].to_state == "APPROVED"


def test_outline_same_status_transition_rejected() -> None:
    outline = Outline(title="T")
    with pytest.raises(StateTransitionError):
        outline.transition_to(OutlineStatus.DRAFT, reason="noop")
