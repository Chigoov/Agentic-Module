# Laporan Fase 2.1 — Publish or Perish Hardening

**Proyek:** AUTONOMI AGENTIC ILMIAH
**Fase:** 2.1 — Publish or Perish Hardening
**Status:** ✅ **SELESAI**
**Tanggal:** 2026-09-03
**Build Phase:** 2.1

---

## 1. Tujuan

Menutup gap verifikasi yang ditemukan setelah Phase 2, **tanpa merombak
architecture** dan **tanpa membangun ulang foundation**. Phase 2.1 bersifat
*additive only*: tidak ada kode Phase 1/2 yang lulus test yang dihapus atau
dibangun ulang.

---

## 2. Hasil Discovery Runtime (jujur, bukan tebakan)

Seluruh status di bawah berasal dari **probe runtime nyata** terhadap
`pop8query.exe` di environment ini. Tidak ada klaim `VERIFIED` tanpa perintah
yang benar-benar dieksekusi.

### 2.1 Tool & CLI

| Kapabilitas | Status | Bukti |
|-------------|--------|-------|
| `tool_availability` | ✅ `VERIFIED` | `pop8query.exe` teresolusi dari config & terkonfirmasi di disk |
| `cli_availability` | ✅ `VERIFIED` | `--help` dieksekusi (exit 0), menampilkan set flag lengkap |
| `output_availability` | ✅ `VERIFIED` | `--format jsonl` menulis satu objek JSON/baris; didecode `utf-8-sig` |
| `normalization_availability` | ✅ `VERIFIED` | title/authors/year/venue/doi/url dipetakan; author dict di-flatten ke string |

### 2.2 Datasource

| Datasource | Status | Bukti |
|-----------|--------|-------|
| Crossref | ✅ `VERIFIED` | title/keywords/author/journal/sort exit 0, data nyata, tanpa API key |
| PubMed | ✅ `VERIFIED` | title search exit 0, 3 record nyata |
| OpenAlex | ⚠️ `PARTIALLY_VERIFIED` | single-term title OK; multi-term title & keywords gagal (exit 2) |
| Semantic Scholar | ⚠️ `PARTIALLY_VERIFIED` | keywords OK; `--max` diabaikan (return 1000); `--title` unsupported |
| Google Scholar | 🚫 `UNAVAILABLE` | `--dryrun` cancel (exit 3); automasi live tidak diandalkan |
| Scopus | 🔒 `PENDING_CONFIGURATION` | butuh credentials; belum diuji |
| WoS | 🔒 `PENDING_CONFIGURATION` | butuh credentials; belum diuji |
| Lens | 🔒 `PENDING_CONFIGURATION` | butuh credentials; belum diuji |

### 2.3 Query Field

| Field | Status | Bukti |
|-------|--------|-------|
| `title` | ✅ `VERIFIED` | crossref/pubmed/openalex(single-term) exit 0 |
| `keywords` | ⚠️ `PARTIALLY_VERIFIED` | crossref & semantic_scholar exit 0; openalex gagal |
| `author` | ✅ `VERIFIED` | crossref full-name exit 0 dan cocok dengan author |
| `journal` | ✅ `VERIFIED` | crossref journal exit 0 |
| `years` | ✅ `VERIFIED` | `--years from-to` diteruskan ke command line |
| `max` | ⚠️ `PARTIALLY_VERIFIED` | crossref menghormati `--max`; semantic_scholar mengabaikan → adapter truncate lokal |
| `sort` | ✅ `VERIFIED` | `year` dan `-cites` exit 0 pada crossref |

---

## 3. Gap Verifikasi yang Ditutup

| Kapabilitas | Sebelum (Phase 2) | Sesudah (Phase 2.1) |
|-------------|-------------------|---------------------|
| Keyword search | ⚠️ flag ada, belum diuji | ✅ crossref & semantic_scholar exit 0 (openalex partial) |
| Author search | ⚠️ flag ada, belum diuji | ✅ crossref full-name exit 0 dan cocok |
| Journal search | ⚠️ flag ada, belum diuji | ✅ crossref journal exit 0 |
| Datasource tambahan | ⚠️ hanya crossref | ✅ pubmed verified; openalex/semantic_scholar partial |
| Enforce `--max` | ⚠️ diasumsikan | ⚠️ crossref patuh; semantic_scholar → truncate lokal |

---

## 4. Hardening Kode (additive)

| Perubahan | Alasan |
|-----------|--------|
| Konsolidasi `_QUERY_FIELD_FLAGS` (module-level) | Perbaiki bug laten: error path referensi `field_flag_map` duplikat yang stale |
| Flatten author dict (`{name, affiliation}` → nama) | OpenAlex return dict, Crossref return string; dinormalisasi keduanya |
| Truncate `max_results` lokal di `execute()` | Semantic Scholar abaikan `--max`; adapter kini patuh secara lokal |
| Tambah `capability_matrix()` | Status granular per-dimensi; satu `VERIFIED` tidak lagi berarti semua fitur |

---

## 5. File yang Dibuat / Diubah

| File | Perubahan |
|------|-----------|
| `src/tools/publish_or_perish.py` | Hardening + `capability_matrix()` |
| `tests/test_tools.py` | +3 fast test (author dict, author string, capability matrix) |
| `docs/POP_CAPABILITY_MATRIX.md` | [BARU] Evidence matrix per-dimensi |
| `docs/PHASE_2_REPORT.md` | Tambah section 17 (addendum Phase 2.1) |
| `docs/LAPORAN_FASE_2_1.md` | [BARU] Laporan ini |

---

## 6. Hasil Test

### Fast suite
```
$ python -m pytest tests/ -v
... 76 passed, 5 deselected in 0.48s
```
✅ **76 passed** (3 test baru), 5 integration test tetap deselected.

### Bootstrap
```
$ python -m src.runtime.bootstrap
[OK] System health check passed
[OK] Bootstrap complete
```
✅ Bootstrap bersih.

### Import check
```
from src.tools.publish_or_perish import PublishOrPerishTool
-> imports OK
```
✅ Semua import teresolusi.

---

## 7. Kepatuhan terhadap Konstitusi & Direktif

| Aturan | Status |
|--------|--------|
| NEVER INVENT A SOURCE / DOI / METADATA | ✅ Semua record dari runtime nyata; missing = None |
| NEVER CITE AN UNVERIFIED SOURCE | ✅ Tidak ada `VERIFIED` tanpa test runtime nyata |
| Jangan rebuild Phase 1/2 | ✅ Hanya hardening additive |
| Jangan hapus implementasi lulus test | ✅ Semua kode Phase 2 yang lulus dipertahankan |
| Status granular (bukan global) | ✅ `capability_matrix()` per-dimensi |
| STOP setelah Phase 2.1 | ✅ Phase 3 tidak dimulai |

---

## 8. Ringkasan Status Jujur

- **`VERIFIED`:** tool/CLI/output/normalization; Crossref (semua field); PubMed (title).
- **`PARTIALLY_VERIFIED`:** OpenAlex (single-term title saja); Semantic Scholar (keywords, tanpa `--max`); field `max`.
- **`PENDING_CONFIGURATION`:** Scopus, WoS, Lens (credentials).
- **`UNAVAILABLE`:** Google Scholar live automation.

**Tidak ada kapabilitas yang dilabeli `VERIFIED` tanpa test runtime nyata.**
Evidence table lengkap tersedia di [POP_CAPABILITY_MATRIX.md](POP_CAPABILITY_MATRIX.md).
