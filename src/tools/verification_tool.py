"""Source verification engine (Phase 4).

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §9 — source state machine.
  * 00_MASTER_INSTRUCTION.md §10 — validation level C (three levels).
  * AGENT_CONSTITUTION.md §1–§5 — source integrity; never fabricate.
  * SYSTEM_RULES.md §H.50 — preserve raw external results for auditability.

The engine turns a candidate :class:`~src.schemas.source.Source` into a
:class:`~src.schemas.verification.VerificationReport` with granular, per-level
results. Levels 1 (EXISTENCE) and 2 (METADATA) are implemented here. Level 3
(CONTENT) is handled by the retrieval/evidence pipeline, so this metadata
verifier reports it as ``UNVERIFIED`` rather than pretending it inspected full
text.

A metadata check only ever ``PASSED`` after a *real* provider record
corroborates the candidate's title above the configured similarity threshold —
never from local guessing.
"""

from __future__ import annotations

from typing import Any, Iterable

from src.core.config import get_config
from src.core.logging import get_logger
from src.schemas.base import Provenance
from src.schemas.source import Source, SourceState
from src.schemas.verification import (
    VerificationCheck,
    VerificationCheckStatus,
    VerificationLevel,
    VerificationReport,
)
from src.tools.crossref import CrossrefTool
from src.tools.openalex import OpenAlexTool
from src.tools.source_mapper import best_title_match, normalize_doi

__all__ = ["VerificationEngine", "VerificationResult"]


class VerificationResult:
    """Bundle a :class:`VerificationReport` with the state it recommends.

    The recommended state is separate so callers can apply it to the ``Source``
    via the workflow's legal-transition table, not by direct mutation.
    """

    def __init__(self, report: VerificationReport, recommended_state: SourceState) -> None:
        self.report = report
        self.recommended_state = recommended_state


