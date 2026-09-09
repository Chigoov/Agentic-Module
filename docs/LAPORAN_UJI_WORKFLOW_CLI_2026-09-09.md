# Laporan Uji Workflow Akademik via CLI
Tanggal: 9 September 2026
Project: `C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH\DATA BASE`
Metode: CLI (`python -m src ...`) — bukan dashboard. Fokus: penggunaan pribadi multi-laptop Windows.

---

## 1. Ringkasan
Workflow akademik via CLI **berfungsi end-to-end** untuk input yang sah dan **menolak semua 5 skenario negatif** sesuai rancangan gate. Selama pengujian ditemukan **3 bug nyata** (2 kualitas output, 1 false positive gate) yang semuanya sudah diperbaiki pada akar masalah dan dilindungi regression test baru (suite naik 300 → **303 passed**).

| Hasil | Nilai |
|---|---|
| Health check | Lulus (exit 0) |
| Uji positif | Lulus — draft, 2 audit, DOCX lengkap, tanpa token internal, sitasi APA konsisten |
| Uji negatif | 5/5 ditolak dengan exit code 1, tidak ada `final.docx` di jalur gagal |
| Bug ditemukan | 3 (semua diperbaiki + regression test) |
| Suite penuh setelah perbaikan | **303 passed, 10 deselected**; health check exit 0 |

## 2. Perintah yang Dijalankan
```powershell
python -m src check
python cache\uji_cli\siapkan_input.py            # ambil metadata live + tulis 6 input JSON
python -m src run-academic --input-json cache\uji_cli\input_positif.json
python -m src run-academic --input-json cache\uji_cli\input_neg1_evidence_palsu.json
python -m src run-academic --input-json cache\uji_cli\input_neg2_sumber_belum_verified.json
python -m src run-academic --input-json cache\uji_cli\input_neg3_doi_palsu.json
python -m src run-academic --input-json cache\uji_cli\input_neg4_token_internal.json
python -m src run-academic --input-json cache\uji_cli\input_neg5_sitasi_yatim.json
python -m pytest -q --tb=short
```
Sumber uji: **LeCun, Bengio & Hinton (2015), "Deep learning", Nature, DOI 10.1038/nature14539** — metadata diambil langsung dari Crossref saat pengujian (tidak dikarang), lalu diverifikasi live oleh `VerificationEngine`: **DOI_VERIFIED, ratio 1.00**. Crossref tidak menyediakan abstrak untuk artikel ini, sehingga evidence memakai parafrase yang jujur (`verbatim=false`, bukan kutipan karangan).

## 3. Uji Positif — BERHASIL
**Input:** `cache/uji_cli/input_positif.json` (sumber DOI_VERIFIED, claim SUPPORTED, evidence terhubung, outline sederhana).
**Keluar CLI:** exit 0, `success=true`, tahap lengkap: synthesis → outline → writing → citation_audit → fact_audit → docx_generation.

**Lokasi output:** `AUTONOMI AGENTIC ILMIAH\TUGAS 1\uji-positif\`
| File | Status |
|---|---|
| `draft.md` (291 B) | Klaim + sitasi `(LeCun et al., 2015)` + daftar referensi |
| `citation_audit.json` | `passed: true`, orphan/internal/author-year semua kosong |
| `fact_audit.json` | `passed: true` |
| `final.docx` (35 KB) | Terbaca normal via python-docx |

**Pemeriksaan wajib sesuai instruksi:**
- ✅ Token internal (`turn…/view…/search…/filecite/【…】`): **TIDAK ADA** di draft maupun DOCX (dicek regex terhadap seluruh teks DOCX).
- ✅ Sitasi in-text: `(LeCun et al., 2015)` — APA 7 benar (3+ penulis → et al.).
- ✅ Daftar pustaka: `Yann LeCun, Yoshua Bengio, & Geoffrey Hinton (2015). Deep learning. Nature. https://doi.org/10.1038/nature14539` — APA 7 (penulis. (tahun). judul. venue. DOI), metadata lengkap sehingga tidak perlu `[sumber belum lengkap]` (mekanisme marker sendiri teruji di regression `test_draft_markdown_carries_reference_list` pada entri berfield-hilang).
- ✅ Heading `References` muncul tepat **satu kali** di DOCX.

