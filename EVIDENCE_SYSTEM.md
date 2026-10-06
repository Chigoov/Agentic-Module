# Scientific Evidence Intelligence System
## AUTONOMI AGENTIC ILMIAH (AAI) v1.1.0

---

## 1. Executive Summary & Architectural Overview

The **Scientific Evidence Intelligence System** elevates AUTONOMI AGENTIC ILMIAH (AAI) from a literature search and summarization pipeline into a deterministic, auditable research platform. While standard AI academic tools generate fluent summaries prone to subtle hallucinations, ungrounded causal claims, and citation drift, AAI enforces **full claim traceability**, **epistemic evidence classification**, **reading depth boundaries**, **structured extraction**, and **automated contradiction detection**.

```
[Academic Sources: Journals, Books, Reports]
                     │
                     ▼
             Retrieval Agent
       (ReadingDepth & RetrievalStatus)
                     │
                     ▼
         Evidence Extraction Agent
  (Structured Extraction & Verbatim Verification)
                     │
                     ▼
          Evidence Intelligence Layer
  ┌────────────────────────────────────────────────────────┐
  │  • Epistemic Classification (EvidenceType)             │
  │  • Reading Depth Constraints (ReadingDepth)            │
  │  • Support Level Calculation (compute_support_level)   │
  │  • Confidence Calibration (calibrate_confidence)       │
  │  • Contradiction Detection (detect_contradictions)     │
  │  • Traceability Graph (build_evidence_graph)           │
  │  • Provenance Chains (build_provenance_chain)          │
  └────────────────────────────────────────────────────────┘
                     │
                     ▼
          Research Integrity Gate
         (Academic Integrity Checks)
                     │
                     ▼
             Writer & Audits
       (DOCX Output + Audit Bundles)
```

Every claim asserted in final academic prose must be traced through an immutable provenance chain back to specific, verified source content, corroborated bibliographic metadata, and classified epistemic warrants.

---

## 2. Epistemic Evidence Classification (`EvidenceType`)

Evidence classification in AAI separates **what** the evidence is epistemically (`EvidenceType`) from **which direction** it points (`EvidenceRelationship`) and **how much weight** it carries (`EvidenceStrength`).

### 2.1 The Seven Epistemic Categories

The `EvidenceType` enum (`src/schemas/evidence.py`) defines exactly seven members:

| EvidenceType | Definition | Academic Example | Impact on Evaluation |
| :--- | :--- | :--- | :--- |
| `DIRECT` | Empirical data directly observing the exact claim phenomenon and population. | Randomized controlled trial or survey directly measuring TikTok Streak usage and loneliness in university students. | Full evidential weight; base strength preserved; confidence multiplier `1.0`. |
| `PARTIAL` | Empirical findings observing related or overlapping phenomena, or non-identical populations. | Study examining Instagram interaction streaks and adolescent peer connection. | Degraded confidence multiplier `0.8`; cannot alone support STRONG claim level. |
| `THEORETICAL` | Conceptual models, deductive logic, literature reviews, or frameworks without new primary empirical data. | Sociological paper discussing symbolic interactionism and digital habit formation. | Strength degraded by 1 ladder step (e.g. STRONG → MODERATE); confidence multiplier `0.6`. |
| `FUNCTIONAL_EQUIVALENT` | Empirical evidence from an analog, alternative technology, or proxy mechanism. | Study of Snapchat streaks or Duolingo streaks used as a proxy for TikTok streaks. | Strength degraded by 1 ladder step; confidence multiplier `0.7`; cannot stand as DIRECT evidence. |
| `BACKGROUND` | Contextual definitions, historical timelines, macro statistics, or general setting. | Report showing 70% of university students own smartphones. | Effective strength capped at `WEAK`; confidence multiplier `0.3`. |
| `CONTRADICTORY` | Evidence refuting, challenging, or presenting opposite outcomes to the claim. | Longitudinal study finding no correlation between social media streaks and connectedness. | Triggers contradiction detection; records contradictory findings; decreases claim confidence by `0.4`. |
| `NOT_SUPPORTED` | Null findings, uninformative data, or failed replications showing no statistically significant effect. | Study showing $p = 0.42$ with no measurable effect of streak length on student wellbeing. | Strictly excluded from positive support calculations; captured as null findings in contradiction reports. |

### 2.2 Mathematical & Logical Impact on Claim Evaluation

In `src/workflows/evidence_flow.py`, `EvidenceType` governs how evidence weight propagates into claim support:

1. **Exclusion of Non-Supporting Evidence**:
   ```python
   valid_supporting = [
       e for e in supporting if _get_evidence_type(e) != EvidenceType.NOT_SUPPORTED
   ]
   ```
   Evidence records marked `NOT_SUPPORTED` yield zero positive weight towards `SupportLevel`.

