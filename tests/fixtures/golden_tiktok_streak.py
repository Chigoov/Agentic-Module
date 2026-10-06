"""Golden research case fixture: TikTok Streak and social connectedness.

Specification anchors:
  * Requirement 15: Golden Test Case Validation
  * Acceptance Criteria 15.1: Claim text "TikTok Streak increases social connectedness among university students"
"""

from __future__ import annotations

from src.schemas.claim import Claim, ClaimImportance, ClaimStatus
from src.schemas.evidence import (
    Evidence,
    EvidenceLocation,
    EvidenceRelationship,
    EvidenceStrength,
    EvidenceType,
    ExtractionMethod,
    ReadingDepth,
)
from src.schemas.source import RetrievalStatus, Source, SourceState

__all__ = ["get_golden_fixture"]


def get_golden_fixture() -> tuple[Claim, list[Source], dict[str, Evidence]]:
    """Return fresh instances of the golden research case scenario.

    Scenario:
      * Claim: "TikTok Streak increases social connectedness among university students"
      * Sources:
        - src_tiktok: TikTok study on university students (ABSTRACT_ONLY, PARTIAL retrieval)
        - src_snapchat: Snapchat streak study on adolescents (FULL_TEXT, RETRIEVED)
        - src_connectedness: Social connectedness theory (FULL_TEXT, RETRIEVED)
        - src_activity: Activity streaks gamification (FULL_TEXT, RETRIEVED)
        - src_counter: Longitudinal counter-evidence finding no connection (FULL_TEXT, RETRIEVED)
      * Evidence items:
        - ev_tiktok: PARTIAL, ABSTRACT_ONLY, PARTIALLY_SUPPORTS, MODERATE
        - ev_snapchat: FUNCTIONAL_EQUIVALENT, FULL_TEXT, SUPPORTS, STRONG
        - ev_connectedness: THEORETICAL, FULL_TEXT, SUPPORTS, DEFINITIVE
        - ev_activity: THEORETICAL, FULL_TEXT, SUPPORTS, MODERATE
        - ev_counter: CONTRADICTORY, FULL_TEXT, CONTRADICTS, STRONG

    Returns:
      tuple[Claim, list[Source], dict[str, Evidence]]
    """
    claim = Claim(
        id="clm_golden_tiktok",
        claim_text="TikTok Streak increases social connectedness among university students",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.PROPOSED,
        required_source_count=2,
    )

    src_tiktok = Source(
        id="src_tiktok",
        title="TikTok usage and social connectedness among university students",
        authors=["Chen, L."],
        year=2023,
        venue="Computers in Human Behavior",
        doi="10.1016/j.chb.2023.107000",
        state=SourceState.APPROVED,
        publisher_verified=True,
        reading_depth=ReadingDepth.ABSTRACT_ONLY,
        retrieval_status=RetrievalStatus.PARTIAL,
    )

    src_snapchat = Source(
        id="src_snapchat",
        title="Sharing the small moments: Ephemeral social interaction on Snapchat",
        authors=["Bayer, J. B."],
        year=2016,
        venue="Journal of Computer-Mediated Communication",
        doi="10.1111/jcc4.12143",
        state=SourceState.APPROVED,
        publisher_verified=True,
        reading_depth=ReadingDepth.FULL_TEXT,
        retrieval_status=RetrievalStatus.RETRIEVED,
    )

    src_connectedness = Source(
        id="src_connectedness",
        title="The Social Connectedness Scale",
        authors=["Lee, R. M."],
        year=2001,
        venue="Journal of Counseling Psychology",
        doi="10.1037/0022-0167.48.3.310",
        state=SourceState.APPROVED,
        publisher_verified=True,
        reading_depth=ReadingDepth.FULL_TEXT,
        retrieval_status=RetrievalStatus.RETRIEVED,
    )

    src_activity = Source(
        id="src_activity",
        title="Activity streaks and user engagement in gamified mobile apps",
        authors=["Silverman, M."],
        year=2022,
        venue="ACM CHI",
        doi="10.1145/3491102.3501821",
        state=SourceState.APPROVED,
        publisher_verified=True,
        reading_depth=ReadingDepth.FULL_TEXT,
        retrieval_status=RetrievalStatus.RETRIEVED,
    )

    src_counter = Source(
        id="src_counter",
        title="Do social media streaks foster genuine connection? A longitudinal study",
        authors=["Dienlin, T."],
        year=2021,
        venue="Human Communication Research",
        doi="10.1093/hcr/hqaa014",
        state=SourceState.APPROVED,
        publisher_verified=True,
        reading_depth=ReadingDepth.FULL_TEXT,
        retrieval_status=RetrievalStatus.RETRIEVED,
    )

    sources = [
        src_tiktok,
        src_snapchat,
        src_connectedness,
        src_activity,
        src_counter,
    ]

    ev_tiktok = Evidence(
        id="ev_tiktok",
        claim_id=claim.id,
        source_id=src_tiktok.id,
        evidence_text=(
            "TikTok usage among undergraduate students correlates with peer socialization, "
            "though specific streak features were not evaluated."
        ),
        evidence_type=EvidenceType.PARTIAL,
        reading_depth=ReadingDepth.ABSTRACT_ONLY,
        extraction_method=ExtractionMethod.VERBATIM_ABSTRACT,
        relationship=EvidenceRelationship.PARTIALLY_SUPPORTS,
        strength=EvidenceStrength.MODERATE,
        location=EvidenceLocation(section="Abstract"),
        verbatim=True,
        quote_verified=True,
    )

    ev_snapchat = Evidence(
        id="ev_snapchat",
        claim_id=claim.id,
        source_id=src_snapchat.id,
        evidence_text=(
            "Snapchat streak maintenance among adolescents increases daily perceived closeness "
            "and interpersonal communication rituals."
        ),
        evidence_type=EvidenceType.FUNCTIONAL_EQUIVALENT,
        reading_depth=ReadingDepth.FULL_TEXT,
        extraction_method=ExtractionMethod.VERBATIM_FULLTEXT,
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        location=EvidenceLocation(page=14, section="Results"),
        verbatim=True,
        quote_verified=True,
    )

    ev_connectedness = Evidence(
        id="ev_connectedness",
        claim_id=claim.id,
        source_id=src_connectedness.id,
        evidence_text=(
            "Social connectedness represents a subjective sense of belonging and affinity "
            "sustained by recurring reciprocal interactions."
        ),
        evidence_type=EvidenceType.THEORETICAL,
        reading_depth=ReadingDepth.FULL_TEXT,
        extraction_method=ExtractionMethod.VERBATIM_FULLTEXT,
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.DEFINITIVE,
        location=EvidenceLocation(page=312, section="Discussion"),
        verbatim=True,
        quote_verified=True,
    )

    ev_activity = Evidence(
        id="ev_activity",
        claim_id=claim.id,
        source_id=src_activity.id,
        evidence_text=(
            "Activity streaks gamification reinforces habit formation and daily user return "
            "across interactive digital platforms."
        ),
        evidence_type=EvidenceType.THEORETICAL,
        reading_depth=ReadingDepth.FULL_TEXT,
        extraction_method=ExtractionMethod.VERBATIM_FULLTEXT,
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.MODERATE,
        location=EvidenceLocation(page=8, section="Gamification"),
        verbatim=True,
        quote_verified=True,
    )

    ev_counter = Evidence(
        id="ev_counter",
        claim_id=claim.id,
        source_id=src_counter.id,
        evidence_text=(
            "Longitudinal analysis found no significant association between maintaining app streaks "
            "and improved social connectedness or well-being."
        ),
        evidence_type=EvidenceType.CONTRADICTORY,
        reading_depth=ReadingDepth.FULL_TEXT,
        extraction_method=ExtractionMethod.VERBATIM_FULLTEXT,
        relationship=EvidenceRelationship.CONTRADICTS,
        strength=EvidenceStrength.STRONG,
        location=EvidenceLocation(page=25, section="Longitudinal Findings"),
        verbatim=True,
        quote_verified=True,
    )

    evidence_dict: dict[str, Evidence] = {
        "ev_tiktok": ev_tiktok,
        "ev_snapchat": ev_snapchat,
        "ev_connectedness": ev_connectedness,
        "ev_activity": ev_activity,
        "ev_counter": ev_counter,
    }

    return claim, sources, evidence_dict
