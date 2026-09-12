# LAPORAN EVALUASI & REVISI SKILL: PORTABLE AGENT PROTOCOL

**Tanggal Pelaksanaan:** 11 September 2026  
**Repositori:** `AUTONOMI AGENTIC ILMIAH` (`DATA BASE`)  
**Status Evaluasi:** **SELESAI, TERVERIFIKASI PENUH, & TER-PACKAGING RESMI**  

---

## 1. Latar Belakang & Evaluasi Awal

Evaluasi independen terhadap skill/plugin `skills/autonomi-agentic-ilmiah/` menemukan bahwa instruksi lama mengasumsikan agen AI memiliki akses terminal tanpa batasan dan belum mendefinisikan batas kapabilitas lingkungan secara eksplisit. Hal ini berpotensi menimbulkan risiko:
1. **Kekeliruan Peran:** Agen menganggap skill sebagai runtime tersendiri atau sebaliknya menganggap repositori Python membutuhkan model provider cloud tertentu (misalnya OpenRouter) agar dapat beroperasi.
2. **Ketiadaan Mode Degradasi Aman:** Jika agen beroperasi di lingkungan tanpa akses internet untuk verifikasi sumber, instruksi lama tidak memberikan panduan tegas mengenai batasan draft, sehingga berisiko memicu halusinasi DOI atau referensi fiktif demi memenuhi syarat input.
3. **Pembaruan Fitur yang Tertinggal:** Skill lama belum memuat fitur-fitur Roadmap R4 terbaru (inspeksi riwayat `runs`, retensi `--prune --keep N`, pengemasan arsip mandiri `export-bundle`, serta metadata bibliografi terstruktur `volume`/`issue`/`pages`).

---

## 2. Pemisahan Peran Arsitektur yang Tegas

Revisi ini menetapkan batasan peran yang tidak boleh dicampuradukkan:

1. **Skill / Plugin (Protokol Kognitif & Workflow):**  
   Instruksi etika riset, aturan verifikasi anti-fabrikasi, panduan penyusunan data, dan alur operasional yang ditaati oleh agen AI. Skill bukan runtime Python dan bukan model inference.
2. **Repositori Python (Mesin Eksekusi Deterministik):**  
   Modul kode di dalam folder `DATA BASE` (`src/`) yang mengeksekusi gate integritas akademik (`gates.py`), audit sitasi dan fakta (`audit.py`), kompilasi dokumen Word (`docx_generator.py`), pelacakan per-run (`audit_trail.py`), serta pengemasan bundle (`export_bundle.py`).
3. **Model Provider (Komponen Opsional):**  
   Penyedia inferensi LLM (OpenRouter, local Ollama, vLLM, Claude, GPT, atau model mandiri). Engine inti repositori bekerja secara deterministik tanpa kewajiban menggunakan OpenRouter atau API komersial berbayar tertentu.
4. **Internet Search (Komponen Wajib untuk Verifikasi Sumber):**  
   Alat penelusuran web/API yang digunakan agen untuk memvalidasi keberadaan karya ilmiah nyata, memastikan keaktifan DOI resmi, mengekstrak nomor volume/isu/halaman, dan memeriksa keaslian kutipan (Crossref, PubMed, SAGE, Wiley, Google Scholar).
5. **Sandbox & Terminal (Komponen Wajib untuk Eksekusi Nyata):**  
   Environment eksekusi tempat agen menjalankan perintah shell (`python -m src ...`), membaca/menulis berkas proyek, dan menghasilkan artefak dokumen terkompilasi.

---

## 3. Protokol Deteksi Kapabilitas Lingkungan (Capability Detection)

Agen AI diinstruksikan untuk mengenali kapabilitas lingkungannya sebelum bertindak:

| Mode | Karakteristik Lingkungan | Alur Tindakan Agen | Batasan & Status Luaran |
|---|---|---|---|
| **Full Mode** | Sandbox + Terminal + Internet Search + File Write tersedia lengkap. | 1. `src check`<br>2. Verifikasi sumber riil via internet.<br>3. Tulis JSON `state: APPROVED`.<br>4. Eksekusi `run-academic`.<br>5. Audit lulus & `export-bundle`. | **Karya Ilmiah Final Terverifikasi.** Dokumen Word resmi (`final.docx`) dan bundle ZIP siap ditelaah manusia. |
| **Limited Mode** | Salah satu komponen tidak tersedia (misal terminal ada tapi internet mati, ATAU internet ada tapi sandbox read-only). | • Jika tanpa internet: proses hanya sumber yang metadata/file-nya sudah tersimpan lokal.<br>• Jika tanpa terminal: verifikasi sumber, buat JSON valid, dan instruksikan pengguna menjalankan CLI manual. | **Asistensi Riset Terbatas.** Transparan terhadap batasan; dilarang mengklaim eksekusi jika tahap tertentu dilewati. |
| **Draft-Only Mode** | Tidak ada internet search dan tidak ada database verifikasi lokal. | 1. **Dilarang keras finalisasi akademik.**<br>2. **Dilarang mengarang DOI, kutipan, nomor halaman, atau daftar pustaka.**<br>3. Status klaim diset `PROPOSED` / `INSUFFICIENT_EVIDENCE`.<br>4. Sumber ditandai `[sumber belum lengkap]`. | **Draft Konseptual / Outline Hipotetis Saja.** Naskah diberi *disclaimer* tegas bahwa seluruh rujukan belum terverifikasi empiris. |

---

## 4. Penegakan Gate Integritas Output Akademik

