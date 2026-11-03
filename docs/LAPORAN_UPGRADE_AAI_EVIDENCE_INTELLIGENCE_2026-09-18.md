# COMPREHENSIVE SYSTEM UPGRADE REPORT
## AAI Scientific Evidence Intelligence System (v1.1.0)
**Date:** September 18, 2026  
**System:** AUTONOMI AGENTIC ILMIAH (AAI)  
**Spec ID:** `aai-evidence-intelligence` (Fast-Task Feature Spec)  
**Build Phase:** Phase 18 Extended  
**Runtime Environment:** Python 3.11+ / Pydantic 2.x / Pytest 9.x / Windows PowerShell  
**Status:** FULLY IMPLEMENTED, TESTED, AND VERIFIED (408 passed, 0 failed, 10 deselected)  

---

## Executive Summary

This report documents the architectural and functional upgrade of **AUTONOMI AGENTIC ILMIAH (AAI)** from a literature search and summarization pipeline into a deterministic **Scientific Evidence Intelligence System (v1.1.0)**. 

Prior to this upgrade (v1.0.0), AAI effectively automated bibliographic queries, APA 7 citations, and basic fact audits. However, the system lacked epistemic nuance: it could not distinguish direct empirical findings from indirect proxies or theoretical models, did not track reading depth (allowing abstract reads to claim full-text verbatim authenticity), could not detect conflicting evidence automatically, and had no unified claim-evidence-source mapping graph or human review queue.

Under this upgrade, 18 formal requirements spanning epistemic evidence classification, reading depth constraints, retrieval state machines, publisher and database indexation corroboration, structured extraction, automated contradiction detection, evidence graph mapping, provenance persistence, and extended academic integrity gates were implemented. All 28 correctness properties were verified with **408 passing tests** (+59 new tests, 0 failures), maintaining 100% backward compatibility with legacy v1.0 records.

---

## 1. Repository State Before Upgrade

### 1.1 Baseline System Overview (v1.0.0 / Phase 18)
Before the Evidence Intelligence upgrade, AAI operated as a high-integrity academic drafting engine comprising:
- **Pydantic Schemas (`src/schemas/`)**: `BaseRecord`, `Source`, `Claim`, `Evidence`, `VerificationReport`.
- **Source State Machine**: Sources transitioned through `DISCOVERED` -> `EXISTENCE_VERIFIED` -> `METADATA_VERIFIED` -> `CONTENT_VERIFIED` -> `APPROVED`.
- **Research Adapters (`src/tools/`)**: Integration with Crossref, OpenAlex, Semantic Scholar, PubMed, and Publish or Perish.
- **Academic Writing Flow & Auditing (`src/workflows/`, `src/agents/`)**: Deterministic citation formatting (APA 7), two-pass writing with safe Indonesian humanizer, and fact audit bypass closures (closing empty reviews, token matching, and consequential unverified claims).
- **Test Baseline**: **349 passing tests** (unit and integration tests).

### 1.2 Identified System Limitations Prior to Upgrade
Despite rigorous anti-hallucination measures in v1.0.0, deep architectural gaps remained:
1. **Epistemic Invariance**: An `Evidence` record only tracked `relationship` (`SUPPORTS`, `PARTIALLY_SUPPORTS`, `CONTRADICTS`) and `strength` (`WEAK`, `MODERATE`, `STRONG`, `DEFINITIVE`). It could not distinguish empirical field experiments from conceptual frameworks, proxy platforms, or background context.
2. **Untracked Reading Depth**: The system recorded extraction methods (`VERBATIM_FULLTEXT`, `VERBATIM_ABSTRACT`, etc.) but did not track whether the researcher or tool had access to the full text, only the abstract, or solely bibliographic metadata. An abstract-only read could erroneously claim full-text verbatim extraction.
3. **Retrieval State Inconsistencies**: Sources could transition into `FULLTEXT_RETRIEVED` state even if retrieval had never been attempted (`NOT_ATTEMPTED`), creating phantom full-text references.
4. **Lack of Contradiction Modeling**: Claims with conflicting empirical findings were not automatically evaluated for contradiction severity, nor were null findings segregated from positive evidence.
5. **No Graph Traceability**: Assertions in drafted text could not be programmatically traversed backwards through a unified graph connecting Claim -> Evidence -> Source with specific page and section references.
6. **No Centralized Review Queue**: Gate warnings and semantic review flags were scattered across CLI logs rather than collected into a durable, prioritizeable review queue.

---

## 2. Problems Found and Resolutions

During the architectural audit and pre-implementation analysis, seven significant vulnerabilities and structural defects were identified. All were resolved with strict deterministic guards:

