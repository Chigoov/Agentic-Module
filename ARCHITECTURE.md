# SYSTEM ARCHITECTURE
## AUTONOMI AGENTIC ILMIAH v1.1.0

---

## 1. HIGH-LEVEL ARCHITECTURE

```
                                USER / CLI
                                     │
                                     ▼
                            OrchestratorAgent
                                     │
    ┌────────────────────────────────┼────────────────────────────────┐
    │                                │                                │
    ▼                                ▼                                ▼
TaskAnalyzerAgent           ResearchPlannerAgent               DiscoveryAgent
    │                                │                                │
    ▼                                ▼                                ▼
VerificationAgent             RetrievalAgent              EvidenceExtractionAgent
                                                                      │
                                                                      ▼
                                                          ClaimVerificationAgent
                                                                      │
                                                                      ▼
                                                      Evidence Intelligence Workflows
                                                      ┌──────────────────────────────┐
                                                      │ • evidence_graph             │
                                                      │ • evidence_audit             │
                                                      │ • contradiction              │
                                                      │ • provenance                 │
                                                      │ • gates (14 integrity checks)│
                                                      │ • review_queue               │
                                                      └──────────────────────────────┘
                                                                      │
    ┌────────────────────────────────┬────────────────────────────────┘
    │                                │
    ▼                                ▼
SynthesisAgent                  OutlineAgent
    │                                │
    ▼                                ▼
WriterAgent                  CitationAuditAgent & FactAuditAgent
    │                                │
    └────────────────────────────────┼────────────────────────────────┘
                                     │
                                     ▼
                        DOCX OUTPUT & AUDIT BUNDLE
```

Agents execute reasoning and state-machine transitions, delegating discrete capabilities to specialized Tools, Workflows, and Adapters.

---

## 2. SYSTEM LAYERING

### 2.1 Agents
Reasoning, decision-making, and goal-directed task execution:
- `TaskAnalyzerAgent`, `ResearchPlannerAgent`, `DiscoveryAgent`, `VerificationAgent`, `RetrievalAgent`, `EvidenceExtractionAgent`, `ClaimVerificationAgent`, `SynthesisAgent`, `OutlineAgent`, `WriterAgent`, `CitationAuditAgent`, `FactAuditAgent`, `OrchestratorAgent`.

### 2.2 Evidence Intelligence & Workflow Layer
Deterministic algorithms enforcing mathematical, logical, and epistemic invariants:
- **`evidence_graph`**: Bipartite claim-evidence-source mapping with broken reference detection.
- **`evidence_audit`**: Verification auditing, detection of quote status, depth mismatches, and type inconsistencies.
- **`contradiction`**: Conflict detection, contradictory excerpt extraction, null finding aggregation, and conflict severity scoring (`HIGH`/`MEDIUM`/`LOW`).
- **`provenance`**: End-to-end provenance chain generation linking locators, timestamps, and verification methods.
- **`gates`**: Academic integrity gate executing 14 distinct checks prior to writing; output text scanning for orphan citations and internal LLM tokens.
- **`evidence_flow`**: Support level heuristics, ladder strength degradation, and confidence calibration.
- **`writing_flow`**: Pre-writing validation, section synthesis, and citation placement.

### 2.3 Tools & Adapters
External provider adapters and capabilities:
- `PublishOrPerishTool`, `CrossrefTool`, `OpenAlexTool`, `SemanticScholarTool`, `PubMedTool`, `DOABTool` (Open Access Books), `OpenLibraryTool` (Book Metadata & Availability), `WebSearchTool`, `RetrievalTool` (Direct Download & Abstract), `PDFParserTool` (Page-based extraction), `DocxGenerationTool`, `FileSystemTool`, `ModelRouterTool` (Fail-safe capability router).

### 2.4 Schemas (Pydantic 2.x)
Strict, machine-readable contracts with immutable state-transition logging:
- `Source`, `Evidence`, `Claim`, `VerificationReport`, `ProvenanceRecord`, `ReviewItem`, `ReviewQueue`, `Outline`, `Project`.

### 2.5 Storage & Registries
Safe filesystem primitives with boundary checking (`ensure_within`) and atomic writes:
- `sources.json`, `evidence.jsonl`, `claims.json`, `evidence_graph.json`, `provenance.jsonl`, `review_queue.json`, cache directories, run history, and audit bundles.

---

## 3. DATA BASE ROLE & DIRECTORY STRUCTURE

`DATA BASE/` serves as the system root and operational workspace.

