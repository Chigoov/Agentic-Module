# Laporan Pengerjaan — Perbaikan Project Berdasarkan Audit Independen
Tanggal pengerjaan: 7–8 September 2026
Project: AUTONOMI AGENTIC ILMIAH (`DATA BASE`)
Baseline kode: `99a71bb2eb8e453c3cd94a03a5df71810ad45ae8` (HEAD saat audit — tidak diubah)
Sumber temuan: `docs/audit_independen_2026-09-07/LAPORAN_AUDIT.md` + berkas pendukungnya
Laporan hasil teknis terpisah: `docs/audit_independen_2026-09-07/HASIL_PERBAIKAN_2026-09-07.md`

---

## 1. Lingkaran Kerja yang Diminta
1. Gunakan berkas di `docs/audit_independen_2026-09-07/` (LAPORAN_AUDIT.md, CATATAN_PER_FILE.md, probe_results.json, portability.json; reproduce.py sebagai referensi pengujian).
2. Pertahankan laporan dan hasil audit awal sebagai baseline; simpan hasil pengujian baru secara terpisah.
3. Verifikasi setiap temuan terhadap kode terbaru sebelum mengubahnya.
4. Kerjakan bertahap: R1 (gate akademik) → R2 (perlindungan output & keamanan localhost) → R3 (portabilitas multi-device) → integrasi workflow akademik & sitasi.
5. Perbaiki akar masalah dengan perubahan sekecil mungkin; jangan melonggarkan audit atau mengubah test hanya agar hijau.
6. Tambahkan regression test, jalankan health check + test, laporkan temuan yang tertutup beserta buktinya.
7. Fokus penggunaan pribadi multi-laptop Windows; tanpa kebutuhan komersialisasi/deployment publik.

Semua butir di atas dikerjakan dan dipenuhi (rincian di bawah).

## 2. Berkas Audit yang Dibaca
| Berkas | Peran dalam pengerjaan |
|---|---|
| `LAPORAN_AUDIT.md` | 18 temuan (A01–A18), status fase, roadmap R0–R6 |
| `CATATAN_PER_FILE.md` | Catatan per file source + peta 37 file test |
| `probe_results.json` | Bukti mentah perilaku salah (evidence ghost, token internal, DOI mismatch 0.0 → DOI_VERIFIED, overwrite, CORS `*`, malformed JSON, dll.) |
| `portability.json` | Bukti clean clone gagal health check tanpa trik + 2 test gagal (test_paths.py:53, 62) |
| `reproduce.py` | Referensi gaya probe; hasil baru **tidak** menimpa berkas probe asli |
| `completion_check.json`, `import_check.json`, `source_inventory.json`, `packaging.json` | Konteks inventaris & status (tidak diubah) |

## 3. Verifikasi Temuan terhadap Kode Terbaru
Setiap temuan prioritas dicek langsung di source sebelum ada perubahan; semua terkonfirmasi masih ada:
- A01: `orchestrator.py` langsung synthesis→outline→writer tanpa verifikasi; `claim.is_writable` hanya memeriksa keberadaan list ID.
- A02: `CitationAuditAgent` hanya regex machine key; tidak ada pemeriksaan token internal maupun format `(Author, Year)`.
- A03: `VerificationEngine._corroborate` menerima record DOI tanpa membandingkan judul; threshold hanya dipakai cabang bibliografik.
- A04: `CONFLICTED` termasuk `WRITABLE_STATUSES`; tidak ada syarat disclosure.
- A05: writer/audit menulis `overwrite=True` tanpa backup; `backup_file` hanya presisi detik; DOCX disimpan langsung ke target.
- A06: monitor: CORS `*`, OPTIONS permisif, tanpa token, `project_path` dari request dipakai apa adanya.
- A07: root wajib bernama `DATA BASE`; manifest path absolut dimuat apa adanya; test_paths tergantung folder `TUGAS 1`/`TUGAS 2` fisik.
- A12: `http_client` memotong body pada 200.000 karakter sebelum `json.loads`.
- A15 (parsial): `do_POST` mem-parse di luar error boundary → koneksi terputus tanpa JSON.