| Problem ID | Module & File | Severity | Vulnerability / Defect Description | Systemic Impact | Applied Resolution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **PROB-01** | `src/workflows/evidence_flow.py`<br>`src/workflows/gates.py` | **HIGH** | **Overclaim Vulnerability on Indirect Evidence:** Claims supported solely by theoretical models (`THEORETICAL`) or analog technology (`FUNCTIONAL_EQUIVALENT`) could achieve `SUPPORTED` status with `STRONG` support level. | Academic drafts made definitive empirical claims about novel phenomena without primary data (e.g., asserting TikTok Streaks cause connectedness based solely on Snapchat studies). | Created `EvidenceType` enum; degraded effective strength by 1 ladder level; capped indirect-only evidence at `MODERATE`; added Check 10 in `check_academic_integrity` to block overclaims with hard gate violations. |
| **PROB-02** | `src/schemas/evidence.py`<br>`src/workflows/evidence_audit.py` | **HIGH** | **Abstract-Level Verbatim Citation Drift:** Evidence records extracted from abstract-only reads could specify `extraction_method = VERBATIM_FULLTEXT`. | Created false impressions of comprehensive document review; risked out-of-context citation and unverified quote fabrication. | Added `ReadingDepth` enum; introduced Pydantic `@model_validator(mode="after")` blocking `VERBATIM_FULLTEXT` when `reading_depth == ABSTRACT_ONLY`; added audit flag `depth_method_mismatch`. |
| **PROB-03** | `src/schemas/source.py` | **MEDIUM** | **Premature State Transition to `FULLTEXT_RETRIEVED`:** Sources could advance to `FULLTEXT_RETRIEVED` state when `retrieval_status == NOT_ATTEMPTED`. | Downstream agents assumed full-text files existed on disk when no retrieval had occurred, causing IO crashes. | Added `RetrievalStatus` enum and transition guard in `Source.transition_to` raising `StateTransitionError` on unattempted retrievals. |
| **PROB-04** | `src/workflows/gates.py` | **MEDIUM** | **Unvalidated DOI Strings Allowing Malformed Identifiers:** Source DOIs were accepted as arbitrary strings without structural verification. | Permitted arbitrary URLs, truncated tokens, or fabricated non-DOI strings into academic bibliographies. | Implemented strict regex validation (`^10\.\d{4,}/\S+$`) in Check 7 of `check_academic_integrity`. |
| **PROB-05** | `src/workflows/gates.py`<br>`src/workflows/contradiction.py` | **MEDIUM** | **Conflicting Evidence Direction and Epistemic Classification:** An evidence record could be labeled `evidence_type = CONTRADICTORY` while concurrently declaring `relationship = SUPPORTS`. | Corrupted support level scoring and broke mathematical confidence calibration. | Added Check 8 in `check_academic_integrity` and `type_relationship_mismatch` flag in `audit_evidence`. |
| **PROB-06** | `src/schemas/source.py`<br>`src/workflows/gates.py` | **LOW-MEDIUM** | **Silent Citation of Unverified & Unindexed Sources:** Sources lacking publisher corroboration or recognized academic database indexing were cited without alert. | Predatory journals, uncorroborated preprints, or gray literature entered drafts without reviewer awareness. | Added `publisher_verified: bool` and `index_status: dict[str, bool]` to `Source`; added Checks 12, 13, and 14 in Integrity Gate to generate review reasons. |
| **PROB-07** | `src/workflows/evidence_graph.py` | **LOW-MEDIUM** | **Silent Broken References in Traceability:** Orphan evidence records referencing missing source IDs produced runtime KeyErrors during graph compilation. | Failed audit trail generation on partial payloads. | Built `build_evidence_graph` with explicit `broken_reference: True` edge tagging, allowing graceful degradation and reporting. |

---

## 3. Features Implemented

The upgrade fully satisfied all 18 requirements from the specification. There are **0 partially implemented** and **0 unimplemented** requirements.

### 3.1 Implementation Status Matrix