2. **Ladder Step Degradation (`_effective_strength`)**:
   Evidence strength follows a 4-step ladder: `WEAK` → `MODERATE` → `STRONG` → `DEFINITIVE`.
   - `THEORETICAL` and `FUNCTIONAL_EQUIVALENT` are degraded by 1 level (e.g., `STRONG` becomes `MODERATE`, `MODERATE` becomes `WEAK`).
   - `BACKGROUND` is capped at `WEAK` regardless of nominal `strength`.
   - Pre-upgrade unclassified records default to `DIRECT` for backward compatibility.

3. **Ceiling on Indirect Evidence**:
   If **all** supporting evidence for a claim is indirect (`PARTIAL`, `THEORETICAL`, `FUNCTIONAL_EQUIVALENT`, or `BACKGROUND`), the claim's `SupportLevel` is capped at `MODERATE`, preventing strong or definitive assertions without direct empirical warrants.

4. **Confidence Multipliers**:
   During `calibrate_confidence`, evidence types apply multiplicative adjustments to base confidence:
   - `DIRECT`: $\times 1.0$
   - `PARTIAL`: $\times 0.8$
   - `FUNCTIONAL_EQUIVALENT`: $\times 0.7$
   - `THEORETICAL`: $\times 0.6$
   - `BACKGROUND`: $\times 0.3$

---

## 3. Reading Depth Classification (`ReadingDepth`)

Reading depth tracks the actual depth of analysis performed on a source, acknowledging physical and legal constraints on document access.

### 3.1 The Four Reading Depths

The `ReadingDepth` enum (`src/schemas/evidence.py`) defines four discrete depths:

```
FULL_TEXT ──────> Complete article, book chapter, or document retrieved and read
ABSTRACT_ONLY ──> Only title, abstract, and indexing metadata retrieved
METADATA_ONLY ──> Only citation record, DOI, title, and venue available
UNAVAILABLE ────> Source identified but text/metadata inaccessible
```

### 3.2 Reading Depth Constraints & Enforcements

1. **Extraction Method Guard**:
   An evidence record cannot claim verbatim full-text extraction if the source was only read at abstract depth.
   ```python
   @model_validator(mode="after")
   def _check_reading_depth_constraints(self) -> "Evidence":
       if (
           self.reading_depth == ReadingDepth.ABSTRACT_ONLY
           and self.extraction_method == ExtractionMethod.VERBATIM_FULLTEXT
       ):
           raise ValueError(
               "extraction_method cannot be VERBATIM_FULLTEXT when "
               "reading_depth is ABSTRACT_ONLY"
           )
       return self
   ```

2. **Confidence Caps in Evidence Flow**:
   - When all supporting evidence for a claim has `reading_depth == ABSTRACT_ONLY`, calibrated confidence is **strictly capped at 0.5**.
   - When all supporting evidence has `reading_depth in (METADATA_ONLY, UNAVAILABLE)`, confidence is **strictly capped at 0.2**.

3. **Integrity Gate Review Reason**:
   Any claim marked `SUPPORTED` whose supporting evidence consists entirely of `ABSTRACT_ONLY` readings triggers a mandatory review reason in `check_academic_integrity`.

4. **Source History Recording**:
   When a source's reading depth changes, the transition is recorded in the source's `history` via `Source.update_reading_depth(new_depth, reason=..., actor=...)`.

---

## 4. Retrieval Status Tracking (`RetrievalStatus`)

The `RetrievalStatus` enum (`src/schemas/source.py`) tracks the operational outcome of full-text retrieval:

- `RETRIEVED`: Full text successfully acquired and parsed.
- `PARTIAL`: Incomplete document, paywalled section, or partial pages acquired.
- `FAILED`: Retrieval attempt failed (network error, paywall, 404, unsupported format).
- `NOT_ATTEMPTED`: Discovery phase candidate where retrieval has not yet been executed.

### 4.1 State Transition Guard

To prevent unretrieved sources from bypassing audit controls, the `Source` state machine enforces:
```python
if (
    new_state == SourceState.FULLTEXT_RETRIEVED
    and self.retrieval_status == RetrievalStatus.NOT_ATTEMPTED
):
    raise StateTransitionError(
        f"Source {self.id} cannot advance to FULLTEXT_RETRIEVED "
        "with retrieval_status NOT_ATTEMPTED"
    )
```

### 4.2 Error Recording

When retrieval fails, the system sets `retrieval_status = RetrievalStatus.FAILED` and records an immutable `ErrorInfo` in the source's `errors` list detailing the failure reason.

---

## 5. Structured Evidence Extraction Fields

To prevent ambiguous quoting and support structured synthesis, `Evidence` records incorporate 8 specialized extraction fields.

### 5.1 Field Definitions

