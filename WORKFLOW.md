# WORKFLOW
## AUTONOMI AGENTIC ILMIAH v1.0

## 1. ACADEMIC WRITING MODE

CREATED
 -> PLANNED
 -> RESEARCHING
 -> VERIFYING
 -> RETRIEVING
 -> EXTRACTING
 -> SYNTHESIZING
 -> WRITING
 -> AUDITING
 -> APPROVED
 -> COMPLETED

Typical compact route:

TASK
 -> PLAN
 -> DISCOVER
 -> VERIFY
 -> EVIDENCE
 -> WRITE
 -> CITATION AUDIT
 -> FACT AUDIT
 -> DOCX

---

## 2. DEEP RESEARCH MODE

TASK
 -> RESEARCH QUESTIONS
 -> MULTI-QUERY DISCOVERY
 -> MULTI-SOURCE DISCOVERY
 -> DEDUPLICATION
 -> SOURCE RANKING
 -> METADATA VERIFICATION
 -> FULL-TEXT RETRIEVAL
 -> EVIDENCE EXTRACTION
 -> CLAIM MAPPING
 -> CONFLICT DETECTION
 -> SYNTHESIS
 -> OUTLINE
 -> WRITING
 -> CITATION AUDIT
 -> FACT AUDIT
 -> DOCX

Repeat discovery/verification/evidence stages when:
- evidence is insufficient;
- major claims remain unsupported;
- evidence conflicts materially;
- source quality is inadequate.

---

## 3. HUMAN REVIEW GATE

Trigger review when:
- DOI cannot be verified after reasonable attempts;
- evidence is materially conflicting;
- interpretation is ambiguous;
- important claim remains unsupported;
- a destructive filesystem action is proposed;
- a required capability is unavailable.

Decision request:

ISSUE
CONTEXT
WHY IT MATTERS
OPTIONS
RECOMMENDED ACTION

---

## 4. RETRY POLICY

Retries must be bounded.

Each retry should:
- record why retry occurred;
- modify the search/verification strategy when appropriate;
- avoid repeating an identical failed action indefinitely.

When retries are exhausted:
NEEDS_REVIEW or INSUFFICIENT_EVIDENCE

---

## 5. FINALIZATION CRITERIA

A research project may be marked COMPLETED only when:
- required sources are verified;
- important claims have sufficient evidence;
- citation audit passes;
- fact audit passes;
- final artifact is generated successfully;
- project state and artifacts are coherent.
