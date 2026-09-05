"""Fast, network-free tests for the ClaimVerificationAgent (Phase 6)."""

from __future__ import annotations

from pathlib import Path

from src.agents.claim_verification import (
    ClaimVerificationAgent,
    ClaimVerificationRequest,
)
from src.core.claim_registry import ClaimRegistry
from src.core.evidence_registry import EvidenceRegistry
from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import (
    Evidence,
    EvidenceRelationship,
    EvidenceStrength,
)
from src.schemas.project import Project


def _project(tmp_path: Path) -> Project:
    directory = tmp_path / "proj"
    directory.mkdir()
    return Project(name="proj", workspace="TUGAS 1", path=str(directory))


def _seed(
    tmp_path: Path,
    claims: list[Claim],
    evidence: list[Evidence] | None = None,
) -> Project:
    """Persist claims (and evidence) to disk so the agent can load them."""
    project = _project(tmp_path)
    claim_registry = ClaimRegistry(project)
    for claim in claims:
        claim_registry.add(claim)
    claim_registry.save()

    if evidence:
        evidence_registry = EvidenceRegistry(project)
        for item in evidence:
            evidence_registry.add(item)
        evidence_registry.save()
    return project


def test_agent_classifies_supported_claim(tmp_path: Path) -> None:
    claim = Claim(claim_text="Supported claim")
    evidence = Evidence(
        claim_id=claim.id,
        source_id="src_1",
        evidence_text="strong passage",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.DEFINITIVE,
    )
    project = _seed(tmp_path, [claim], [evidence])

    response = ClaimVerificationAgent().execute(ClaimVerificationRequest(project=project))

    assert response.success
    assert response.writable == 1
    assert len(response.outcomes) == 1
    outcome = response.outcomes[0]
    assert outcome.to_status is ClaimStatus.SUPPORTED
    assert outcome.support_level is SupportLevel.STRONG


def test_agent_classifies_unsupported_claim(tmp_path: Path) -> None:
    claim = Claim(claim_text="Unsupported claim")
    project = _seed(tmp_path, [claim])

    response = ClaimVerificationAgent().execute(ClaimVerificationRequest(project=project))

    assert response.success
    assert response.writable == 0
    assert response.insufficient == 1
    assert response.outcomes[0].to_status is ClaimStatus.INSUFFICIENT_EVIDENCE


def test_agent_classifies_conflicted_claim(tmp_path: Path) -> None:
    claim = Claim(claim_text="Contested claim")
    support = Evidence(
        claim_id=claim.id,
        source_id="src_1",
        evidence_text="supports",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
    )
    contradiction = Evidence(
        claim_id=claim.id,
        source_id="src_2",
        evidence_text="contradicts",
        relationship=EvidenceRelationship.CONTRADICTS,
        strength=EvidenceStrength.STRONG,
    )
    project = _seed(tmp_path, [claim], [support, contradiction])

    response = ClaimVerificationAgent().execute(ClaimVerificationRequest(project=project))

    assert response.success
    assert response.conflicted == 1
    assert response.outcomes[0].to_status is ClaimStatus.CONFLICTED


def test_agent_persists_verdict_to_disk(tmp_path: Path) -> None:
    claim = Claim(claim_text="Supported claim")
    evidence = Evidence(
        claim_id=claim.id,
        source_id="src_1",
        evidence_text="strong passage",
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.DEFINITIVE,
    )
    project = _seed(tmp_path, [claim], [evidence])

    ClaimVerificationAgent().execute(ClaimVerificationRequest(project=project))

    loaded = ClaimRegistry.load(project).get(claim.id)
    assert loaded is not None
    assert loaded.status is ClaimStatus.SUPPORTED
    assert loaded.support_level is SupportLevel.STRONG


def test_agent_handles_empty_project(tmp_path: Path) -> None:
    project = _seed(tmp_path, [])
    response = ClaimVerificationAgent().execute(ClaimVerificationRequest(project=project))

    assert response.success
    assert response.outcomes == []
    assert response.writable == 0