## 4. Perbaikan per Temuan (akar masalah, perubahan minimal)

### R1 — Gate akademik
| ID | Perbaikan | Berkas |
|---|---|---|
| A01 | Gate integritas baru `check_academic_integrity()`: semua referensi claim→evidence→source wajib resolve; source yang dikutip wajib state verified dari engine (bukan flag input); duplicate evidence ID ditolak; klaim penting wajib evidence. Dipanggil di awal `OrchestratorAgent._execute`; kegagalan → `AcademicGateError` (turunan `HumanReviewRequired`, pesan terstruktur). | `src/workflows/gates.py` (baru), `src/workflows/orchestrator.py` |
| A02 | (a) `INTERNAL_TOKEN_PATTERN` + `detect_internal_tokens()` untuk `turn…/view…/search…/filecite/【…】/citeturn…`; (b) `AUTHOR_YEAR_CITATION_PATTERN` + `detect_orphan_author_year_citations()` untuk sitasi nama–tahun tanpa sumber; (c) `scan_output_text()` dijalankan orchestrator setelah writing; (d) `CitationAuditAgent` kini melaporkan `internal_tokens` + `author_year_orphans` dan menggagalkan audit bila ada. Token **dilaporkan**, tidak dihapus diam-diam. | `src/tools/citation_manager.py`, `src/agents/audit.py`, `src/workflows/orchestrator.py` |
| A03 | Pembandingan identitas diberlakukan di kedua cabang: `_corroborate()` menolak record di bawah threshold; `_identity_mismatches()` menghasilkan check `metadata_identity_match` FAILED; mismatch material → rekomendasi `NEEDS_HUMAN_REVIEW` (bukan `DOI_VERIFIED`, bukan backfill). | `src/tools/verification_tool.py` |
| A04 | Claim `CONFLICTED` wajib punya qualifier ATAU evidence kontradiksi yang benar-benar melekat; otherwise gate menolak dengan pesan disclosure. | `src/workflows/gates.py` |

### R2 — Perlindungan output & keamanan localhost
| ID | Perbaikan | Berkas |
|---|---|---|
| A05 | `backup_file()` → suffix microsecond + counter anti-tabrakan; writer mem-backup `draft.md` lama sebelum overwrite; audit mem-backup `citation_audit.json`; DOCX ditulis ke sibling temp lalu `os.replace` (atomic; fd mkstemp ditutup dulu untuk Windows). | `src/core/storage.py`, `src/agents/writer.py`, `src/agents/audit.py`, `src/tools/docx_generator.py` |
| A06 | (a) Token lokal wajib di endpoint tulis: `get_api_token()` — per-laptop di `state/monitor_token.txt`, override `AUTONOMI_API_TOKEN`, dibandingkan dengan `secrets.compare_digest`; (b) CORS wildcard dihapus — hanya Origin loopback yang mendapat header; Origin asing → 403; (c) `project_path` dari request **diabaikan** — direktori ditentukan server di dalam workspace root; objek `project` dari payload wajib berada di dalam workspace; (d) body >10 MB → 413, Content-Length rusak → 400. | `src/runtime/monitor.py` |
| A15 (parsial) | Semua kegagalan parse/validasi POST menjawab JSON terstruktur (`error_code`: `INVALID_REQUEST`, `PAYLOAD_TOO_LARGE`, `INVALID_CONTENT_LENGTH`, `BODY_READ_FAILED`) — bukan koneksi terputus. | `src/runtime/monitor.py` |

