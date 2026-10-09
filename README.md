# AUTONOMI AGENTIC ILMIAH

Evidence-controlled autonomous academic research workflow engine.

Agent/Hermes payloads must follow the current
[input contract](skills/autonomi-agentic-ilmiah/references/input-json.md), also
linked by both repository skills. The supplied
[synthetic input](skills/autonomi-agentic-ilmiah/references/input-synthetic.json)
is schema-valid and deliberately PARTIAL. Positive synthetic pipeline tests
do not verify real literature, providers, or Hermes execution. Proposed research
rubric: [reviewable proposal](docs/USULAN_RUBRIK_KUANTITATIF.md), not approved weights.

**System root:** `DATA BASE/`

AUTONOMI AGENTIC ILMIAH is an academic research operating system designed
to produce **scientifically verifiable academic writing** using
**evidence-based references**. Every important claim is traceable to a
verified source and located evidence. No source, DOI, or quotation is ever
invented.

Each CLI execution receives a fresh uniquely named project folder under the
selected workspace. Before any agent or tool call, the workflow checks system
health, writable execution storage, and required tool availability.

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
│   └── runtime/               # Bootstrap, execution isolation & health check
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

### Windows Shortcut Launcher (`aai.bat`)

From `DATA BASE/`, you can use the short `aai.bat` launcher:

```cmd
:: 1. Setelah clone (cek kesiapan sistem)
aai.bat check

:: 2. Buka live progress di browser (menyalakan monitor jika belum aktif)
aai.bat open

:: 3. Jalankan workflow akademik dari input JSON
aai.bat run skills/autonomi-agentic-ilmiah/references/input-synthetic.json

:: 4. Lihat riwayat audit trail eksekusi
aai.bat runs skills/autonomi-agentic-ilmiah/references/input-synthetic.json

:: 5. Ekspor bundle paket riset (.zip)
aai.bat bundle skills/autonomi-agentic-ilmiah/references/input-synthetic.json
```

---

### Direct Python Commands

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
   Build phase: 18
```

`Build phase: 18` means the current roadmap has completed the local API and
workflow monitor pass in `BUILD_PLAN.md`.

Run the fast test suite:

```bash
python -m pytest tests/ -q
```

Create a plan from a topic:

```bash
python -m src plan "your research topic"
```

Run end-to-end Deep Research Mode from a raw topic or JSON:

```bash
python -m src research --topic "your research topic"
python -m src research --input-json research_request.json
```

Run Academic Writing Mode from a JSON payload:

```bash
python -m src run-academic --input-json input.json
```

For a quantitative article review, add `quantitative_review: true` and
`quantitative_review_records` to the same JSON payload. The workflow writes
`quantitative_review.xlsx`, `quantitative_review_report.md`, and
`checksum_manifest.json` from the supplied standard workbook. The template is
resolved from `quantitative_review_template`, then
`AUTONOMI_QUANTITATIVE_REVIEW_TEMPLATE`, then the bundled
[standard workbook](templates/Standar%20Baku%20Hasil%20Agent.xlsx) in `templates/`.
The user's `Documents/Codex` folder is a final fallback. The number 40 is an initial target: records above 40
are retained. Final ranking requires a completed rubric, traceable assessment,
and scientific/access eligibility; placeholder weights never produce final scores.
Use `quantitative_review_exact_count: 40` only when
the request explicitly says “tepat 40 artikel”. A request for “artikel
terbaik” without a count returns structured clarification while preserving the
corpus. Selection limits the ranked selection, while `screening_audit.json`
retains all candidates and reasons.

New tasks receive new projects; revisions use `--resume` or API `resume: true`
and create a new run in the same project. Review options and semantic reviews
persist through CLI, API, resume, and finalize. Export packages immutable
artifacts from the requested run and writes a separate ZIP checksum manifest.

`success` retains its established execution/audit contract. Additional response
metadata and `run_summary.json` distinguish `execution_success`, `result_status`
(`PASS`, `PARTIAL`, `FAILED`), `needs_human_review`, and `finalization_allowed`.
A processed PARTIAL result can be saved/exported without producing a final DOCX.
Use project `output_type: "literature_review"` for mandatory nonempty review
sections, or `required_sections` for a user template. Other output types retain
their own structure. Set project `research_options.require_free_full_text: true`
for legal free full-text research, with manuscript version and scientific
eligibility recorded separately from access.

Stored full-text proof uses `metadata.retrieval` (artifact SHA-256, retrieval
time and origin), `metadata.examination` (source ID, artifact SHA-256, reviewer,
time, scope, located excerpts), and `metadata.eligibility_review` (decision and
located construct/population/design evidence). Workbook assessment records
bind criterion scores to that artifact and the template rubric. Metadata
verification snapshots are written by the existing verification engine and
reused only while their identity and integrity can be checked. Legacy records
without these proofs remain candidates requiring verification.

Run the local workflow monitor:

```bash
python -m src monitor --port 8000
```

Then open `http://127.0.0.1:8000`.

On Windows, non-technical users can double-click:

```text
OPEN_LIVE_PROGRESS.bat
```

`START_MONITOR.bat` is also available when the user wants the server to run in
the same terminal window.

For sharing and AI-agent usage, see `docs/CARA_MEMBAGIKAN_PROJECT.md` and
`docs/CARA_CEPAT_UNTUK_ORANG_AWAM.md`.

---

## Build Status

See `BUILD_PLAN.md` for the current roadmap. Completed code includes
Discovery/Foundation, PoP + research discovery tools, Context Intelligence,
Verification, Evidence/Claim, Retrieval, Research Agents, Orchestrator,
Model Routing telemetry, Synthesis/Outline, Writing, Audit, DOCX generation,
Academic Writing Mode, Deep Research Mode, End-to-End Validation, Optimization,
and a local workflow monitor.

---

## Integration Status (honest, granular)

| Provider | Adapter | Status |
|---|---|---|
| Crossref | `src/tools/crossref.py` | ✅ VERIFIED (real run) |
| OpenAlex | `src/tools/openalex.py` | ✅ VERIFIED (real run) |
| PubMed | `src/tools/pubmed.py` | ✅ VERIFIED (real run) |
| Semantic Scholar | `src/tools/semantic_scholar.py` | ⚠️ NOT_VERIFIED (HTTP 429, needs API key) |
| Publish or Perish | `src/tools/publish_or_perish.py` | ✅ VERIFIED (real run) |
| DOAB (Open Access Books) | `src/tools/doab.py` | ✅ VERIFIED_LIVE (real REST run) |
| Open Library | `src/tools/open_library.py` | ✅ VERIFIED_LIVE (real search.json run) |
| Model Router | `src/routing/model_router.py` | 🟡 PENDING_CONFIGURATION / TESTED_OFFLINE |
| PDF Parser (Page-based) | `src/tools/pdf_parser.py` | ✅ TESTED_OFFLINE |

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
