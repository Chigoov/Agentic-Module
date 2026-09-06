# Input JSON

`run-academic` expects this shape:

```json
{
  "project": {
    "name": "contoh",
    "workspace": "TUGAS 1",
    "path": "C:\\path\\to\\project",
    "title": "Judul",
    "citation_style": "APA7",
    "language": "id"
  },
  "sources": [],
  "claims": [],
  "evidence": [],
  "outline": {}
}
```

Objects must match the Pydantic schemas in `src/schemas`.

Minimal outputs:

- `draft.md`
- `citation_audit.json`
- `fact_audit.json`
- `final.docx`