```python
class Evidence(BaseRecord):
    ...
    # Structured extraction fields — all optional, never fabricated
    normalized_finding: str | None = None
    population: str | None = None
    sample_size: str | None = None
    methodology: str | None = None
    variables: list[str] | None = None
    instruments: list[str] | None = None
    statistical_result: str | None = None
    limitations: str | None = None
```

- **`normalized_finding`**: A concise, neutral proposition summarizing what the evidence found without hyperbolic adjectives.
- **`population`**: Demographics and geographic/institutional scope (e.g., `"Indonesian undergraduate students aged 18–22"`).
- **`sample_size`**: Validated participant or observation count (e.g., `"N = 412 (218 female, 194 male)"`).
- **`methodology`**: Research design (e.g., `"Cross-sectional survey with structural equation modeling"`).
- **`variables`**: Independent, dependent, mediator, and moderator variables (e.g., `["TikTok streak length", "perceived social support", "FOMO"]`).
- **`instruments`**: Validated scales and measurement tools (e.g., `["Social Connectedness Scale-Revised (Lee & Robbins, 1995)"]`).
- **`statistical_result`**: Exact statistical metrics (e.g., `"r = 0.34, p < .001; beta = 0.28, t = 4.12, R2 = 0.16"`).
- **`limitations`**: Author-reported or methodologically apparent limitations (e.g., `"Self-reported measures, convenience sampling, cross-sectional design"`).

### 5.2 Anti-Fabrication Rule (UNKNOWN > Fabricated)

Per `AGENT_CONSTITUTION.md §8` and Requirement 6.3:
- If a source does not state the sample size or statistical values, the corresponding field remains `None`.
- Under no circumstances does the system fabricate, infer, or interpolate missing parameters.
- For `ABSTRACT_ONLY` evidence, `methodology`, `instruments`, `variables`, and `statistical_result` remain `None` unless the abstract explicitly states them.
- JSON serialization omits `None` fields to keep payloads compact and readable.

---

## 6. Claim-Evidence-Source Mapping Graph (`evidence_graph.json`)

The mapping graph (`src/workflows/evidence_graph.py`) establishes an explicit bipartite dependency network connecting every claim to its justifying evidence passages, and every passage to its verified source record.

### 6.1 Topology & Schema

```json
{
  "claims": {
    "clm_001": {
      "claim_id": "clm_001",
      "claim_text": "TikTok Streak gamification increases perceived peer connectedness.",
      "status": "SUPPORTED",
      "supporting_count": 2,
      "contradicting_count": 1,
      "evidence": [
        {
          "evidence_id": "evd_001",
          "source_id": "src_001",
          "evidence_type": "PARTIAL",
          "relationship": "supports",
          "strength": "MODERATE",
          "reading_depth": "ABSTRACT_ONLY",
          "location": { "page": 12, "section": "Discussion" },
          "verification_status": "verified",
          "broken_reference": false
        }
      ]
    }
  },
  "sources": {
    "src_001": {
      "source_id": "src_001",
      "title": "Social Connectedness in Digital Spaces",
      "authors": ["Chen, L.", "Santoso, B."],
      "year": 2024,
      "doi": "10.1016/j.chb.2024.108000",
      "state": "APPROVED",
      "publisher_verified": true,
      "index_status": { "crossref": true, "pubmed": false },
      "retrieval_status": "RETRIEVED"
    }
  }
}
```

### 6.2 Broken Reference Detection

If an evidence record references a `source_id` that is not present in the sources list, the graph engine automatically flags:
```json
"broken_reference": true
```
The Integrity Gate treats any broken reference as a critical validation failure.

### 6.3 Human-Readable Graph Summary

The helper function `summarize_evidence_graph(graph)` renders a readable text tree for research audits:

```text
Evidence Graph Summary
========================================

Claim [clm_001] (SUPPORTED): "TikTok Streak gamification increases perceived peer connectedness."
  Support: 2 supporting | 1 contradicting
  ├─ Supporting: evd_001 (PARTIAL, ABSTRACT_ONLY, verified) [p. 12, §Discussion] → src_001 "Social Connectedness in Digital Spaces" (2024)
  ├─ Supporting: evd_002 (FUNCTIONAL_EQUIVALENT, FULL_TEXT, verified) [p. 45] → src_002 "Snapchat Streaks and Youth Engagement" (2022)
  └─ Contradicting: evd_003 (CONTRADICTORY, FULL_TEXT, verified) [p. 110] → src_003 "Longitudinal Assessment of Digital Streaks" (2023)
```

---

## 7. Research Provenance Chains (`provenance.jsonl`)

Provenance tracking guarantees that every single empirical assertion can be audited back to the exact second, agent, locator, and method of retrieval and verification.

### 7.1 `ProvenanceRecord` Schema

`src/schemas/provenance_record.py` defines the canonical schema:

```python
class ProvenanceRecord(SchemaModel):
    source_id: str
    evidence_id: str
    claim_id: str
    reading_depth: ReadingDepth
    page: int | None = None
    section: str | None = None
    retrieved_at: datetime | None = None
    verified_at: datetime | None = None
    verification_method: str | None = None
    evidence_relation: EvidenceRelationship
```

### 7.2 Construction Logic (`build_provenance_chain`)

The workflow `src/workflows/provenance.py` constructs chains without fabricating timestamps:
- `retrieved_at` is sourced from `source.provenance.retrieved_at`.
- `verification_method` is taken from `source.provenance.tool` or `source.provenance.origin`.
- `verified_at` is extracted from the timestamp of the first transition in `source.history` into a verified state (`SourceState.METADATA_VERIFIED`, `SourceState.APPROVED`, etc.).
- Undetermined fields remain `None`.

### 7.3 Serialization & Storage

Chains are stored in JSON Lines (`provenance.jsonl`) using atomic append operations (`append_jsonl` / `save_provenance_chain`). Each line represents an independent, immutable audit log entry.

---

## 8. Contradiction Detection Engine

A core requirement of academic integrity is that conflicting empirical evidence must be openly disclosed rather than hidden to manufacture artificial consensus.

### 8.1 Workflow: `detect_contradictions`

`src/workflows/contradiction.py` analyzes all evidence associated with a claim:

```python
@dataclass
class ContradictionReport:
    claim_id: str
    has_mixed_evidence: bool
    conflict_severity: str | None  # "HIGH", "MEDIUM", "LOW", or None
    contradictory_findings: list[ContradictoryFinding]
    null_findings: list[NullFinding]
```

### 8.2 Conflict Classification Rules

1. **Mixed Evidence**:
   Set to `True` when a claim is linked to at least one piece of supporting evidence (`SUPPORTS` or `PARTIALLY_SUPPORTS`) AND at least one piece of contradictory evidence (`CONTRADICTS` or `EvidenceType.CONTRADICTORY`).

2. **Conflict Severity Scoring**:
   Computed based on the strongest contradictory evidence attached to the claim:
   - **`HIGH`**: Strongest contradictory evidence has strength `STRONG` or `DEFINITIVE`.
   - **`MEDIUM`**: Strongest contradictory evidence has strength `MODERATE`.
   - **`LOW`**: Strongest contradictory evidence has strength `WEAK`.
   - **`None`**: No contradictory evidence present.

3. **Contradictory Findings Excerpts**:
   For each contradictory evidence record, the engine captures the `evidence_id`, `source_id`, and a verbatim excerpt of the first 200 characters of the evidence text.

4. **Null Findings**:
   Evidence records where `evidence_type == NOT_SUPPORTED` are aggregated into `null_findings` so that non-replications and null statistical results are transparently visible to writers and auditors.

### 8.3 Integration with Claim Evaluation

In `src/workflows/evidence_flow.py`, `evaluate_claim` runs `detect_contradictions`:
- When both supporting and contradicting evidence exist, the claim status becomes `ClaimStatus.CONFLICTED`.
- The evaluation `reason` field explicitly details:
  `"{N} supporting vs {M} contradicting evidence (severity: {HIGH|MEDIUM|LOW}); conflict disclosed, not hidden"`.
- A conflicted claim cannot be finalized in prose unless an academic qualifier or structured disclosure is explicitly provided.

---

## 9. Evidence Verification Audit Workflow (`audit_evidence`)

The `audit_evidence` workflow (`src/workflows/evidence_audit.py`) validates the consistency and credibility of the entire evidence pool prior to document compilation.

### 9.1 Audit Checks & Flags

| Audit Flag | Trigger Condition | Rationale |
| :--- | :--- | :--- |
| `unverified_verbatim` | `verbatim == True` and `quote_verified == False` | Verbatim text has not been confirmed present in the actual retrieved text snapshot. |
| `depth_method_mismatch` | `reading_depth == ABSTRACT_ONLY` and `extraction_method == VERBATIM_FULLTEXT` | A full-text quote cannot be extracted from a source read only at abstract level. |
| `type_relationship_mismatch` | `evidence_type == CONTRADICTORY` and `relationship == SUPPORTS` | Epistemic contradiction cannot be modeled as a supporting relationship. |
| `source_not_found` | `evidence.source_id` missing from provided sources list | Referential integrity violation in evidence registry. |
| `unverified_source` | Evidence cites a source whose state is not verified (`is_verified(state) == False`) | Quotes from unverified sources cannot be cited in academic writing. |

### 9.2 Summary Output

The audit produces an `AuditResult` containing:
- Total evidence records.
- Breakdown counts by `EvidenceType` and `ReadingDepth`.
- Counts of verified vs. unverified quotations.
- Complete list of flagged issues (`AuditFlag`).
- Machine-readable JSON output via `to_dict()` and formatted text reports via `to_text()`.