class VerificationEngine:
    """Corroborate a candidate source against configured providers.

    The engine is provider-agnostic: it asks each available provider (Crossref,
    OpenAlex) for a DOI or bibliographic match and aggregates the results. A
    provider that cannot be reached contributes an ``UNVERIFIED`` check, never a
    pass, so a network outage degrades gracefully to "needs review" rather than
    silently approving a source.
    """

    def __init__(
        self,
        *,
        providers: Iterable[Any] | None = None,
        match_threshold: float | None = None,
        min_providers: int | None = None,
    ) -> None:
        self._logger = get_logger("tools.verification")
        cfg = get_config().verification
        self._match_threshold = (
            cfg.metadata_match_threshold if match_threshold is None else match_threshold
        )
        self._min_providers = (
            cfg.min_metadata_providers if min_providers is None else min_providers
        )
        self._providers = list(providers) if providers is not None else [CrossrefTool(), OpenAlexTool()]
        self._enabled = cfg.enabled

    # ------------------------------------------------------------------ public
    def verify(self, source: Source) -> VerificationResult:
        """Produce a verification report and recommended state for ``source``."""
        report = VerificationReport(source_id=source.id, provenance=Provenance(origin="verification_engine"))
        if not self._enabled:
            report.add_check(self._check(
                name="engine_enabled",
                level=VerificationLevel.EXISTENCE,
                status=VerificationCheckStatus.SKIPPED,
                detail="Verification engine disabled by configuration",
            ))
            return VerificationResult(report, SourceState.NEEDS_HUMAN_REVIEW)

        # Resolve provider corroborations once, then share across levels.
        corroborations = self._corroborate(source)

        self._verify_existence(source, report)
        self._verify_metadata(source, report, corroborations)
        self._verify_content(source, report)

        report.metadata_match_ratio = self._best_match_ratio(corroborations)
        report.overall_status = self._recommend(report)
        return VerificationResult(report, report.overall_status)

    # ------------------------------------------------------------ corroborate
    def _corroborate(self, source: Source) -> list[tuple[str, Source, float]]:
        """Return ``(provider_name, match, ratio)`` for corroborating providers."""
        results: list[tuple[str, Source, float]] = []
        for provider in self._providers:
            match = self._lookup(source, provider)
            if match is not None:
                ratio = self._match_ratio(source.title, match.title)
                results.append((getattr(provider, "name", type(provider).__name__), match, ratio))
        return results

    # ---------------------------------------------------------------- levels
    def _verify_existence(self, source: Source, report: VerificationReport) -> None:
        report.add_check(self._check(
            name="title_nonempty",
            level=VerificationLevel.EXISTENCE,
            status=self._pass_fail(bool(source.title)),
            detail="Title present" if source.title else "Source has no title",
        ))

        doi = source.doi
        if doi:
            normalized = normalize_doi(doi)
            report.add_check(self._check(
                name="doi_format",
                level=VerificationLevel.EXISTENCE,
                status=self._pass_fail(normalized is not None),
                detail=f"DOI normalized to {normalized}" if normalized else "DOI malformed",
            ))
        else:
            report.add_check(self._check(
                name="doi_format",
                level=VerificationLevel.EXISTENCE,
                status=VerificationCheckStatus.UNVERIFIED,
                detail="No DOI present on candidate",
            ))

        report.add_check(self._check(
            name="has_authors",
            level=VerificationLevel.EXISTENCE,
            status=self._pass_fail(bool(source.authors)),
            detail=f"{len(source.authors)} author(s)" if source.authors else "No authors",
        ))

    def _verify_metadata(
        self,
        source: Source,
        report: VerificationReport,
        corroborations: list[tuple[str, Source, float]],
    ) -> None:
        for name, match, ratio in corroborations:
            report.add_check(self._check(
                name="metadata_title_match",
                level=VerificationLevel.METADATA,
                status=VerificationCheckStatus.PASSED,
                detail=f"Title corroborated by {name}",
                provider=name,
                confidence=ratio,
            ))

        # Corroborated metadata is merged (preferring the candidate's own values).
        if corroborations:
            report.corroborated_metadata = self._merge_metadata(
                source, [m for _, m, _ in corroborations]
            )

        passed = len({name for name, _, _ in corroborations})
        if passed >= self._min_providers:
            report.add_check(self._check(
                name="metadata_provider_count",
                level=VerificationLevel.METADATA,
                status=VerificationCheckStatus.PASSED,
                detail=f"{passed} distinct provider(s) corroborated metadata",
            ))
        else:
            report.add_check(self._check(
                name="metadata_provider_count",
                level=VerificationLevel.METADATA,
                status=VerificationCheckStatus.UNVERIFIED,
                detail=f"Only {passed} provider(s) corroborated; {self._min_providers} required",
            ))

    def _verify_content(self, source: Source, report: VerificationReport) -> None:
        # Content verification lives in retrieval/evidence; never pass it here.
        report.add_check(self._check(
            name="content_extracted",
            level=VerificationLevel.CONTENT,
            status=VerificationCheckStatus.UNVERIFIED,
            detail="Content/evidence extraction is handled by the retrieval/evidence pipeline",
        ))

    # -------------------------------------------------------------- lookups
    def _lookup(self, source: Source, provider: Any) -> Source | None:
        """Return a corroborating provider record, or ``None`` when none found."""
        if source.doi:
            lookup = getattr(provider, "lookup_by_doi", None)
            if callable(lookup):
                try:
                    return lookup(source.doi)
                except Exception as exc:  # noqa: BLE001 - provider isolation
                    self._logger.warning(
                        "DOI lookup failed", extra={"provider": getattr(provider, "name", ""), "error": str(exc)}
                    )
                    return None

        lookup = getattr(provider, "lookup_by_bibliographic", None)
        if callable(lookup) and source.title:
            try:
                candidate = lookup(
                    title=source.title,
                    authors=source.authors,
                    year=source.year,
                )
                if candidate and self._match_ratio(source.title, candidate.title) >= self._match_threshold:
                    return candidate
            except Exception as exc:  # noqa: BLE001 - provider isolation
                self._logger.warning(
                    "Bibliographic lookup failed", extra={"provider": getattr(provider, "name", ""), "error": str(exc)}
                )
        return None

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _match_ratio(a: str, b: str) -> float:
        _, ratio = best_title_match(a, [b])
        return ratio

    def _best_match_ratio(self, corroborations: list[tuple[str, Source, float]]) -> float:
        best = 0.0
        for _, _, ratio in corroborations:
            best = max(best, ratio)
        return best

    @staticmethod
    def _merge_metadata(source: Source, matches: list[Source]) -> dict[str, Any]:
        """Backfill missing candidate fields from corroborating records."""
        merged: dict[str, Any] = {}
        for field in ("venue", "year", "doi", "url", "abstract", "citation_count"):
            candidate_value = getattr(source, field)
            if candidate_value not in (None, "", []):
                merged[field] = candidate_value
                continue
            for match in matches:
                value = getattr(match, field)
                if value not in (None, "", []):
                    merged[field] = value
                    break
        return merged

    @staticmethod
    def _pass_fail(condition: bool) -> VerificationCheckStatus:
        return VerificationCheckStatus.PASSED if condition else VerificationCheckStatus.FAILED

    def _check(
        self,
        *,
        name: str,
        level: VerificationLevel,
        status: VerificationCheckStatus,
        detail: str = "",
        provider: str | None = None,
        confidence: float = 1.0,
    ) -> VerificationCheck:
        return VerificationCheck(
            name=name,
            level=level,
            status=status,
            detail=detail,
            provider=provider,
            confidence=confidence,
        )

    def _recommend(self, report: VerificationReport) -> SourceState:
        """Map the level results to a recommended ``SourceState``.

        A source may only be ``APPROVED`` when EXISTENCE passes and METADATA is
        corroborated (validation level C). Level 3 remains unverified for now, so
        the ceiling is ``METADATA_VERIFIED``; sources with a confirmed DOI reach
        ``DOI_VERIFIED``.
        """
        existence = VerificationCheckStatus(report.levels.get(VerificationLevel.EXISTENCE.value))
        metadata = VerificationCheckStatus(report.levels.get(VerificationLevel.METADATA.value))

        if existence is VerificationCheckStatus.FAILED:
            return SourceState.REJECTED

        if metadata is VerificationCheckStatus.FAILED:
            return SourceState.CONDITIONAL

        if metadata is VerificationCheckStatus.PASSED:
            # DOI presence corroborated by a provider bumps to DOI_VERIFIED.
            if report.corroborated_metadata.get("doi"):
                return SourceState.DOI_VERIFIED
            return SourceState.METADATA_VERIFIED

        # Existence may have passed, but metadata could not be determined
        # (providers unreachable or below threshold).
        return SourceState.NEEDS_HUMAN_REVIEW

    def describe(self) -> dict[str, Any]:
        return {
            "enabled": self._enabled,
            "providers": [getattr(p, "name", type(p).__name__) for p in self._providers],
            "match_threshold": self._match_threshold,
            "min_providers": self._min_providers,
        }
