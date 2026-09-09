# Hasil Perbaikan — Tindak Lanjut Audit Independen
Tanggal: 7 September 2026. Baseline: `99a71bb2eb8e453c3cd94a03a5df71810ad45ae8` (HEAD saat audit, tidak diubah).
Laporan baseline: `LAPORAN_AUDIT.md` (dipertahankan apa adanya sebagai pembanding). Berkas hasil baru ini mencatat perbaikan, bukti, dan sisa risiko.

## 1. Ringkasan
R1–R3 dari roadmap audit telah ditutup pada level akar masalah, ditambah sebagian R4 (subsection writer dan daftar pustaka pada draft Markdown). Laporan audit awal dan seluruh berkas probe asli tidak diubah; hasil pengujian baru disimpan terpisah.

| Bukti | Nilai |
|---|---|
| `python -m pytest -q --tb=short` | **300 passed, 10 deselected** (baseline: 272 passed; +28 regression test baru) |
| `python -m src check` | Exit 0, `[OK] System health check passed` |
| Probe pasca-perbaikan | `verifikasi_perbaikan_2026-09-07.json` (dihasilkan `verify_fixes.py`, fixtures terkarantina) |

## 2. Temuan yang Ditutup
| ID | Perbaikan | Bukti |
|---|---|---|
| **A01** (P1) | Gate integritas akademik baru `src/workflows/gates.py` dijalankan orchestrator **sebelum tahap pertama**: semua ID claim→evidence→source harus resolve dalam payload, source yang dikutip wajib berstatus verified dari engine (bukan flag input), duplicate ID ditolak, klaim penting wajib punya evidence pendukung. | Probe `nonexistent_evidence` kini **gagal** dengan pesan gate; regression `test_gate_rejects_nonexistent_evidence_id`, `test_gate_rejects_unverified_source`, `test_orchestrator_rejects_nonexistent_evidence` |
| **A02** (P1) | (a) Detektor token internal (`turn…`, `view…`, `search…`, `filecite`, `【…】`, `citeturn…`) pada seluruh teks output — token dilaporkan, tidak pernah dihapus diam-diam. (b) Audit sitasi kini juga memeriksa format yang benar-benar ditulis: sitasi nama–tahun tanpa sumber (`(Nonexistent, 2024)`) ditolak. (c) Draft membawa daftar referensi dengan key yang sama seperti body. | Probe `internal_tokens` dan `author_year_orphan` kini **gagal** di gate; `CitationAuditResponse.internal_tokens/author_year_orphans` terisi; regression `test_output_scan_blocks_tokens_and_orphans`, `test_citation_audit_agent_blocks_tokens_and_orphans`, `test_orchestrator_rejects_internal_tokens` |
| **A03** (P1) | Cabang DOI lookup kini melalui pembandingan identitas yang sama dengan pencarian bibliografik: threshold judul diberlakukan pada kedua cabang, ketidaksesuaian material menghasilkan check `metadata_identity_match` FAILED dan rekomendasi `NEEDS_HUMAN_REVIEW` — bukan `DOI_VERIFIED`. | Probe `real_doi_wrong_metadata`: state **NEEDS_HUMAN_REVIEW**, ratio 0.0 (sebelumnya DOI_VERIFIED); regression `test_doi_with_wrong_title_needs_human_review`, `test_doi_with_matching_title_still_verified` |
| **A04** (P1) | Claim CONFLICTED hanya boleh ditulis bila ada disclosure terstruktur: qualifier pada claim atau evidence kontradiksi yang benar-benar melekat. | Probe `conflict_undisclosed` **gagal** dengan pesan disclosure; regression `test_gate_rejects_conflicted_claim_without_disclosure`, `test_gate_accepts_conflicted_claim_with_qualifier` |
| **A05** (P1) | `backup_file` memakai suffix microsecond + counter anti-tabrakan (dua backup dalam detik sama tidak saling menimpa). Writer/audit mem-backup draft & audit lama sebelum overwrite; DOCX ditulis ke sibling temp lalu `os.replace` (atomic). | Probe `overwrite`: `old_draft_preserved=true` dengan backup unik `draft.md.20260907T165105.946739Z.bak` (sebelumnya `false`, `[]`); regression `test_backup_same_instant_yields_unique_names`, `test_rerun_preserves_manual_draft_edit`, `test_docx_overwrite_creates_unique_backups` |
| **A06** (P1) | Localhost API: (a) token lokal wajib pada endpoint tulis (`X-Autonomi-Token`, token per-laptop di `state/monitor_token.txt`, override `AUTONOMI_API_TOKEN`); (b) CORS wildcard dihapus — hanya Origin loopback yang mendapat header CORS, Origin asing ditolak 403; (c) direktori output **ditentukan server**, `project_path` dari request diabaikan; (d) `project` dari payload wajib berada di dalam workspace root. | Probe `api_untrusted_origin_write`: **HTTP 403** (sebelumnya 200 + penulisan artifact); regression `test_api_rejects_missing_token`, `test_api_rejects_foreign_origin`, `test_api_rejects_arbitrary_project_path` |
| **A07** (P1) | (a) Root discovery berlapis: folder `DATA BASE` tetap diterima, dan fresh clone di folder bernama apa pun ditemukan lewat marker spec files kanonik. (b) `AUTONOMI_WORKSPACE_ROOT` dan `AUTONOMI_SYSTEM_ROOT` dihormati independen (checkout dan workspace boleh terpisah). (c) `ProjectManager.load()` **rebase** path manifest ke lokasi aktual. (d) Dua test yang tergantung folder lokal `TUGAS 1`/`TUGAS 2` dibuat mandiri (workspace sintetis per-test). | Regression `test_manifest_load_rebases_to_actual_location`; `tests/test_paths.py` kini lulus tanpa folder workspace lokal (kegagalan clean-clone 270/2 pada audit tidak lagi relevan); probe verifikasi `_discover_system_root` menemukan clone bernama `Agentic-Module` |
| **A12** (P2) | `HttpClient`: body tidak lagi dipotong sebelum parse — batas baca eksplisit 10 MB dengan error `RESPONSE_TOO_LARGE`; field `excerpt` terpisah untuk log. | Probe audit (JSON valid 210.000 char) kini ter-parse; regression `test_large_valid_json_parses`; test fake `read()` diperbaiki mengikuti kontrak `read(n)` (bukan melonggarkan kode) |
| **A15** (P2, parsial) | POST dengan Content-Length rusak, body >10 MB, JSON malformed, atau schema invalid kini menjawab **JSON terstruktur** (400/413 dengan `error_code`) — bukan memutus koneksi. | Probe `api_malformed_json`: HTTP 400, `error_code=INVALID_REQUEST` (sebelumnya `RemoteDisconnected`); regression `test_api_malformed_json_returns_structured_error` |

