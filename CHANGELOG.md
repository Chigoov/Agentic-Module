# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.1.0] - 2026-09-14

### Added
- **Epistemic Evidence Classification (`EvidenceType`)**: Added 7-category epistemic classification enum (`DIRECT`, `PARTIAL`, `THEORETICAL`, `FUNCTIONAL_EQUIVALENT`, `BACKGROUND`, `CONTRADICTORY`, `NOT_SUPPORTED`) in `src/schemas/evidence.py`.
- **Reading Depth Tracking (`ReadingDepth`)**: Added 4-category reading depth classification enum (`FULL_TEXT`, `ABSTRACT_ONLY`, `METADATA_ONLY`, `UNAVAILABLE`) in `src/schemas/evidence.py` with model validation preventing verbatim full-text claims on abstract-only reads.
- **Retrieval Status Tracking (`RetrievalStatus`)**: Added retrieval status tracking enum (`RETRIEVED`, `PARTIAL`, `FAILED`, `NOT_ATTEMPTED`) and state transition guard in `src/schemas/source.py`.
- **Structured Evidence Extraction**: Added 8 structured extraction fields to `Evidence` model: `normalized_finding`, `population`, `sample_size`, `methodology`, `variables`, `instruments`, `statistical_result`, and `limitations`.
- **Publisher & Database Indexing Verification**: Added `publisher_verified: bool` and `index_status: dict[str, bool]` fields to `Source` model.
- **Research Provenance Chains**: Created `ProvenanceRecord` schema and `build_provenance_chain` workflow in `src/workflows/provenance.py` for end-to-end evidence traceability persisted to `provenance.jsonl`.
- **Claim-Evidence-Source Mapping Graph**: Added `build_evidence_graph` and `summarize_evidence_graph` workflows in `src/workflows/evidence_graph.py` with broken reference detection, persisted to `evidence_graph.json`.
- **Contradiction Detection Engine**: Added `detect_contradictions` workflow in `src/workflows/contradiction.py` detecting mixed evidence, extracting contradictory excerpts, capturing null findings, and computing conflict severity scores (`HIGH`, `MEDIUM`, `LOW`).
- **Evidence Verification Audit Workflow**: Added `audit_evidence` in `src/workflows/evidence_audit.py` detecting unverified verbatim quotes, depth/method mismatches, and type/relationship conflicts.
- **Human Review Queue**: Created `ReviewItem` and `ReviewQueue` in `src/schemas/review.py` supporting severity-based filtering, atomic persistence to `review_queue.json`, and blocking checks for `CRITICAL` items.
- **Extended Integrity Gate Checks**: Added 7 new checks to `check_academic_integrity` in `src/workflows/gates.py`:
  - Check 7: DOI format regex validation (`^10\.\d{4,}/\S+$`).
  - Check 8: Evidence type and relationship mismatch detection (`CONTRADICTORY` + `SUPPORTS`).
  - Check 9: Empty support detection on claims marked `SUPPORTED`.
  - Check 10: Overclaim detection for claims backed solely by indirect evidence.
  - Check 11: Abstract-only evidence detection generating review items.
  - Check 12: Unverified and unretrieved source detection.
  - Check 13: Publisher-unverified cited source review reasons.
  - Check 14: Unindexed source review reasons.
- **Storage Primitives for Audit Artifacts**: Added `save_evidence_graph`, `load_evidence_graph`, `save_provenance_chain`, and `load_provenance_chain` in `src/core/storage.py`.
- **Golden Research Test Fixture**: Added canonical TikTok Streak research fixture (`tests/fixtures/golden_tiktok_streak.py`) and comprehensive test suite (`tests/test_evidence_intelligence.py`) covering all 28 correctness properties (+59 tests, total 408 tests passing).

### Changed
- **Evidence Schema Versioning**: Incremented `schema_version` default to `"1.1"` for `Evidence`, `Source`, and `ReviewItem` while maintaining full backward-compatible deserialization for v1.0 records.
- **Support Level Heuristics (`compute_support_level`)**: Updated calculation in `src/workflows/evidence_flow.py` to degrade `THEORETICAL` and `FUNCTIONAL_EQUIVALENT` by one ladder level, cap `BACKGROUND` at `WEAK`, cap indirect evidence combinations at `MODERATE`, and exclude `NOT_SUPPORTED` evidence from positive support calculations.
- **Confidence Calibration (`calibrate_confidence`)**: Added epistemic confidence multipliers (`PARTIAL` 0.8, `FUNCTIONAL_EQUIVALENT` 0.7, `THEORETICAL` 0.6, `BACKGROUND` 0.3) and strict reading depth ceilings (0.5 for `ABSTRACT_ONLY`, 0.2 for `METADATA_ONLY`).
- **Claim Evaluation Flow (`evaluate_claim`)**: Integrated automated contradiction detection into claim evaluation; conflicted claims now disclose conflict severity in evaluation reasons.
- **Source State Machine Guard**: Enforced that sources with `retrieval_status == NOT_ATTEMPTED` cannot transition to `FULLTEXT_RETRIEVED`.

### Fixed
- **Overclaim Vulnerability**: Resolved vulnerability where claims backed entirely by conceptual theory or proxy platforms could be marked as empirically `SUPPORTED` with strong evidential weight.
- **Abstract Citation Drift**: Fixed issue allowing verbatim full-text extraction claims when sources were only retrieved or read at the abstract level.
- **Silent Unindexed Sources**: Eliminated silent omission of indexing verification by generating actionable review queue items when sources fail database corroboration.

### Security
- **Path Traversal Protection**: Enforced `ensure_within` boundary checks on all newly added storage operations (`evidence_graph.json`, `provenance.jsonl`, `review_queue.json`) to prevent writes outside project roots.
- **DOI Regular Expression Sanitization**: Applied strict regex validation to prevent malicious URLs or arbitrary strings from being injected into bibliographic records.

---

## [1.0.0] - 2026-09-07

### Added
- **Core AAI Platform**: Initial release of AUTONOMI AGENTIC ILMIAH (AAI).
- **Three-Level Source Verification**: Implemented verification engine covering Level 1 (Existence), Level 2 (Metadata Corroboration), and Level 3 (Content Verification).
- **Research Tools**: Integrated adapters for Crossref, OpenAlex, Semantic Scholar, PubMed, and Publish or Perish.
- **Evidence & Claim Registries**: Created in-memory and file-backed registries (`evidence.jsonl`, `claims.json`, `sources.json`).
- **APA 7 Citation & Reference Manager**: Deterministic in-text citation placement and bibliography formatting.
- **Academic Writing Flow & DOCX Generator**: Automated structured document compilation with humanizer pass and table rendering.
- **Initial Test Suite**: 349 unit and integration tests passing.

