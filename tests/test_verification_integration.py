"""Integration test for the verification engine (real HTTP calls).

Verifies the engine end-to-end against the real Crossref/OpenAlex providers using
a well-known DOI. Excluded from the fast suite (``@pytest.mark.integration``).

Run with:
  python -m pytest tests/test_verification_integration.py -m integration -v
"""

from __future__ import annotations

import pytest

from src.schemas.source import Source
from src.schemas.verification import VerificationCheckStatus, VerificationLevel
from src.tools.verification_tool import VerificationEngine

pytestmark = pytest.mark.integration

# A stable, well-known DOI (LeCun et al. 2015, "Deep Learning").
_WELL_KNOWN_DOI = "10.1038/nature14539"


def test_engine_verifies_real_doi() -> None:
    """Verify a real source by DOI against live providers."""
    source = Source(
        title="Deep learning",
        authors=["LeCun, Y.", "Bengio, Y.", "Hinton, G."],
        year=2015,
        doi=_WELL_KNOWN_DOI,
    )
    engine = VerificationEngine()
    result = engine.verify(source)

    report = result.report
    # Existence must pass: title and DOI are present and well-formed.
    assert report.level_status(VerificationLevel.EXISTENCE) is VerificationCheckStatus.PASSED
    # At least one live provider corroborated the DOI.
    assert report.metadata_match_ratio > 0.0
    # The report must carry a recommended state in the verified family.
    assert result.recommended_state in {
        "METADATA_VERIFIED",
        "DOI_VERIFIED",
        "PUBLISHER_VERIFIED",
        "NEEDS_HUMAN_REVIEW",
    }
