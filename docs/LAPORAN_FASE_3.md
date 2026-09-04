# LAPORAN FASE 3 — RESEARCH TOOLS (LENGKAP)

> **Status:** ✅ SELESAI — `build_phase = 3` DIFINALISASI
> **Tanggal:** 2026-09-03
> **Bahasa:** Indonesia
> **Dasar:** [implementation_plan.md](file:///c:/Users/HYPE%20AMD/.gemini/antigravity-ide/brain/c745d19e-546e-4bb3-85d0-f4cbda166977/implementation_plan.md) + **PHASE 3 EXECUTION ADDENDUM (10 poin)**

---

## 1. Ringkasan Eksekutif

Fase 3 (Research Tools) selesai. Tiga dari empat provider riset akademik **terverifikasi nyata terhadap respons runtime**, lapisan normalisasi/dedup/HTTP adapter terpasang dan ter-test, kedua prasyarat audit (A1, A2) ditutup, dan **Semantic Scholar secara jujur ditandai `NOT_VERIFIED`** karena rate-limit (HTTP 429) di lingkungan ini — sesuai Addendum #4 (tidak ada promosi status spekulatif).

---

## 2. Hasil Test (Bukti Runtime)

### 2.1 Fast suite (baseline + test baru)
```
python -m pytest tests/ -q
→ 115 passed, 9 deselected
```
- **Baseline (sebelum Fase 3): 76 passed, 5 deselected** (dicatat sebagai `task.md #1`).
- **Test baru Fase 3: +39** (source_mapper, dedupe, http_client, research_tools).
- **9 deselected** = 5 integration lama + 4 integration baru (otomatis, sesuai `pyproject.toml`).

### 2.2 Integration suite (network nyata)
```
python -m pytest tests/ -m integration -v
```

| File | Hasil | Bukti |
|---|---|---|
| `test_publish_or_perish_integration.py` | **5 passed** | Regresi Fase 2/2.1 terjaga (Addendum #6) |
| `test_research_tools_integration.py` | **4 passed** | Crossref, year-filter, OpenAlex, PubMed |

### 2.3 Bootstrap health check
```
python -m src.runtime.bootstrap --check
→ [OK] System health check passed — Build phase: 3
```

---

## 3. Capability Matrix (Granular — Addendum #4)

| Provider | Adapter | Status | Bukti Runtime |
|---|---|---|---|
| **Crossref** | `src/tools/crossref.py` | ✅ **VERIFIED** | `test_crossref_real_search` + `test_crossref_year_filter_passed_through` |
| **OpenAlex** | `src/tools/openalex.py` | ✅ **VERIFIED** | `test_openalex_real_search` |
| **PubMed** | `src/tools/pubmed.py` | ✅ **VERIFIED** | `test_pubmed_real_search` (esearch + esummary) |
| **Semantic Scholar** | `src/tools/semantic_scholar.py` | ⚠️ **NOT_VERIFIED** | HTTP 429 berulang (shared egress IP, tanpa API key) |

> [!IMPORTANT]
> **Semantic Scholar TIDAK ditandai VERIFIED.** Selama Phase 3 discovery, endpoint `api.semanticscholar.org` berulang kali mengembalikan HTTP 429 dari IP egress bersama tanpa API key. Adapter ditulis sesuai skema publik yang terdokumentasi, tetapi statusnya dibiarkan `NOT_VERIFIED` — mempromosikannya tanpa run sukses melanggar Addendum #4 dan `AGENT_CONSTITUTION.md §23`.

---

## 4. Prasyarat Audit yang Ditutup

| ID | Prasyarat | Status | Cara |
|---|---|---|---|
| **A1** 🔴 | Hardcoded path `_DEFAULT_INSTALL_DIRS` di source | ✅ **DITUTUP** | Hapus konstanta; tambah `search_dirs` ke `ToolSection` + `system.yaml`; `_executable()` baca dari config |
| **A2** 🟠 | `PoP._normalize()` tidak cocok skema `Source` | ✅ **DITUTUP** | `source_mapper.py` + `PublishOrPerishTool.to_sources()` menghasilkan `list[Source]` |
| **B2** 🟡 | `build_phase` masih `1` | ✅ **DITUTUP** | Difinalisasi ke `3` **setelah** semua acceptance lulus (Addendum #2) |

> [!NOTE]
> **A3** (StateMachine ABC tanpa subclass) dan **B1** (ModelCapability ≠ ARCHITECTURE.md §6) **tidak disentuh** — di luar scope Fase 3 (Addendum #9).

---

## 5. File yang Dibuat / Diubah

### Lapisan normalisasi/dedup (murni, fast-test)
- [NEW] `src/tools/source_mapper.py` — normalisasi DOI/title/authors/type/year + `source_from_dict()`
- [NEW] `src/tools/dedupe.py` — dedup by DOI lalu title+author+year, merge record terlengkap

### HTTP adapter
- [NEW] `src/tools/http_client.py` — stdlib `urllib`, retry/backoff/timeout, structured failure

### Empat tool riset
- [NEW] `src/tools/crossref.py` — `CrossrefTool`
- [NEW] `src/tools/openalex.py` — `OpenAlexTool`
- [NEW] `src/tools/semantic_scholar.py` — `SemanticScholarTool` (preservasi limit, Addendum #5)
- [NEW] `src/tools/pubmed.py` — `PubMedTool`
- [NEW] `src/tools/research_tool.py` — shared `ResearchRequest`/`ResearchResponse`/`ResearchTool` base

### Integrasi PoP (non-breaking)
- [MODIFY] `src/tools/publish_or_perish.py` — hapus `_DEFAULT_INSTALL_DIRS`, tambah `to_sources()`
- [MODIFY] `src/core/config.py` — tambah `search_dirs` ke `ToolSection`
- [MODIFY] `config/system.yaml` — `search_dirs` + finalisasi `build_phase: 3`
- [MODIFY] `src/tools/__init__.py` — ekspor modul baru
- [MODIFY] `src/__init__.py` — `BUILD_PHASE = 3`

### Tests
- [NEW] `tests/test_source_mapper.py` (14 test)
- [NEW] `tests/test_dedupe.py` (9 test)
- [NEW] `tests/test_http_client.py` (7 test)
- [NEW] `tests/test_research_tools.py` (9 test, parser tanpa jaringan)
- [NEW] `tests/test_research_tools_integration.py` (4 test, `@pytest.mark.integration`)
- [MODIFY] `tests/test_config.py` — assertion `build_phase == 3`

---

## 6. Kepatuhan Addendum (10 Poin)

| # | Poin | Status |
|---|---|---|
| 1 | Baseline test dinamis (tidak asumsi jumlah tetap) | ✅ Baseline 76 dicatat; +39 di atasnya |
| 2 | `build_phase` tidak dinaikkan di awal | ✅ Dinaikkan ke 3 hanya setelah acceptance lulus |
| 3 | Verifikasi endpoint nyata | ✅ Crossref/OpenAlex/PubMed/PubMed-esummary di-fetch real; Semantic Scholar 429 terdokumentasi |
| 4 | Granular capability status | ✅ Semantic Scholar tetap `NOT_VERIFIED` meski 3 provider lain `VERIFIED` |
| 5 | Preservasi limit (requested_max/raw_count/returned_count/local_truncation) | ✅ `ResearchResponse` + `SemanticScholarTool` |
| 6 | Perlindungan regresi Fase 1/2/2.1 | ✅ PoP integration 5 passed; fast suite baseline hijau |
| 7 | Preservasi field tak dikenal → `metadata` | ✅ `source_from_dict()` + `test_preserves_unknown_fields_in_metadata` |
| 8 | Structured failure (tidak pernah kosong "tampak sukses") | ✅ `IntegrationError` + `test_http_client` (404/429/URLError/invalid JSON) |
| 9 | Larangan implementasi (ModelRouter/agents/orchestrator/Writing/DOCX) | ✅ Tidak ada yang disentuh |
| 10 | Stop setelah Fase 3 + laporan lengkap | ✅ Laporan ini |

---

## 7. Acceptance Criteria — Semua LULUS

1. ✅ Empat tool riset punya adapter + granular capability status.
2. ✅ Lapisan normalisasi/mapping/dedup terpasang dan ter-test (fast).
3. ✅ Fast suite hijau (115); integration lulus untuk tool yang bisa diakses jaringan (9 test: 5 PoP + 4 riset).
4. ✅ `VERIFIED` hanya setelah run nyata, granular per kapabilitas.
5. ✅ Field tak dikenal → `metadata`; network gagal → structured failure.
6. ✅ Hardcoded path (A1) hilang dari source.
7. ✅ `build_phase = 3` difinalisasi setelah 1–6 lulus.
8. ✅ Laporan Fase 3 lengkap ditulis.

---

## 8. Catatan & Rekomendasi Lanjutan

> [!TIP]
> **Untuk membuktikan Semantic Scholar:** set `SEMANTIC_SCHOLAR_API_KEY` (environment variable) lalu jalankan ulang `python -m pytest tests/test_research_tools_integration.py -m integration -v`. Tanpa API key, rate-limit 429 dari IP egress bersama membuat run nyata tidak mungkin stabil.

> [!NOTE]
> **Scope berikutnya (di luar Fase 3):** ModelRouter, agents (TaskAnalyzer/ResearchPlanner/Discovery/Verification), Orchestrator, Writing, DOCX. Semua ditunda sesuai Addendum #9.
