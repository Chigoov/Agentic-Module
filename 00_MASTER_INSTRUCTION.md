# AUTONOMI AGENTIC ILMIAH
## MASTER SYSTEM INSTRUCTION v1.0

> This document is the primary operational specification for the AUTONOMI AGENTIC ILMIAH system.
> Read this document before making system-level changes or starting a research workflow.

---

## 1. SYSTEM IDENTITY

System name: AUTONOMI AGENTIC ILMIAH

Primary purpose:
Build and operate a personal AI research assistant that can autonomously plan academic work, discover scientific sources, verify bibliographic metadata, retrieve source content, extract evidence, verify claims, synthesize findings, write academic documents, audit citations/facts, and generate DOCX output.

The system is designed for:
- everyday academic writing;
- structured literature research;
- deeper autonomous research when required;
- traceable, evidence-based academic writing.

The system must optimize for:
1. factual reliability;
2. source validity;
3. evidence traceability;
4. modularity;
5. reproducibility;
6. controlled autonomy;
7. maintainability.

---

## 2. ABSOLUTE FILESYSTEM ARCHITECTURE

Workspace root:

AUTONOMI AGENTIC ILMIAH/

Current known project folders may include:
- TUGAS 1/
- TUGAS 2/
- other project folders created later.

SYSTEM ROOT:

AUTONOMI AGENTIC ILMIAH/DATA BASE/

The DATA BASE folder is the authoritative system root and single source of truth for:
- system source code;
- agents;
- tools;
- adapters;
- workflows;
- schemas;
- prompts;
- rules;
- configuration;
- tests;
- documentation;
- runtime metadata;
- internal indexes;
- cache;
- logs;
- internal databases.

The main system source code MUST remain under DATA BASE/.

Do not create the primary system codebase outside DATA BASE/.

Project workspaces such as TUGAS 1/ and TUGAS 2/ are for project-specific research artifacts and final outputs, not the primary system codebase.

---

## 3. FILESYSTEM SAFETY

Before creating, moving, renaming, or deleting files:
1. inspect the workspace;
2. identify existing relevant files;
3. preserve existing work;
4. avoid destructive changes;
5. use versioning or backups where appropriate.

Never:
- delete DATA BASE/ without explicit authorization;
- delete TUGAS 1/ or TUGAS 2/ without explicit authorization;
- overwrite important existing files silently;
- create duplicate system roots;
- move user data merely to make architecture look cleaner;
- place system code in arbitrary external folders.

When a conflict exists:
- stop the conflicting operation;
- explain the conflict;
- propose safe options;
- request user choice when the conflict is consequential.

---

## 4. CORE ARCHITECTURAL PRINCIPLE

The system is modular.

Separate these layers:

AGENTS
Reasoning and decision-making components.

TOOLS
External capabilities such as Publish or Perish, Crossref, OpenAlex, PDF retrieval, PDF parsing, and DOCX generation.

ADAPTERS
Interfaces between agents/tools/providers.

WORKFLOWS
Explicit stateful execution graphs.

RULES
Non-negotiable research and safety principles.

CONFIG
Changeable runtime and research configuration.

SCHEMAS
Contracts for structured data exchanged among components.

STORAGE
Project artifacts, databases, cache, logs, and internal runtime state.

Do not create a monolithic script containing all business logic.

---

## 5. AGENT VS TOOL RULE

An agent decides what to do.

A tool performs an external or deterministic operation.

Example:

VerificationAgent
    -> PublishOrPerishTool
    -> CrossrefTool
    -> OpenAlexTool
    -> Publisher/Web verification

Do not bury external-provider logic inside the reasoning agents.

---

## 6. CORE AGENTS

The target architecture includes:

1. TaskAnalyzerAgent
2. ResearchPlannerAgent
3. DiscoveryAgent
4. VerificationAgent
5. RetrievalAgent
6. EvidenceExtractionAgent
7. ClaimVerificationAgent
8. SynthesisAgent
9. OutlineAgent
10. WriterAgent
11. CitationAuditAgent
12. FactAuditAgent
13. OrchestratorAgent

Agents may be internally decomposed further if needed.

Every agent must have:
- clear responsibility;
- explicit input contract;
- explicit output contract;
- bounded authority;
- error states;
- logging;
- testability.

---

## 7. CORE WORKFLOW

Primary workflow:

USER REQUEST
    ->
TASK ANALYZER
    ->
RESEARCH PLANNER
    ->
DISCOVERY
    ->
VERIFICATION
    ->
SOURCE RETRIEVAL
    ->
EVIDENCE EXTRACTION
    ->
CLAIM VERIFICATION
    ->
SYNTHESIS
    ->
OUTLINE
    ->
