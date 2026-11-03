# LAPORAN IMPLEMENTASI: UPGRADE DEEP RESEARCH WORKFLOW, OPEN-ACCESS BOOKS, DAN PROVENANCE EVIDENCE
## AUTONOMI AGENTIC ILMIAH (AAI)
**Tanggal**: 22 September 2026  
**System Root**: `C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH\DATA BASE`  
**Workspace Root**: `C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH`  

---

## 1. Ringkasan Eksekutif Perubahan

Tujuan utama pekerjaan ini telah diselesaikan secara penuh:
1. **Transformasi Deep Research menjadi End-to-End Workflow**: Mengubah `DeepResearchWorkflow` dari perencana statis (*planner stub*) menjadi alur kerja ilmiah otonom 16-tahap yang menerima topik mentah, melakukan pencarian lintas provider, verifikasi metadata, klasifikasi lisensi, pengambilan konten, ekstraksi klaim & bukti berbasis halaman, deteksi kontradiksi, sintesis, penulisan ter-disambiguasi, hingga audit sitasi dan fakta.
2. **Pencarian E-Book Open-Access & Legal**: Mengintegrasikan dua provider buku resmi via REST API publik tanpa scraping:
   - **DOAB** (*Directory of Open Access Books*) via REST API resmi (`directory.doabooks.org`).
   - **Open Library** via Search API resmi (`openlibrary.org/search.json`).
3. **Klasifikasi Hak Akses & Status Unduh**: Menambahkan model data hak akses `AccessMode` (`OPEN_DOWNLOAD`, `READ_ONLINE`, `BORROW_ONLY`, `PREVIEW_ONLY`, `UNKNOWN`) dan `RightsStatus` (`PUBLIC_DOMAIN`, `OPEN_LICENSE`, `PROVIDER_STATED_FREE`, `RESTRICTED`, `UNKNOWN`). Menegakkan aturan: `SourceState.APPROVED` tidak berarti otomatis boleh diunduh; unduh otomatis dilarang untuk lisensi tidak jelas (`UNKNOWN`) dan buku pinjaman perpustakaan digital (`BORROW_ONLY`).
4. **Direct Download pada `RetrievalTool`**: Mendukung pemisahan landing page dan URL direct download, batas ukuran berkas, penolakan file 0 byte, integritas hash SHA-256, path safety (`ensure_within`), backup otomatis file yang berubah, dan pencatatan metadata retrieval terstruktur.
5. **Ekstraksi PDF Berbasis Halaman**: Mengintegrasikan `PDFParserTool` menggunakan parser ter-pin `pypdf==6.11.0` yang mengekstrak teks dengan nomor halaman nyata (1-indexed) dan offset karakter tanpa menebak. Pindaian PDF tanpa text layer ditandai sebagai `OCR_REQUIRED` tanpa memfabrikasi teks.
6. **Disambiguasi Sitasi & Keterlacakan (Traceability)**: Menyinkronkan pemetaan sitasi pusat di `CitationManager`, `WriterAgent`, `format_reference_list`, `CitationAuditAgent`, dan `FactAuditAgent`. Sumber dengan penulis dan tahun sama menghasilkan `(Smith, 2023a)` dan `(Smith, 2023b)` secara konsisten pada naskah dan daftar pustaka. Menghasilkan artefak relasional `citation_map.json`.
7. **Model Router Fail-Safe & Capability Routing**: Router memetakan kapabilitas konseptual (`PLANNING`, `RESEARCH`, `WRITING`, `AUDITING`) ke model operasional, menyediakan klien OpenAI-compatible standar, dan tetap gagal aman (*fail-safe*) melaporkan `PENDING_CONFIGURATION` tanpa mengarang completion jika kredensial belum ada.
8. **Human Review Queue**: Mengintegrasikan `ReviewQueue` yang mencatat alasan tertolak/ambigu (lisensi tidak jelas, buku pinjaman, PDF scan, kontradiksi bukti) ke `review_queue.json` dengan rekomendasi tindakan nyata.
9. **Antarmuka CLI Baru**: Menambahkan perintah CLI `python -m src research --topic "..."` dan `python -m src research --input-json ...`.

---

## 2. File yang Diubah atau Ditambahkan

