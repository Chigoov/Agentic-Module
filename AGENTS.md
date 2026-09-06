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

## Rules

- Do not invent sources, DOI, quotes, page numbers, or evidence.
- Only pass claims/evidence/sources that are already represented in JSON.
- Check the command exit code and parse stdout as JSON when the command returns JSON.
- Run `python -m pytest -q --tb=short` after code changes.
- Run `python -m src check` before reporting completion.

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
