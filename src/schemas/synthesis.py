"""Synthesis schema — findings produced by SynthesisAgent.

Specification anchors:
  * 00_MASTER_INSTRUCTION.md §17 — evidence synthesis in deep research.
  * AGENT_CONSTITUTION.md §14/§15 — conflicts disclosed, uncertainty preserved.

A :class:`Synthesis` aggregates the writable claims into a set of findings plus
an explicit ``open_gaps`` list for claims that could not be written. It is the
bridge between the evidence engine (Fase 5) and the outline/writer (Fase 6).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field

from src.schemas.base import BaseRecord, SchemaModel
from src.schemas.claim import SupportLevel

__all__ = ["SynthesisStatus", "SynthesisFinding", "Synthesis"]


class SynthesisStatus(StrEnum):
    """Lifecycle of a synthesis document."""

    DRAFT = "DRAFT"
    COMPLETE = "COMPLETE"


class SynthesisFinding(SchemaModel):
    """One aggregated finding: a statement carried by one or more claims.

    ``conflicts_disclosed`` is ``True`` when the finding is knowingly contested,
    so downstream writing preserves the disagreement (SYSTEM_RULES.md §E.37).
    """

    statement: str
    claim_ids: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    support_level: SupportLevel = SupportLevel.NONE
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    conflicts_disclosed: bool = False


class Synthesis(BaseRecord):
    """The aggregate synthesis for one project."""

    id_prefix: str = Field(default="syn", exclude=True, repr=False)

    project_id: str | None = None
    findings: list[SynthesisFinding] = Field(default_factory=list)
    #: Human-readable notes for claims that could not be written as stated.
    open_gaps: list[str] = Field(default_factory=list)
    status: SynthesisStatus = SynthesisStatus.DRAFT