### File Baru
- `src/tools/doab.py`: Adapter resmi pencarian buku akademik open-access DOAB REST API.
- `src/tools/open_library.py`: Adapter ketersediaan dan metadata buku Open Library.
- `src/tools/pdf_parser.py`: Parser PDF berbasis halaman dan locator bukti verbatim.
- `tests/test_doab.py`: Unit test offline DOABTool (mapping, metadata, mock search, filter tahun) (4 test).
- `tests/test_open_library.py`: Unit test offline OpenLibraryTool (mapping, borrowable vs public, mock search) (3 test).
- `tests/test_book_access_status.py`: Pengujian aturan klasifikasi hak akses dan izin unduh (8 test).
- `tests/test_book_download.py`: Pengujian direct download, rights check, hash, backup, dan batas ukuran (6 test).
- `tests/test_pdf_parser.py`: Pengujian ekstraksi nomor halaman, locator bukti, dan deteksi `OCR_REQUIRED` (5 test).
- `tests/test_model_router_safe_failure.py`: Pengujian fail-safe status dan kapabilitas router (4 test).
- `tests/test_citation_disambiguation.py`: Pengujian suffix `a`/`b` sitasi dan artefak `citation_map.json` (2 test).
- `tests/test_research_pipeline.py`: Pengujian integrasi alur riset end-to-end dari topik mentah (4 test).

### File Dimodifikasi
- `src/schemas/source.py`: Menambahkan `AccessMode`, `RightsStatus`, atribut buku/hak, properti `download_allowed`, dan backward-compatible serialization.
- `src/schemas/__init__.py`: Ekspor `AccessMode`, `RightsStatus`, dan model pendukung.
- `src/schemas/project.py`: Menambahkan `CITATION_MAP` dan `REVIEW_QUEUE` pada `ProjectArtifact`.
- `src/tools/source_mapper.py`: Fungsi `classify_rights_and_access`, parsing toleran terhadap format lisensi list/dict/string, mapping atribut buku.
- `src/tools/retrieval.py`: Dukungan `direct_download`, verifikasi hak, hash SHA-256, atomic safety, integrasi `PDFParserTool`.
- `src/tools/citation_manager.py`: Disambiguasi label in-text human form (`Smith, 2023a`), fungsi `build_citation_map`.
- `src/tools/reference_formatter.py`: Dukungan suffix disambiguasi pada entri daftar pustaka APA 7.
- `src/tools/dedupe.py`: Deduplikasi multi-kunci deterministik (DOI, ISBN, Provider ID, URL, Title/Author/Year).
- `src/agents/writer.py`: Integrasi label sitasi seragam dari CitationManager dan pembuatan `citation_map.json`.
- `src/agents/research.py`: Peningkatan `DiscoveryAgent` (multi-provider), `RetrievalAgent` (direct dl fallback), `EvidenceAgent` (page-based PDF locator), dan fungsi `rank_sources`.
- `src/routing/model_router.py`: Kapabilitas konseptual, fallback aman, klien OpenAI-compatible.
- `src/workflows/deep_research.py`: Implementasi 16 tahap alur riset end-to-end, grounding bukti, evaluasi klaim, stopping conditions, dan review queue.
- `src/runtime/cli.py`: Subcommand baru `python -m src research --topic ...`.
- `config/system.yaml`: Konfigurasi provider `doab` dan `open_library`.
- `requirements.txt` & `pyproject.toml`: Pinned dependency `pypdf==6.11.0`.
- `README.md`, `ARCHITECTURE.md`, `BUILD_PLAN.md`, `docs/CARA_PAKAI_UNTUK_AI_AGENT.md`: Sinkronisasi dokumentasi arsitektur dan panduan pengguna.

---

## 3. Alur Workflow Riset yang Aktif

Alur yang sekarang berjalan pada `DeepResearchWorkflow` (`python -m src research`):

```text
User Request / Raw Topic
    ↓
1. Task Analyzer (TaskAnalyzerAgent — ekstraksi intensi & kata kunci)
    ↓
2. Research Planner (ResearchPlannerAgent — formulasi query pencarian)
    ↓
3. Discovery (DiscoveryAgent — pencarian paralel DOAB, Open Library, Crossref)
    ↓
4. Deduplication (deduplicate — DOI, ISBN, Provider ID, Title/Author/Year)
    ↓
5. Ranking (rank_sources — evaluasi status, hak akses unduh, sitasi, kebaruan)
    ↓
6. Metadata Verification (VerificationAgent — verifikasi eksistensi, DOI, publisher)
    ↓
7. Access / License Classification (classify_rights_and_access — hak & lisensi)
    ↓
8. Full-Text Retrieval (RetrievalAgent / RetrievalTool — direct download PDF atau abstract)
    ↓
9. Evidence Extraction (EvidenceExtractor + find_passage_page_location — exact match & halaman asli)
    ↓
10. Claim Verification (ClaimAgent — evaluasi tingkat dukungan bukti)
    ↓
11. Contradiction Detection (detect_contradictions — identifikasi pertentangan bukti)
    ↓
12. Synthesis (SynthesisAgent — agregasi klaim terverifikasi)
    ↓
13. Writing (WriterAgent — penyusunan draf, sitasi ter-disambiguasi Smith 2023a/b, citation_map.json)
    ↓
14. Citation Audit (CitationAuditAgent — audit token internal & sitasi yatim)
    ↓
15. Fact Audit (FactAuditAgent — audit klaim, bukti, dan qualifier)
    ↓
16. DOCX Generation atau Human Review (menghasilkan final.docx jika lolos, atau eskalasi review_queue.json)
```

