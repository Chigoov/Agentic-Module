"""Fast, network-free tests for the Phase 4 verification engine.

These tests exercise the pure, deterministic parts of the verification layer
(schema aggregation, title matching, legal transitions, and the engine's
decision logic with injected fake providers). They never touch the network.
"""

from __future__ import annotations

import pytest

from src.schemas.source import Source, SourceState
from src.schemas.verification import (
    VerificationCheck,
    VerificationCheckStatus,
    VerificationLevel,
    VerificationReport,
)
from src.tools.source_mapper import best_title_match
from src.tools.verification_tool import VerificationEngine
from src.workflows.verification_flow import apply_verification_result, is_legal_transition


# --------------------------------------------------------------------------- #
# best_title_match
# --------------------------------------------------------------------------- #
def test_best_title_match_exact() -> None:
    title, ratio = best_title_match(
        "Deep Learning for Medical Imaging",
        ["A Survey of CNNs", "Deep Learning for Medical Imaging", "Other Work"],
    )
    assert title == "Deep Learning for Medical Imaging"
    assert ratio == 1.0


def test_best_title_match_case_punctuation_insensitive() -> None:
    title, ratio = best_title_match(
        "Deep Learning for Medical Imaging.",
        ["deep learning for medical imaging"],
    )
    assert title == "deep learning for medical imaging"
    assert ratio == 1.0


def test_best_title_match_empty_returns_none() -> None:
    title, ratio = best_title_match("", ["anything"])
    assert title is None
    assert ratio == 0.0


def test_best_title_match_no_candidates() -> None:
    title, ratio = best_title_match("x", [])
    assert title is None
    assert ratio == 0.0


# --------------------------------------------------------------------------- #
# VerificationReport schema
# --------------------------------------------------------------------------- #
def test_report_level_aggregation() -> None:
    report = VerificationReport(source_id="src_test")
    report.add_check(VerificationCheck(
        name="title_nonempty", level=VerificationLevel.EXISTENCE, status=VerificationCheckStatus.PASSED
    ))
    report.add_check(VerificationCheck(
        name="doi_format", level=VerificationLevel.EXISTENCE, status=VerificationCheckStatus.UNVERIFIED
    ))
    assert report.level_status(VerificationLevel.EXISTENCE) is VerificationCheckStatus.UNVERIFIED


def test_report_level_all_passed() -> None:
    report = VerificationReport(source_id="src_test")
    report.add_check(VerificationCheck(
        name="a", level=VerificationLevel.EXISTENCE, status=VerificationCheckStatus.PASSED
    ))
    report.add_check(VerificationCheck(
        name="b", level=VerificationLevel.EXISTENCE, status=VerificationCheckStatus.PASSED
    ))
    assert report.level_status(VerificationLevel.EXISTENCE) is VerificationCheckStatus.PASSED


def test_report_level_failure_wins() -> None:
    report = VerificationReport(source_id="src_test")
    report.add_check(VerificationCheck(
        name="a", level=VerificationLevel.EXISTENCE, status=VerificationCheckStatus.PASSED
    ))
    report.add_check(VerificationCheck(
        name="b", level=VerificationLevel.EXISTENCE, status=VerificationCheckStatus.FAILED
    ))
    assert report.level_status(VerificationLevel.EXISTENCE) is VerificationCheckStatus.FAILED


def test_report_empty_level_is_unverified() -> None:
    report = VerificationReport(source_id="src_test")
    assert report.level_status(VerificationLevel.CONTENT) is VerificationCheckStatus.UNVERIFIED


# --------------------------------------------------------------------------- #
# Verification flow — legal transitions
# --------------------------------------------------------------------------- #
def test_legal_transition_from_discovered() -> None:
    assert is_legal_transition(SourceState.DISCOVERED, SourceState.METADATA_VERIFIED) is True
    assert is_legal_transition(SourceState.DISCOVERED, SourceState.DOI_VERIFIED) is True


def test_illegal_same_state() -> None:
    assert is_legal_transition(SourceState.METADATA_VERIFIED, SourceState.METADATA_VERIFIED) is False


def test_terminal_has_no_exit() -> None:
    assert is_legal_transition(SourceState.APPROVED, SourceState.REJECTED) is False
    assert is_legal_transition(SourceState.REJECTED, SourceState.APPROVED) is False


def test_apply_verification_result_updates_source() -> None:
    source = Source(title="X")
    new_state = apply_verification_result(
        source, SourceState.METADATA_VERIFIED, reason="metadata corroborated"
    )
    assert new_state is SourceState.METADATA_VERIFIED
    assert source.state is SourceState.METADATA_VERIFIED


# --------------------------------------------------------------------------- #
# VerificationEngine with fake providers
# --------------------------------------------------------------------------- #
class _FakeMatchingProvider:
    name = "fake"

    def __init__(self, *, match: bool = True) -> None:
        self._match = match

    def lookup_by_doi(self, doi: str) -> Source | None:
        return Source(title="Deep Learning for Medical Imaging", doi=doi) if self._match else None

    def lookup_by_bibliographic(self, *, title: str, authors=None, year=None) -> Source | None:
        return Source(title="Deep Learning for Medical Imaging") if self._match else None


def _engine(providers=None, **kwargs) -> VerificationEngine:
    return VerificationEngine(providers=providers, match_threshold=0.6, min_providers=1, **kwargs)


def test_engine_rejects_empty_title() -> None:
    engine = _engine([_FakeMatchingProvider()])
    source = Source(title="")
    result = engine.verify(source)
    assert result.recommended_state is SourceState.REJECTED
    assert result.report.level_status(VerificationLevel.EXISTENCE) is VerificationCheckStatus.FAILED


def test_engine_metadata_verified_with_corroboration() -> None:
    engine = _engine([_FakeMatchingProvider()])
    source = Source(title="Deep Learning for Medical Imaging", authors=["A"])
    result = engine.verify(source)
    assert result.recommended_state is SourceState.METADATA_VERIFIED
    assert result.report.level_status(VerificationLevel.METADATA) is VerificationCheckStatus.PASSED
    assert result.report.metadata_match_ratio == 1.0


def test_engine_doi_verified_when_doi_corroborated() -> None:
    engine = _engine([_FakeMatchingProvider()])
    source = Source(title="Deep Learning for Medical Imaging", authors=["A"], doi="10.1000/xyz")
    result = engine.verify(source)
    # DOI corroborated → DOI_VERIFIED (a metadata pass plus a confirmed DOI).
    assert result.recommended_state is SourceState.DOI_VERIFIED


def test_engine_unverified_when_no_provider_match() -> None:
    engine = _engine([_FakeMatchingProvider(match=False)])
    source = Source(title="Some Uncorroborated Title", authors=["A"])
    result = engine.verify(source)
    assert result.recommended_state is SourceState.NEEDS_HUMAN_REVIEW
    assert result.report.level_status(VerificationLevel.METADATA) is VerificationCheckStatus.UNVERIFIED


def test_engine_content_always_unverified() -> None:
    engine = _engine([_FakeMatchingProvider()])
    source = Source(title="Deep Learning for Medical Imaging", authors=["A"])
    result = engine.verify(source)
    assert result.report.level_status(VerificationLevel.CONTENT) is VerificationCheckStatus.UNVERIFIED