```text
DATA BASE/
├── 00_MASTER_INSTRUCTION.md      # Foundational operating charter
├── AGENT_CONSTITUTION.md         # Ethical and anti-fabrication constitution
├── ARCHITECTURE.md               # System architecture and layering (this file)
├── EVIDENCE_SYSTEM.md            # Evidence intelligence specifications
├── RESEARCH_INTEGRITY.md         # Integrity gate, review queue, and checks
├── SCHEMA.md                     # Pydantic schema contracts reference
├── TESTING.md                    # Test suite structure and 28 correctness properties
├── CHANGELOG.md                  # Keep a Changelog release notes
├── SYSTEM_RULES.md               # Operational rules and gate thresholds
├── WORKFLOW.md                   # State transition lifecycle
├── BUILD_PLAN.md                 # Implementation roadmap
├── src/                          # Application source code
│   ├── schemas/                  # Pydantic data models
│   ├── workflows/                # Deterministic workflows and gates
│   ├── tools/                    # Research and verification tools
│   ├── core/                     # Storage, errors, registries
│   └── app/                      # CLI entrypoints and commands
├── database/                     # Operational database files
├── cache/                        # Cached full texts, PDFs, and probe runs
├── state/                        # Active project runtime states
├── logs/                         # Execution logs and telemetry
└── tests/                        # 408-test automated pytest suite
    └── fixtures/                 # Golden research cases (TikTok Streak)
```

---

## 4. AGENT RESPONSIBILITIES

- **TaskAnalyzerAgent**: Converts user input into structured requirements, constraints, and research questions.
- **ResearchPlannerAgent**: Formulates search keywords, inclusion/exclusion criteria, recency windows, and citation style.
- **DiscoveryAgent**: Orchestrates discovery adapters (Crossref, PubMed, etc.), aggregates candidate sources, and deduplicates records.
- **VerificationAgent**: Executes 3-level verification (Existence, Metadata, Content); corroborates DOIs and publisher records; transitions source states.
- **RetrievalAgent**: Fetches abstracts, full-text PDFs, or HTML pages; sets `ReadingDepth` and `RetrievalStatus`.
- **EvidenceExtractionAgent**: Extracts passages with precise locators (page, section); populates structured extraction fields; sets `EvidenceType`.
- **ClaimVerificationAgent**: Links evidence to claims; runs `detect_contradictions`; computes support levels and calibrated confidence.
- **SynthesisAgent**: Synthesizes verified evidence into comparative matrices, highlighting consensus and academic divergence.
- **OutlineAgent**: Structures the academic manuscript in accordance with journal/thesis guidelines.
- **WriterAgent**: Drafts academic prose exclusively from verified claims and citable evidence.
- **CitationAuditAgent**: Verifies that every citation maps to an approved source and conforms to APA 7 style.
- **FactAuditAgent**: Audits factual consistency between draft text and underlying evidence passages.
- **OrchestratorAgent**: Manages state transitions, invokes integrity gates, and queues ambiguous cases into `ReviewQueue`.

---

## 5. RESEARCH DATA FLOW

```
[Candidate Source from Discovery Tools]
                 │
                 ▼
[Normalized Source Record (SourceState.DISCOVERED)]
                 │
                 ▼
[Multi-Level Verification Engine (Existence, Metadata, Content)]
                 │
                 ▼
[Approved Source (SourceState.APPROVED, publisher_verified, index_status)]
                 │
                 ▼
[Full-Text / Abstract Retrieval (ReadingDepth, RetrievalStatus)]
                 │
                 ▼
[Structured Evidence Extraction (EvidenceType, normalized_finding, population, etc.)]
                 │
                 ▼
[Evidence Verification Audit (audit_evidence)]
                 │
                 ▼
[Claim Evaluation (compute_support_level, calibrate_confidence, detect_contradictions)]
                 │
                 ▼
[Research Integrity Gate (check_academic_integrity — 14 Checks)]
                 │
     ┌───────────┴───────────┐
     │                       │
     ▼ (Pass)                ▼ (Review Reasons)
[Outline & Synthesis]    [Human Review Queue (review_queue.json)]
     │                       │
     ▼                       ▼ (Resolved by Researcher)
[Writer Drafting & Humanizer]
     │
     ▼
[Output Text Scan (scan_output_text: tokens & orphan citations)]
     │
     ▼
[Final DOCX Generation & Export Bundle (.zip)]
```

---

## 6. EVIDENCE INTELLIGENCE & CLAIM TRACEABILITY ARCHITECTURE

Version 1.1.0 introduces the **Scientific Evidence Intelligence Subsystem**, transitioning AAI from generic literature synthesis to strict epistemic claim traceability.

### 6.1 Epistemic Evidence Classification (`EvidenceType`)
Evidence is classified across seven discrete epistemic dimensions: `DIRECT`, `PARTIAL`, `THEORETICAL`, `FUNCTIONAL_EQUIVALENT`, `BACKGROUND`, `CONTRADICTORY`, and `NOT_SUPPORTED`. 
- Indirect evidence (`THEORETICAL`, `FUNCTIONAL_EQUIVALENT`) degrades effective strength by one ladder notch.
- `BACKGROUND` evidence is capped at `WEAK`.
- `NOT_SUPPORTED` evidence is excluded from positive support calculations.
- Claims supported solely by indirect evidence are capped at `SupportLevel.MODERATE` and cannot claim `STRONG` or `DEFINITIVE` certainty.

