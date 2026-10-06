# Research Integrity & Academic Gate Architecture
## AUTONOMI AGENTIC ILMIAH (AAI) v1.1.0

---

## 1. Introduction: Zero Tolerance for Academic Fabrication

AUTONOMI AGENTIC ILMIAH (AAI) is built on an unwavering ethical and operational principle: **Academic Integrity by Construction**. 

In conventional generative AI systems, models routinely hallucinate plausible-sounding citations, fabricate DOIs, misattribute quotes, conflate theoretical hypotheses with proven facts, and extrapolate findings from completely unrelated populations. In AAI, the core engine operates under strict anti-fabrication rules:

$$\text{UNKNOWN} > \text{FABRICATED}$$

If a page number is absent from retrieved content, it remains `None`. If an author list or DOI cannot be corroborated against real bibliographic databases (Crossref, PubMed, OpenAlex, Semantic Scholar), the source is marked as unverified or `[sumber belum lengkap]`. If evidence for an empirical claim is only theoretical or from a proxy platform, the system actively refuses to mark the claim as `SUPPORTED`.

The central enforcement mechanism is the **Research Integrity Gate** (`src/workflows/gates.py`).

---

## 2. Research Integrity Gate (`check_academic_integrity`)

The `check_academic_integrity` function acts as a mandatory pre-writing and pre-export barrier. No academic prose, claim compilation, or DOCX document can be generated if any integrity violations exist in the input payload.

### 2.1 Gate Architecture & Contract

```python
def check_academic_integrity(
    *,
    claims: list[Claim],
    evidence: list[Evidence],
    sources: list[Source],
) -> GateResult:
    ...
```

The gate returns a `GateResult` dataclass:
```python
@dataclass
class GateResult:
    violations: list[str] = field(default_factory=list)
    review_reasons: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.violations and not self.review_reasons
```

- **`violations`**: Hard integrity breaches. These immediately halt document generation and throw an `AcademicGateError` (subclass of `HumanReviewRequired`).
- **`review_reasons`**: Ambiguities, unindexed sources, abstract-only warnings, or uncorroborated publisher flags that must be logged into the `ReviewQueue` for expert human evaluation.

---

## 3. The 14 Academic Integrity Checks

The integrity gate executes 14 distinct deterministic checks covering referential consistency, source authenticity, evidential sufficiency, and epistemic fidelity:

```
                                 check_academic_integrity
                                             │
      ┌──────────────────────────────────────┼──────────────────────────────────────┐
      │                                      │                                      │
  [Referential & State]             [Methodology & Epistemic]             [Metadata & Indexing]
  1. ID Referencing                 7. DOI Format Regex                   12. Unverified/Unretrieved
  2. Evidence Resolution            8. Type/Relation Mismatch             13. Publisher Verification
  3. Source Verification State      9. Empty Support on SUPPORTED         14. Database Indexing
  4. Important Claim Evidence      10. Overclaim Detection
  5. Conflict Disclosure           11. Abstract-Only Support
  6. Verbatim Quote Source
```

### Check 1: Referential Integrity of Evidence and Source IDs
- **Rule**: Every evidence ID referenced in `claim.supporting_evidence` or `claim.contradicting_evidence`, and every source ID referenced in `claim.supporting_sources`, must exist in the provided payload. Duplicate evidence IDs are rejected as ambiguous bookkeeping.
- **Violation Message**:
  - `"claim {claim_id} references nonexistent supporting evidence {evidence_id}"`
  - `"claim {claim_id} references nonexistent contradicting evidence {evidence_id}"`
  - `"claim {claim_id} references nonexistent source {source_id}"`
  - `"duplicate evidence IDs in payload"`
- **Historical Fix**: Audit Finding A01 (preventing untrusted claim-evidence references from leaking into documents).

### Check 2: Evidence Resolves to Valid Claim and Source
- **Rule**: Every `Evidence` record must reference a `claim_id` and a `source_id` that are present and active in the project registries. Orphan evidence is strictly prohibited.
- **Violation Message**:
  - `"evidence {evidence_id} references nonexistent claim {claim_id}"`
  - `"evidence {evidence_id} references nonexistent source {source_id}"`

### Check 3: Cited Sources Must Be Verified
- **Rule**: Status flags in user input JSON are *not* evidence. Every source cited by a claim or referenced by an evidence record must carry an authentic verification state recorded by the verification engine (`is_verified(source.state) == True`).
- **Violation Message**:
  - `"source {source_id} cited but never verified (state={source.state})"`

### Check 4: Important Claims Must Have Supporting Evidence
- **Rule**: Claims marked with `ClaimImportance.HIGH` or `ClaimImportance.CRITICAL` (which represent the central thesis or load-bearing assertions of the paper) cannot have empty `supporting_evidence`.
- **Violation Message**:
  - `"important claim {claim_id} has no supporting evidence"`

