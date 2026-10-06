# Testing & Quality Assurance Architecture
## AUTONOMI AGENTIC ILMIAH (AAI) v1.1.0

---

## 1. Test Suite Overview & Evolution

AAI enforces rigorous test-driven validation. Every architectural invariant, gate rule, and schema constraint is accompanied by automated unit, property, and integration tests.

### 1.1 Test Evolution Metric

```
┌────────────────────────────────────────────────────────┐
│  Baseline (v1.0.0): 349 tests passed                   │
│  Evidence Intelligence Upgrade (v1.1.0): +59 tests     │
│  Current Total: 408 passed, 10 deselected in ~8.9s     │
└────────────────────────────────────────────────────────┘
```

The test suite covers:
- Core schema invariants and model validation.
- Serialization round-trips and backward compatibility.
- Academic integrity gates and anti-fabrication guards.
- Workflow algorithms (evidence graph, audit, contradiction, provenance).
- Real-world golden scenarios (TikTok Streak fixture).
- CLI smoke checks and system health verifications.

---

## 2. Test Execution Instructions

Run all tests from the `DATA BASE` directory using PowerShell or standard shell:

```powershell
# Standard quiet test run with short tracebacks
python -m pytest -q --tb=short

# Run specifically the Evidence Intelligence test suite
python -m pytest tests/test_evidence_intelligence.py -v

# Run with coverage report
python -m pytest --cov=src --cov-report=term-missing
```

### CLI Smoke Testing
Verify that system CLI entrypoints remain operational and compliant:

```powershell
# System health check (verifies root, paths, build phase, schema load)
python -m src check

# Planner smoke check
python -m src plan "Dampak Gamifikasi Terhadap Retensi Belajar Siswa"
```

---

## 3. The 28 Correctness Properties

The Evidence Intelligence implementation formally validates 28 correctness properties mapped directly to user requirements.

| Property | Description | Requirement | Test Target |
| :--- | :--- | :--- | :--- |
| **Property 1** | Evidence field independence — all enum combinations of EvidenceType, EvidenceRelationship, and EvidenceStrength are valid without conflict. | Req 1.3, 1.6 | `test_property_1_evidence_field_independence` |
| **Property 2** | `NOT_SUPPORTED` evidence excluded from positive support calculations in `compute_support_level`. | Req 1.5 | `test_property_2_not_supported_excluded` |
| **Property 3** | `ABSTRACT_ONLY` depth strictly prevents `VERBATIM_FULLTEXT` extraction at model validation. | Req 2.4 | `test_property_3_abstract_only_prevents_verbatim_fulltext` |
| **Property 4** | Reading depth caps confidence: `ABSTRACT_ONLY` caps at `0.5`, `METADATA_ONLY` caps at `0.2`. | Req 2.5 | `test_property_4_reading_depth_caps_confidence` |
| **Property 5** | `NOT_ATTEMPTED` retrieval status blocks transition to `FULLTEXT_RETRIEVED`. | Req 3.5 | `test_property_5_not_attempted_blocks_fulltext_retrieved` |
| **Property 6** | Failed retrieval records error in source's `errors` list with status `FAILED`. | Req 3.4 | `test_property_6_failed_retrieval_records_error` |
| **Property 7** | Evidence type degradation in support level: THEORETICAL and FUNCTIONAL_EQUIVALENT degrade 1 level; BACKGROUND capped at WEAK. | Req 12.1, 12.2, 12.3 | `test_property_7_evidence_type_degradation` |
| **Property 8** | All PARTIAL/THEORETICAL evidence caps support level at `MODERATE`. | Req 12.4 | `test_property_8_indirect_evidence_caps_at_moderate` |
| **Property 9** | Evidence type confidence multipliers: PARTIAL $\times 0.8$, THEORETICAL $\times 0.6$, FUNCTIONAL_EQUIVALENT $\times 0.7$, BACKGROUND $\times 0.3$. | Req 12.5 | `test_property_9_confidence_multipliers` |
| **Property 10** | Evidence serialization round-trip preserves all fields, enums, and structured extraction metadata. | Req 1.6, 6.4, 14.1, 14.2 | `test_property_10_evidence_serialization_roundtrip` |
| **Property 11** | Backward compatibility: legacy v1.0 records deserialize with specified defaults. | Req 14.1, 14.2, 14.3, 14.5 | `test_property_11_backward_compatibility_defaults` |
| **Property 12** | DOI format validation against `^10\.\d{4,}/\S+$` regex. | Req 10.1, 10.2 | `test_property_12_doi_format_validation` |
| **Property 13** | Evidence type / relationship mismatch detection (`CONTRADICTORY` + `SUPPORTS`). | Req 10.3 | `test_property_13_type_relationship_mismatch` |
| **Property 14** | Overclaim detection: SUPPORTED claims backed solely by indirect evidence are flagged. | Req 10.4 | `test_property_14_overclaim_detection` |
| **Property 15** | Abstract-only evidence on SUPPORTED claim triggers review reason. | Req 10.5 | `test_property_15_abstract_only_review_reason` |
| **Property 16** | Mixed evidence classification: claims with both SUPPORTS and CONTRADICTS flagged. | Req 11.2 | `test_property_16_mixed_evidence_classification` |
| **Property 17** | Conflict severity computed from strongest contradictory evidence (STRONG/DEFINITIVE $\to$ HIGH, MODERATE $\to$ MEDIUM, WEAK $\to$ LOW). | Req 11.4 | `test_property_17_conflict_severity_scoring` |
| **Property 18** | Evidence graph completeness and broken reference detection for unresolvable source IDs. | Req 7.1, 7.2, 7.3, 7.4 | `test_property_18_evidence_graph_completeness` |
| **Property 19** | Audit flags detection for unverified verbatim, depth/method mismatch, and type/relationship conflict. | Req 8.3, 8.4 | `test_property_19_audit_flags_detection` |
| **Property 20** | Audit statistics accuracy: aggregate counts match exact manual iterations. | Req 8.6 | `test_property_20_audit_statistics_accuracy` |
| **Property 21** | Provenance chain completeness: generates exact 1:1 records with authentic timestamps. | Req 9.2, 9.3, 9.5 | `test_property_21_provenance_chain_completeness` |
| **Property 22** | `ProvenanceRecord` serialization round-trip to/from dict and JSON. | Req 9.4, 9.5 | `test_property_22_provenance_serialization_roundtrip` |
| **Property 23** | `ReviewQueue` persistence round-trip (`review_queue.json`). | Req 13.2, 16.1 | `test_property_23_review_queue_persistence` |
| **Property 24** | `ReviewQueue` filtering correctness across status, severity, and item_type. | Req 13.5 | `test_property_24_review_queue_filtering` |
| **Property 25** | `GateResult.review_reasons` convert into PENDING `ReviewItem` records. | Req 13.3 | `test_property_25_review_reasons_to_queue` |
| **Property 26** | Semantic review severity maps directly from `ClaimImportance` (CRITICAL $\to$ CRITICAL, HIGH $\to$ HIGH, etc.). | Req 13.7 | `test_property_26_semantic_review_severity_mapping` |
| **Property 27** | Unverified source with `publisher_verified == False` flagged on citation. | Req 4.5 | `test_property_27_publisher_unverified_flagged` |
| **Property 28** | Source not indexed in any queried database triggers review reason. | Req 5.4 | `test_property_28_source_not_indexed_review_reason` |