## 4. Uji Negatif — SEMUA DITOLAK (exit 1, tidak ada final.docx)
| # | Skenario | Hasil | Pesan |
|---|---|---|---|
| 1 | Evidence ID palsu (`evd_palsu_tidak_ada`) | ✅ Ditolak pra-tahap (stages=0) | `claim clm_uji references nonexistent supporting evidence evd_palsu_tidak_ada` |
| 2 | Sumber belum approved (`state=DISCOVERED`) | ✅ Ditolak pra-tahap | `source … cited but never verified (state=DISCOVERED)` |
| 3 | DOI palsu (`10.9999/doi-palsu-uji`) | ✅ Ditolak gate; engine live juga `NEEDS_HUMAN_REVIEW` (ratio 0.0) | `cited but never verified (state=DISCOVERED)` |
| 4 | Token internal `turn0search0 view0 filecite` | ✅ Ditolak setelah writing (hanya draft.md diagnostik tertinggal) | `Output scan failed: internal citation tokens present in draft: ['turn0', 'search0', 'view0', 'filecite']` |
| 5 | Sitasi yatim `(Nonexistent, 2024)` | ✅ Ditolak setelah writing | `Output scan failed: author-year citations with no matching source: ['(Nonexistent, 2024)']` |

Catatan penting: skenario negatif 4 dan 5 **sengaja** menyisakan `draft.md` sebagai jejak diagnostik (lokasi bug terlihat), tetapi **tidak** menghasilkan `final.docx` dan `success=false` — konsisten dengan prinsip "simpan draft diagnostik terpisah, jangan final".

## 5. Bug yang Ditemukan Selama Uji (semua sudah diperbaiki)
1. **False positive citation key dari path DOI** — entri referensi `https://doi.org/10.1038/nature14539` terbaca sebagai orphan key `nature14539`, sehingga **uji positif pertama gagal** meski input sah.
   *Perbaikan akar:* `CITATION_KEY_PATTERN` lookbehind kini mengecualikan `/`.
   *Regression:* `test_citation_key_pattern_ignores_doi_url_path`.
2. **Kapitalisasi nama APA salah** — in-text menampilkan `Lecun et al.` (seharusnya `LeCun`). `.title()` merusak nama dengan huruf besar internal.
   *Perbaikan akar:* `_display_surname()` — mixed-case dipertahankan, title-case hanya untuk nama lowercase.
   *Regression:* `test_in_text_preserves_mixed_case_surname`.
3. **Bibliografi dobel di final.docx** — draft kini membawa `## References` sendiri, sementara DOCX generator menambahkan heading yang sama → "References" muncul 2×.
   *Perbaikan akar:* generator melewati blok referensi milik draft saat reference list terstruktur disuplai.
   *Regression:* `test_docx_has_single_references_heading`.

## 6. Temuan UX/Fungsional (belum diperbaiki, rekomendasi terkecil)
1. **Pesan gate lewat jalur exception** — CLI mencetak `Agent raised an unhandled exception: Academic integrity gate rejected…` (sebagian besar detail justru di stderr, bukan field JSON).
   *Rekomendasi terkecil:* di `OrchestratorAgent._execute` (atau `BaseAgent.execute`), tangkap `HumanReviewRequired`/`AcademicGateError` → kembalikan response `success=false, needs_human_review=true, review_prompt=<render()>` tanpa teks "unhandled exception", dan (untuk CLI) pastikan pesan masuk `error_message` di stdout JSON.
2. **Negatif pra-gate tidak menyisakan folder diagnostik** — skenario 1–3 gagal sebelum `project.directory` dipakai, jadi tidak ada jejak file. Wajar untuk CLI, tetapi bila ingin jejak konsisten: tulis `gate_rejection.json` di folder project sebelum raise (perubahan ~5 baris).
3. **Log penyelamatan** — stdout JSON kini bersih (terverifikasi `ConvertFrom-Json` sukses), tetapi banner log ke stderr. Kontrak AGENTS.md sudah benar ("parse stdout as JSON"); cukup didokumentasikan agar pengguna memisahkan stream (`2>$null`) saat parsing.

## 7. Kesesuaian dengan Kebutuhan Multi-Laptop Pribadi
- CLI alur `check → siapkan JSON → run-academic → periksa 4 file` bekerja tanpa langkah manual tersembunyi; folder output otomatis di bawah `TUGAS 1` sesuai workspace.
- Tidak ada kebutuhan dashboard baru — semua validasi dilakukan lewat file + JSON (sesuai instruksi, dashboard tidak disentuh).
- Uji ini dijalankan pada checkout utama dengan Python 3.14.5; klaim portabilitas lintas laptop tetap menunggu uji fisik laptop kedua (regression test mandiri sudah menutup sisi logikanya).

## 8. Perubahan Kode Akibat Uji Ini
- `src/tools/citation_manager.py` (regex lookbehind `/`)
- `src/tools/reference_formatter.py` (`_display_surname`, dipakai in-text)
- `src/tools/docx_generator.py` (skip blok referensi draft di DOCX)
- `tests/test_audit_fix_regression.py` (+3 regression test)
Hasil akhir: **303 passed, 10 deselected**; `python -m src check` exit 0. Folder bukti uji: `cache/uji_cli/` (input) dan `TUGAS 1/uji-*` (output).