### 6.2 Reading Depth Boundaries (`ReadingDepth`)
Tracks whether sources were read at `FULL_TEXT`, `ABSTRACT_ONLY`, `METADATA_ONLY`, or are `UNAVAILABLE`.
- `ABSTRACT_ONLY` readings strictly forbid `VERBATIM_FULLTEXT` extraction.
- `ABSTRACT_ONLY` caps claim confidence at `0.5`.
- `METADATA_ONLY` caps claim confidence at `0.2`.

### 6.3 Structured Evidence Extraction
Captures eight empirical attributes without fabrication: `normalized_finding`, `population`, `sample_size`, `methodology`, `variables`, `instruments`, `statistical_result`, and `limitations`. Missing data remains `None`.

### 6.4 Claim-Evidence-Source Bipartite Mapping Graph (`evidence_graph.py`)
Constructs an explicit graph mapping every claim to its attached evidence passages, and every passage to its verified source. Detects broken references and outputs both JSON (`evidence_graph.json`) and formatted text summaries.

### 6.5 Research Provenance Chains (`provenance.py`)
Generates immutable `ProvenanceRecord` chains linking each empirical claim to its exact page, section, retrieval timestamp, verification timestamp, and verification method in `provenance.jsonl`.

### 6.6 Contradiction Detection Engine (`contradiction.py`)
Evaluates claims for mixed evidence (`SUPPORTS` and `CONTRADICTS`), extracts 200-character contradictory excerpts, aggregates null findings, and calculates conflict severity (`HIGH`, `MEDIUM`, `LOW`), forcing disclosure in academic prose.

### 6.7 Research Integrity Gate (`gates.py`)
Enforces 14 automated integrity checks prior to writing, including DOI regex verification, overclaim prevention, abstract-only flagging, unindexed source detection, and publisher corroboration checks.

### 6.8 Human Review Queue (`review.py`)
Captures non-blocking ambiguities and semantic review requirements in `review_queue.json`. Items with `severity == "CRITICAL"` block final publication until explicitly resolved by a human researcher.

---

## 7. WORKFLOW SUBSYSTEMS REFERENCE

| Workflow Module | Primary Function | Primary Outputs | Key Constraints |
| :--- | :--- | :--- | :--- |
| `src/workflows/evidence_graph.py` | `build_evidence_graph`, `summarize_evidence_graph` | `evidence_graph.json`, text summary | Flags broken references; JSON-native types only. |
| `src/workflows/evidence_audit.py` | `audit_evidence` | `AuditResult`, `AuditFlag` | Checks unverified verbatim, depth/method mismatch, and type conflicts. |
| `src/workflows/contradiction.py` | `detect_contradictions` | `ContradictionReport`, `conflict_severity` | Detects mixed evidence; extracts excerpts; scores severity. |
| `src/workflows/provenance.py` | `build_provenance_chain` | `list[ProvenanceRecord]`, `provenance.jsonl` | Never fabricates timestamps; extracts authentic history. |
| `src/workflows/gates.py` | `check_academic_integrity`, `scan_output_text` | `GateResult`, `ReviewQueue` | 14 checks; blocks on violations; routes reasons to review queue. |
| `src/workflows/evidence_flow.py` | `evaluate_claim`, `compute_support_level`, `calibrate_confidence` | `EvaluationResult` | Epistemic multipliers; reading depth caps; overclaim prevention. |
| `src/workflows/deep_research.py` | `DeepResearchWorkflow` | `draft.md`, `citation_map.json`, `review_queue.json`, `final.docx` | 16-stage end-to-end research workflow from raw query to audit gates and DOCX output. |
| `src/tools/citation_manager.py` | `CitationManager`, `build_citation_map` | `citation_map.json`, in-text labels | Disambiguates collisions (`Smith, 2023a` vs `Smith, 2023b`) across writer, references, and audits. |

---

## 8. DESIGN RULES & EXTENSION CONTRACTS

1. **Deterministic Execution**: All gate checks, confidence calibrations, and support level calculations must be deterministic and testable without external network dependencies.
2. **Stable Identifiers**: Every record must carry a typed prefix (`src_`, `evd_`, `clm_`, `rev_item_`) and an immutable identifier.
3. **Audit Trail Immutability**: State transitions, error logs, and provenance timestamps must only be appended, never edited or overwritten.
4. **UNKNOWN > Fabricated**: Missing data must remain `None` or be flagged as incomplete; never infer or interpolate empirical figures.
5. **Path Safety**: All file writes must validate paths against authorized directory roots using `ensure_within`.

