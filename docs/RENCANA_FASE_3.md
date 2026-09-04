# RENCANA IMPLEMENTASI FASE 3 — RESEARCH TOOLS (PENYELESAIAN)

> Status: **DRAFT — MENUNGGU REVIEW. BELUM DIEKSEKUSI.**
> Bahasa dokumen: Indonesia.
> Tanggal penyusunan: 2026-09-02.
> Sesuai permintaan user: *"buatkan implementasi untuk apa yang kamu kerjakan ke depannya, tapi jangan eksekusi dulu, aku ingin review dulu."*

---

## 1. Ringkasan & Konteks

Fase 2 (integrasi nyata **Publish or Perish**) telah **SELESAI dan TERVERIFIKASI**:

```
python -m pytest tests/test_publish_or_perish_integration.py -m integration -v
→ 5 passed in 7.89s
```

Pembuktian end-to-end menghasilkan data Crossref nyata (judul, penulis, tahun, DOI) tanpa API key, dan `status()` berpromosi dari `NOT_IMPLEMENTED` → `VERIFIED` hanya setelah run nyata berhasil.

Fase ini (yang saya sebut **Fase 3**) adalah **melengkapi sisanya dari `BUILD_PLAN.md` PHASE 3 — RESEARCH TOOLS**, yang masih tersisa setelah PoP selesai:

| Item BUILD_PLAN Phase 3 | Status |
|---|---|
| PublishOrPerish | ✅ SELESAI (Fase 2) |
| Crossref | ⬜ belum |
| OpenAlex | ⬜ belum |
| Semantic Scholar | ⬜ belum |
| PubMed | ⬜ belum |
| web search | ⬜ belum (lihat Open Question #2) |
| deduplication/normalization | ⬜ belum (fondasi Fase 3) |

> [!IMPORTANT]
> Fase ini **HANYA membangun TOOLS + lapisan normalisasi/dedup**. Tidak ada agent, tidak ada orchestrator, tidak ada ModelRouter — sesuai hard-stop directive user pada akhir Fase 2 dan keputusan user untuk **menunda integrasi LLM**.

---

## 2. Rekonsiliasi Penomoran Fase

Ada ketidaksesuaian antara penomoran `BUILD_PLAN.md` dengan keputusan user. Saya catat eksplisit agar tidak ada kebingungan:

| BUILD_PLAN.md | Status aktual |
|---|---|
| Phase 0 — Discovery | ✅ selesai |
| Phase 1 — Foundation | ✅ selesai & terverifikasi (73 test fast) |
| Phase 2 — MODEL ROUTING | ⏸ **DITUNDA** (user: "Belum tahu — tunda integrasi LLM") |
| Phase 3 — RESEARCH TOOLS | 🔶 **sebagian** (hanya PoP yang selesai) |

**Kesimpulan penomoran:** "Fase 2" yang disetujui user adalah *Publish or Perish* (salah satu item BUILD_PLAN Phase 3). Sementara "Phase 2 — Model Routing" di BUILD_PLAN masih ditunda. Maka pekerjaan berikutnya adalah **menyelesaikan BUILD_PLAN Phase 3 (Research Tools)**. Saya memberi label "Fase 3" untuk pekerjaan ini agar tidak bertabrakan dengan "Fase 2 = PoP" yang sudah dikenal user.

---

## 3. Status Saat Ini (yang sudah ada)

Komponen fondasi yang sudah terverifikasi dan **tidak akan dirombak**:

- `src/tools/base.py` — `BaseTool` dengan gate status (`execute()` menolak memanggil tool yang `is_usable()`-nya false) dan normalisasi error (`_failure()`).
- `src/schemas/source.py` — `Source` (state machine DISCOVERED→…→APPROVED), `SourceType` (enum), `SourceState`, helper `is_verified`/`is_approved`.
- `src/schemas/base.py` — `BaseRecord` (`extra="forbid"`), `Provenance`, `dump_jsonl`/`load_jsonl`.
- `src/core/storage.py` — `write_json`/`read_json`/`append_jsonl` (atomic, boundary-check).
- `src/core/config.py` — `ToolSection` dengan `status, enabled, base_url, api_key_env, contact_email_env, timeout_seconds` + property `api_key`/`contact_email`.
- `src/tools/publish_or_perish.py` — adapter PoP nyata (terverifikasi).
- `config/system.yaml` — sudah punya stub `tools.crossref`, `tools.openalex`, `tools.semantic_scholar`, `tools.pubmed`, `tools.web_search` dengan `status: NOT_IMPLEMENTED`.

### Masalah teknis yang harus diselesaikan Fase 3

1. **Naming mismatch PoP → `Source`.** `PublishOrPerishTool._normalize()` mengeluarkan key `source_origin`, `cited_by`, `rank`, `publisher`, `issn`, `volume`, `issue`, `pages`, `_raw`, dan `source_type` berupa *string mentah*. Sementara `Source` punya `citation_count` (bukan `cited_by`), `source_type` berupa *enum* `SourceType`, dan **tidak punya** field top-level `source_origin/publisher/issn/volume/issue/pages`. Karena `Source` mewarisi `extra="forbid"`, field ekstra ini **wajib dipindah ke `Source.metadata`** lewat *mapping layer*.

2. **Tidak ada HTTP adapter bersama.** PoP memakai `subprocess`; API Crossref/OpenAlex/Semantic Scholar/PubMed memakai HTTP. Perlu satu `HttpClient` bersama (stdlib, tanpa dependensi baru) agar politeness header, timeout, retry, dan preservasi raw response konsisten.

3. **Tidak ada dedup/normalisasi.** BUILD_PLAN Phase 3 mensyaratkan *deduplication/normalization*.

---

## 4. Ruang Lingkup Fase 3

### In scope ✅

1. **Lapisan normalisasi & mapping** (deterministik, murni, testable offline).
2. **Deduplikasi** sumber.
3. **`HttpClient`** berbasis stdlib.
4. **CrossrefTool** (tanpa API key — sudah terbukti bekerja via PoP).
5. **OpenAlexTool** (tanpa key; pakai `mailto` politeness).
6. **SemanticScholarTool** (tanpa key; rate-limited).
7. **PubMedTool** (E-utilities; tanpa key; politeness wajib).
8. Konfigurasi tiap tool (sudah ada stub; tinggal diaktifkan setelah terverifikasi).
9. Unit test (fast) + integration test (`@pytest.mark.integration`).

### Out of scope ❌

- **ModelRouter / integrasi LLM** — ditunda (user).
- **Agent apa pun** (TaskAnalyzer, ResearchPlanner, Discovery, Verification, dst.) — fase berikutnya.
- **Workflow orchestrator** — fase berikutnya.
- **web_search** — diusulkan **ditunda** (butuh keputusan provider, lihat Open Question #2).
- **Scopus / Web of Science / Lens** — butuh akses berbayar/berlisensi; tidak tersedia di lingkungan ini.
- **DOCX, Synthesis, Audit** — fase 6–8.
- **TUGAS 1 / TUGAS 2** — tidak disentuh.

---

## 5. Arsitektur Target

```
agents/            (tetap kosong — fase berikutnya)
tools/
  base.py          (ada)
  publish_or_perish.py   (ada)
  model_router.py        (ada, ditunda)
  http_client.py         [BARU]  HttpClient stdlib
  source_mapper.py       [BARU]  normalisasi + map dict -> Source
  dedupe.py              [BARU]  deduplikasi
  crossref.py            [BARU]  CrossrefTool
  openalex.py            [BARU]  OpenAlexTool
  semantic_scholar.py    [BARU]  SemanticScholarTool
  pubmed.py              [BARU]  PubMedTool
```

Prinsip:
- Setiap tool = subclass `BaseTool` dengan `status()` konservatif (sama seperti PoP): `NOT_IMPLEMENTED` → `VERIFIED` **hanya** setelah run nyata menghasilkan ≥1 `Source`.
- Tool **tidak** memuat logika provider di dalam agent (agent belum ada). Lapisan adaptor (`http_client.py`) dipisah dari kontrak tool.

---

## 6. Desain Detail

### 6.1 `source_mapper.py` — normalisasi & mapping (INTI)

Fungsi murni, tanpa I/O:

| Fungsi | Tujuan |
|---|---|
| `normalize_doi(value) -> str \| None` | strip `https://doi.org/`, `http://dx.doi.org/`, `doi:`, lowercase, trim. Kembalikan `None` bila kosong/malformed. |
| `normalize_title(value) -> str` | lowercase, buang tanda baca, collapse whitespace — untuk kunci dedup. |
| `normalize_authors(raw) -> list[str]` | terima `list[str]`/string; pecah `;`/`,`; buang kosong. |
| `coerce_source_type(raw) -> SourceType` | map string tipe Crossref/OpenAlex/PubMed → enum `SourceType`, default `OTHER`. |
| `source_from_dict(data, *, origin, source_type_hint=None) -> Source` | map dict provider → `Source`; field tak dikenal → `Source.metadata`. |

**Tabel mapping PoP → `Source`:**

| Key PoP (`_normalize`) | Field `Source` | Catatan |
|---|---|---|
| `title` | `title` | wajib |
| `authors` | `authors` | |
| `year` | `year` | |
| `venue` | `venue` | PoP menamainya `source` (journal) |
| `doi` | `doi` | lewat `normalize_doi` |
| `url` | `url` | PoP: `article_url` |
| `abstract` | `abstract` | |
| `source_type` (string) | `source_type` (enum) | lewat `coerce_source_type` |
| `cited_by` | `citation_count` | **rename** |
| `source_origin` | `metadata["source_origin"]` | ekstra |
| `publisher` | `metadata["publisher"]` | ekstra |
| `issn` / `volume` / `issue` / `pages` / `rank` | `metadata[...]` | ekstra |
| `_raw` | `metadata["_raw"]` | preservasi raw |

**Mapping `coerce_source_type` (Crossref type → `SourceType`):**

| String provider | `SourceType` |
|---|---|
| `journal-article` | `JOURNAL_ARTICLE` |
| `proceedings-article` | `CONFERENCE_PAPER` |
| `book` | `BOOK` |
| `book-chapter` | `BOOK_CHAPTER` |
| `dissertation` | `THESIS` |
| `posted-content` | `PREPRINT` |
| `report` | `TECHNICAL_REPORT` |
| lainnya | `OTHER` |

**Kunci dedup (`dedupe_key`):**
- `doi` ternormalisasi jika ada; jika tidak, `normalize_title(title) + "|" + first_author + "|" + year`.

### 6.2 `dedupe.py` — deduplikasi

- `deduplicate(sources: Iterable[Source]) -> list[Source]`
- Prioritas: cocokkan **DOI** dulu; fallback cocokkan **judul ternormalisasi + penulis pertama + tahun**.
- Pertahankan record dengan metadata terlengkap saat duplikat; catat merge di `verification_notes`.

### 6.3 `http_client.py` — HTTP adapter stdlib

- Pakai `urllib.request` (stdlib) — **tanpa dependensi baru** (sesuai batasan "no new package installs").
- Header politeness:
  - `User-Agent: AUTONOMI-AGENTIC-ILMIAH/1.0 (mailto:<email>)`
  - OpenAlex: parameter `mailto`; PubMed: parameter `tool` + `email`.
- Timeout dari config (`timeout_seconds`, default 30).
- **Retry terbatas** (WORKFLOW §4): `research.max_discovery_retries` (default 3), exponential backoff, **hanya** pada kondisi transient (429 / 5xx), catat alasan tiap retry, dan **variasikan** (mis. tunggu lebih lama tiap percobaan). Saat habis → `NEEDS_REVIEW` / failure terstruktur, **bukan** hasil kosong yang seolah sukses.
- **Preservasi raw** (SYSTEM_RULES §H.50): simpan teks respons mentah (terpotong di `response`, lengkap di cache/log bila relevan).

### 6.4 Tool API (Crossref/OpenAlex/Semantic Scholar/PubMed)

Pola kontrak sama untuk keempatnya:

- `XxxRequest(ToolRequest)`: `query`, filter opsional (`year_start/year_end`, `source_type`), `max_results`, `timeout_seconds`.
- `XxxResponse(ToolResponse)`: `results: list[Source]`, `result_count`, `raw_count`, `query_used`, `raw_response_text` (terpotong), `request_url`.
- `XxxTool._execute()` → `HttpClient.get_json(...)` → `source_from_dict(...)` → kembalikan `list[Source]`.
- `status()`: `NOT_IMPLEMENTED` sampai run nyata sukses + parse ≥1 `Source`; lalu `mark_verified()` (pola flag module-level seperti PoP, reset tiap proses).

**Rincian endpoint (fakta umum, akan diverifikasi saat implementasi — tidak menebak di kode):**

| Tool | Endpoint | Key? | Politeness |
|---|---|---|---|
| Crossref | `https://api.crossref.org/works?query.bibliographic=...&rows=N` | Tidak | `mailto` |
| OpenAlex | `https://api.openalex.org/works?search=...&per-page=N` | Tidak | `mailto` |
| Semantic Scholar | `https://api.semanticscholar.org/graph/v1/paper/search?query=...` | Opsional (rate-limit 429) | `User-Agent` |
| PubMed | E-utilities `esearch` + `esummary` (dua langkah) | Tidak | `tool` + `email`, ≤3 req/detik |

> [!NOTE]
> Endpoint dan nama field respons di atas adalah *target* yang **akan diverifikasi terhadap respons nyata** saat implementasi (sesuai pola discovery yang sama seperti PoP — jangan menebak syntax/field). Field hasil nyata yang tidak dikenal selalu masuk ke `metadata`, tidak pernah di-drop.

---

## 7. Perubahan per File (Proposed Changes)

### Komponen 1 — Lapisan normalisasi/dedup (tanpa I/O, fast-test)

#### [NEW] [source_mapper.py](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/src/tools/source_mapper.py)
Fungsi normalisasi + `source_from_dict` + `coerce_source_type` (lihat §6.1).

#### [NEW] [dedupe.py](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/src/tools/dedupe.py)
`deduplicate(...)` + `dedupe_key(...)` (lihat §6.2).

### Komponen 2 — HTTP adapter

#### [NEW] [http_client.py](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/src/tools/http_client.py)
`HttpClient` stdlib + retry terbatas + politeness (lihat §6.3).

### Komponen 3 — Empat tool riset

#### [NEW] [crossref.py](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/src/tools/crossref.py)
#### [NEW] [openalex.py](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/src/tools/openalex.py)
#### [NEW] [semantic_scholar.py](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/src/tools/semantic_scholar.py)
#### [NEW] [pubmed.py](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/src/tools/pubmed.py)

### Komponen 4 — Integrasi kecil PoP (opsional, non-breaking)

#### [MODIFY] [publish_or_perish.py](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/src/tools/publish_or_perish.py)
Tambahkan method `to_sources() -> list[Source]` yang memanggil `source_from_dict(...)` atas `results` yang sudah ada. **Tidak mengubah** kontrak `results: list[dict]` yang sudah di-test, agar tidak merusak Fase 2 yang selesai.

### Komponen 5 — Konfigurasi

#### [MODIFY] [system.yaml](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/config/system.yaml)
Stub tool sudah ada. Fase ini **tidak** menandai `status: VERIFIED` secara preemptif. Hanya:
- Menambah `user_agent` / `mailto` default bila relevan.
- `contact_email_env` sudah ada; memastikan property `contact_email` dipakai HttpClient.
- **Opsional:** bump `system.build_phase` 1 → 3 (lihat Open Question #5).

### Komponen 6 — Tests

#### [NEW] [test_source_mapper.py](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/tests/test_source_mapper.py)
Unit test murni (fast): normalisasi DOI/title/authors, `coerce_source_type`, mapping dict PoP → `Source` (termasuk field ekstra → `metadata`), kunci dedup.

#### [NEW] [test_dedupe.py](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/tests/test_dedupe.py)
Unit test murni (fast): dedup by DOI, dedup by title+author+year, pertahankan record terlengkap.

#### [NEW] [test_http_client.py](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/tests/test_http_client.py)
Unit test (fast, tanpa jaringan nyata) dengan stub/monkeypatch `urllib.request` untuk retry & timeout & parsing error.

#### [NEW] [test_research_tools_integration.py](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/tests/test_research_tools_integration.py)
`@pytest.mark.integration`: run nyata Crossref/OpenAlex/Semantic Scholar/PubMed, assert `status` promosi ke `VERIFIED` hanya setelah run nyata.

---

## 8. Status Gate & No-Fabrication (wajib)

Mengikuti pola PoP yang sudah terbukti:

- `status()` tiap tool = `NOT_IMPLEMENTED` sampai run nyata sukses & parse ≥1 `Source`.
- `mark_verified()` hanya dipanggil oleh integration test setelah bukti nyata.
- Tool tidak pernah mengembalikan hasil kosong yang "tampak sukses" saat network/API gagal — selalu failure terstruktur.
- Field tak dikenal → `metadata`, **tidak pernah di-drop atau ditemukan**.
- Raw response dipertahankan untuk audit.
- Tidak menandai `VERIFIED` di `system.yaml` sebelum integration test lulus.

---

## 9. Rencana Pengujian

### Automated (fast suite — harus tetap hijau)

```
python -m pytest tests/ -v        # 73 existing + unit test baru; integration auto-deselect
```

### Automated (integration — jaringan nyata)

```
python -m pytest tests/ -m integration -v
```

Kriteria lulus per tool: exit/HTTP sukses, `result_count >= 1`, `status()` → `VERIFIED` setelah `mark_verified()`.

### Manual / verifikasi tambahan

- `python -m src.runtime.bootstrap --check` → tetap `[OK]`.
- `import` semua modul baru → tidak ada error.

---

## 10. Open Questions / Keputusan yang Dibutuhkan

> [!IMPORTANT]
> **1. Pustaka HTTP — `urllib.request` (stdlib) vs `requests`.** Saya rekomendasikan **stdlib** untuk menghormati batasan "tidak install paket baru". Konfirmasi tidak apa-apa tanpa `requests`.

> [!IMPORTANT]
> **2. `web_search`.** Perlu keputusan provider (API key? scraping?). Saya rekomendasikan **TUNDA `web_search` ke fase berikutnya** (sifatnya mirip keputusan LLM), dan Fase 3 fokus ke 4 API akademik yang tidak butuh key. Konfirmasi.

> [!IMPORTANT]
> **3. Urutan implementasi.** Rekomendasi: (1) source_mapper + dedupe (murni), (2) http_client, (3) Crossref, (4) OpenAlex, (5) Semantic Scholar, (6) PubMed. Konfirmasi urutan ini atau mau urutan lain.

> [!IMPORTANT]
> **4. Batas cakupan.** Konfirmasi Fase 3 = **tools saja** (tanpa agent, tanpa orchestrator, tanpa ModelRouter).

> [!IMPORTANT]
> **5. `build_phase`.** `config/system.yaml` masih `build_phase: 1`, dan `tests/test_config.py::test_system_section_defaults` meng-assert `build_phase == 1`. Saya usulkan bump ke `3` + update test tersebut. Konfirmasi boleh, atau biarkan dulu.

---

## 11. Batasan yang Diketahui

- Semantic Scholar tanpa key sangat rate-limited (429); integrasi bisa "flaky" pada test berulang → akan di-handle dengan retry + backoff dan test yang toleran.
- PubMed E-utilities mewajibkan jeda antar-request; lebih lambat dari yang lain.
- web_search ditunda (kalau disetujui).
- Scopus/WoS/Lens tidak tersedia (berbayar/berlisensi).

---

## 12. Kriteria Selesai Fase 3

1. Keempat tool riset (Crossref, OpenAlex, Semantic Scholar, PubMed) punya adapter + status gate.
2. Lapisan normalisasi/mapping/dedup terpasang dan ter-test (fast).
3. Fast suite tetap hijau; integration test lulus untuk tool yang bisa diakses jaringan.
4. `status: VERIFIED` hanya muncul setelah run nyata (bukan di YAML preemptif).
5. Dokumentasi fase + laporan status (sesuai `BUILD_PLAN.md` DEVELOPMENT RULE).