Event progress yang dicatat ke `state/progress.jsonl` dan terpantau pada monitor:
`task_analysis`, `planning`, `discovery`, `deduplication`, `ranking`, `verification`, `access_check`, `retrieval`, `evidence_extraction`, `claim_verification`, `conflict_detection`, `synthesis`, `writing`, `citation_audit`, `fact_audit`, `docx_generation`, `human_review`.

---

## 4. Status Provider Buku yang Tersedia

| Provider | File Modul | Endpoint Resmi | Status Integritas |
|---|---|---|---|
| **DOAB** | `src/tools/doab.py` | `https://directory.doabooks.org/rest/search` | `VERIFIED_LIVE` (terbukti via pemanggilan API nyata) |
| **Open Library** | `src/tools/open_library.py` | `https://openlibrary.org/search.json` | `VERIFIED_LIVE` (terbukti via pemanggilan API nyata) |

---

## 5. Status Download E-Book

- **Bukan Sekadar Discovery**: Unduhan file nyata dieksekusi secara aktif oleh `RetrievalTool`.
- **Kondisi Izin Unduh**: Berkas hanya diunduh jika `source.access_mode == AccessMode.OPEN_DOWNLOAD` dan `source.rights_status in {RightsStatus.PUBLIC_DOMAIN, RightsStatus.OPEN_LICENSE, RightsStatus.PROVIDER_STATED_FREE}` dengan download URL yang valid.
- **Integritas & Proteksi**:
  - File disimpan di dalam direktori proyek: `source_documents/<id>.pdf`.
  - Checksum dihitung: `sha256`.
  - Jika berkas berstatus pinjaman perpustakaan digital (`BORROW_ONLY`) atau lisensi tidak jelas (`UNKNOWN`), proses unduh **otomatis diblokir** (`BORROW_ONLY_DOWNLOAD_FORBIDDEN` / `DOWNLOAD_RIGHTS_UNCLEAR`) dan kasus dicatat ke `review_queue.json`.

---

## 6. Status PDF Extraction

- **Implementasi**: `src/tools/pdf_parser.py` berbasis library resmi `pypdf==6.11.0`.
- **Ekstraksi Berbasis Halaman**: Mempertahankan nomor halaman asli 1-indexed dan offset karakter.
- **Locator Bukti**: Fungsi `find_passage_page_location` memetakan kutipan verbatim langsung ke nomor halaman nyata (`EvidenceLocation(page=idx, locator=f"p. {idx}")`).
- **Penolakan Fabrikasi**: Dokumen pindaian gambar tanpa teks layer ditandai sebagai `OCR_REQUIRED = True` dan `has_text_layer = False` tanpa menebak isi teks.

---

## 7. Status Model Router

- **Status Konfigurasi**: `PENDING_CONFIGURATION`.
- **Status Kode**: `IMPLEMENTED` dan `TESTED_OFFLINE`. Klien HTTP OpenAI-compatible siap pakai pada endpoint `/chat/completions`.
- **Prinsip Aman**: Jika API key belum diset, model router mengembalikan kegagalan terstruktur `PENDING_CONFIGURATION` tanpa mengarang completion dan tanpa melempar exception.
- **Independensi Deterministik**: Workflow dapat menyelesaikan riset, ekstraksi bukti, sitasi, dan audit secara 100% deterministik tanpa ketergantungan pada model eksternal.

---

## 8. Hasil Pengujian (Test Suite)

### A. Keseluruhan Test Suite
```powershell
python -m pytest -q --tb=short
```
- **Total Lulus**: **464 passed** (naik dari baseline awal 418 passed)
- **Gagal**: **0 failed**
- **Deselected**: **10 deselected** (integration tests bertanda `-m "not integration"`)
- **Waktu Eksekusi**: ~10.23 detik