| Requirement | Description | Status | Implementation Target |
| :--- | :--- | :--- | :--- |
| **Req 1** | Epistemic Evidence Classification (`EvidenceType` enum with 7 members) | **FULLY IMPLEMENTED** | `src/schemas/evidence.py` |
| **Req 2** | Reading Depth Tracking (`ReadingDepth` enum with 4 members & model validator) | **FULLY IMPLEMENTED** | `src/schemas/evidence.py`, `src/schemas/source.py` |
| **Req 3** | Retrieval Status Tracking (`RetrievalStatus` enum & state machine guard) | **FULLY IMPLEMENTED** | `src/schemas/source.py` |
| **Req 4** | Publisher Verification Flag (`publisher_verified: bool` & gate check) | **FULLY IMPLEMENTED** | `src/schemas/source.py`, `src/workflows/gates.py` |
| **Req 5** | Database Index Status Tracking (`index_status: dict[str, bool]`) | **FULLY IMPLEMENTED** | `src/schemas/source.py`, `src/workflows/gates.py` |
| **Req 6** | Structured Evidence Extraction Fields (8 structured extraction fields) | **FULLY IMPLEMENTED** | `src/schemas/evidence.py` |
| **Req 7** | Claim-Evidence-Source Mapping Graph (`build_evidence_graph` & summary) | **FULLY IMPLEMENTED** | `src/workflows/evidence_graph.py` |
| **Req 8** | Evidence Verification Audit (`audit_evidence`, `AuditResult`, `AuditFlag`) | **FULLY IMPLEMENTED** | `src/workflows/evidence_audit.py` |
| **Req 9** | Research Provenance Records (`ProvenanceRecord`, `build_provenance_chain`) | **FULLY IMPLEMENTED** | `src/schemas/provenance_record.py`, `src/workflows/provenance.py` |
| **Req 10** | Extended Research Integrity Gate (Checks 7 through 14) | **FULLY IMPLEMENTED** | `src/workflows/gates.py` |
| **Req 11** | Contradiction Detection Engine (`detect_contradictions`, severity scoring) | **FULLY IMPLEMENTED** | `src/workflows/contradiction.py` |
| **Req 12** | Evidence Strength & Confidence Calibration Integration | **FULLY IMPLEMENTED** | `src/workflows/evidence_flow.py` |
| **Req 13** | Human Review Queue (`ReviewItem`, `ReviewQueue`, persistence) | **FULLY IMPLEMENTED** | `src/schemas/review.py`, `src/workflows/gates.py` |
| **Req 14** | Schema Backward Compatibility (v1.0 defaults infill, v1.1 versioning) | **FULLY IMPLEMENTED** | `src/schemas/base.py`, `src/schemas/evidence.py`, `src/schemas/source.py` |
| **Req 15** | Golden Test Case Validation (TikTok Streak Scenario Fixture) | **FULLY IMPLEMENTED** | `tests/fixtures/golden_tiktok_streak.py`, `tests/test_evidence_intelligence.py` |
| **Req 16** | Persistent Storage for New Records (with path boundary checks) | **FULLY IMPLEMENTED** | `src/core/storage.py`, `src/schemas/review.py` |
| **Req 17** | CLI Backward Compatibility (`run-academic`, `check`, `export-bundle`) | **FULLY IMPLEMENTED** | `src/runtime/cli.py`, `src/__main__.py` |
| **Req 18** | Comprehensive Test Coverage (28 Correctness Properties) | **FULLY IMPLEMENTED** | `tests/test_evidence_intelligence.py` |

### 3.2 Key Technical Capabilities Delivered

1. **Epistemic Classification (`EvidenceType`)**:
   - Members: `DIRECT`, `PARTIAL`, `THEORETICAL`, `FUNCTIONAL_EQUIVALENT`, `BACKGROUND`, `CONTRADICTORY`, `NOT_SUPPORTED`.
   - Independent dimension from `EvidenceRelationship` (direction) and `EvidenceStrength` (weight).
2. **Reading Depth Tracking (`ReadingDepth`)**:
   - Members: `FULL_TEXT`, `ABSTRACT_ONLY`, `METADATA_ONLY`, `UNAVAILABLE`.
   - Hard validator prevents `VERBATIM_FULLTEXT` extraction on `ABSTRACT_ONLY`.
   - Confidence ceilings: `0.5` for abstract-only, `0.2` for metadata-only.
3. **Structured Evidence Metadata**:
   - 8 optional fields added to `Evidence`: `normalized_finding`, `population`, `sample_size`, `methodology`, `variables`, `instruments`, `statistical_result`, `limitations`.
   - Omitted from JSON when `None` for compact storage.
4. **Automated Contradiction Detection**:
   - Analyzes claims with mixed evidence; computes `conflict_severity` (`HIGH`, `MEDIUM`, `LOW`).
   - Automatically shifts claim status to `CONFLICTED` and generates explicit disclosure requirements.
5. **Traceability & Provenance**:
   - `build_evidence_graph`: Produces JSON-serializable bipartite graph with broken reference detection.
   - `build_provenance_chain`: Generates 1:1 `ProvenanceRecord` items linking retrieval and verification timestamps from source state history to evidence locators.
6. **The 14 Integrity Gate Checks**:
   - Enforces referential integrity, authentic source states, DOI formatting regex, overclaim detection, abstract-only warnings, and indexing corroboration.
