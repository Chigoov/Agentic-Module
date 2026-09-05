"""Verification report schema.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §9 — source state machine.
  * 00_MASTER_INSTRUCTION.md §10 — validation level C (three levels).
  * AGENT_CONSTITUTION.md §1–§5 — source integrity; never fabricate.
  * SYSTEM_RULES.md §H.50 — preserve raw external results for auditability.

The :class:`VerificationEngine` produces a :class:`VerificationReport` for each
candidate :class:`~src.schemas.source.Source`. The report stores the granular
per-level results *separately* from the source (finding: evidence is stored apart
from sources), so the ``Source`` schema stays clean and the audit trail remains
independently inspectable.

A report never "looks successful" without proof: a check that was not performed
or could not be corroborated is marked ``UNVERIFIED``, and a level that did not
pass is never promoted silently.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from src.schemas.base import BaseRecord, ErrorInfo, Provenance
from src.schemas.source import SourceState

__all__ = [
    "VerificationLevel",
    "VerificationCheckStatus",
    "VerificationCheck",
    "VerificationReport",
    "LEVEL_ORDER",
]


class VerificationLevel(StrEnum):
    """The three validation levels from 00_MASTER_INSTRUCTION.md §10."""

    #: Level 1 — the record exists and carries minimally sufficient identity.
    EXISTENCE = "EXISTENCE"
    #: Level 2 — bibliographic metadata corroborated against ≥1 provider.
    METADATA = "METADATA"
    #: Level 3 — content/evidence extracted from full text (future phase).
    CONTENT = "CONTENT"


#: Ordering of the three validation levels defined by 00_MASTER_INSTRUCTION.md §10.
LEVEL_ORDER: tuple[VerificationLevel, ...] = (
    VerificationLevel.EXISTENCE,
    VerificationLevel.METADATA,
    VerificationLevel.CONTENT,
)


class VerificationCheckStatus(StrEnum):
    """Outcome of a single granular check."""

    PASSED = "PASSED"
    FAILED = "FAILED"
    #: Could not be determined (e.g. provider unreachable); never treated as pass.
    UNVERIFIED = "UNVERIFIED"
    #: Deliberately not run (e.g. publisher check skipped by configuration).
    SKIPPED = "SKIPPED"


class VerificationCheck(BaseRecord):
    """One granular, named check within a level.

    Attributes
    ----------
    name:
        Stable, human-readable check name (e.g. ``title_nonempty``,
        ``doi_format``, ``metadata_title_match``).
    level:
        Which validation level this check belongs to.
    status:
        PASSED / FAILED / UNVERIFIED / SKIPPED.
    detail:
        Short evidence string backing the status (never empty on FAILED).
    provider:
        Provider that corroborated the check, when any.
    confidence:
        Confidence in ``[0.0, 1.0]`` that the check result is correct.
    """

    id_prefix: str = Field(default="vchk", exclude=True, repr=False)

    name: str = Field(min_length=1)
    level: VerificationLevel
    status: VerificationCheckStatus = VerificationCheckStatus.UNVERIFIED
    detail: str = ""
    provider: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class VerificationReport(BaseRecord):
    """Result of verifying a single candidate source.

    Attributes
    ----------
    source_id:
        ID of the :class:`~src.schemas.source.Source` under verification.
    checks:
        Ordered granular checks performed.
    levels:
        Per-level aggregate status.
    overall_status:
        Recommended :class:`SourceState` for the source after verification.
    corroborated_metadata:
        Metadata merged from cross-check providers (never invented).
    metadata_match_ratio:
        Best field-match ratio in ``[0.0, 1.0]`` observed across providers.
    provenance:
        Origin of the verification run itself.
    errors:
        Structured failures encountered while verifying.
    """

    id_prefix: str = Field(default="vrep", exclude=True, repr=False)

    source_id: str = Field(min_length=1)
    checks: list[VerificationCheck] = Field(default_factory=list)
    levels: dict[str, VerificationCheckStatus] = Field(default_factory=dict)
    overall_status: SourceState = SourceState.DISCOVERED
    corroborated_metadata: dict[str, Any] = Field(default_factory=dict)
    metadata_match_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    provenance: Provenance | None = None
    errors: list[ErrorInfo] = Field(default_factory=list)

    def add_check(self, check: VerificationCheck) -> None:
        """Append a check and refresh the aggregate per-level status."""
        self.checks.append(check)
        self._recompute_levels()
        self.touch()

    def level_status(self, level: VerificationLevel) -> VerificationCheckStatus:
        """Aggregate status for ``level`` computed from its checks.

        ``PASSED`` only when *every* non-skipped check passed; ``FAILED`` when
        any check failed; ``SKIPPED`` when all checks were skipped; otherwise
        ``UNVERIFIED``.
        """
        statuses = [c.status for c in self.checks if c.level is level]
        if not statuses:
            return VerificationCheckStatus.UNVERIFIED
        if any(s is VerificationCheckStatus.FAILED for s in statuses):
            return VerificationCheckStatus.FAILED
        if all(s is VerificationCheckStatus.SKIPPED for s in statuses):
            return VerificationCheckStatus.SKIPPED
        if all(s is VerificationCheckStatus.PASSED for s in statuses):
            return VerificationCheckStatus.PASSED
        return VerificationCheckStatus.UNVERIFIED

    def _recompute_levels(self) -> None:
        for level in VerificationLevel:
            self.levels[level.value] = self.level_status(level).value

    def add_error(self, error: ErrorInfo) -> None:
        self.errors.append(error)
        self.touch()
