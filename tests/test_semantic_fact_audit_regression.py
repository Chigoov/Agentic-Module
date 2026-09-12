"""Regression tests for semantic fact audit and anti-hallucination gates (Tahap 7).

Verifies the 9 required scenarios:
  1. Claim marked SUPPORTED but evidence content does not support it -> rejected / NEEDS_HUMAN_REVIEW.
  2. Important claim without semantic review -> final output (DOCX) rejected.
  3. Claim with fake/nonexistent evidence ID -> rejected.
  4. REFUTED claim -> rejected.
  5. PARTIALLY_SUPPORTED claim without qualifier written as full claim -> rejected.
  6. Fully supported claim with valid source, evidence, precise location, and semantic review -> passed.
  7. Incomplete author metadata -> marked [sumber belum lengkap].
  8. Output text containing internal tokens (turn..., view..., search..., filecite) -> rejected.
  9. Safe legacy workflow continues to operate according to its contract.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from src.agents.audit import (
    FactAuditAgent,
    FactAuditRequest,
)
from src.schemas.claim import (
    Claim,
    ClaimImportance,
    ClaimStatus,
    SemanticDecision,
    SemanticReview,
    SupportLevel,
    requires_semantic_review,
)
from src.schemas.evidence import (
    Evidence,
    EvidenceLocation,
    EvidenceRelationship,
    EvidenceStrength,
    ExtractionMethod,
)
from src.schemas.outline import Outline, OutlineSection
from src.schemas.project import Project
from src.schemas.source import Source, SourceState
from src.tools.reference_formatter import format_reference
from src.tools.verification_tool import VerificationEngine
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow
from src.workflows.gates import scan_output_text


def _project(tmp_path: Path, name: str = "proj") -> Project:
    p = tmp_path / name
    p.mkdir(parents=True, exist_ok=True)
    return Project(name=name, workspace="test_ws", path=str(p), title="Semantic Test Project")


def _valid_source() -> Source:
    return Source(
        id="src_valid_1",
        title="Valid Scientific Study on Attention Mechanisms",
        authors=["Vaswani, A.", "Shazeer, N."],
        year=2017,
        venue="NeurIPS",
        volume=30,
        issue=1,
        pages="6000–6010",
        doi="10.48550/arXiv.1706.03762",
        state=SourceState.APPROVED,
        abstract="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
    )


class _FakeMatchingProvider:
    name = "fake_provider"

    def lookup_by_doi(self, doi: str) -> Source | None:
        return Source(
            id="src_valid_1",
            title="Valid Scientific Study on Attention Mechanisms",
            authors=["Vaswani, A.", "Shazeer, N."],
            year=2017,
            doi=doi,
            state=SourceState.APPROVED,
        )

    def lookup_by_bibliographic(self, title: str, authors: list[str] | None = None, year: int | None = None) -> Source | None:
        return Source(
            id="src_valid_1",
            title=title,
            authors=authors or ["Vaswani, A."],
            year=year or 2017,
            state=SourceState.APPROVED,
        )


def _valid_evidence(claim_id: str, source_id: str) -> Evidence:
    return Evidence(
        id="evd_valid_1",
        claim_id=claim_id,
        source_id=source_id,
        evidence_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        location=EvidenceLocation(locator="abstract", page=6000),
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        quote_verified=True,
    )


# ---------------------------------------------------------------------------
# 1. Claim SUPPORTED but evidence mismatch -> rejected / NEEDS_HUMAN_REVIEW
# ---------------------------------------------------------------------------
def test_claim_supported_status_but_evidence_mismatch_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "test_1")
    source = _valid_source()
    claim = Claim(
        id="clm_1",
        claim_text="Intervensi diet ketogenik menyembuhkan penyakit Alzheimer secara permanen.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source.id],
        supporting_evidence=["evd_mismatch"],
    )
    # Evidence text talks about coffee consumption, completely irrelevant to the claim
    evidence = Evidence(
        id="evd_mismatch",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="Studi ini mengevaluasi kebiasaan minum kopi pada orang dewasa di pedesaan.",
        location=EvidenceLocation(locator="abstract"),
        relationship=EvidenceRelationship.SUPPORTS,
    )
    # Semantic review by external agent reveals evidence mismatch / refuted
    review = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.REFUTED,
        reason="Isi evidence membahas konsumsi kopi, tidak ada data mengenai diet ketogenik atau Alzheimer.",
        evidence_id=evidence.id,
        source_id=source.id,
        evidence_excerpt="Studi ini mengevaluasi kebiasaan minum kopi...",
    )

    response = FactAuditAgent().execute(
        FactAuditRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            semantic_reviews=[review],
        )
    )

    assert response.passed is False
    assert response.semantic_passed is False
    assert any("REFUTED" in r for r in response.rejection_reasons)
    assert claim.id in response.unsupported_claims


# ---------------------------------------------------------------------------
# 2. Important claim without semantic review -> final output rejected
# ---------------------------------------------------------------------------
def test_important_claim_without_semantic_review_final_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "test_2")
    source = _valid_source()
    claim = Claim(
        id="clm_important",
        claim_text="Teknologi transformer meningkatkan efisiensi komputasi bahasa secara signifikan.",
        importance=ClaimImportance.HIGH,  # Important claim!
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source.id],
        supporting_evidence=["evd_valid_1"],
    )
    evidence = _valid_evidence(claim.id, source.id)
    outline = Outline(
        title="Document Outline",
        sections=[OutlineSection(title="Section 1", claim_ids=[claim.id])],
    )

    # Execute workflow with NO semantic review passed
    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
            semantic_reviews=[],  # Explicitly empty
        )
    )

    assert response.success is False
    # Draft is produced for diagnostic inspection, but final DOCX is NOT generated!
    assert (project.directory / "draft.md").exists()
    assert not (project.directory / "final.docx").exists()

    # Fact audit report records the failure
    fact_audit_file = project.directory / "fact_audit.json"
    assert fact_audit_file.exists()
    audit_data = json.loads(fact_audit_file.read_text(encoding="utf-8"))
    assert audit_data["passed"] is False
    assert audit_data["semantic_passed"] is False
    assert any("no semantic review" in r for r in audit_data["rejection_reasons"])


# ---------------------------------------------------------------------------
# 3. Claim with fake/nonexistent evidence ID -> rejected
# ---------------------------------------------------------------------------
def test_claim_with_fake_evidence_id_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "test_3")
    source = _valid_source()
    claim = Claim(
        id="clm_fake",
        claim_text="Klaim dengan evidence palsu.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source.id],
        supporting_evidence=["evd_palsu_ghost"],  # Fake ID
    )
    evidence = _valid_evidence(claim.id, source.id)
    outline = Outline(
        title="Doc Outline",
        sections=[OutlineSection(title="S1", claim_ids=[claim.id])],
    )

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
        )
    )
    assert response.success is False
    assert not (project.directory / "final.docx").exists()


# ---------------------------------------------------------------------------
# 4. REFUTED claim -> rejected
# ---------------------------------------------------------------------------
def test_refuted_claim_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "test_4")
    source = _valid_source()
    claim = Claim(
        id="clm_refuted",
        claim_text="Bumi itu datar.",
        importance=ClaimImportance.MEDIUM,
        status=ClaimStatus.REFUTED,
        supporting_sources=[source.id],
    )

    response = FactAuditAgent().execute(
        FactAuditRequest(
            project=project,
            claims=[claim],
            sources=[source],
        )
    )
    assert response.passed is False
    assert any("REFUTED" in r for r in response.rejection_reasons)


# ---------------------------------------------------------------------------
# 5. PARTIALLY_SUPPORTED claim without qualifier -> rejected
# ---------------------------------------------------------------------------
def test_partially_supported_claim_without_qualifier_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "test_5")
    source = _valid_source()
    claim = Claim(
        id="clm_partial",
        claim_text="Intervensi ini efektif untuk seluruh kelompok anak dan remaja.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.PARTIALLY_SUPPORTED,
        qualifier=None,  # Missing mandatory qualifier!
        supporting_sources=[source.id],
        supporting_evidence=["evd_valid_1"],
    )
    evidence = _valid_evidence(claim.id, source.id)
    review = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.PARTIALLY_SUPPORTED,
        reason="Hanya terbukti pada kelompok usia 12-14 tahun, belum terbukti pada seluruh usia.",
        evidence_id=evidence.id,
        source_id=source.id,
    )

    response = FactAuditAgent().execute(
        FactAuditRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            semantic_reviews=[review],
        )
    )
    assert response.passed is False
    assert any("qualifier" in r.lower() for r in response.rejection_reasons)


# ---------------------------------------------------------------------------
# 6. Fully supported claim with source, evidence, location & review -> passes
# ---------------------------------------------------------------------------
def test_fully_supported_claim_with_valid_source_evidence_location_and_review_passes(tmp_path: Path) -> None:
    project = _project(tmp_path, "test_6")
    source = _valid_source()
    claim = Claim(
        id="clm_valid",
        claim_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        support_level=SupportLevel.STRONG,
        supporting_sources=[source.id],
        supporting_evidence=["evd_valid_1"],
    )
    evidence = _valid_evidence(claim.id, source.id)
    review = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.SUPPORTED,
        reason="Kutipan empiris abstrak Vaswani (2017) mendukung penuh pernyataan klaim.",
        evidence_id=evidence.id,
        source_id=source.id,
        evidence_excerpt=evidence.evidence_text,
        location="p. 6000, §Abstract",
    )
    outline = Outline(
        title="Valid Research Output",
        sections=[OutlineSection(title="Findings", claim_ids=[claim.id])],
    )

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
            semantic_reviews=[review],
            verification_engine=VerificationEngine(providers=[_FakeMatchingProvider()]),
        )
    )

    assert response.success is True
    assert (project.directory / "draft.md").exists()
    assert (project.directory / "final.docx").exists()

    fact_audit_file = project.directory / "fact_audit.json"
    audit_data = json.loads(fact_audit_file.read_text(encoding="utf-8"))
    assert audit_data["passed"] is True
    assert audit_data["structural_passed"] is True
    assert audit_data["semantic_passed"] is True
    assert audit_data["unsupported_claims"] == []


# ---------------------------------------------------------------------------
# 7. Incomplete author metadata -> marked [sumber belum lengkap]
# ---------------------------------------------------------------------------
def test_incomplete_author_metadata_marked_sumber_belum_lengkap(tmp_path: Path) -> None:
    source = Source(
        id="src_incomplete",
        title="Anonymous Report Without Declared Authors",
        authors=[],  # Incomplete authors!
        year=2023,
        venue="Working Papers",
    )
    entry = format_reference(source)
    assert "[missing: author]" in entry.formatted or "[sumber belum lengkap]" in entry.formatted
    assert "author" in entry.missing_fields

    project = _project(tmp_path, "test_7")
    response = FactAuditAgent().execute(
        FactAuditRequest(
            project=project,
            claims=[],
            sources=[source],
        )
    )
    assert len(response.bibliographic_findings) >= 1
    assert response.bibliographic_findings[0]["marker"] == "[sumber belum lengkap]"


# ---------------------------------------------------------------------------
# 8. Output containing internal tokens -> rejected
# ---------------------------------------------------------------------------
def test_output_containing_internal_tokens_rejected() -> None:
    source = _valid_source()
    dirty_drafts = [
        "Temuan ini didukung oleh data turn0search1 dalam teks.",
        "Lihat hasil pada view5filecite2.",
        "Kutipan dari sumber 【turn2search0】.",
        "Hasil ekstraksi filecite menunjukkan perbedaan signifikan.",
    ]
    for draft in dirty_drafts:
        violations = scan_output_text(draft=draft, sources=[source])
        assert violations, f"Expected output scan to reject dirty draft: {draft}"
        assert any("internal citation tokens" in v for v in violations)


# ---------------------------------------------------------------------------
# 9. Safe legacy workflow continues to operate according to its contract
# ---------------------------------------------------------------------------
def test_safe_legacy_workflow_operates_according_to_contract(tmp_path: Path) -> None:
    project = _project(tmp_path, "test_9")
    source = _valid_source()
    # Ordinary supporting statement (medium importance)
    claim = Claim(
        id="clm_legacy",
        claim_text="Model jaringan saraf tiruan memproses representasi data secara berlapis.",
        importance=ClaimImportance.MEDIUM,
        status=ClaimStatus.SUPPORTED,
        support_level=SupportLevel.STRONG,
        supporting_sources=[source.id],
        supporting_evidence=["evd_legacy"],
    )
    evidence = Evidence(
        id="evd_legacy",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="Model jaringan saraf tiruan memproses representasi data secara berlapis.",
        location=EvidenceLocation(locator="abstract"),
        relationship=EvidenceRelationship.SUPPORTS,
        quote_verified=True,
    )
    outline = Outline(
        title="Legacy Safe Outline",
        sections=[OutlineSection(title="Overview", claim_ids=[claim.id])],
    )

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
        )
    )

    assert response.success is True
    assert (project.directory / "draft.md").exists()
    assert (project.directory / "final.docx").exists()

    fact_audit_file = project.directory / "fact_audit.json"
    audit_data = json.loads(fact_audit_file.read_text(encoding="utf-8"))
    assert audit_data["passed"] is True
    assert audit_data["structural_passed"] is True


# ---------------------------------------------------------------------------
# 10. Overclaiming check: strong causal claims with preliminary evidence
# ---------------------------------------------------------------------------
def test_overclaim_with_preliminary_evidence_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "test_overclaim")
    source = _valid_source()
    claim = Claim(
        id="clm_overclaim",
        claim_text="Intervensi ini membuktikan pencegahan stres secara permanen.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        qualifier=None,  # Missing qualifier for strong assertion!
        supporting_sources=[source.id],
        supporting_evidence=["evd_pilot"],
    )
    evidence = Evidence(
        id="evd_pilot",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="Studi pilot observasional pada 12 responden menunjukkan indikasi awal.",
        location=EvidenceLocation(locator="abstract"),
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.WEAK,
    )
    response = FactAuditAgent().execute(
        FactAuditRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            semantic_reviews=[SemanticReview(claim_id=claim.id, decision=SemanticDecision.SUPPORTED, reason="Preliminary pilot")],
        )
    )
    assert response.passed is False
    assert any("strong claim" in r for r in response.rejection_reasons)
    assert len(response.overclaim_findings) >= 1


# ===========================================================================
# 4 Anti-Hallucination Bypass Regression Tests (11 Negatives + 1 Positive)
# ===========================================================================

class _FakeUnrelatedProvider:
    name = "fake_unrelated"

    def lookup_by_doi(self, doi: str) -> Source | None:
        if doi == "10.9999/definitely.fake.2026":
            return None
        return Source(
            id="src_other",
            title="An Unrelated Study on Deep Sea Fish Biology",
            authors=["Ichthyologist, A."],
            year=2020,
            doi=doi,
            state=SourceState.APPROVED,
        )

    def lookup_by_bibliographic(self, title: str, authors: list[str] | None = None, year: int | None = None) -> Source | None:
        return None


# 1. Negative: SUPPORTED review tanpa rincian bukti ditolak
def test_regression_supported_review_without_evidence_details_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "reg_empty_rev")
    source = _valid_source()
    claim = Claim(
        id="clm_empty_rev",
        claim_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source.id],
        supporting_evidence=["evd_valid_1"],
    )
    evidence = _valid_evidence(claim.id, source.id)
    # Empty review payload: only claim_id and decision
    empty_review = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.SUPPORTED,
        reason="",  # empty!
        evidence_id=None,
        source_id=None,
        evidence_excerpt=None,
        location=None,
    )
    outline = Outline(title="T", sections=[OutlineSection(title="S", claim_ids=[claim.id])])

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
            semantic_reviews=[empty_review],
            verification_engine=VerificationEngine(providers=[_FakeMatchingProvider()]),
        )
    )
    assert response.success is False
    assert (project.directory / "draft.md").exists()
    assert not (project.directory / "final.docx").exists()

    fact_file = project.directory / "fact_audit.json"
    audit_data = json.loads(fact_file.read_text(encoding="utf-8"))
    assert audit_data["passed"] is False
    assert any("missing required fields" in r for r in audit_data["rejection_reasons"])


# 2. Negative: Evidence dan excerpt hanya berbagi satu kata umum ditolak
def test_regression_evidence_and_excerpt_sharing_only_one_common_word_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "reg_one_word")
    source = _valid_source()
    claim = Claim(
        id="clm_oneword",
        claim_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source.id],
        supporting_evidence=["evd_oneword"],
    )
    evidence = Evidence(
        id="evd_oneword",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        location=EvidenceLocation(locator="abstract", page=6000),
        quote_verified=True,
    )
    # Excerpt only shares single word 'transformers' with completely different text
    review = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.SUPPORTED,
        reason="Mengklaim mendukung padahal kutipan berbeda.",
        evidence_id=evidence.id,
        source_id=source.id,
        evidence_excerpt="Transformers are electric devices designed to convert alternating currents between voltages.",
        location="p. 6000, §Abstract",
    )
    outline = Outline(title="T", sections=[OutlineSection(title="S", claim_ids=[claim.id])])

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
            semantic_reviews=[review],
            verification_engine=VerificationEngine(providers=[_FakeMatchingProvider()]),
        )
    )
    assert response.success is False
    assert not (project.directory / "final.docx").exists()

    fact_file = project.directory / "fact_audit.json"
    audit_data = json.loads(fact_file.read_text(encoding="utf-8"))
    assert audit_data["passed"] is False
    assert any("exact substring" in r for r in audit_data["rejection_reasons"])


# 3. Negative: Klaim MEDIUM berisi sebab-akibat dan angka tanpa semantic review ditolak
def test_regression_medium_claim_causal_numeric_without_semantic_review_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "reg_medium_causal")
    source = Source(
        id="src_med",
        title="Dietary intervention study",
        authors=["Nutritionist, N."],
        year=2021,
        state=SourceState.APPROVED,
        abstract="Intervensi diet rendah gula menyebabkan penurunan berat badan sebesar 15 persen secara konsisten.",
    )
    claim = Claim(
        id="clm_med_causal",
        claim_text="Intervensi diet rendah gula menyebabkan penurunan berat badan sebesar 15 persen secara konsisten.",
        importance=ClaimImportance.MEDIUM,  # MEDIUM priority!
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source.id],
        supporting_evidence=["evd_med"],
    )
    assert requires_semantic_review(claim) is True

    evidence = Evidence(
        id="evd_med",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="Intervensi diet rendah gula menyebabkan penurunan berat badan sebesar 15 persen secara konsisten.",
        location=EvidenceLocation(locator="abstract"),
        quote_verified=True,
    )
    outline = Outline(title="T", sections=[OutlineSection(title="S", claim_ids=[claim.id])])

    # No semantic review supplied
    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
            semantic_reviews=[],
            verification_engine=VerificationEngine(providers=[_FakeMatchingProvider()]),
        )
    )
    assert response.success is False
    assert not (project.directory / "final.docx").exists()

    fact_file = project.directory / "fact_audit.json"
    audit_data = json.loads(fact_file.read_text(encoding="utf-8"))
    assert audit_data["passed"] is False
    assert any("consequential claim has no semantic review record" in r for r in audit_data["rejection_reasons"])


# 4. Negative: Duplicate semantic review untuk satu claim ditolak
def test_regression_duplicate_semantic_review_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "reg_dup_rev")
    source = _valid_source()
    claim = Claim(
        id="clm_dup",
        claim_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source.id],
        supporting_evidence=["evd_valid_1"],
    )
    evidence = _valid_evidence(claim.id, source.id)
    rev1 = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.SUPPORTED,
        reason="First review rationale.",
        evidence_id=evidence.id,
        source_id=source.id,
        evidence_excerpt=evidence.evidence_text,
        location="p. 6000, §Abstract",
    )
    rev2 = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.SUPPORTED,
        reason="Second competing review rationale.",
        evidence_id=evidence.id,
        source_id=source.id,
        evidence_excerpt=evidence.evidence_text,
        location="p. 6000, §Abstract",
    )
    outline = Outline(title="T", sections=[OutlineSection(title="S", claim_ids=[claim.id])])

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
            semantic_reviews=[rev1, rev2],  # Duplicate!
            verification_engine=VerificationEngine(providers=[_FakeMatchingProvider()]),
        )
    )
    assert response.success is False
    assert not (project.directory / "final.docx").exists()

    fact_file = project.directory / "fact_audit.json"
    audit_data = json.loads(fact_file.read_text(encoding="utf-8"))
    assert audit_data["passed"] is False
    assert any("duplicate semantic reviews" in r for r in audit_data["rejection_reasons"])


# 5. Negative: Review menunjuk evidence milik claim lain ditolak
def test_regression_review_pointing_to_evidence_of_another_claim_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "reg_evd_wrong_claim")
    source = _valid_source()
    claim_a = Claim(
        id="clm_A",
        claim_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source.id],
        supporting_evidence=["evd_for_B"],
    )
    evidence_b = Evidence(
        id="evd_for_B",
        claim_id="clm_B",  # Belongs to claim B!
        source_id=source.id,
        evidence_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        location=EvidenceLocation(locator="abstract"),
        quote_verified=True,
    )
    review = SemanticReview(
        claim_id=claim_a.id,
        decision=SemanticDecision.SUPPORTED,
        reason="Cross-claim evidence pointer.",
        evidence_id=evidence_b.id,
        source_id=source.id,
        evidence_excerpt=evidence_b.evidence_text,
        location="abstract",
    )
    response = FactAuditAgent().execute(
        FactAuditRequest(
            project=project,
            claims=[claim_a],
            evidence=[evidence_b],
            sources=[source],
            semantic_reviews=[review],
            verification_engine=VerificationEngine(providers=[_FakeMatchingProvider()]),
        )
    )
    assert response.passed is False
    assert any("belongs to claim 'clm_B', not 'clm_A'" in r for r in response.rejection_reasons)


# 6. Negative: Review menunjuk source yang berbeda dari source evidence ditolak
def test_regression_review_source_mismatch_from_evidence_source_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "reg_src_mismatch")
    source_1 = _valid_source()
    source_2 = Source(id="src_other_2", title="Other Paper", authors=["O."], year=2020, state=SourceState.APPROVED)
    claim = Claim(
        id="clm_src_mismatch",
        claim_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source_1.id, source_2.id],
        supporting_evidence=["evd_valid_1"],
    )
    evidence = _valid_evidence(claim.id, source_1.id)
    # Review erroneously points to source_2 while evidence came from source_1
    review = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.SUPPORTED,
        reason="Mismatched source pointer.",
        evidence_id=evidence.id,
        source_id=source_2.id,  # Mismatch!
        evidence_excerpt=evidence.evidence_text,
        location="p. 6000, §Abstract",
    )
    response = FactAuditAgent().execute(
        FactAuditRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source_1, source_2],
            semantic_reviews=[review],
            verification_engine=VerificationEngine(providers=[_FakeMatchingProvider()]),
        )
    )
    assert response.passed is False
    assert any("does not match review source" in r for r in response.rejection_reasons)


# 7. Negative: Klaim penting hanya didukung MODEL_PARAPHRASE ditolak
def test_regression_consequential_claim_supported_only_by_model_paraphrase_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "reg_only_paraphrase")
    source = _valid_source()
    claim = Claim(
        id="clm_paraphrase",
        claim_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source.id],
        supporting_evidence=["evd_paraphrase"],
    )
    evidence = Evidence(
        id="evd_paraphrase",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="Arsitektur ini memanfaatkan mekanisme atensi tanpa komponen rekuren.",
        location=EvidenceLocation(locator="abstract"),
        extraction_method=ExtractionMethod.MODEL_PARAPHRASE,
        verbatim=False,  # Not verbatim!
        quote_verified=False,
    )
    review = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.SUPPORTED,
        reason="Model paraphrase evaluation.",
        evidence_id=evidence.id,
        source_id=source.id,
        evidence_excerpt=evidence.evidence_text,
        location="abstract",
    )
    response = FactAuditAgent().execute(
        FactAuditRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            semantic_reviews=[review],
            verification_engine=VerificationEngine(providers=[_FakeMatchingProvider()]),
        )
    )
    assert response.passed is False
    assert any("MODEL_PARAPHRASE cannot be the sole evidence" in r for r in response.rejection_reasons)


# 8. Negative: quote_verified: true dari payload tanpa teks sumber ditolak
def test_regression_quote_verified_true_without_source_text_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "reg_quote_no_source_text")
    # Source has no abstract and no retrieval_path
    source_no_text = Source(
        id="src_no_text",
        title="Paper Without Abstract Or Retrieval Path",
        authors=["Author, A."],
        year=2022,
        state=SourceState.APPROVED,
        abstract=None,
        retrieval_path=None,
    )
    claim = Claim(
        id="clm_no_srctext",
        claim_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source_no_text.id],
        supporting_evidence=["evd_fake_quote"],
    )
    evidence = Evidence(
        id="evd_fake_quote",
        claim_id=claim.id,
        source_id=source_no_text.id,
        evidence_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        location=EvidenceLocation(locator="abstract"),
        extraction_method=ExtractionMethod.VERBATIM_ABSTRACT,
        verbatim=True,
        quote_verified=True,  # Forged flag on input!
    )
    review = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.SUPPORTED,
        reason="Asserted verbatim quote.",
        evidence_id=evidence.id,
        source_id=source_no_text.id,
        evidence_excerpt=evidence.evidence_text,
        location="abstract",
    )
    response = FactAuditAgent().execute(
        FactAuditRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source_no_text],
            semantic_reviews=[review],
            verification_engine=VerificationEngine(providers=[_FakeMatchingProvider()]),
        )
    )
    assert response.passed is False
    assert any("source text for source 'src_no_text' is unavailable to recompute quote validity" in r for r in response.rejection_reasons)


# 9. Negative: Sumber fiktif dengan DOI definitely.fake.2026 dan state buatan APPROVED ditolak
def test_regression_fake_source_with_fake_doi_and_forged_approved_state_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "reg_fake_doi")
    fake_source = Source(
        id="src_fake_doi",
        title="A Completely Invented Study",
        authors=["Fraudster, F."],
        year=2026,
        doi="10.9999/definitely.fake.2026",
        state=SourceState.APPROVED,  # Forged state on payload!
        abstract="Completely fabricated abstract text for testing.",
    )
    claim = Claim(
        id="clm_fake_src",
        claim_text="Klaim berlandaskan studi yang sepenuhnya fiktif dengan DOI palsu.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[fake_source.id],
        supporting_evidence=["evd_fake_src"],
    )
    evidence = Evidence(
        id="evd_fake_src",
        claim_id=claim.id,
        source_id=fake_source.id,
        evidence_text="Completely fabricated abstract text for testing.",
        location=EvidenceLocation(locator="abstract"),
        extraction_method=ExtractionMethod.VERBATIM_ABSTRACT,
        verbatim=True,
        quote_verified=True,
    )
    review = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.SUPPORTED,
        reason="Semantically consistent with fabricated text.",
        evidence_id=evidence.id,
        source_id=fake_source.id,
        evidence_excerpt=evidence.evidence_text,
        location="abstract",
    )
    outline = Outline(title="T", sections=[OutlineSection(title="S", claim_ids=[claim.id])])

    # Provider cannot corroborate the fake DOI
    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[fake_source],
            outline=outline,
            semantic_reviews=[review],
            verification_engine=VerificationEngine(providers=[_FakeUnrelatedProvider()]),
        )
    )
    assert response.success is False
    assert (project.directory / "draft.md").exists()
    assert not (project.directory / "final.docx").exists()

    fact_file = project.directory / "fact_audit.json"
    audit_data = json.loads(fact_file.read_text(encoding="utf-8"))
    assert audit_data["passed"] is False
    assert any("failed provider verification" in r for r in audit_data["rejection_reasons"])
    # Verification report preserved in audit trail
    assert len(audit_data["verification_reports"]) >= 1


# 10. Negative: Provider tidak tersedia -> status NEEDS_HUMAN_REVIEW dan DOCX diblokir
def test_regression_provider_unavailable_requires_human_review(tmp_path: Path) -> None:
    project = _project(tmp_path, "reg_prov_unavailable")
    source = _valid_source()
    claim = Claim(
        id="clm_unavail",
        claim_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source.id],
        supporting_evidence=["evd_valid_1"],
    )
    evidence = _valid_evidence(claim.id, source.id)
    review = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.SUPPORTED,
        reason="Kutipan empiris abstrak Vaswani (2017) mendukung penuh pernyataan klaim.",
        evidence_id=evidence.id,
        source_id=source.id,
        evidence_excerpt=evidence.evidence_text,
        location="p. 6000, §Abstract",
    )
    outline = Outline(title="T", sections=[OutlineSection(title="S", claim_ids=[claim.id])])

    # Provider list is empty (providers unreachable / unavailable)
    empty_engine = VerificationEngine(providers=[])
    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
            semantic_reviews=[review],
            verification_engine=empty_engine,
        )
    )
    assert response.success is False
    assert (project.directory / "draft.md").exists()
    assert not (project.directory / "final.docx").exists()

    fact_file = project.directory / "fact_audit.json"
    audit_data = json.loads(fact_file.read_text(encoding="utf-8"))
    assert audit_data["passed"] is False
    assert any("failed provider verification: state=NEEDS_HUMAN_REVIEW" in r for r in audit_data["rejection_reasons"])


# 11. Negative: Metadata provider tidak cocok dengan metadata input ditolak
def test_regression_provider_metadata_mismatch_rejected(tmp_path: Path) -> None:
    project = _project(tmp_path, "reg_prov_mismatch")
    # Candidate source has title on attention mechanisms with DOI 10.1038/nature14539
    source = Source(
        id="src_mismatch_doi",
        title="Valid Scientific Study on Attention Mechanisms",
        authors=["Vaswani, A."],
        year=2017,
        doi="10.1038/mismatch.doi",
        state=SourceState.APPROVED,
        abstract="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
    )
    claim = Claim(
        id="clm_mismatch_meta",
        claim_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        supporting_sources=[source.id],
        supporting_evidence=["evd_meta"],
    )
    evidence = Evidence(
        id="evd_meta",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        location=EvidenceLocation(locator="abstract"),
        quote_verified=True,
    )
    review = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.SUPPORTED,
        reason="Claim-evidence evaluation.",
        evidence_id=evidence.id,
        source_id=source.id,
        evidence_excerpt=evidence.evidence_text,
        location="abstract",
    )
    outline = Outline(title="T", sections=[OutlineSection(title="S", claim_ids=[claim.id])])

    # Provider resolves DOI to completely unrelated work ("An Unrelated Study on Deep Sea Fish Biology")
    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
            semantic_reviews=[review],
            verification_engine=VerificationEngine(providers=[_FakeUnrelatedProvider()]),
        )
    )
    assert response.success is False
    assert (project.directory / "draft.md").exists()
    assert not (project.directory / "final.docx").exists()

    fact_file = project.directory / "fact_audit.json"
    audit_data = json.loads(fact_file.read_text(encoding="utf-8"))
    assert audit_data["passed"] is False
    assert any("failed provider verification" in r for r in audit_data["rejection_reasons"])


# 12. Positive: Sumber terverifikasi, evidence verbatim dari abstract, review lengkap -> final DOCX berhasil
def test_regression_positive_verified_source_verbatim_evidence_full_review_produces_docx(tmp_path: Path) -> None:
    project = _project(tmp_path, "reg_positive_end_to_end")
    source = _valid_source()
    claim = Claim(
        id="clm_pos_valid",
        claim_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        importance=ClaimImportance.HIGH,
        status=ClaimStatus.SUPPORTED,
        support_level=SupportLevel.STRONG,
        supporting_sources=[source.id],
        supporting_evidence=["evd_pos_1"],
    )
    evidence = Evidence(
        id="evd_pos_1",
        claim_id=claim.id,
        source_id=source.id,
        evidence_text="Transformers rely on multi-head attention mechanisms to model dependencies without recurrent connections.",
        location=EvidenceLocation(locator="abstract", page=6000),
        relationship=EvidenceRelationship.SUPPORTS,
        strength=EvidenceStrength.STRONG,
        extraction_method=ExtractionMethod.VERBATIM_ABSTRACT,
        verbatim=True,
        quote_verified=True,
    )
    review = SemanticReview(
        claim_id=claim.id,
        decision=SemanticDecision.SUPPORTED,
        reason="Kutipan empiris abstrak Vaswani (2017) mendukung penuh pernyataan klaim.",
        evidence_id=evidence.id,
        source_id=source.id,
        evidence_excerpt=evidence.evidence_text,
        location="p. 6000, §Abstract",
        reviewer="antigravity_agent",
        method="semantic_evaluation",
    )
    outline = Outline(
        title="Positive Verified Output",
        sections=[OutlineSection(title="Results", claim_ids=[claim.id])],
    )

    response = AcademicWritingWorkflow().execute(
        AcademicWritingRequest(
            project=project,
            claims=[claim],
            evidence=[evidence],
            sources=[source],
            outline=outline,
            semantic_reviews=[review],
            verification_engine=VerificationEngine(providers=[_FakeMatchingProvider()]),
        )
    )

    assert response.success is True
    assert (project.directory / "draft.md").exists()
    assert (project.directory / "final.docx").exists()

    fact_file = project.directory / "fact_audit.json"
    audit_data = json.loads(fact_file.read_text(encoding="utf-8"))
    assert audit_data["passed"] is True
    assert audit_data["structural_passed"] is True
    assert audit_data["semantic_passed"] is True
    assert audit_data["unsupported_claims"] == []
    assert audit_data["rejection_reasons"] == []
    assert len(audit_data["verification_reports"]) >= 1