7. **Human Review Queue**:
   - Non-blocking warnings and semantic review triggers populate `ReviewItem` entries in `review_queue.json` grouped by severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).

---

## 4. Files Changed

Following the design principle **Extension > Refactor > Duplication**, no existing fields or files were deleted or renamed. All modifications are strictly additive.

### 4.1 Created Files (14 Files)

| File Path | Component | Purpose & Rationale |
| :--- | :--- | :--- |
| `src/schemas/provenance_record.py` | Schema Layer | Defines `ProvenanceRecord(SchemaModel)` for 1:1 claim-evidence-source audit trails. |
| `src/schemas/review.py` | Schema Layer | Defines `ReviewItem(BaseRecord)` and `ReviewQueue` for managing human-in-the-loop review queues. |
| `src/workflows/contradiction.py` | Workflow Layer | Implements `detect_contradictions`, `ContradictionReport`, `ContradictoryFinding`, and `NullFinding`. |
| `src/workflows/evidence_audit.py` | Workflow Layer | Implements `audit_evidence`, `AuditResult`, and `AuditFlag` for automated evidence quality audits. |
| `src/workflows/evidence_graph.py` | Workflow Layer | Implements `build_evidence_graph` and `summarize_evidence_graph` with broken reference handling. |
| `src/workflows/provenance.py` | Workflow Layer | Implements `build_provenance_chain` extracting timestamps from source transition history. |
| `tests/fixtures/golden_tiktok_streak.py` | Test Layer | Canonical research scenario fixture (TikTok Streak and social connectedness). |
| `tests/test_evidence_intelligence.py` | Test Layer | Comprehensive test suite containing 59 tests validating all 28 correctness properties. |
| `CHANGELOG.md` | Documentation | Formal changelog in Keep a Changelog format tracking v1.0.0 and v1.1.0 releases. |
| `EVIDENCE_SYSTEM.md` | Technical Docs | Exhaustive technical specification for the Evidence Intelligence architecture. |
| `RESEARCH_INTEGRITY.md` | Technical Docs | Reference documentation for the 14 Integrity Gate checks and anti-fabrication rules. |
| `SCHEMA.md` | Technical Docs | Full schema reference for Pydantic models, enums, fields, and backward compatibility. |
| `TESTING.md` | Technical Docs | Testing and QA guide mapping all 28 properties to test implementations. |
| `UPGRADE_REPORT.md` | Root Documentation | Comprehensive upgrade report at repository root. |

### 4.2 Modified Files (10 Files)

| File Path | Changes Made | Rationale |
| :--- | :--- | :--- |
| `src/schemas/evidence.py` | Added `EvidenceType`, `ReadingDepth` enums; added 8 structured extraction fields; added `@model_validator`; bumped `schema_version` default to `"1.1"`. | Implements Requirements 1, 2, 6, and 14. |
| `src/schemas/source.py` | Added `RetrievalStatus` enum, `reading_depth`, `retrieval_status`, `publisher_verified`, `index_status`; added `update_reading_depth()`; guarded `transition_to()`. | Implements Requirements 2, 3, 4, 5, and 14. |
| `src/schemas/__init__.py` | Exported `EvidenceType`, `ReadingDepth`, `RetrievalStatus`, `ProvenanceRecord`, `ReviewItem`, `ReviewQueue`. | Makes new schema entities accessible across project packages. |
| `src/workflows/evidence_flow.py` | Extended `compute_support_level` with `_effective_strength` ladder degradation; extended `calibrate_confidence` with multipliers and caps; wired `detect_contradictions` into `evaluate_claim`. | Implements Requirements 11 and 12. |
| `src/workflows/gates.py` | Added Checks 7-14 to `check_academic_integrity`; added helper to convert `review_reasons` into `ReviewQueue` items with severity mapping. | Implements Requirements 10 and 13. |
| `src/workflows/__init__.py` | Exported new workflow functions (`build_evidence_graph`, `audit_evidence`, `detect_contradictions`, `build_provenance_chain`). | Exposes new workflows to CLI and orchestrator. |
| `src/core/storage.py` | Added `save_evidence_graph`, `load_evidence_graph`, `save_provenance_chain`, `load_provenance_chain` with `ensure_within` path safety. | Implements Requirement 16. |
| `src/tools/retrieval.py` | Propagated `reading_depth` and `retrieval_status` into source objects during retrieval workflows. | Aligns tool output with new schema capabilities. |
| `tests/test_schemas.py` | Updated schema tests to verify new fields, defaults, and backward compatibility. | Ensures no regressions in core schema tests. |
| `ARCHITECTURE.md` | Documented 4-layer architecture, data flows, and new workflow modules. | Keeps architectural documentation in sync. |

### 4.3 Deleted Files
- **0 files deleted.** No legacy code was removed.

