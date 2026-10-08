# AI AGENT INSTRUCTIONS

Use this repository through the CLI. Work from the `DATA BASE` folder.

## Mandatory execution isolation and preflight

- Every new agent task, plan, or search must create a new uniquely named project
  folder under the selected project workspace (`TUGAS 1`, `TUGAS 2`, etc.).
  A revision/resume of the same task uses a new immutable run in the same project;
  use `--resume` or API `resume: true`. Preserve title, language, citation style,
  research options, source provenance, and semantic reviews.
- Before an agent workflow starts, centralized preflight must pass the system
  health check, confirm the execution folder is writable, and verify every
  tool required by that flow is available. If one check fails, stop and report
  the missing capability; do not continue with partial or invented output.
- Existing `source_documents/` may be copied into the new execution folder as
  immutable inputs. Generated artifacts and audit trails belong only to it.
- Quantitative article reviews must set `quantitative_review: true` (or provide
  `quantitative_review_records`) and use the supplied `Standar Baku Hasil
  Agent.xlsx`. The workbook is preflighted before the workflow starts; missing
  templates or unavailable tools stop the run. Forty is an initial target, not
  a maximum; select exactly N only when explicitly requested (the structured
  option or “tepat N artikel”). Keep the full corpus and screening reasons.
  “Artikel terbaik” without a count requires structured clarification; independent
  verification and corpus storage may continue.
- Do not trust APPROVED, FULL_TEXT, quote_verified, or total_score flags from raw
  input. Recheck metadata snapshots, retrieval hashes, article identity, readable
  full manuscript content, located quotes, and logged examination/assessment.
- `require_free_full_text` is a project policy, not a global restriction. Main
  synthesis/final ranking require scientific eligibility and legally free,
  obtained, readable manuscripts. Retain other candidates and their reasons.
- Keep technical execution separate from scientific readiness. Preserve `success`
  compatibility; report `execution_success`, `result_status`,
  `finalization_allowed`, and `needs_human_review` in response metadata/run summary.
  PARTIAL workbook/scoring, incomplete required sections, and unresolved blocking
  review items prevent final DOCX. Resolved items and optional warnings do not.

## Commands

Health check:

```powershell
python -m src check
```

Create a research plan:

```powershell
python -m src plan "topik atau instruksi riset"
```

Run Academic Writing Mode from JSON:

```powershell
python -m src run-academic --input-json path\to\input.json
```

Inspect run history:

```powershell
python -m src runs --input-json path\to\input.json
python -m src runs --input-json path\to\input.json --run-id <run_id>
```

Prune older runs, keeping the N newest runs:

```powershell
python -m src runs --input-json path\to\input.json --prune --keep 20
```

Export academic output bundle as .zip:

```powershell
python -m src export-bundle --input-json path\to\input.json
python -m src export-bundle --input-json path\to\input.json --run-id <run_id>
```

Run Deep Research Mode:

```powershell
python -m src research --topic "topik atau instruksi riset" --workspace "TUGAS 1" --min-sources 2 --max-sources 5
```

Inspect and resolve review queue:

```powershell
python -m src review-queue path\to\project --status PENDING
python -m src review-queue path\to\project --resolve <item_or_claim_id> --notes "catatan resolusi" --decision SUPPORTED
```

Finalize academic project after resolving review items:

```powershell
python -m src finalize path\to\project
```

## Rules

- Do not invent sources, DOI, quotes, page numbers, or evidence.
- Only pass claims/evidence/sources that are already represented in JSON.
- Academic final outputs must not contain internal ChatGPT/File citation tokens such as `turn...`, `view...`, `search...`, or `filecite`.
- Academic final outputs use APA 7 pointers and references for sources actually
  cited. Available, assessed, synthesized, and cited counts may differ; never
  force every available source into the body. Mark missing metadata consistently.
- For every data source, legal source, and scientific article, report the source name, year, title, link/DOI when available, and page/section when available.
- Every final academic output must be reviewed and verified by a human expert before publication or submission.
- Never finalize academic output (SourceState.APPROVED or final DOCX) if sources have not been verified against real bibliographic databases (Crossref/PubMed/etc.).
- Run the humanizer pass before final DOCX: keep Indonesian prose simple, natural, and student-like; remove generic AI filler without adding facts, citations, sources, or evidence.
- Enforce the `human-doc-output-guard` policy: follow user instructions narrowly without unsolicited bloat, maintain natural student tone without AI clichés, keep tables/spreadsheets simple and authentic, and verify `human_style_audit.json` passes.
- Use normal student document layout: short headings, ordinary paragraphs, bullets only for real lists, and tables only for comparisons/data/rubrics. Keep tables compact with clear headers, usually 2-4 columns, and avoid long paragraphs inside cells.
- Check the command exit code and parse stdout as JSON when the command returns JSON.
- Run `python -m pytest -q --tb=short` after code changes.
- Run `python -m src check` before reporting completion.

## Environment Capability Modes

Before running academic tasks, detect your environment capability:

1. **Full Mode (Sandbox + Terminal + Internet + File Write):**
   - Verify real sources via internet search (Crossref, DOI, venues, authors, volume, issue, pages).
   - Build verified JSON payload (`input_json.md`).
   - Run `python -m src run-academic --input-json input.json`.
   - Verify citation and fact audits (`passed: true`).
   - Export bundle with `python -m src export-bundle`.

2. **Limited Mode (Missing Terminal or Internet or Write Access):**
   - If no internet: operate only on verified sources already stored locally. Do not guess new sources.
   - If no terminal: verify sources, construct valid input JSON, and provide exact CLI command for user execution.
   - Transparently disclose environment limits; never pretend execution occurred if skipped.

3. **Draft-Only Mode (No Internet Search / Sources Cannot Be Verified):**
   - STRICTLY FORBIDDEN: creating fake DOIs, fake quotes, fake page numbers, or fake bibliographies.
   - STRICTLY FORBIDDEN: final academic publication or claiming sources are verified.
   - Mark claims as `PROPOSED` or `INSUFFICIENT_EVIDENCE`.
   - Mark incomplete sources as `[sumber belum lengkap]`.
   - Produce only conceptual outlines or draft notes with explicit unverified disclaimers.

## Architectural Boundaries

- **Skill:** Workflow instructions, ethical rules, and agent reasoning protocol.
- **Python Engine:** Deterministic verification gates, audit checks, citation formatting, and DOCX/ZIP packaging.
- **Model Provider:** Optional component (OpenRouter or any provider is NOT a mandatory prerequisite; the engine runs locally and deterministically).
- **Internet Search:** Mandatory component for real source verification.
- **Sandbox/Terminal:** Mandatory component for actual execution and compilation.

See `skills/autonomi-agentic-ilmiah/SKILL.md`, `skills/human-doc-output-guard/SKILL.md`, and `skills/autonomi-agentic-ilmiah/references/` for detailed reference.

## Minimal JSON Shape

`run-academic` expects:

```json
{
  "project": {},
  "sources": [],
  "claims": [],
  "evidence": [],
  "outline": {}
}
```

The objects must match the Pydantic schemas in `src/schemas`.
