# AI AGENT INSTRUCTIONS

Use this repository through the CLI. Work from the `DATA BASE` folder.

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

## Rules

- Do not invent sources, DOI, quotes, page numbers, or evidence.
- Only pass claims/evidence/sources that are already represented in JSON.
- Academic final outputs must not contain internal ChatGPT/File citation tokens such as `turn...`, `view...`, `search...`, or `filecite`.
- Academic final outputs must convert every verified source into APA 7 in-text citations and a bibliography entry, or mark the source as `[sumber belum lengkap]`.
- For every data source, legal source, and scientific article, report the source name, year, title, link/DOI when available, and page/section when available.
- Every final academic output must be reviewed and verified by a human expert before publication or submission.
- Never finalize academic output (SourceState.APPROVED or final DOCX) if sources have not been verified against real bibliographic databases (Crossref/PubMed/etc.).
- Run the humanizer pass before final DOCX: keep Indonesian prose simple, natural, and student-like; remove generic AI filler without adding facts, citations, sources, or evidence.
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

See `skills/autonomi-agentic-ilmiah/SKILL.md` and `skills/autonomi-agentic-ilmiah/references/` for detailed reference.

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
