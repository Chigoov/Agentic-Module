"""Outline schema — document skeleton contract.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §22 — ``outline.json`` project artifact.
  * SYSTEM_RULES.md §E.31 — writer works from approved claims only.

An :class:`Outline` is the evidence-anchored skeleton the WriterAgent turns into
a draft. Each :class:`OutlineSection` names the claims it will carry, so a later
audit can confirm that every claim in the outline is actually supported.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from src.core.errors import StateTransitionError
from src.schemas.base import BaseRecord

__all__ = ["OutlineStatus", "OutlineSection", "Outline"]


class OutlineStatus(StrEnum):
    """Lifecycle of an outline document."""

    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    REVISED = "REVISED"


class OutlineSection(BaseRecord):
    """A heading in the document outline, optionally nested.

    Each section is itself a record (stable id + history) so an audit can trace
    how the skeleton changed over time. ``claim_ids`` is the load-bearing link:
    it names exactly which claims this section will state.
    """

    id_prefix: str = Field(default="sec", exclude=True, repr=False)

    title: str = Field(min_length=1)
    level: int = Field(default=1, ge=1, le=6)
    summary: str | None = None
    claim_ids: list[str] = Field(default_factory=list)
    subsections: list["OutlineSection"] = Field(default_factory=list)
    order: int = Field(default=0, ge=0)


class Outline(BaseRecord):
    """The full document skeleton for one project."""

    id_prefix: str = Field(default="out", exclude=True, repr=False)

    project_id: str | None = None
    title: str = Field(min_length=1)
    sections: list[OutlineSection] = Field(default_factory=list)
    citation_style: str = "APA7"
    language: str = "id"
    status: OutlineStatus = OutlineStatus.DRAFT

    @model_validator(mode="after")
    def _check_unique_claims(self) -> "Outline":
        """A claim may appear at most once in an outline (avoid silent duplication)."""
        seen: set[str] = set()

        def walk(section: OutlineSection) -> None:
            for claim_id in section.claim_ids:
                if claim_id in seen:
                    raise ValueError(f"Duplicate claim_id in outline: {claim_id}")
                seen.add(claim_id)
            for subsection in section.subsections:
                walk(subsection)

        for section in self.sections:
            walk(section)
        return self

    @property
    def claim_ids(self) -> list[str]:
        """Every claim referenced anywhere in the outline, in document order."""

        def walk(section: OutlineSection, out: list[str]) -> None:
            out.extend(section.claim_ids)
            for subsection in section.subsections:
                walk(subsection, out)

        collected: list[str] = []
        for section in self.sections:
            walk(section, collected)
        return collected

    def transition_to(
        self, new_status: OutlineStatus, *, reason: str, actor: str | None = None
    ) -> None:
        """Move the outline to ``new_status``, recording an audited transition."""
        old_status = self.status
        if old_status == new_status:
            raise StateTransitionError(
                f"Outline {self.id} is already in status {old_status}",
                outline_id=self.id,
                status=str(old_status),
            )
        self.record_transition(
            from_state=str(old_status), to_state=str(new_status), reason=reason, actor=actor
        )
        self.status = new_status
