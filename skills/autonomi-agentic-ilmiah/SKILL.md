---
name: autonomi-agentic-ilmiah
description: Portable agent protocol and operational workflow for AUTONOMI AGENTIC ILMIAH. Guides AI agents across any sandbox environment to plan, verify, audit, and generate evidence-controlled academic writing without fabricating sources, citations, or data.
metadata:
  short-description: Evidence-controlled academic research and writing protocol
---

# AUTONOMI AGENTIC ILMIAH — Portable Agent Protocol

Protokol operasional ini memandu agen AI (Codex, Claude, GPT, Gemini, atau model mandiri) untuk mengoperasikan repositori **AUTONOMI AGENTIC ILMIAH** secara aman, deterministik, dan bebas dari halusinasi akademik.

---

## 1. Pemisahan Peran Arsitektur

Agar sistem dapat berjalan portabel di berbagai environment agen, bedakan secara tegas peran lima komponen utama:

1. **Skill (Protokol Workflow & Instruksi Kognitif):**
   Panduan aturan etika riset, alur kerja, validasi integritas data, dan heuristik penalaran yang wajib ditaati oleh agen AI. Skill **bukan mesin eksekusi** dan **bukan model runtime**.
2. **Repositori Python (Mesin Eksekusi Deterministik):**
   Kumpulan modul Python di folder `DATA BASE` (`src/`) yang mengeksekusi pemeriksaan skema (Pydantic), gate integritas akademik (`gates.py`), audit sitasi dan fakta (`audit.py`), kompilasi dokumen Word (`docx_generator.py`), pelacakan jejak run (`audit_trail.py`), serta pengemasan berkas (`export_bundle.py`).
3. **Model Provider (Komponen Opsional):**
   Penyedia inferensi LLM tambahan (seperti model lokal Ollama, vLLM, atau API eksternal). Model provider **bersifat opsional**; engine inti repositori bekerja secara deterministik tanpa mewajibkan OpenRouter atau penyedia komersial tertentu.
4. **Internet Search (Komponen Wajib untuk Verifikasi Sumber):**
   Kemampuan web search / API query (Crossref, PubMed, Semantic Scholar, dsb.) yang digunakan oleh agen untuk memverifikasi keberadaan publikasi nyata, mencocokkan DOI resmi, mengecek nomor volume/isu/halaman, dan memastikan kutipan bukan rekayasa.
5. **Sandbox & Terminal (Komponen Wajib untuk Eksekusi Nyata):**
   Environment eksekusi lokal tempat agen dapat menjalankan perintah terminal (`python -m src ...`) dan menulis berkas luaran proyek (`draft.md`, `final.docx`, `runs/`, `exports/`).

---

## 2. Mode Deteksi Kapabilitas Lingkungan (Capability Detection)

Sebelum memulai tugas akademik, agen AI wajib mengidentifikasi kapabilitas environment kerjanya:

### A. Full Mode (Sandbox + Terminal + Internet Search + File Write)
* **Kondisi:** Agen memiliki akses shell terminal, dapat membaca/menulis berkas di sandbox, dan memiliki koneksi internet/search tool.
* **Alur:**
  1. Jalankan `python -m src check` untuk memastikan kesiapan repositori.
  2. Gunakan internet search untuk mencari dan memverifikasi sumber ilmiah asli (judul, penulis, tahun, jurnal, volume, isu, halaman, DOI aktif).
  3. Susun input JSON sesuai skema Pydantic (`input_json.md`) dengan status sumber `APPROVED`.
  4. Jalankan `python -m src run-academic --input-json <path>`.
  5. Periksa audit sitasi (`citation_audit.json`), audit fakta (`fact_audit.json`), dan naskah final (`final.docx`).
  6. Kemas bukti run dengan `python -m src export-bundle`.

### B. Limited Mode (Salah Satu Komponen Terbatas)
* **Kondisi:** Agen memiliki sandbox/terminal tetapi akses internet dibatasi, ATAU agen memiliki internet search tetapi akses terminal/file hanya baca (read-only).
* **Alur & Batasan:**
  * Jika terminal tersedia tetapi internet mati: agen hanya boleh menggunakan sumber yang **sudah terverifikasi sebelumnya** di repositori atau file lokal. Agen **dilarang menebak metadata baru**.
  * Jika internet tersedia tetapi terminal tidak bisa dieksekusi: agen memverifikasi sumber dan menyusun payload JSON yang valid, lalu meminta pengguna menjalankan CLI secara manual di komputernya.
  * Laporkan secara transparan komponen apa yang tidak tersedia; jangan berpura-pura telah mengeksekusi pipeline jika perintah tidak dijalankan.

