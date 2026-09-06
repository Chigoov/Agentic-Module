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
- Academic final outputs must not contain internal ChatGPT/File citation tokens such as `turn...`, `view...`, `search...`, or `filecite`.
- Academic final outputs must convert every verified source into APA 7 in-text citations and a bibliography entry, or mark the source as `[sumber belum lengkap]`.
- For every data source, legal source, and scientific article, report the source name, year, title, link/DOI when available, and page/section when available.
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