---

## 4. Test Suite Structure & Breakdown

The test suite is organized into modular components in `tests/`:

### 4.1 Schema & Validation Tests
- `tests/test_schemas.py`: Base record behavior, state transition immutability, locator parsing, offset validation.
- `tests/test_outline_schema.py`: Document structure, section headers, target word count bounds.
- `tests/test_evidence_intelligence.py`: Enums (`EvidenceType`, `ReadingDepth`, `RetrievalStatus`), structured extraction fields, Pydantic validators.

### 4.2 Research & Tool Tests
- `tests/test_research_tools.py` & `test_research_tools_integration.py`: Mocked and live adapters for Crossref, OpenAlex, Semantic Scholar, PubMed.
- `tests/test_dedupe.py`: DOI and title-based bibliographic deduplication algorithms.
- `tests/test_verification.py`: Multi-level source verification (existence, metadata, content).
- `tests/test_retrieval.py`: PDF fetching, full-text caching, text extraction.

### 4.3 Workflows & Gate Tests
- `tests/test_evidence_flow.py`: Claim evaluation, support level heuristics, confidence calibration.
- `tests/test_writing_flow.py`: Pre-writing assertions, citation placement, paragraph synthesis.
- `tests/test_phase_14_17_workflows.py`: Evidence graph generation, contradiction reports, provenance chains.
- `tests/test_audit_agents.py` & `test_citation_manager.py`: Author-year orphan citations, internal token scanner.

### 4.4 Golden Fixture & Scenario Tests
- `tests/fixtures/golden_tiktok_streak.py`: The canonical TikTok Streak research scenario.
- `tests/test_evidence_intelligence.py::test_golden_tiktok_streak_scenario`: Validates end-to-end rejection of overclaims, abstract-only confidence caps, and contradiction disclosure.

### 4.5 Negative Tests
- Verification that invalid DOI formats, mismatched relationships, circular states, and unverified verbatim quotes raise appropriate violations or exceptions rather than failing silently.

---

## 5. Continuous Integration (CI) Guidelines

All pull requests and changes must satisfy:
1. `python -m pytest -q --tb=short` must report **0 failures** and **0 errors**.
2. `python -m src check` must return exit code **0** with `[OK] System health check passed`.
3. No internal tokens (`turn...`, `filecite`, `search...`) may appear in codebase or test fixtures.
4. Schema versions must strictly adhere to semantic versioning contracts.