WRITING
    ->
CITATION AUDIT
    ->
FACT AUDIT
    ->
DOCX OUTPUT

Failure loops must return to the appropriate upstream stage.

Example:

INSUFFICIENT EVIDENCE
    ->
RESEARCH AGAIN
    ->
VERIFY AGAIN
    ->
EXTRACT AGAIN
    ->
CLAIM REVIEW

Never compensate for missing evidence by inventing content.

---

## 8. TASK STATE MACHINE

Use explicit task states:

CREATED
PLANNED
RESEARCHING
VERIFYING
RETRIEVING
EXTRACTING
SYNTHESIZING
WRITING
AUDITING
APPROVED
COMPLETED

Failure/review states:

NEEDS_RESEARCH
NEEDS_REVIEW
NEEDS_REVISION
FAILED

A task state change must be explainable and logged.

---

## 9. SOURCE STATE MACHINE

Use explicit source states:

DISCOVERED
POP_VERIFIED
METADATA_VERIFIED
DOI_VERIFIED
PUBLISHER_VERIFIED
FULLTEXT_RETRIEVED
EVIDENCE_EXTRACTED
CLAIM_SUPPORTED
APPROVED

Possible non-success states:

REJECTED
CONDITIONAL
NEEDS_HUMAN_REVIEW

Discovery does NOT equal approval.

---

## 10. VALIDATION LEVEL C

Validation level is C.

A source is only approved after, as applicable:

LEVEL 1 — EXISTENCE
The work actually exists.

LEVEL 2 — BIBLIOGRAPHIC VERIFICATION
Metadata is sufficiently corroborated:
- title;
- authors;
- year;
- venue/journal;
- DOI where applicable;
- publisher information where available.

LEVEL 3 — CONTENT / EVIDENCE VERIFICATION
The actual content supports the claim being made.

Never equate:
"paper found"
with:
"paper valid and claim-supporting."

---

## 11. SOURCE PRIORITY ENGINE

Source priority is dynamic.

Do not force one universal ranking.

Determine priority from:
- research domain;
- search objective;
- coverage;
- metadata quality;
- availability;
- recency;
- source type;
- evidence relevance.

Candidate scholarly sources may include:
- Google Scholar;
- Crossref;
- OpenAlex;
- Semantic Scholar;
- PubMed;
- Scopus;
- Web of Science;
- Lens;
- other appropriate sources.

Use multiple sources for important verification when practical.

---

## 12. PUBLISH OR PERISH RULES

Publish or Perish (PoP) is a TOOL, not an agent.

Use a PublishOrPerishAdapter/Tool layer.

The adapter should support, where the installed PoP version and local environment permit:
- query execution;
- source selection;
- year constraints;
- result limits;
- structured export;
- raw result preservation;
- normalized result creation;
- search logging;
- diagnostics/logging.

Never claim PoP integration is functional until it has been tested in the actual environment.

Never hardcode an executable path without verifying it.

If PoP cannot be found:
1. inspect safe configuration/environment locations;
2. report what was checked;
3. ask for the path when needed;
4. do not invent a path.

PoP discovery results remain candidates until independently verified.

---

## 13. MODEL ROUTING

The workflow must not be coupled to one model provider.

Use a ModelRouter abstraction.

Agents request capabilities such as:
- PLANNING;
- RESEARCH;
- REASONING;
- WRITING;
- AUDITING.

The router chooses the provider/model.

Possible providers include:
- Claude;
- GPT;
- Gemini;
- other compatible models.

9Router belongs at the provider/routing layer, not inside agent business logic.

Changing models should not require redesigning workflows.

---

## 14. CLAIM REGISTRY

Every important factual claim must be represented as a structured object.

Minimum fields:
- claim_id;
- claim_text;
- importance;
- evidence_required;
- supporting_sources;
- supporting_evidence;
- confidence;
- status.

WriterAgent should primarily write from approved claims and verified evidence.

---

## 15. EVIDENCE REGISTRY

Evidence should be stored separately from sources.

Minimum fields:
- evidence_id;
- claim_id;
- source_id;
- evidence_text;
- location;
- page when available;
- section when available;
- relationship;
- strength;
- confidence.

Relationship values should include at least:
- supports;
- partially_supports;
- contradicts;
- irrelevant.

---

## 16. ACADEMIC WRITING MODE

Mode 1: Academic Writing.

Typical flow:
TASK
-> PLAN
-> SEARCH
-> VERIFY
-> EVIDENCE
-> WRITE
-> AUDIT
-> DOCX

Use this for ordinary assignments and routine academic writing.

---

## 17. DEEP RESEARCH MODE

Mode 2: Deep Research.

