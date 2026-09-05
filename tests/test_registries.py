"""Fast tests for claim and evidence registries (Phase 5)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.claim_registry import ClaimRegistry
from src.core.errors import ProjectError
from src.core.evidence_registry import EvidenceRegistry
from src.schemas.claim import Claim, ClaimImportance
from src.schemas.evidence import Evidence
from src.schemas.project import Project


def _project(tmp_path: Path) -> Project:
    directory = tmp_path / "proj"
    directory.mkdir()
    return Project(name="proj", workspace="TUGAS 1", path=str(directory))


def _claim() -> Claim:
    return Claim(claim_text="A test claim", importance=ClaimImportance.HIGH)


def _evidence(claim_id: str, source_id: str = "src_a") -> Evidence:
    return Evidence(claim_id=claim_id, source_id=source_id, evidence_text="passage")


def test_claim_registry_add_and_get(tmp_path: Path) -> None:
    registry = ClaimRegistry(_project(tmp_path))
    claim = _claim()
    registry.add(claim)
    assert registry.get(claim.id) is claim
    assert len(registry.all()) == 1


def test_claim_registry_rejects_duplicate(tmp_path: Path) -> None:
    registry = ClaimRegistry(_project(tmp_path))
    claim = _claim()
    registry.add(claim)
    with pytest.raises(ProjectError):
        registry.add(claim)


def test_claim_registry_round_trip(tmp_path: Path) -> None:
    project = _project(tmp_path)
    registry = ClaimRegistry(project)
    claim = _claim()
    registry.add(claim)
    registry.save()

    loaded = ClaimRegistry.load(project)
    assert loaded.get(claim.id) is not None
    assert loaded.get(claim.id).claim_text == "A test claim"


def test_claim_registry_load_missing_is_empty(tmp_path: Path) -> None:
    loaded = ClaimRegistry.load(_project(tmp_path))
    assert loaded.all() == []


def test_claim_registry_writable_filters_unsupported(tmp_path: Path) -> None:
    project = _project(tmp_path)
    registry = ClaimRegistry(project)
    # A claim that requires evidence but has none is never writable.
    registry.add(_claim())
    registry.add(Claim(claim_text="Proposed", importance=ClaimImportance.HIGH))
    assert registry.writable() == []


def test_evidence_registry_round_trip(tmp_path: Path) -> None:
    project = _project(tmp_path)
    registry = EvidenceRegistry(project)
    evidence = _evidence("clm_1")
    registry.add(evidence)
    written = registry.save()
    assert written == 1

    loaded = EvidenceRegistry.load(project)
    assert loaded.get(evidence.id) is not None
    assert loaded.get(evidence.id).evidence_text == "passage"


def test_evidence_registry_append_only_no_duplicate(tmp_path: Path) -> None:
    project = _project(tmp_path)
    registry = EvidenceRegistry(project)
    evidence = _evidence("clm_1")
    registry.add(evidence)
    registry.save()

    # A fresh registry loading the same file and saving again appends nothing.
    reloaded = EvidenceRegistry.load(project)
    assert reloaded.save(new_only=True) == 0


def test_evidence_registry_for_claim(tmp_path: Path) -> None:
    project = _project(tmp_path)
    registry = EvidenceRegistry(project)
    registry.add(_evidence("clm_1", source_id="src_a"))
    registry.add(_evidence("clm_2", source_id="src_b"))
    assert len(registry.for_claim("clm_1")) == 1
    assert registry.for_claim("clm_1")[0].source_id == "src_a"
