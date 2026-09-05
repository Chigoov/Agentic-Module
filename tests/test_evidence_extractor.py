"""Fast, network-free tests for the evidence extractor (Phase 5)."""

from __future__ import annotations

from src.schemas.evidence import (
    EvidenceRelationship,
    EvidenceStrength,
    ExtractionMethod,
)
from src.schemas.source import Source
from src.tools.evidence_extractor import EvidenceExtractor


def _source() -> Source:
    return Source(title="Example Paper")


def test_extract_verbatim_found() -> None:
    source = _source()
    haystack = "The first sentence. The method improved accuracy by 20 percent. Conclusion."
    passage = "The method improved accuracy by 20 percent."
    result = EvidenceExtractor().extract_verbatim(
        passage=passage, haystack=haystack, claim_id="clm_1", source=source
    )
    assert result.found is True
    assert result.evidence is not None
    assert result.evidence.quote_verified is True
    assert result.evidence.extraction_method is ExtractionMethod.VERBATIM_FULLTEXT


def test_extract_verbatim_tolerates_whitespace() -> None:
    source = _source()
    haystack = "line one\nline two\nline three"
    passage = "line two\nline three"
    result = EvidenceExtractor().extract_verbatim(
        passage=passage, haystack=haystack, claim_id="clm_1", source=source
    )
    assert result.found is True


def test_extract_verbatim_not_found() -> None:
    source = _source()
    result = EvidenceExtractor().extract_verbatim(
        passage="a passage that does not exist",
        haystack="different content",
        claim_id="clm_1",
        source=source,
    )
    assert result.found is False
    assert result.evidence is None
    assert result.error is not None


def test_extract_verbatim_empty_passage() -> None:
    source = _source()
    result = EvidenceExtractor().extract_verbatim(
        passage="  ", haystack="content", claim_id="clm_1", source=source
    )
    assert result.found is False
    assert "empty" in result.error.lower()


def test_record_paraphrase_is_non_verbatim() -> None:
    source = _source()
    evidence = EvidenceExtractor().record_paraphrase(
        text="The authors found an improvement.",
        claim_id="clm_1",
        source=source,
        confidence=0.7,
        strength=EvidenceStrength.MODERATE,
        relationship=EvidenceRelationship.SUPPORTS,
    )
    assert evidence.extraction_method is ExtractionMethod.MODEL_PARAPHRASE
    assert evidence.verbatim is False
    assert evidence.quote_verified is False
    assert evidence.is_citable_quotation is False