### R3 — Portabilitas multi-device
| ID | Perbaikan | Berkas |
|---|---|---|
| A07 | (a) `_discover_system_root()` dua lapis: pass 1 folder `DATA BASE` (kompatibilitas), pass 2 marker spec files kanonik — clone di folder bernama apa pun terdeteksi; (b) `_resolve_roots()` menghormati `AUTONOMI_WORKSPACE_ROOT` dan `AUTONOMI_SYSTEM_ROOT` secara independen; (c) `ProjectManager.load()` me-rebase `path` manifest ke lokasi aktual (+ defense in depth); (d) dua test yang tergantung folder lokal dibuat mandiri (workspace sintetis per-test via env). | `src/core/paths.py`, `src/core/project_manager.py`, `tests/test_paths.py` |
| A12 | Body tidak dipotong sebelum parse: `read(_MAX_BODY_BYTES+1)`; >10 MB → error `RESPONSE_TOO_LARGE`; field `excerpt` terpisah untuk log; body penuh dipakai `json()`. Test fake `read()` diperbaiki mengikuti kontrak `read(n)` produksi (bukan kode yang dilonggarkan). | `src/tools/http_client.py`, `tests/test_http_client.py` |

### Integrasi workflow akademik & sitasi (R4 lingkup kecil)
| Item | Perbaikan | Berkas |
|---|---|---|
| A17 (subsection) | `_render_section()` rekursif — klaim pada subsection outline kini ter-render (sebelumnya hilang diam-diam). | `src/agents/writer.py` |
| A10 (paket sitasi) | Daftar pustaka dirender ke `draft.md` (satu pemetaan ID→label dengan body) + marker `[sumber belum lengkap]` untuk entri berfield-hilang; run `--no-docx` tetap menyodorkan paket sitasi lengkap. | `src/agents/writer.py` |

## 5. Regression Test yang Ditambahkan
`tests/test_audit_fix_regression.py` — **26 test baru** (fixture terkarantina, tanpa jaringan):
- A01: `test_gate_rejects_nonexistent_evidence_id`, `test_gate_rejects_nonexistent_source_reference`, `test_gate_rejects_unverified_source`, `test_gate_accepts_verified_bundle`, `test_orchestrator_rejects_nonexistent_evidence`
- A02: `test_internal_token_detector_finds_all_variants`, `test_output_scan_blocks_tokens_and_orphans`, `test_output_scan_accepts_legitimate_citation`, `test_citation_audit_agent_blocks_tokens_and_orphans`, `test_orchestrator_rejects_internal_tokens`, `test_orchestrator_rejects_author_year_orphan`
- A03: `test_doi_with_wrong_title_needs_human_review`, `test_doi_with_matching_title_still_verified`
- A04: `test_gate_rejects_conflicted_claim_without_disclosure`, `test_gate_accepts_conflicted_claim_with_qualifier`
- A05: `test_backup_same_instant_yields_unique_names`, `test_rerun_preserves_manual_draft_edit`, `test_docx_overwrite_creates_unique_backups`
- A06: `test_api_rejects_missing_token`, `test_api_rejects_foreign_origin`, `test_api_rejects_arbitrary_project_path`, `test_api_malformed_json_returns_structured_error`, `test_api_token_is_stable_and_secret_shaped`
- A07: `test_manifest_load_rebases_to_actual_location`, `test_backup_names_embed_microseconds`
- A12: `test_large_valid_json_parses`
- R4: `test_writer_renders_nested_subsection_claims`, `test_draft_markdown_carries_reference_list`

Catatan integritas test: tidak ada assertion yang dilonggarkan. Satu penyesuaian test dilakukan karena fake test lama tidak mengikuti kontrak produksi `read(n)` (`tests/test_http_client.py`), dan dua test regersi awal diperbaiki karena salah merumuskan ekspektasi (path relocation; probe `project_path`). Dua test clean-clone yang gagal pada audit dibuat mandiri, bukan dihapus.

## 6. Bukti Hasil Pengujian (disimpan terpisah dari baseline)
| Verifikasi | Hasil |
|---|---|
| `python -m pytest -q --tb=short` | **300 passed, 10 deselected** (baseline audit: 272 passed → +28) |
| `python -m src check` | Exit 0, `[OK] System health check passed` |
| `verify_fixes.py` (probe pasca-perbaikan, server terisolasi) | `docs/audit_independen_2026-09-07/verifikasi_perbaikan_2026-09-07.json` |
| Kontrol positif | Fixture sah tetap menghasilkan `draft.md` + `citation_audit.json` + `fact_audit.json` + `final.docx` melalui jalur publik |

