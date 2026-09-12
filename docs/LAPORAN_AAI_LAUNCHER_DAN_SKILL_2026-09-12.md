# LAPORAN PENAMBAHAN LAUNCHER AAI DAN DOKUMENTASI SKILL AGENT

**Tanggal:** 12 September 2026  
**Sistem:** AUTONOMI AGENTIC ILMIAH (Build Phase 18)  
**Status Eksekusi:** SIAP COMMIT FINAL (Clean, 0 Warnings, 100% Tests Passed)  

---

## 1. Ringkasan Pekerjaan

Sebagai langkah pematangan sebelum commit final, telah ditambahkan konsep pemanggilan pendek **`aai`** dan standarisasi dokumentasi **Skill AAI** agar repositori AUTONOMI AGENTIC ILMIAH dapat dioperasikan secara ergonomis dan konsisten oleh manusia (via terminal/PowerShell) maupun oleh AI Agent (Kiro IDE, Antigravity, Claude, Codex, GPT, dll.).

Pekerjaan ini dilakukan secara minimal:
- **Reuse CLI yang sudah ada** (`python -m src ...`) tanpa menambah dependency baru;
- **Tidak membuat installer global PATH** yang rumit (cukup launcher lokal di root repo);
- **Launcher lama tetap ada dan berfungsi** (`START_MONITOR.bat`, `OPEN_LIVE_PROGRESS.bat`, `OPEN_LIVE_PROGRESS.ps1`);
- **Tidak melakukan commit atau push** sebelum persetujuan pengguna.

---

## 2. Berkas yang Ditambahkan dan Diubah

### A. Berkas Baru (Added)
1. **`aai.ps1`**: Launcher PowerShell lokal mandiri dengan penanganan path otomatis (`Set-Location $repoRoot`), port-testing untuk monitor live dashboard, validasi eksistensi input JSON, dan pesan bantuan ramah.
2. **`aai.bat`**: Pembungkus CMD/Batch sederhana untuk mengeksekusi `aai.ps1` dengan `ExecutionPolicy Bypass`.
3. **`skills/aai/SKILL.md`**: Alias pendek untuk skill AAI yang merangkum protokol kerja 6 langkah agen dan pintasan perintah.
4. **`tests/test_aai_launcher.py`**: Unit test penguji eksistensi launcher, ketiadaan hardcoded user path, dan kelengkapan dokumentasi skill.

### B. Berkas yang Diperbarui (Modified)
1. **`skills/autonomi-agentic-ilmiah/SKILL.md`**: Memperbarui panduan skill utama dengan identitas AAI, pemicu skill, alur kerja 6 tahap, kewajiban audit mandatori (`citation_audit.json` dan `fact_audit.json`), dan aturan anti-halusinasi.
2. **`README.md`**: Menambahkan petunjuk cepat penggunaan `aai.bat` pada bagian Quick Start.
3. **`docs/CARA_CEPAT_UNTUK_ORANG_AWAM.md`**: Menambahkan bagian "Cara Cepat dengan Perintah aai.bat" di awal dokumen.

---

## 3. Contoh Cara Memanggil `aai` (Bagi Pengguna Manusia)

Dari terminal PowerShell atau CMD di folder `DATA BASE`:

```cmd
:: 1. Periksa kesiapan sistem setelah clone
.\aai.bat check

:: 2. Buka live dashboard monitor di browser (menjalankan server port 8000 jika belum aktif)
.\aai.bat open

:: 3. Jalankan server monitor di jendela terminal ini
.\aai.bat monitor

:: 4. Jalankan alur penulisan akademik lengkap dari file JSON
.\aai.bat run input_edjust_mini.json

:: 5. Lihat riwayat audit trail eksekusi proyek
.\aai.bat runs input_edjust_mini.json

:: 6. Ekspor berkas paket terkompresi (.zip)
.\aai.bat bundle input_edjust_mini.json

:: 7. Tampilkan menu bantuan
.\aai.bat help
```

---

## 4. Contoh Cara AI Agent Memakai "Skill AAI"

Ketika pengguna meminta: *"Gunakan skill AAI untuk menulis paper tentang topik X"* atau *"Pakai Autonomi Agentic Ilmiah"*, agen AI mengikuti siklus kerja 6 tahap berikut:

```
[1. aai check] -> [2. Web Search] -> [3. Buat input.json] -> [4. aai run] -> [5. Cek Audit] -> [6. Revisi jika Gagal]
```

1. **Tahap 1 (Health Check):**  
   Agen memanggil `.\aai.bat check`. Memastikan status `[OK] System health check passed`.
