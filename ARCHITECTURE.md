# SYSTEM ARCHITECTURE
## AUTONOMI AGENTIC ILMIAH v1.0

## 1. HIGH-LEVEL ARCHITECTURE

USER
  |
  v
OrchestratorAgent
  |
  +--> TaskAnalyzerAgent
  +--> ResearchPlannerAgent
  +--> DiscoveryAgent
  +--> VerificationAgent
  +--> RetrievalAgent
  +--> EvidenceExtractionAgent
  +--> ClaimVerificationAgent
  +--> SynthesisAgent
  +--> OutlineAgent
  +--> WriterAgent
  +--> CitationAuditAgent
  +--> FactAuditAgent
  |
  v
DOCX OUTPUT

Agents use Tools through interfaces/adapters.

---

## 2. LAYERING

### Agents
Reasoning and decisions.

### Tools
Capabilities:
- Publish or Perish;
- Crossref;
- OpenAlex;
- Semantic Scholar;
- PubMed;
- web search;
- PDF retrieval/parsing;
- DOCX generation;
- filesystem.

### Adapters
Provider-specific implementations.

### Workflows
State machines and orchestration rules.

### Schemas
Machine-readable contracts.

### Rules
System constitution and operational policies.

### Config
Environment and research configuration.

### Storage
Artifacts, logs, cache, state metadata, and databases.

---

## 3. DATA BASE ROLE

DATA BASE/ is the system root.

Recommended structure:

DATA BASE/
├── 00_MASTER_INSTRUCTION.md
├── AGENT_CONSTITUTION.md
├── ARCHITECTURE.md
├── SYSTEM_RULES.md
├── WORKFLOW.md
├── BUILD_PLAN.md
├── agents/
├── tools/
├── adapters/
├── workflows/
├── schemas/
├── prompts/
├── config/
├── app/
├── database/
├── state/
├── cache/
├── logs/
├── tests/
└── docs/

The implementation may use another structure when technically justified, but it must remain internally coherent and documented.

---

## 4. AGENT RESPONSIBILITIES

TaskAnalyzerAgent
- convert user request into structured requirements.

ResearchPlannerAgent
- define research questions;
- keywords;
- source requirements;
- year strategy;
- citation style;
- mode selection.

DiscoveryAgent
- generate search strategies;
- call source discovery tools;
- collect candidates;
- deduplicate.

VerificationAgent
- verify existence and metadata;
- corroborate DOI and publisher information;
- score/rank candidates;
- control source state.

RetrievalAgent
- obtain abstract/full text/source pages when legally and technically available.

EvidenceExtractionAgent
- extract evidence with location metadata.

ClaimVerificationAgent
- map claims to evidence;
- classify support strength;
- detect overclaiming.

SynthesisAgent
- synthesize verified evidence;
- represent agreement and conflict.

OutlineAgent
- structure the document.

WriterAgent
- generate prose from verified claims/evidence.

CitationAuditAgent
- verify citations and references.

FactAuditAgent
- audit factual claims and evidence fit.

OrchestratorAgent
- coordinate state transitions;
- manage retries;
- invoke review gates;
- never replace specialized agent responsibilities with hidden monolithic logic.

---

## 5. TOOL MAP

PublishOrPerishTool
CrossrefTool
OpenAlexTool
SemanticScholarTool
PubMedTool
WebSearchTool
PDFRetrievalTool
PDFParsingTool
DOCXGenerationTool
FileSystemTool

Every tool should have a stable interface and a provider-specific implementation.

---

## 6. MODEL ROUTING

ModelRouter abstracts model providers.

Capability examples:
PLANNING
RESEARCH
REASONING
WRITING
AUDITING

Possible model providers:
Claude
GPT
Gemini
others

ModelRouter is an optional routing/provider layer and must not leak into business logic.

---

## 7. RESEARCH DATA FLOW

Candidate source
    ->
normalized source record
    ->
verification
    ->
approved source
    ->
retrieval
    ->
evidence
    ->
claim support
    ->
synthesis
    ->
draft
    ->
audit
    ->
final DOCX

---

## 8. DESIGN RULE

Every important object should have:
- stable ID;
- schema;
- provenance;
- status;
- timestamps where useful;
- error information where useful.

The system should support future extensions without rewriting existing workflow contracts.