### Check 5: Conflicted Claims Must Be Disclosed
- **Rule**: Claims with status `CONFLICTED` cannot be drafted as uncontroversial statements. They must carry an explicit academic qualifier (e.g., *"Meski beberapa studi mendukung, temuan longitudinal menunjukkan hasil sebaliknya..."*) or have the contradicting evidence attached and analyzed.
- **Violation Message**:
  - `"conflicted claim {claim_id} carries no disclosure: add a qualifier or attach the contradicting evidence"`
- **Historical Fix**: Audit Finding A04.

### Check 6: Verbatim Quotes Must Come from Verified Sources
- **Rule**: If an evidence record asserts `verbatim == True`, its underlying source must be verified (`is_verified(source.state) == True`). Quoting unverified or uncorroborated sources as direct citations is prohibited.
- **Violation Message**:
  - `"verbatim quote in evidence {evidence_id} cites unverified source {source_id}"`

### Check 7: DOI Format Validation
- **Rule**: Every DOI provided for a source must conform to the international standard syntax defined by the International DOI Foundation (IDF). The gate validates all non-null DOIs against the strict regular expression:
  ```python
  DOI_PATTERN = re.compile(r"^10\.\d{4,}/\S+$")
  ```
- **Violation Message**:
  - `"invalid DOI format for source {source_id}: {doi}"`

### Check 8: Evidence Type / Relationship Mismatch Detection
- **Rule**: The epistemic classification of evidence must logically correspond with its claimed relationship. An evidence record classified as `EvidenceType.CONTRADICTORY` cannot simultaneously claim a relationship of `EvidenceRelationship.SUPPORTS`.
- **Violation Message**:
  - `"evidence type/relationship mismatch for evidence {evidence_id}"`

### Check 9: Empty Support on SUPPORTED Claim
- **Rule**: A claim marked with `status = ClaimStatus.SUPPORTED` must actually have entries in its `supporting_evidence` list. A claim cannot claim supported status in vacuum.
- **Violation Message**:
  - `"claim {claim_id} marked SUPPORTED with no supporting evidence"`

### Check 10: Overclaim Detection
- **Rule**: A claim cannot be marked `SUPPORTED` if **all** of its supporting evidence is indirect (i.e. solely `FUNCTIONAL_EQUIVALENT` or `THEORETICAL`). Claims asserting empirical reality cannot rest entirely on proxy platforms or conceptual frameworks without direct empirical warrants.
- **Violation Message**:
  - `"claim {claim_id} overclaimed: no direct evidence supports the claim"`

### Check 11: Abstract-Only Evidence Check
- **Rule**: When a claim marked `SUPPORTED` is substantiated solely by evidence extracted at `ReadingDepth.ABSTRACT_ONLY`, the system flags this epistemic vulnerability for human review.
- **Review Reason**:
  - `"claim {claim_id} supported only by abstract-level evidence"`

### Check 12: Unverified / Unretrieved Source Check
- **Rule**: An evidence record cannot cite a source that has `publisher_verified == False` and `retrieval_status == RetrievalStatus.NOT_ATTEMPTED`. Sources that were neither corroborated by publisher records nor retrieved cannot substantiate claims.
- **Violation Message**:
  - `"evidence {evidence_id} cites unverified, unretrieved source {source_id}"`

### Check 13: Publisher-Unverified Cited Source Review Reason
- **Rule**: If a source is cited in a claim but carries `publisher_verified == False`, a review item is generated to alert the researcher that the publisher has not independently corroborated this publication.
- **Review Reason**:
  - `"source {source_id} cited in claim but publisher_verified is False"`

### Check 14: Unindexed Source Review Reason
- **Rule**: If a source has an empty `index_status` dictionary or none of the queried bibliographic databases (Crossref, PubMed, Scopus, OpenAlex) report a match (`all(values == False)`), a review item is raised.
- **Review Reason**:
  - `"source {source_id} not indexed in any queried database"`

---

## 4. Output Text Scanning (`scan_output_text`)

In addition to structural integrity checks on the JSON graph, AAI runs a post-generation scan on the raw generated Markdown/prose before compiling to DOCX:

1. **Internal Token Detection (`detect_internal_tokens`)**:
   - Searches for internal agent or LLM citation artifacts: `turn...`, `view...`, `search...`, `filecite`, `cite...`.
   - Any surviving internal token is treated as an unresolvable provenance leak and immediately blocks export.

2. **Author-Year Orphan Detection (`detect_orphan_author_year_citations`)**:
   - Scans text for in-text parenthetical citations (e.g., `(Smith, 2024)`).
   - Confirms that every in-text citation matches an approved, verified source in the project bibliography. Orphan citations are flagged as violations.

---

## 5. Human Review Queue (`ReviewQueue` and `ReviewItem`)

When non-blocking ambiguities or review reasons arise, AAI routes them to the **Human Review Queue** (`src/schemas/review.py`). This guarantees that automated systems do not make arbitrary decisions on marginal evidence without expert oversight.

### 5.1 Data Model: `ReviewItem`

```python
class ReviewItem(BaseRecord):
    id_prefix: str = Field(default="rev_item", exclude=True, repr=False)
    schema_version: str = "1.1"

    item_type: str            # "claim", "evidence", "source", "system"
    item_id: str              # Target identifier (e.g. "clm_001", "src_002")
    severity: str             # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    reason: str               # Explicit description of the issue
    recommended_action: str   # Suggested resolution for human researcher
    status: str = "PENDING"   # "PENDING", "IN_REVIEW", "RESOLVED", "DISMISSED"
    resolution_notes: str | None = None
```