### B. Modul Uji Baru (36 Test Lulus 100%)
- `tests/test_doab.py`: 4 passed
- `tests/test_open_library.py`: 3 passed
- `tests/test_book_access_status.py`: 8 passed
- `tests/test_book_download.py`: 6 passed
- `tests/test_pdf_parser.py`: 5 passed
- `tests/test_model_router_safe_failure.py`: 4 passed
- `tests/test_citation_disambiguation.py`: 2 passed
- `tests/test_research_pipeline.py`: 4 passed

### C. Pengujian Jaringan Live Nyata
1. **DOAB Live**: Mengambil buku `Confronting Climate Coloniality` (`success=True`).
2. **Open Library Live**: Mengambil buku `Man, climate and architecture` dan mendeteksi hak `BORROW_ONLY` secara tepat (`success=True`).
3. **CLI Research Live**: Menjalankan 16 tahap riset lengkap dari query mentah topik iklim hingga audit integritas fakta.

---

## 9. Hasil Pemeriksaan Kesehatan Sistem (`python -m src check`)

```text
[OK] System health check passed
   SYSTEM_ROOT: C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH\DATA BASE
   WORKSPACE_ROOT: C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH
   Spec version: 1.0
   Build phase: 18
```
Exit code: `0`.

---

## 10. Perintah Eksekusi dan Artefak yang Dihasilkan

### Perintah CLI

```powershell
# 1. Jalankan riset otonom end-to-end dari topik mentah
python -m src research --topic "Dampak perubahan iklim terhadap ketahanan pangan"

# 2. Jalankan riset dari payload JSON terstruktur
python -m src research --input-json research_request.json

# 3. Jalankan mode penulisan akademik manual
python -m src run-academic --input-json input.json

# 4. Cek integritas sistem
python -m src check
```

### Artefak yang Dihasilkan di Direktori Proyek

- `draft.md`: Draf naskah ilmiah lengkap dengan sitasi ter-disambiguasi (`Smith, 2023a`, `Smith, 2023b`) dan daftar pustaka APA 7.
- `citation_map.json`: Pemetaan relasional label sitasi, source ID, claim ID, evidence ID, dan lokasi halaman.
- `review_queue.json`: Berkas antrean tinjauan manusia berisi deskripsi masalah dan tindakan rekomendasi.
- `candidates.jsonl`: Jejak penemuan kandidat literatur.
- `verified_sources.json`: Basis data pustaka yang telah diverifikasi.
- `citation_audit.json`: Hasil audit sitasi.
- `fact_audit.json`: Hasil audit fakta.
- `final.docx`: Dokumen Word final (dibuat hanya jika seluruh audit integritas lolos).

---

## 11. Status Komponen Sistem Berdasarkan Bukti

- **`VERIFIED_LIVE`**:
  - `CrossrefTool` (Jurnal & DOI)
  - `OpenAlexTool` (Katalog terbuka global)
  - `PubMedTool` (Biomedis & kesehatan)
  - `PublishOrPerishTool` (Metrik sitasi lokal)
  - `DOABTool` (Buku akademik open-access)
  - `OpenLibraryTool` (Metadata buku & status pinjaman)
- **`TESTED_OFFLINE`**:
  - `DeepResearchWorkflow` (Pipeline riset 16-tahap)
  - `PDFParserTool` (Ekstraksi berbasis halaman)
  - `RetrievalTool` (Direct download, verifikasi hak, hash SHA-256)
  - `CitationManager` (Disambiguasi label dan `citation_map.json`)
- **`PENDING_CONFIGURATION`**:
  - `ModelRouterTool` (Fail-safe aktif, klien siap pakai, menunggu konfigurasi API key jika model generatif diaktifkan).
- **`UNVERIFIED`**:
  - `SemanticScholarTool` (Menghasilkan HTTP 429 pada shared IP tanpa API key).
- **`NEEDS_HUMAN_REVIEW`**:
  - Dialirkan ke `review_queue.json` saat:
    1. Lisensi tidak jelas (`UNKNOWN`) pada URL unduhan yang tersedia.
    2. E-book berstatus `BORROW_ONLY`.
    3. Pindaian PDF tanpa lapisan teks (`OCR_REQUIRED`).
    4. Bukti temuan bertentangan (*mixed evidence*) tanpa *qualifier*.