## 3. Tambahan R4 (integrasi workflow akademik & sitasi, lingkup kecil)
| Item | Perbaikan | Bukti |
|---|---|---|
| A17 (subsection) | Writer menelusuri subsection outline secara rekursif — klaim pada subsection tidak lagi hilang diam-diam. | Regression `test_writer_renders_nested_subsection_claims`; probe manual nested outline: klaim kini hadir di draft |
| A10 (paket sitasi) | Daftar pustaka dirender ke `draft.md` dengan marker `[sumber belum lengkap]` untuk entri berfield-hilang, sehingga run `--no-docx` tetap menyodorkan paket sitasi + daftar pustaka yang konsisten dengan body. | Regression `test_draft_markdown_carries_reference_list` |

## 4. Kontrol positif
Fixture sah (source APPROVED, claim terverifikasi, evidence utuh) **tetap menghasilkan** draft + audit + final.docx melalui jalur publik — gate tidak melonggarkan jalur yang benar. Probe `positive_control`: `success=true`, file `citation_audit.json`, `draft.md`, `fact_audit.json`, `final.docx`.

## 5. Perubahan berkas
- Baru: `src/workflows/gates.py`, `tests/test_audit_fix_regression.py` (28 test), `docs/audit_independen_2026-09-07/verify_fixes.py` + `verifikasi_perbaikan_2026-09-07.json`
- Diubah: `src/workflows/orchestrator.py`, `src/agents/writer.py`, `src/agents/audit.py`, `src/tools/citation_manager.py`, `src/tools/verification_tool.py`, `src/tools/http_client.py`, `src/tools/docx_generator.py`, `src/core/storage.py`, `src/core/paths.py`, `src/core/project_manager.py`, `src/runtime/monitor.py`, `tests/test_paths.py`, `tests/test_http_client.py`
- Tidak diubah: seluruh isi laporan audit baseline (`LAPORAN_AUDIT.md`, `CATATAN_PER_FILE.md`, `probe_results.json`, `portability.json`, `reproduce.py`, dll.)

## 6. Catatan penggunaan (localhost token)
Endpoint `POST /api/run-academic` kini memerlukan header `X-Autonomi-Token`. Token per laptop tersimpan di `DATA BASE/state/monitor_token.txt` (dibuat otomatis saat monitor pertama jalan; diabaikan Git via folder `state/`). Halaman dashboard pada origin loopback tetap berfungsi tanpa konfigurasi tambahan untuk endpoint GET.

## 7. Sisa risiko yang belum ditutup (jujur)
Mengikuti prioritas R1–R3, temuan berikut **belum** dikerjakan dan tetap berlaku seperti dicatat audit:
- A08 (status callable vs verified pada public research tools), A09 (safeguard etik Edjust), A11 (audit trail per-run), A13 (tingkat bukti retrieval), A14 (instrumentasi dashboard per-run), A16 (konsistensi `.env`/config), A17 sisanya (provider client, deep research E2E, validator kosong), A18.
- Autentikasi token monitor melindungi endpoint tulis dari halaman asing dan proses lain di mesin yang sama, tetapi bukan enkripsi: tetap ikat ke loopback.
- Pengujian fisik pada laptop kedua, versi Python lain, dan jaringan provider live belum dilakukan dalam sesi ini; clean-clone assertion dibuktikan lewat regression test mandiri dan probe discovery, bukan clone fisik baru.