### 5.2 Review Queue Management (`ReviewQueue`)

The `ReviewQueue` manages items in memory and persists them to `review_queue.json` within the project root:

- **`add(item: ReviewItem)`**: Appends a new review item to the queue.
- **`query(*, status, severity, item_type)`**: Filters items by specific attributes.
- **`has_blocking_items(item_id: str) -> bool`**: Returns `True` if an entity has unresolved review items with `severity == "CRITICAL"`.
- **`save(path, root)` / `load(path)`**: Atomic JSON serialization ensuring state persistence across CLI runs.
- **`summary()`**: Generates human-readable progress reports grouped by severity.

### 5.3 Review Severity Mapping & Blocking Behavior

The helper `create_review_queue_from_gate_result` automatically ingests `GateResult.review_reasons` and semantic review triggers into the `ReviewQueue`:

| Severity | Triggers | System Behavior |
| :--- | :--- | :--- |
| **`CRITICAL`** | Semantic review required on `ClaimImportance.CRITICAL` claims; unresolved critical contradictions. | **BLOCKS FINAL OUTPUT**. The associated claim or source cannot be included in final DOCX compilation until marked `RESOLVED` or `DISMISSED`. |
| **`HIGH`** | Semantic review required on `ClaimImportance.HIGH` claims; high-severity evidence contradictions ($p < .01$). | Requires explicit user acknowledgement or resolution in human review mode. |
| **`MEDIUM`** | Abstract-only supporting evidence; publisher unverified; unindexed sources; medium importance semantic review. | Generates prominent audit warnings in reports and exports. |
| **`LOW`** | Minor formatting anomalies, background citation warnings, low importance semantic review. | Informational audit trail. |

---

## 6. Golden Test Case: TikTok Streak Scenario

To prove end-to-end correctness across the entire evidence intelligence pipeline, AAI incorporates a standardized, rigorous **Golden Research Case** (`tests/fixtures/golden_tiktok_streak.py` and `tests/test_evidence_intelligence.py`).

### 6.1 The Research Scenario

- **Claim**: *"TikTok Streak increases social connectedness among university students"*
- **Importance**: `ClaimImportance.HIGH`
- **Required Sources**: 2 distinct approved sources.

### 6.2 Attached Evidence Mix

1. **TikTok Study (`src_tiktok`)**:
   - `ReadingDepth`: `ABSTRACT_ONLY`
   - `RetrievalStatus`: `PARTIAL`
   - `EvidenceType`: `PARTIAL`
   - `Relationship`: `PARTIALLY_SUPPORTS`
   - `Strength`: `MODERATE`
2. **Snapchat Study (`src_snapchat`)**:
   - `ReadingDepth`: `FULL_TEXT`
   - `RetrievalStatus`: `RETRIEVED`
   - `EvidenceType`: `FUNCTIONAL_EQUIVALENT` (Snapchat streaks used as a proxy)
   - `Relationship`: `SUPPORTS`
   - `Strength`: `STRONG`
3. **Social Connectedness Theory (`src_connectedness`)**:
   - `ReadingDepth`: `FULL_TEXT`
   - `EvidenceType`: `THEORETICAL`
   - `Relationship`: `SUPPORTS`
   - `Strength`: `DEFINITIVE`
4. **Counter-Evidence Study (`src_counter`)**:
   - `ReadingDepth`: `FULL_TEXT`
   - `EvidenceType`: `CONTRADICTORY`
   - `Relationship`: `CONTRADICTS`
   - `Strength`: `STRONG`

### 6.3 Validated Invariants (Golden Test Assertions)

The golden test suite (`test_golden_tiktok_streak_scenario`) executes this exact scenario and verifies four fundamental integrity properties:

1. **Rejection of Overclaim**:
   Even though the input includes a `STRONG` functional equivalent and a `DEFINITIVE` theoretical warrant, `compute_support_level` strictly caps the support level at `MODERATE` due to the lack of direct empirical evidence.
2. **Confidence Degradation**:
   `calibrate_confidence` applies multipliers ($0.7 \times 0.6 = 0.42$) and further caps confidence at $0.5$ because the only direct study was read at `ABSTRACT_ONLY` depth.
3. **Contradiction Disclosure**:
   `detect_contradictions` correctly identifies `has_mixed_evidence == True`, computes `conflict_severity == "HIGH"` (driven by the `STRONG` longitudinal counter-evidence), and forces `evaluate_claim` to return `ClaimStatus.CONFLICTED`.
4. **Integrity Gate Defense**:
   If a user attempts to force the claim into `ClaimStatus.SUPPORTED` without direct evidence, `check_academic_integrity` immediately catches the overclaim (Check 10) and flags the abstract-only dependency (Check 11).

This golden scenario demonstrates that AAI cannot be coerced into presenting indirect, theoretical, or disputed findings as established factual consensus.
