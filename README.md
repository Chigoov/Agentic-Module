# AUTONOMI AGENTIC ILMIAH

Evidence-controlled autonomous academic research workflow engine.

**System root:** `DATA BASE/`

AUTONOMI AGENTIC ILMIAH is an academic research operating system designed
to produce **scientifically verifiable academic writing** using
**evidence-based references**. Every important claim is traceable to a
verified source and located evidence. No source, DOI, or quotation is ever
invented.

---

## Mission

To build the most trustworthy autonomous academic research assistant
capable of producing scientifically verifiable academic writing using
evidence-based references.

The conceptual chain the system enforces:

```
DISCOVER → VERIFY → RETRIEVE → UNDERSTAND → EXTRACT → SUPPORT
        → SYNTHESIZE → WRITE → AUDIT
```

---

## Repository Layout

```
DATA BASE/
├── 00_MASTER_INSTRUCTION.md   # Authoritative operational specification
├── AGENT_CONSTITUTION.md      # Non-negotiable integrity rules
├── ARCHITECTURE.md            # Layered architecture
├── BUILD_PLAN.md              # Development roadmap (phases)
├── ENGINEERING_PROTOCOL.md    # Mandatory engineering process
├── SYSTEM_INDEX.md            # Documentation navigation index
├── SYSTEM_RULES.md            # Operational rules
├── WORKFLOW.md                # Research lifecycle / state machines
├── config/system.yaml         # System configuration
├── docs/                      # Phase reports, audits, capability matrix
├── src/                       # System source code
│   ├── core/                  # Deterministic infra (paths, config, storage)
│   ├── schemas/               # Data contracts (Source, Claim, Evidence…)
│   ├── tools/                 # External capabilities + provider adapters
│   ├── agents/                # Reasoning components (interface)
│   ├── workflows/             # State machines / orchestration
│   └── runtime/               # Bootstrap & health check
└── tests/                     # Fast + integration tests
```

Project workspaces (`TUGAS 1/`, `TUGAS 2/`, …) sit **outside** `DATA BASE/`
and hold project-specific research artifacts and final outputs.

---

## Requirements

- Python **3.11+** (developed/tested on 3.14)
- `pydantic==2.13.4`, `PyYAML==6.0.3`, `python-dotenv==1.2.2`
- `pytest==9.1.1` (for tests)

Install:

```bash
pip install -r requirements.txt
```

---

## Quick Start

Run the system health check (validates spec files, config, storage, and
that no integration is falsely claimed as verified):

```bash
# From DATA BASE/
python -m src check
```

Expected output:

```
[OK] System health check passed
   SYSTEM_ROOT: ...\DATA BASE
   WORKSPACE_ROOT: ...\AUTONOMI AGENTIC ILMIAH
   Spec version: 1.0
   Build phase: 17
```

`Build phase: 17` means the current roadmap has completed the optimization
reporting pass in `BUILD_PLAN.md`.

Run the fast test suite:

```bash
python -m pytest tests/ -q
```

Create a plan from a topic:

```bash
python -m src plan "your research topic"
```

Run Academic Writing Mode from a JSON payload:

```bash
python -m src run-academic --input-json input.json
```

---

## Build Status

See `BUILD_PLAN.md` for the current roadmap. Completed code includes
Discovery/Foundation, PoP + research discovery tools, Context Intelligence,
Verification, Evidence/Claim, Retrieval, Research Agents, Orchestrator,
Model Routing telemetry, Synthesis/Outline, Writing, Audit, DOCX generation,
Academic Writing Mode, Deep Research Mode, End-to-End Validation, and Optimization.

---

## Integration Status (honest, granular)

| Provider | Adapter | Status |
|---|---|---|
| Crossref | `src/tools/crossref.py` | ✅ VERIFIED (real run) |
| OpenAlex | `src/tools/openalex.py` | ✅ VERIFIED (real run) |
| PubMed | `src/tools/pubmed.py` | ✅ VERIFIED (real run) |
| Semantic Scholar | `src/tools/semantic_scholar.py` | ⚠️ NOT_VERIFIED (HTTP 429, needs API key) |
| Publish or Perish | `src/tools/publish_or_perish.py` | ✅ VERIFIED (real run) |

Semantic Scholar was **not** promoted to VERIFIED because the shared egress
IP returns HTTP 429 without an API key. Set `SEMANTIC_SCHOLAR_API_KEY` and
re-run the integration suite to prove it.

---

## Configuration

Configuration lives in `config/system.yaml`. Every value can be overridden
with environment variables using the `AUTONOMI__` prefix and `__` as the
nesting separator, e.g.:

```bash
AUTONOMI__LOGGING__LEVEL=DEBUG
AUTONOMI__TOOLS__PUBLISH_OR_PERISH__EXECUTABLE_PATH="D:/PoP/pop8query.exe"
```

---

## Principles

- **No fabrication.** Never invent a source, DOI, metadata, quote, page
  number, or tool result.
- **Evidence-controlled.** A claim is only written after verified evidence
  supports it.
- **Trustworthy by design.** Every integration status is earned by a real
  test run, never claimed from a config file.

---

## License

(TBD — add a license before public distribution.)
