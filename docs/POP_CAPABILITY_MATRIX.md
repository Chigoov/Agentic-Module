# PoP Capability Matrix — Phase 2.1 Hardening

**Project:** AUTONOMI AGENTIC ILMIAH
**Phase:** 2.1 — Publish or Perish Hardening
**Date:** 2026-09-02
**Status:** ✅ Complete (honest, evidence-backed)

> **Purpose:** A single tool-level `VERIFIED` never implies every PoP capability
> is proven. This matrix reports each capability dimension separately, recorded
> from **real runtime probes** against `pop8query.exe` in this environment. No
> status below is asserted without an actual executed command.

---

## Status vocabulary

| Status | Meaning |
|--------|---------|
| `VERIFIED` | A real call succeeded in this environment and the result was validated |
| `PARTIALLY_VERIFIED` | Works under some conditions; fails or degrades under others (documented) |
| `PENDING_CONFIGURATION` | Implemented but requires credentials not present |
| `UNAVAILABLE` | Deliberately not usable in this environment (e.g. Google Scholar automation) |
| `FAILED` | Implemented but failing here |

---

## 1. Tool & CLI availability

| Capability | Status | Evidence |
|-----------|--------|----------|
| `tool_availability` | ✅ `VERIFIED` | `pop8query.exe` resolved from `config/system.yaml` and confirmed on disk |
| `cli_availability` | ✅ `VERIFIED` | `--help` executed (exit 0), revealing the full flag set |
| `output_availability` | ✅ `VERIFIED` | `--format jsonl` writes one JSON object per line; decoded `utf-8-sig` |
| `normalization_availability` | ✅ `VERIFIED` | title/authors/year/venue/doi/url mapped; dict authors flattened to name strings |

---

## 2. Datasource status

| Datasource | Status | Evidence |
|-----------|--------|----------|
| `crossref` | ✅ `VERIFIED` | title/keywords/author/journal/sort exit 0 with real records; **no API key required** |
| `pubmed` | ✅ `VERIFIED` | title search exit 0 with 3 real records |
| `openalex` | ⚠️ `PARTIALLY_VERIFIED` | single-term title works; multi-term title & keywords fail (exit 2, source limits) |
| `semantic_scholar` | ⚠️ `PARTIALLY_VERIFIED` | keywords works, but `--max` ignored (returned 1000); `--title` unsupported |
| `google_scholar` | 🚫 `UNAVAILABLE` | `--dryrun` cancels (exit 3); live automation not relied upon |
| `scopus` | 🔒 `PENDING_CONFIGURATION` | requires credentials; not tested |
| `wos` | 🔒 `PENDING_CONFIGURATION` | requires credentials; not tested |
| `lens` | 🔒 `PENDING_CONFIGURATION` | requires credentials; not tested |

---

## 3. Query field status

| Query field | Status | Evidence |
|-------------|--------|----------|
| `title` | ✅ `VERIFIED` | crossref/pubmed/openalex(single-term) exit 0 |
| `keywords` | ⚠️ `PARTIALLY_VERIFIED` | crossref & semantic_scholar exit 0; openalex fails |
| `author` | ✅ `VERIFIED` | crossref full-name author exit 0 and matched the author |
| `journal` | ✅ `VERIFIED` | crossref journal exit 0 |
| `years` | ✅ `VERIFIED` | `--years from-to` passes through to the command line |
| `max` | ⚠️ `PARTIALLY_VERIFIED` | crossref respects `--max`; semantic_scholar ignores it (adapter truncates locally) |
| `sort` | ✅ `VERIFIED` | `year` and `-cites` exit 0 on crossref |

---

## 4. Mapping to `IntegrationStatus`

This matrix is a **diagnostic** view and does **not** replace the tool-level
`status()` gate. The base `execute()` wrapper still returns
`NOT_IMPLEMENTED` until a real search in *this* process normalizes at least one
`Source` record, after which `mark_verified()` promotes the tool to `VERIFIED`.

The matrix is exposed programmatically via `PublishOrPerishTool.capability_matrix()`
for downstream reporting and gating of *specific* features (e.g. only route a
keyword query to crossref/semantic_scholar, not openalex).

---

## 5. Programmatic access

```python
from src.tools.publish_or_perish import PublishOrPerishTool

tool = PublishOrPerishTool()
matrix = tool.capability_matrix()
assert matrix["datasource_crossref"]["status"] == "VERIFIED"
assert matrix["datasource_openalex"]["status"] == "PARTIALLY_VERIFIED"
assert matrix["datasource_scopus"]["status"] == "PENDING_CONFIGURATION"
```

---

## 6. Compliance with Phase 2.1 directive

| Directive | Status |
|-----------|--------|
| Do not rebuild Phase 1/2 | ✅ Only additive hardening; no deletion of passing code |
| Do not delete tested implementation | ✅ All Phase 2 passing code preserved |
| No `VERIFIED` without real runtime test | ✅ Every `VERIFIED` above has a recorded runtime probe |
| Granular capability status | ✅ Per-dimension matrix, no single global label |
| STOP after Phase 2.1 | ✅ Phase 3 not started |
