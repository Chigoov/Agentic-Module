---
name: autonomi-agentic-ilmiah
description: Use the AUTONOMI AGENTIC ILMIAH repository to plan, run, audit, and generate evidence-controlled Indonesian academic writing through its CLI. Use when asked to operate this repo or produce outputs from its academic workflow; do not use for unrelated research tasks outside this repository.
metadata:
  short-description: Run the AUTONOMI academic workflow CLI
---

# AUTONOMI AGENTIC ILMIAH

Use the repository CLI from its `DATA BASE` folder. The system is designed to
avoid fabricated sources, DOI, quotations, page numbers, and evidence.

## Commands

Health check:

```powershell
python -m src check
```

Plan a topic:

```powershell
python -m src plan "topik riset"
```

Run Academic Writing Mode from JSON:

```powershell
python -m src run-academic --input-json input.json
```

Run the local workflow monitor/API:

```powershell
python -m src monitor --port 8000
```

Open `http://127.0.0.1:8000` to watch progress. AI agents can call:

- `GET /api/progress`
- `GET /api/check`
- `GET /api/plan?topic=topik%20riset`
- `POST /api/run-academic`

## Workflow

1. Run `python -m src check` before using the project.
2. Use `plan` for topic planning.
3. Prepare JSON with real `sources`, `claims`, `evidence`, and `outline`.
4. Run `run-academic`.
5. Verify `success`, `draft_path`, `docx_path`, `citation_audit.json`, and `fact_audit.json`.
6. Use `monitor` when a browser dashboard or localhost API is needed.

For the input shape, read [references/input-json.md](references/input-json.md).

## Rules

- Do not invent sources, DOI, quotes, page numbers, or evidence.
- Do not bypass citation/fact audit.
- If model routing is not configured, report the safe failure instead of inventing model output.
- After code changes, run `python -m pytest -q --tb=short` and `python -m src check`.