Setiap naskah final yang dihasilkan oleh repositori wajib mematuhi kriteria kelulusan gate:
* **Bersih dari Token Internal LLM:** Bebas 100% dari token `turn...`, `view...`, `search...`, `filecite`, `citeturn`, atau kurung CJK `【...】`.
* **Sitasi In-Text APA 7 Presisi:** Titik akhir kalimat diletakkan setelah kurung sitasi (`... (Author, Year).`).
* **Daftar Pustaka APA 7 Granular:** Memuat nama penulis, tahun, judul karya, nama jurnal, volume, nomor terbitan, rentang halaman, dan tautan resolusi DOI aktif (`Journal, Vol(Issue), pages. https://doi.org/...`).
* **Metadata Tidak Lengkap:** Diberi penanda eksplisit `[sumber belum lengkap]` alih-alih dilengkapi dengan tebakan fiktif.

---

## 5. Rincian Berkas yang Diperbarui

1. **`skills/autonomi-agentic-ilmiah/SKILL.md` (Revisi Total):**
   * Menyajikan protokol portabel lengkap dengan frontmatter YAML terstandardisasi.
   * Mendefinisikan pemisahan 5 peran arsitektur dan 3 mode kapabilitas lingkungan.
   * Memuat perintah CLI lengkap (check, plan, run-academic, runs inspection, prune retention, export-bundle, monitor).
2. **`skills/autonomi-agentic-ilmiah/references/input-json.md` (Penyempurnaan):**
   * Memuat skema lengkap Pydantic dengan tipe data dan batasan nilai.
   * Menyajikan contoh nyata terverifikasi (Amato 2000, Pedro-Carroll 2005, McIntosh 2000) dengan metadata jurnal granular (`volume: 62, issue: 4, pages: "1269–1287"`).
   * Menjelaskan panduan perlakuan `[sumber belum lengkap]`.
3. **`skills/autonomi-agentic-ilmiah/references/environment-capabilities.md` (Berkas Baru):**
   * Panduan deteksi kapabilitas lingkungan, matriks toleransi alat, serta batasan ketat pencegahan halusinasi pada Draft-Only Mode.
4. **`skills/autonomi-agentic-ilmiah/references/dry-run-prompt.md` (Berkas Baru):**
   * Contoh interaksi nyata dari perumusan prompt pengguna, penalaran deteksi Full Mode, verifikasi Crossref, eksekusi CLI, hingga respons akhir.
5. **`AGENTS.md` & `docs/CARA_PAKAI_UNTUK_AI_AGENT.md` (Sinkronisasi):**
   * Menyelaraskan aturan agen repositori dengan 3 mode kapabilitas lingkungan, batasan arsitektur, dan larangan finalisasi sumber tanpa verifikasi.
6. **`dist/autonomi-agentic-ilmiah-skill.zip` (Re-packaged):**
   * Berkas arsip distribusi skill dikemas ulang dan diverifikasi memuat 4 berkas: `SKILL.md`, `references/dry-run-prompt.md`, `references/environment-capabilities.md`, dan `references/input-json.md`.

---

## 6. Hasil Validasi & Pengujian

### A. Health Check Sistem
```powershell
python -m src check
```
*Hasil:* `[OK] System health check passed` (Spec version: 1.0, Build phase: 18, Exit Code: 0).

### B. Test Suite Regresi
```powershell
python -m pytest -q --tb=short
```
*Hasil:* **`319 passed, 10 deselected in 6.55s`** (Exit Code: 0, 100% Lulus).

### C. Uji Skenario Dry-Run Akademik
1. **Perencanaan (`plan`):**
   ```powershell
   python -m src plan "Edjust: program edukasi hukum dan dukungan sosial bagi remaja"
   ```
   *Hasil:* Sukses menghasilkan research plan JSON terstruktur dengan mode `ACADEMIC_WRITING` dan kata kunci relevan.
2. **Eksekusi Alur (`run-academic`):**
   ```powershell
   python -m src run-academic --input-json input_edjust_mini.json
   ```
   *Hasil:* Sukses menyelesaikan 6 tahap alur, audit sitasi dan fakta lulus (`passed: true`), serta menghasilkan naskah `draft.md` dan `final.docx`.
3. **Pengemasan Bundle (`export-bundle`):**
   ```powershell
   python -m src export-bundle --input-json input_edjust_mini.json
   ```
   *Hasil:* Sukses mengemas 12 berkas ke `exports/bundle_run_20260912T064628Z_638f6ddc.zip` dengan struktur portabel dan bebas secret/token.
4. **Uji Negatif Anti-Fabrikasi (Negative Dry-Run):**
   ```powershell
   python -m src run-academic --input-json cache/uji_cli/input_neg1_evidence_palsu.json
   ```
   *Hasil:* Ditolak secara tegas dan aman oleh Integrity Gate dengan `success: false, needs_human_review: true`. Audit trail tetap mencatat pelanggaran di `run_summary.json` tanpa membuat berkas `final.docx` palsu.

---

## 7. Kesimpulan & Rekomendasi

Revisi ini berhasil mengubah skill repositori dari sekadar panduan lokal menjadi **protokol agen portabel yang mandiri**. Protokol ini dapat dioperasikan oleh berbagai runtime AI (Codex, Claude, GPT, Gemini, dsb.) dengan transparansi batas kemampuan lingkungan, ketiadaan ketergantungan pada OpenRouter, serta perlindungan mutlak terhadap integritas ilmiah.