---

## 5. Architecture Changes

### 5.1 Layered System Architecture (v1.1.0)

```
┌────────────────────────────────────────────────────────────────────────┐
│                               CLI Layer                                │
│   src/__main__.py / src/runtime/cli.py (check, plan, run-academic)     │
│   Backward-compatible: processes legacy and v1.1 JSON inputs           │
├────────────────────────────────────────────────────────────────────────┤
│                             Workflow Layer                             │
│  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │
│  │    evidence_flow.py     │  │              gates.py               │  │
│  │  • _effective_strength  │  │  • 14 Integrity Gate Checks         │  │
│  │  • calibrate_confidence │  │  • DOI Regex / Overclaim / Abstract │  │
│  │  • evaluate_claim       │  │  • ReviewQueue conversion           │  │
│  └─────────────────────────┘  └─────────────────────────────────────┘  │
│  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │
│  │    evidence_graph.py    │  │          evidence_audit.py          │  │
│  │  • build_evidence_graph │  │  • audit_evidence                   │  │
│  │  • summarize_graph      │  │  • AuditResult & AuditFlag          │  │
│  └─────────────────────────┘  └─────────────────────────────────────┘  │
│  ┌─────────────────────────┐  ┌─────────────────────────────────────┐  │
│  │    contradiction.py     │  │            provenance.py            │  │
│  │  • detect_contradictions│  │  • build_provenance_chain           │  │
│  │  • severity scoring     │  │  • 1:1 trace to source history      │  │
│  └─────────────────────────┘  └─────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────────────────┤
│                              Schema Layer                              │
│  src/schemas/evidence.py  ─ EvidenceType, ReadingDepth, struct fields  │
│  src/schemas/source.py    ─ RetrievalStatus, publisher, index_status   │
│  src/schemas/review.py    ─ ReviewItem, ReviewQueue                    │
│  src/schemas/provenance.py─ ProvenanceRecord                           │
├────────────────────────────────────────────────────────────────────────┤
│                          Core & Storage Layer                          │
│  src/core/storage.py      ─ write_json, read_json, append_jsonl,       │
│                             save/load_evidence_graph, provenance,      │
│                             ensure_within (path traversal guard)       │
└────────────────────────────────────────────────────────────────────────┘
```

### 5.2 End-to-End Evidence Data Flow

```
Academic Source (PDF, Abstract, Metadata)
                  │
                  ▼
          Retrieval Agent
   Sets: ReadingDepth (FULL_TEXT, ABSTRACT_ONLY, METADATA_ONLY)
         RetrievalStatus (RETRIEVED, PARTIAL, FAILED, NOT_ATTEMPTED)
                  │
                  ▼
     Evidence Extraction Agent
   Populates: EvidenceType (DIRECT, PARTIAL, THEORETICAL, etc.)
              Structured extraction fields (population, sample, stats)
              Enforces: ABSTRACT_ONLY != VERBATIM_FULLTEXT
                  │
                  ▼
     Evidence Flow & Claim Evaluation
   • compute_support_level: Degrades THEORETICAL/EQUIVALENT; caps indirect at MODERATE
   • calibrate_confidence: Multiplies by type weight; caps by reading depth
   • detect_contradictions: Scans for conflicting findings; assigns HIGH/MED/LOW severity
                  │
                  ▼
      Research Integrity Gate (14 Checks)
   • Hard Violations: Halt execution (AcademicGateError)
   • Review Reasons: Converted into ReviewItem records (PENDING)
                  │
                  ▼
         Artifact Persistence
   • evidence_graph.json (Bipartite graph with broken reference flags)
   • provenance.jsonl (1:1 traceability records with real timestamps)
   • review_queue.json (Centralized queue for human review)
                  │
                  ▼
          Writer & Packaging
   • APA 7 in-text citations & bibliography
   • Final DOCX / ZIP bundle export
```

---

## 6. Test Suite and Verification

### 6.1 Test Evolution Metric
- **Pre-Upgrade Baseline (v1.0.0):** 349 tests passed.
- **Evidence Intelligence Additions:** +59 tests in `tests/test_evidence_intelligence.py`.
- **Current Total:** **408 passed, 0 failed, 10 deselected** in **8.25 seconds**.
- *Note on Deselected Tests:* Exactly 10 integration tests are deselected by default because they require live network connectivity and API keys for external academic providers (Crossref, PubMed, Semantic Scholar). All offline, mock, and local deterministic tests pass at 100%.

### 6.2 The 28 Correctness Properties Verification Matrix

