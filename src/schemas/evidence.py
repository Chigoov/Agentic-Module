"""Evidence registry schema.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §15 — evidence registry minimum fields.
  * 00_MASTER_INSTRUCTION.md §10 — validation level C, level 3 content verification.
  * AGENT_CONSTITUTION.md §8/§9 — never fabricate evidence, page numbers, or locations.

Evidence is stored separately from sources (§15) because one source can yield
many pieces of evidence, and one claim can be supported by evidence drawn from
several sources. Each record pins the exact location it came from so a citation
audit can trace prose back to a page or section.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from src.schemas.base import BaseRecord, SchemaModel

__all__ = [
    "EvidenceRelationship",
    "EvidenceStrength",
    "ExtractionMethod",
    "EvidenceLocation",
    "Evidence",
    "SUPPORTING_RELATIONSHIPS",
]


class EvidenceRelationship(StrEnum):
    """How the evidence relates to the claim (00_MASTER_INSTRUCTION.md §15)."""

    SUPPORTS = "supports"
    PARTIALLY_SUPPORTS = "partially_supports"
    CONTRADICTS = "contradicts"
    IRRELEVANT = "irrelevant"


class EvidenceStrength(StrEnum):
    """Evidential weight, used to cap the wording strength of the claim.

    00_MASTER_INSTRUCTION.md §19: the language of a claim must not exceed the
    strength of its evidence.
    """

    #: Passing mention, unclear methodology, or anecdote.
    WEAK = "WEAK"
    #: Single study, limited sample, or indirect measurement.
    MODERATE = "MODERATE"
    #: Well-powered study, replication, or authoritative primary source.
    STRONG = "STRONG"
    #: Systematic review, meta-analysis, or canonical definition.
    DEFINITIVE = "DEFINITIVE"


class ExtractionMethod(StrEnum):
    """How the evidence text was obtained; part of its provenance."""

    #: Verbatim span copied from retrieved full text.
    VERBATIM_FULLTEXT = "VERBATIM_FULLTEXT"
    #: Verbatim span copied from an abstract.
    VERBATIM_ABSTRACT = "VERBATIM_ABSTRACT"
    #: Model-written paraphrase of a located passage.
    MODEL_PARAPHRASE = "MODEL_PARAPHRASE"
    #: Numeric/statistical value read from a table or figure caption.
    TABULAR_VALUE = "TABULAR_VALUE"
    #: Supplied directly by the user.
    USER_PROVIDED = "USER_PROVIDED"


#: Relationships that can contribute positive support to a claim.
SUPPORTING_RELATIONSHIPS: frozenset[EvidenceRelationship] = frozenset(
    {EvidenceRelationship.SUPPORTS, EvidenceRelationship.PARTIALLY_SUPPORTS}
)


class EvidenceLocation(SchemaModel):
    """Where inside the source the evidence was found.

    A value object rather than a record: it has no independent identity or
    lifecycle, it only qualifies the :class:`Evidence` that owns it.

    Every field is optional because different retrieval paths expose different
    precision. Fields are only ever populated from real retrieved content —
    a missing page number stays ``None`` rather than being guessed
    (AGENT_CONSTITUTION.md §9).
    """

    page: int | None = Field(default=None, ge=1)
    page_label: str | None = None
    section: str | None = None
    paragraph: int | None = Field(default=None, ge=1)
    #: Character offsets into the retrieved document, when available.
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    #: Free-form pointer for formats without pagination (e.g. HTML anchor).
    locator: str | None = None

    @model_validator(mode="after")
    def _check_offsets(self) -> "EvidenceLocation":
        if (
            self.char_start is not None
            and self.char_end is not None
            and self.char_end < self.char_start
        ):
            raise ValueError("char_end must not precede char_start")
        return self

    @property
    def is_precise(self) -> bool:
        """Whether the location is specific enough to cite a page or section."""
        return any(
            value is not None
            for value in (self.page, self.page_label, self.section, self.locator)
        )

    def describe(self) -> str:
        """Human-readable locator for audit reports, e.g. ``"p. 42, §Results"``."""
        parts: list[str] = []
        if self.page_label:
            parts.append(f"p. {self.page_label}")
        elif self.page is not None:
            parts.append(f"p. {self.page}")
        if self.section:
            parts.append(f"§{self.section}")
        if self.paragraph is not None:
            parts.append(f"¶{self.paragraph}")
        if not parts and self.locator:
            parts.append(self.locator)
        return ", ".join(parts) if parts else "location unspecified"


class Evidence(BaseRecord):
    """A located passage that bears on a specific claim.

    Attributes
    ----------
    claim_id:
        The claim this evidence was extracted for.
    source_id:
        The approved source the passage came from.
    evidence_text:
        The passage itself. For verbatim methods this must be an exact copy.
    location:
        Where in the source the passage occurs.
    relationship:
        Whether it supports, partially supports, contradicts, or is irrelevant.
    strength:
        Evidential weight, capping how strongly the claim may be worded.
    confidence:
        Confidence in ``[0.0, 1.0]`` that the extraction and mapping are correct.
    extraction_method:
        How the text was obtained; verbatim methods are auditable by string match.
    verbatim:
        ``True`` when ``evidence_text`` is an exact quotation of the source.
    quote_verified:
        ``True`` only after the text was confirmed present in retrieved content.
        Never set optimistically (AGENT_CONSTITUTION.md §8).
    extracted_by:
        Agent or tool that produced the record.
    notes:
        Interpretation caveats for the auditor.
    """

    id_prefix: str = Field(default="evd", exclude=True, repr=False)

    claim_id: str
    source_id: str
    evidence_text: str = Field(min_length=1)
    location: EvidenceLocation = Field(default_factory=EvidenceLocation)
    relationship: EvidenceRelationship = EvidenceRelationship.SUPPORTS
    strength: EvidenceStrength = EvidenceStrength.MODERATE
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extraction_method: ExtractionMethod = ExtractionMethod.VERBATIM_FULLTEXT
    verbatim: bool = True
    quote_verified: bool = False
    extracted_by: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _sync_verbatim_flag(self) -> "Evidence":
        # A paraphrase can never be presented as a quotation.
        if self.extraction_method is ExtractionMethod.MODEL_PARAPHRASE and self.verbatim:
            object.__setattr__(self, "verbatim", False)
        return self

    @property
    def is_supporting(self) -> bool:
        return self.relationship in SUPPORTING_RELATIONSHIPS

    @property
    def is_citable_quotation(self) -> bool:
        """Whether the text may be reproduced as a direct quote with a locator.

        Requires a verbatim extraction, a verified quote, and a precise location
        so that page numbers are never invented (AGENT_CONSTITUTION.md §9).
        """
        return self.verbatim and self.quote_verified and self.location.is_precise

    def mark_quote_verified(self, *, haystack: str, actor: str | None = None) -> bool:
        """Verify the passage really occurs in retrieved content.

        Only exact containment counts. The flag is cleared on failure so a
        previously verified record cannot survive a failed re-check.

        Parameters
        ----------
        haystack:
            Retrieved source text to search within.
        actor:
            Component performing the verification, recorded in the history.

        Returns
        -------
        bool
            ``True`` when the passage was found verbatim.
        """
        normalized_needle = " ".join(self.evidence_text.split())
        normalized_haystack = " ".join(haystack.split())
        found = bool(normalized_needle) and normalized_needle in normalized_haystack
        self.quote_verified = found
        self.record_transition(
            from_state="quote_unverified",
            to_state="quote_verified" if found else "quote_verification_failed",
            reason=(
                "Passage located verbatim in retrieved content"
                if found
                else "Passage not found verbatim in retrieved content"
            ),
            actor=actor,
        )
        if not found:
            self.record_error(
                code="QUOTE_NOT_FOUND",
                message="Evidence text could not be located verbatim in the source content",
                recoverable=True,
                source_id=self.source_id,
            )
        return found

    def max_claim_strength(self) -> EvidenceStrength:
        """Ceiling on claim wording implied by this single piece of evidence.

        Partial support degrades the ceiling by one step, so a partially
        supporting definitive source still cannot license an absolute claim.
        """
        if self.relationship is EvidenceRelationship.IRRELEVANT:
            return EvidenceStrength.WEAK
        ladder = [
            EvidenceStrength.WEAK,
            EvidenceStrength.MODERATE,
            EvidenceStrength.STRONG,
            EvidenceStrength.DEFINITIVE,
        ]
        index = ladder.index(self.strength)
        if self.relationship is EvidenceRelationship.PARTIALLY_SUPPORTS:
            index = max(0, index - 1)
        return ladder[index]