Perbandingan probe kunci (sebelum → sesudah):
| Probe | Sebelum | Sesudah |
|---|---|---|
| `nonexistent_evidence` | success=true, DOCX dibuat | **ditolak gate** |
| `internal_tokens` | token bertahan di DOCX | **ditolak gate** |
| `author_year_orphan` | lolos audit | **ditolak gate** |
| `conflict_undisclosed` | ditulis tanpa disclosure | **ditolak gate** |
| `overwrite` | edit manual hilang, `backups: []` | edit selamat, backup unik `draft.md.20260907T165105.946739Z.bak` |
| `real_doi_wrong_metadata` | `DOI_VERIFIED` (ratio 0.0) | **NEEDS_HUMAN_REVIEW** (ratio 0.0, check FAILED) |
| `api_untrusted_origin_write` | HTTP 200, CORS `*`, tulis artifact | **HTTP 403**, tanpa CORS wildcard |
| `api_malformed_json` | koneksi terputus | HTTP 400 `INVALID_REQUEST` |

## 7. Berkas yang Diubah / Ditambahkan
**Baru:**
- `src/workflows/gates.py`
- `tests/test_audit_fix_regression.py`
- `docs/audit_independen_2026-09-07/verify_fixes.py`
- `docs/audit_independen_2026-09-07/verifikasi_perbaikan_2026-09-07.json`
- `docs/audit_independen_2026-09-07/HASIL_PERBAIKAN_2026-09-07.md`
- `docs/LAPORAN_PENGERJAAN_PERBAIKAN_AUDIT_2026-09-08.md` (berkas ini)

**Diubah (13):**
`src/workflows/orchestrator.py`, `src/agents/writer.py`, `src/agents/audit.py`, `src/tools/citation_manager.py`, `src/tools/verification_tool.py`, `src/tools/http_client.py`, `src/tools/docx_generator.py`, `src/core/storage.py`, `src/core/paths.py`, `src/core/project_manager.py`, `src/runtime/monitor.py`, `tests/test_paths.py`, `tests/test_http_client.py`

**Tidak disentuh:** seluruh isi baseline audit (`LAPORAN_AUDIT.md`, `CATATAN_PER_FILE.md`, `probe_results.json`, `portability.json`, `reproduce.py`, dst.), konfigurasi, spec dokumen, dan dokumentasi lama lainnya. Total diff: ±554 baris tambahan / 99 baris berkurang pada 13 file (belum di-commit; menunggu review).

## 8. Catatan Pemakaian
- `POST /api/run-academic` kini butuh header `X-Autonomi-Token`. Token unik per laptop dibuat otomatis di `DATA BASE/state/monitor_token.txt` (folder `state/` diabaikan Git). Endpoint GET dashboard tetap berfungsi normal dari browser localhost.
- Clone baru di folder bernama apa pun (mis. `Agentic-Module`) kini terdeteksi otomatis lewat marker spec files; `AUTONOMI_SYSTEM_ROOT` tetap berlaku sebagai override.
- Proyek yang dipindah/copi antar laptop otomatis dimuat dari lokasi manifest barunya; output tidak lagi mengikuti drive laptop asal.

## 9. Sisa Risiko (jujur, belum dikerjakan)
Mengikuti prioritas R1–R3 + lingkup R4 kecil, temuan berikut **tetap berlaku** seperti dicatat audit dan belum dikerjakan:
- A08 (status callable vs verified pada public research tools), A09 (safeguard etik Edjust — wajib sebelum pengumpulan data partisipan), A11 (audit trail per-run), A13 (tingkat bukti retrieval), A14 (instrumentasi dashboard per-run), A16 (konsistensi `.env`/config), A17 sisanya (provider client, deep research E2E, validator kosong), A18.
- Token monitor melindungi endpoint tulis dari halaman asing/proses lain, tetapi bukan enkripsi — server tetap harus dijalankan pada loopback.
- Belum dilakukan dalam sesi ini: pengujian fisik di laptop kedua, versi Python lain, dan verifikasi jaringan provider live (probe DOI live hanya melalui regression dengan provider palsu + kontrol positif offline).