| Property | Description | Requirement | Test Function in `tests/test_evidence_intelligence.py` | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Property 1** | Evidence field independence: all enum combinations valid without conflict. | Req 1.3, 1.6 | `test_property_1_evidence_field_independence` | **PASSED** |
| **Property 2** | `NOT_SUPPORTED` evidence excluded from positive support calculation. | Req 1.5 | `test_property_2_not_supported_excluded` | **PASSED** |
| **Property 3** | `ABSTRACT_ONLY` depth strictly blocks `VERBATIM_FULLTEXT` extraction. | Req 2.4 | `test_property_3_abstract_only_prevents_verbatim_fulltext` | **PASSED** |
| **Property 4** | Reading depth caps confidence (0.5 for abstract, 0.2 for metadata). | Req 2.5 | `test_property_4_reading_depth_caps_confidence` | **PASSED** |
| **Property 5** | `NOT_ATTEMPTED` retrieval status blocks `FULLTEXT_RETRIEVED` state transition. | Req 3.5 | `test_property_5_not_attempted_blocks_fulltext_retrieved` | **PASSED** |
| **Property 6** | Failed retrieval records error in source `errors` with status `FAILED`. | Req 3.4 | `test_property_6_failed_retrieval_records_error` | **PASSED** |
| **Property 7** | Evidence type degradation in support level (THEORETICAL/EQUIVALENT -1, BACKGROUND=WEAK). | Req 12.1-12.3 | `test_property_7_evidence_type_degradation` | **PASSED** |
| **Property 8** | All PARTIAL/THEORETICAL evidence caps support level at `MODERATE`. | Req 12.4 | `test_property_8_indirect_evidence_caps_at_moderate` | **PASSED** |
| **Property 9** | Evidence type confidence multipliers (0.8, 0.7, 0.6, 0.3). | Req 12.5 | `test_property_9_confidence_multipliers` | **PASSED** |
| **Property 10** | Evidence serialization round-trip preserves all fields and structured metadata. | Req 1.6, 6.4 | `test_property_10_evidence_serialization_roundtrip` | **PASSED** |
| **Property 11** | Backward compatibility: legacy v1.0 records deserialize with specified defaults. | Req 14.1-14.5 | `test_property_11_backward_compatibility_defaults` | **PASSED** |
| **Property 12** | DOI format validation against `^10\.\d{4,}/\S+$` regex. | Req 10.1, 10.2 | `test_property_12_doi_format_validation` | **PASSED** |
| **Property 13** | Evidence type/relationship mismatch detection (`CONTRADICTORY` + `SUPPORTS`). | Req 10.3 | `test_property_13_type_relationship_mismatch` | **PASSED** |
| **Property 14** | Overclaim detection: SUPPORTED claims backed solely by indirect evidence flagged. | Req 10.4 | `test_property_14_overclaim_detection` | **PASSED** |
| **Property 15** | Abstract-only evidence on SUPPORTED claim triggers review reason. | Req 10.5 | `test_property_15_abstract_only_review_reason` | **PASSED** |
| **Property 16** | Mixed evidence classification: claims with both SUPPORTS and CONTRADICTS flagged. | Req 11.2 | `test_property_16_mixed_evidence_classification` | **PASSED** |
| **Property 17** | Conflict severity computed from strongest contradictory evidence (HIGH/MED/LOW). | Req 11.4 | `test_property_17_conflict_severity_scoring` | **PASSED** |
| **Property 18** | Evidence graph completeness and broken reference detection for missing source IDs. | Req 7.1-7.4 | `test_property_18_evidence_graph_completeness` | **PASSED** |
| **Property 19** | Audit flags detection for unverified verbatim, depth mismatch, and type mismatch. | Req 8.3, 8.4 | `test_property_19_audit_flags_detection` | **PASSED** |
| **Property 20** | Audit statistics accuracy: aggregate counts match exact manual iterations. | Req 8.6 | `test_property_20_audit_statistics_accuracy` | **PASSED** |
| **Property 21** | Provenance chain completeness: generates exact 1:1 records with authentic timestamps. | Req 9.2, 9.3 | `test_property_21_provenance_chain_completeness` | **PASSED** |
| **Property 22** | `ProvenanceRecord` serialization round-trip to/from dict and JSON. | Req 9.4, 9.5 | `test_property_22_provenance_serialization_roundtrip` | **PASSED** |
| **Property 23** | `ReviewQueue` persistence round-trip (`review_queue.json`). | Req 13.2, 16.1 | `test_property_23_review_queue_persistence` | **PASSED** |
| **Property 24** | `ReviewQueue` filtering correctness across status, severity, and item_type. | Req 13.5 | `test_property_24_review_queue_filtering` | **PASSED** |
| **Property 25** | `GateResult.review_reasons` convert into PENDING `ReviewItem` records. | Req 13.3 | `test_property_25_review_reasons_to_queue` | **PASSED** |
| **Property 26** | Semantic review severity maps directly from `ClaimImportance` (CRITICAL->CRITICAL). | Req 13.7 | `test_property_26_semantic_review_severity_mapping` | **PASSED** |
| **Property 27** | Unverified source with `publisher_verified == False` flagged on citation. | Req 4.5 | `test_property_27_publisher_unverified_flagged` | **PASSED** |
| **Property 28** | Source not indexed in any queried database triggers review reason. | Req 5.4 | `test_property_28_source_not_indexed_review_reason` | **PASSED** |