### C. Draft-Only Mode (Tidak Ada Internet / Sumber Belum Terverifikasi)
* **Kondisi:** Agen tidak memiliki akses internet search dan tidak ada database verifikasi lokal untuk memeriksa keabsahan sumber.
* **Aturan Mutlak:**
  1. **DILARANG KERAS memfinalisasi naskah akademik** atau mengklaim sumber telah terverifikasi.
  2. **DILARANG mengarang DOI, kutipan teks, nomor halaman, atau entri daftar pustaka palsu.**
  3. Status klaim wajib ditandai `PROPOSED` atau `INSUFFICIENT_EVIDENCE`.
  4. Sumber yang belum lengkap wajib ditulis dengan penanda eksplisit `[sumber belum lengkap]`.
  5. Hasil kerja hanya berupa *draft kerja konseptual / outline hipotetis*; dokumen tidak boleh dipromosikan sebagai karya ilmiah siap publikasi.

---

## 3. Aturan Mutlak Integritas Akademik (Anti-Fabrikasi)

1. **Anti-Fabrikasi Sumber & Metadata:**
   * Jangan pernah mengarang nama penulis, tahun terbit, judul artikel, jurnal, volume, nomor terbitan, maupun rentang halaman.
   * Jangan pernah mengarang atau menebak format DOI.
2. **Larangan Finalisasi Tanpa Verifikasi:**
   * Alur penulisan (`WriterAgent` dan `DocxGenerationTool`) menolak sumber yang statusnya belum mencapai tingkat verifikasi yang disyaratkan (`SourceState.APPROVED` / level verifikasi C).
3. **Kewajiban Gate Integritas Output:**
   Setiap teks luaran akademik wajib bersih dari indikasi kebocoran prompt atau token internal LLM:
   * **DILARANG memuat token:** `turn...`, `view...`, `search...`, `filecite`, `citeturn`, atau kurung CJK `【...】`.
   * **Sitasi In-Text APA 7 Presisi:** Titik akhir kalimat diletakkan *setelah* kurung sitasi, contoh: `... adaptasi individu (Amato, 2000).`
   * **Daftar Pustaka APA 7 Granular:** Wajib menyertakan nama jurnal, volume, nomor, halaman, dan tautan resolusi DOI aktif:
     `Journal of Marriage and Family, 62(4), 1269–1287. https://doi.org/10.1111/...`
   * **Metadata Belum Lengkap:** Jika ada komponen yang tidak terlacak dari sumber asli, tandai `[sumber belum lengkap]` alih-alih melengkapi dengan tebakan.
4. **Pemeriksaan Kritis oleh Manusia:**
   Setiap naskah luaran otomatis wajib ditelaah secara kritis oleh peneliti/manusia sebelum dikirim ke dosen pembimbing, jurnal, atau simposium.

---

## 4. Perintah Operasional CLI Utama

Seluruh perintah dijalankan dari root repositori (folder `DATA BASE`):

### A. Health Check Repositori
```powershell
python -m src check
```
Memverifikasi integritas path, konfigurasi sistem, dan spesifikasi versi (Exit Code: 0).

### B. Perencanaan Riset (Planning)
```powershell
python -m src plan "topik atau pertanyaan penelitian"
```
Menganalisis kebutuhan riset, mendeteksi mode, dan menyusun kata kunci serta tahapan pencarian.

### C. Eksekusi Naskah Akademik (Academic Writing Mode)
```powershell
python -m src run-academic --input-json path/to/input.json
```
Menjalankan alur lengkap: synthesis ➔ outline ➔ writing ➔ citation audit ➔ fact audit ➔ docx generation. Menghasilkan naskah `draft.md`, `final.docx`, dan folder rekam jejak `runs/<run_id>/`.

### D. Inspeksi Riwayat Run & Audit Trail
```powershell
# Melihat seluruh riwayat run proyek:
python -m src runs --input-json path/to/input.json

# Melihat rincian satu run spesifik:
python -m src runs --input-json path/to/input.json --run-id <run_id>
```

### E. Retensi & Pemangkasan Run Lama
```powershell
# Menyimpan 20 run terbaru dan membersihkan sisanya secara aman:
python -m src runs --input-json path/to/input.json --prune --keep 20
```

### F. Pengemasan Bundle Arsip Mandiri (.zip)
```powershell
# Mengemas luaran akademik, audit, dan snapshot run terbaru:
python -m src export-bundle --input-json path/to/input.json
```
Menghasilkan berkas terkompresi portabel di `exports/bundle_<run_id>.zip` yang bebas dari data sensitif/token monitor.

### G. Server Monitor Lokal (Opsional)
```powershell
python -m src monitor --port 8000
```
Menyediakan antarmuka dashboard localhost dan endpoint REST API (`/api/check`, `/api/plan`, `/api/run-academic`).

---

## 5. Berkas Referensi Pendukung

Untuk panduan teknis mendalam, baca berkas referensi berikut:
* [references/input-json.md](references/input-json.md): Format lengkap payload JSON yang valid beserta contoh sumber terverifikasi dan penanganan metadata tidak lengkap.
* [references/environment-capabilities.md](references/environment-capabilities.md): Panduan penentuan mode kerja agen (Full, Limited, Draft-Only) dan matriks toleransi alat.
* [references/dry-run-prompt.md](references/dry-run-prompt.md): Contoh alur prompt dari perumusan topik, pencarian bukti empiris, hingga eksekusi CLI.