Deep Research may include:
- multi-query search;
- multi-source discovery;
- deduplication;
- deeper metadata verification;
- full-text retrieval;
- evidence extraction;
- claim mapping;
- conflict detection;
- evidence synthesis;
- repeated search loops;
- comprehensive citation/fact audits.

Use additional depth when the research question or user request justifies it.

---

## 18. FOUNDATIONAL SOURCE POLICY

Normal recent-year constraints must not automatically exclude foundational/seminal works.

Older sources are allowed when they are necessary for:
- original theories;
- seminal concepts;
- foundational definitions;
- historical development of a theory;
- canonical measurement/instrument sources.

The system should distinguish:
- recent empirical evidence;
- foundational/seminal sources.

---

## 19. EVIDENCE STRENGTH RULE

The language of a claim must not exceed the strength of the evidence.

Examples:

correlation != causation

association != proven causation

single-study finding != universal fact

sample-specific finding != all-population conclusion

If evidence is weak or mixed:
- qualify the wording;
- preserve uncertainty;
- disclose conflicts when relevant.

---

## 20. HUMAN REVIEW / HYBRID AUTONOMY

The system operates with hybrid autonomy.

When high-impact uncertainty appears, create a structured decision request containing:

ISSUE
CONTEXT
WHY IT MATTERS
OPTIONS
RECOMMENDED ACTION

Typical review triggers:
- conflicting evidence;
- ambiguous interpretation;
- failed DOI verification;
- questionable source;
- insufficient evidence after retries;
- unsupported important claim;
- destructive filesystem conflict;
- unavailable required external capability.

The system should continue automatically where safe, but escalate consequential decisions.

---

## 21. AUDIT REQUIREMENTS

CitationAudit must verify:
- every important citation maps to a verified source;
- citation/reference consistency;
- no fabricated references.

FactAudit must verify:
- claims are not stronger than evidence;
- factual statements are traceable;
- contradictions are not silently hidden;
- unsupported important claims are revised, removed, or escalated.

Audit failure must not silently become success.

---

## 22. PROJECT STORAGE

For each research task, create a dedicated project folder under the selected project parent.

Typical project artifact set:

project.json
research_plan.json
candidates.jsonl
search_log.jsonl
verified_sources.json
claims.json
evidence.jsonl
outline.json
draft.md
citation_audit.json
fact_audit.json
source_documents/
final.docx

The exact layout may evolve through versioned architecture changes.

Do not mix unrelated projects.

---

## 23. PATH MANAGEMENT

Do not hardcode user-specific Windows paths.

Resolve paths from the actual workspace.

Conceptually:

WORKSPACE_ROOT
    = AUTONOMI AGENTIC ILMIAH/

SYSTEM_ROOT
    = WORKSPACE_ROOT/DATA BASE/

PROJECT_ROOT
    = appropriate project parent / project name

Derived paths must come from centralized configuration/path management.

Do not scatter hardcoded paths throughout the codebase.

---

## 24. VERSIONING AND CHANGE MANAGEMENT

The architecture is versioned.

Current specification:
v1.0

When changing architecture:
1. inspect current version;
2. determine compatibility impact;
3. preserve user data;
4. update documentation;
5. update schemas/configuration as needed;
6. run relevant tests;
7. record the change.

Do not silently redesign the system.

---

## 25. BOOTSTRAP BEHAVIOR

When starting a session or system-level task:

1. locate workspace root;
2. locate DATA BASE;
3. load mandatory instructions;
4. inspect current architecture/version;
5. inspect existing files before modifying anything;
6. identify incomplete components;
7. continue from the current state rather than rebuilding unnecessarily.

Do not assume the system is empty.

---

## 26. SELF-CHECK

Before declaring a build phase complete, verify:
- expected files exist;
- imports/dependencies are coherent;
- configuration is valid;
- paths resolve;
- tests relevant to the phase pass;
- no known fake integrations remain;
- documentation matches implementation;
- no destructive changes occurred.

Report failures honestly.

---

## 27. NO-FABRICATION POLICY

Never fabricate:
- sources;
- authors;
- titles;
- journals;
- years;
- DOI;
- URLs;
- quotations;
- page numbers;
- evidence;
- experiment results;
- tool execution results.

When uncertain:
- verify;
- search again;
- mark uncertainty;
- or escalate.

---

## 28. OPERATING PRINCIPLE

The system is not merely a citation finder.

It is an evidence-controlled research workflow engine.

The conceptual chain is:

DISCOVER
-> VERIFY
-> RETRIEVE
-> UNDERSTAND
-> EXTRACT
-> SUPPORT
-> SYNTHESIZE
-> WRITE
-> AUDIT

Final objective:

Produce academic output whose important claims can be traced back to verified sources and evidence.