---

## 7. Demonstration: Golden Research Case (TikTok Streak)

The canonical golden test case (`tests/fixtures/golden_tiktok_streak.py`) provides an end-to-end demonstration of the Evidence Intelligence pipeline and Integrity Gate enforcement.

### 7.1 Scenario Setup
- **Claim:** `"TikTok Streak increases social connectedness among university students"` (`clm_golden_tiktok`, Importance: `HIGH`, Required Sources: `2`).
- **Sources:**
  1. `src_tiktok`: Chen, L. (2023), *Computers in Human Behavior*. Evaluates TikTok peer socialization; `reading_depth = ABSTRACT_ONLY`, `retrieval_status = PARTIAL`.
  2. `src_snapchat`: Bayer, J. B. (2016), *JCMC*. Investigates Snapchat streaks in adolescents; `reading_depth = FULL_TEXT`, `retrieval_status = RETRIEVED`.
  3. `src_connectedness`: Lee, R. M. (2001), *J. Counseling Psych*. Foundational theory of social connectedness; `reading_depth = FULL_TEXT`, `retrieval_status = RETRIEVED`.
  4. `src_activity`: Silverman, M. (2022), *ACM CHI*. Streaks gamification and habit formation; `reading_depth = FULL_TEXT`, `retrieval_status = RETRIEVED`.
  5. `src_counter`: Dienlin, T. (2021), *Human Communication Research*. Longitudinal study showing no streak-connection link; `reading_depth = FULL_TEXT`, `retrieval_status = RETRIEVED`.
- **Evidence Records:**
  - `ev_tiktok`: `PARTIAL`, `ABSTRACT_ONLY`, `PARTIALLY_SUPPORTS`, `MODERATE`.
  - `ev_snapchat`: `FUNCTIONAL_EQUIVALENT` (proxy platform), `FULL_TEXT`, `SUPPORTS`, `STRONG`.
  - `ev_connectedness`: `THEORETICAL` (conceptual scale), `FULL_TEXT`, `SUPPORTS`, `DEFINITIVE`.
  - `ev_activity`: `THEORETICAL` (gamification mechanics), `FULL_TEXT`, `SUPPORTS`, `MODERATE`.
  - `ev_counter`: `CONTRADICTORY` (empirical refutation), `FULL_TEXT`, `CONTRADICTS`, `STRONG`.

### 7.2 Step-by-Step Execution Through the Integrity Pipeline

#### Step 1: Indirect Supporting Evidence Evaluation
When `clm_golden_tiktok` is evaluated using only the 4 supporting items (`ev_tiktok`, `ev_snapchat`, `ev_connectedness`, `ev_activity`):
- None of the items are `DIRECT` empirical observations of TikTok streaks causing connectedness in university students.
- `_effective_strength` degrades `ev_snapchat` from `STRONG` -> `MODERATE`.
- `_effective_strength` degrades `ev_connectedness` from `DEFINITIVE` -> `STRONG`.
- `compute_support_level` enforces the indirect cap: because all supporting evidence is indirect, the overall support level is capped at `SupportLevel.MODERATE`.
- `evaluate_claim` returns status `PARTIALLY_SUPPORTED` or `INSUFFICIENT_EVIDENCE`.
- **Result:** The system **strictly refuses** to mark the claim as `SUPPORTED` or `STRONG`.

#### Step 2: Injecting Empirical Counter-Evidence
When `ev_counter` is added to the claim's evidence pool:
- `detect_contradictions(claim, all_evidence)` executes.
- It detects `mixed_evidence = True` (presence of both `SUPPORTS` and `CONTRADICTS`).
- Because `ev_counter.strength == STRONG`, it computes `conflict_severity = "HIGH"`.
- `evaluate_claim` updates the claim status to `ClaimStatus.CONFLICTED`.
- **Result:** The system forces transparent disclosure of the contradiction before any drafting can proceed.