2. **Tahap 2 (Pencarian Sumber Asli):**  
   Agen menggunakan tool internet search miliknya (Crossref, PubMed, arXiv) untuk mencari publikasi nyata, mencatat DOI aktif, dan mengambil kutipan teks secara verbatim dari abstrak/teks lengkap artikel.
3. **Tahap 3 (Penyusunan Input JSON):**  
   Agen menyusun file input JSON (misal `input_project.json`) dengan struktur:
   - `sources`: data bibliografi nyata (status awal `DOI_VERIFIED` atau `DISCOVERED`);
   - `claims`: pernyataan ilmiah yang ingin dibuat;
   - `evidence`: kutipan bukti verbatim dari abstrak/full text (`extraction_method: "VERBATIM_ABSTRACT"` / `"VERBATIM_FULLTEXT"`);
   - `outline`: hierarki judul dan bab;
   - `semantic_reviews`: ulasan kecocokan semantik lengkap (7 field) dengan `evidence_excerpt` yang merupakan substring utuh dari teks bukti.
4. **Tahap 4 (Eksekusi Engine):**  
   Agen menjalankan:
   ```powershell
   .\aai.bat run input_project.json
   ```
5. **Tahap 5 (Verifikasi Mandatori Berkas Audit):**  
   Agen membaca berkas audit sebelum menyatakan selesai:
   - `citation_audit.json`: memastikan `"passed": true`, tidak ada token internal (`turn...`, `view...`, `search...`, `filecite`, `【...】`), dan tidak ada *orphan citation*.
   - `fact_audit.json`: memastikan `"passed": true`, `"structural_passed": true`, `"semantic_passed": true`, dan `"rejection_reasons": []`.
   - `final.docx`: memastikan file dokumen Word telah terbit.
6. **Tahap 6 (Revisi Mandiri jika Ditolak):**  
   Jika audit menghasilkan `passed: false`, agen **tidak boleh memalsukan hasil**. Agen membaca alasan penolakan, memperbaiki payload input JSON, lalu menjalankan ulang `.\aai.bat run input_project.json`.

---

## 5. Hasil Verifikasi Sistem

Semua tahapan verifikasi telah dijalankan secara langsung dan berhasil 100%:

| Perintah Verifikasi | Status | Keterangan |
|---|---|---|
| `.\aai.bat check` | **LULUS** | `[OK] System health check passed` (Build phase: 18) |
| `.\aai.bat run input_edjust_mini.json` | **LULUS** | Menghasilkan draf `draft.md` dan `final.docx` (36.4 KB), audit lulus |
| `.\aai.bat runs input_edjust_mini.json` | **LULUS** | Menampilkan 13 riwayat run audit trail yang tersimpan rapi |
| `.\aai.bat bundle input_edjust_mini.json` | **LULUS** | Mengekspor arsip mandiri `exports/bundle_run_*.zip` |
| `python cache/run_4_probes.py` | **LULUS** | 4 probe anti-halusinasi ditolak secara aman (`passed: false`, `docx_created: false`, 0 warning) |
| `python -m pytest -q --tb=short` | **LULUS** | **346 passed**, 10 deselected dalam 6.79s, **0 warning** |
| `python -m pytest -m integration -q --tb=short` | **LULUS** | **10 passed**, 346 deselected dalam 19.65s (Crossref/OpenAlex live) |

---

## 6. Risiko yang Tersisa & Keterbukaan Ilmiah (Honest Reporting)

* **Bukan Sistem "100% Anti-Halusinasi":**  
  Empat celah bypass yang diuji telah tertutup, sumber dan metadata diverifikasi ulang terhadap basis data resmi, dan kutipan verbatim dicocokkan secara mekanis. Namun, sistem **tidak boleh diklaim "100% anti-halusinasi"**.
* **Ketergantungan Penalaran Semantik:**  
  Kesesuaian makna (*semantic fit*) antara klaim dan bukti tetap bergantung pada model AI reviewer (Antigravity). Oleh karena itu, **penilaian makna ilmiah tetap membutuhkan tinjauan pakar manusia (*Human-in-the-loop*)** sebelum naskah dipublikasikan secara resmi.

---

## 7. Rekomendasi Kesiapan Commit

**SIAP UNTUK COMMIT FINAL.**  
Seluruh perintah pemanggilan pendek `aai`, dokumentasi skill, unit test launcher, perbaikan anti-halusinasi, dan verifikasi integrasi telah berada dalam kondisi stabil, bersih, dan teruji penuh.