#### Step 3: Integrity Gate Enforcement — Overclaim Detection (Case A)
If an upstream agent attempts to force `claim.status = ClaimStatus.SUPPORTED` using only `ev_snapchat` (`FUNCTIONAL_EQUIVALENT`) and `ev_connectedness` (`THEORETICAL`):
- `check_academic_integrity` executes Check 10.
- Check 10 verifies whether any direct empirical evidence supports the claim.
- Finding none, the gate raises a hard violation:  
  `"claim clm_golden_tiktok overclaimed: no direct evidence supports the claim"`
- `gate.ok` evaluates to `False`, throwing `AcademicGateError` and completely blocking document generation.

#### Step 4: Integrity Gate Enforcement — Abstract-Only Evidence Warning (Case B)
If an agent marks the claim `SUPPORTED` relying solely on `ev_tiktok` (`reading_depth = ABSTRACT_ONLY`):
- `check_academic_integrity` executes Check 11.
- Check 11 flags that the claim rests entirely on abstract-level information.
- The gate adds a review reason:  
  `"claim clm_golden_tiktok supported only by abstract-level evidence"`
- The review reason is automatically queued into `ReviewQueue` as a `ReviewItem` with `status = "PENDING"` and `severity = "HIGH"`.

---

## 8. Remaining Limitations

While v1.1.0 establishes robust scientific evidence intelligence, several inherent limitations are documented for operational transparency:

1. **Network Dependency for Real-Time Publisher Verification**:
   When operating in offline sandbox environments without internet access, `publisher_verified` cannot query live Crossref/PubMed APIs and must rely on cached metadata or offline fixtures.
2. **Deterministic Rules vs. Deep Semantic Nuance**:
   The engine uses deterministic rules, regexes, and exact substring matching. While this guarantees 100% reproducibility without LLM hallucinations, subtle semantic misalignments that pass syntactic checks still require human expert review via the `ReviewQueue`.
3. **Automated Full-Text Parsing Ceiling**:
   The system currently relies on structured text passed via JSON or extracted from markdown/text files. It does not yet include a native layout-aware PDF visual parser (e.g. OCR/Grobid) to automatically extract tables, statistical equations, and footnotes directly from raw scanned PDFs.
4. **Offline Deselected Tests**:
   The 10 deselected network integration tests require external API endpoints and valid rate-limited tokens, meaning CI/CD environments without external network egress run 408 rather than 418 total tests.

---

## 9. Recommended Next Phase

Based on the operational achievements of Phase 18 Extended, the following sequential roadmap is recommended for subsequent development phases:

### Phase 19: Full-Text PDF Layout Parser & Multi-Modal Extractor
- Integrate a local, layout-aware PDF parsing engine (e.g., PyMuPDF / Grobid / Marker) capable of parsing two-column academic papers.
- Automatically segment papers into Methodology, Results, and Discussion sections to automatically populate the 8 structured extraction fields (`sample_size`, `statistical_result`, `limitations`).

### Phase 20: Background Bibliographic Corroborator Daemon
- Implement an asynchronous background daemon that monitors `sources.json` and automatically queries Crossref, OpenAlex, PubMed, and Scopus to populate `publisher_verified` and `index_status` without blocking user CLI workflows.
- Automatically fetch open-access full-text PDFs when available (Unpaywall API integration) to promote sources from `ABSTRACT_ONLY` to `FULL_TEXT`.

### Phase 21: Interactive Human Review Dashboard
- Build an interactive terminal TUI (Textual) or local web UI (FastAPI/Vite) that reads `review_queue.json` directly.
- Allow human researchers to inspect pending `ReviewItem` entries, review side-by-side claim and excerpt comparisons, and mark items as `RESOLVED` or `DISMISSED` with structured resolution notes.

### Phase 22: Interactive Epistemic Graph Visualizer
- Implement an exporter converting `evidence_graph.json` into interactive HTML visual graphs (using Cytoscape.js or D3.js).
- Enable academic auditors to visually trace claim hierarchies, highlight contradictory tension edges in red, and inspect provenance chains interactively.

---

## 10. Verification Sign-Off

**Health Check Verification:**
```powershell
PS > python -m src check
[OK] System health check passed
   SYSTEM_ROOT: C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH\DATA BASE
   WORKSPACE_ROOT: C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH
   Spec version: 1.0
   Build phase: 18
```

**Test Suite Verification:**
```powershell
PS > python -m pytest -q --tb=short
.................................. [  8%]
.................................. [ 16%]
.................................. [ 25%]
.................................. [ 33%]
.................................. [ 41%]
.................................. [ 50%]
.................................. [ 58%]
.................................. [ 66%]
.................................. [ 75%]
.................................. [ 83%]
.................................. [ 91%]
.................................. [100%]
408 passed, 10 deselected in 8.25s
```

**Sign-off:** AUTONOMI AGENTIC ILMIAH Development Subagent  
**Date:** September 18, 2026
