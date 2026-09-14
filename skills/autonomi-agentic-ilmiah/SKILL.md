---
name: autonomi-agentic-ilmiah
description: Portable agent protocol and operational workflow for AUTONOMI AGENTIC ILMIAH (AAI). Guides AI agents across any environment (Kiro IDE, Antigravity, Claude, Codex, GPT) to plan, verify, audit, and generate evidence-controlled academic writing without fabricating sources, citations, or data.
metadata:
  short-description: Evidence-controlled academic research and writing protocol (AAI)
---

# AUTONOMI AGENTIC ILMIAH (AAI) — Portable Agent Protocol

Protokol operasional ini memandu agen AI (Kiro IDE, Antigravity, Claude, Codex, GPT, atau model lainnya) untuk mengoperasikan repositori **AUTONOMI AGENTIC ILMIAH (AAI)** secara aman, deterministik, dan berintegritas akademik tinggi.

---

## 1. Identitas & Pemicu Penggunaan Skill (Triggers)

* **Singkatan Resmi:** **AAI** = **AUTONOMI AGENTIC ILMIAH**.
* **Kapan Skill Ini Digunakan:**
  Aktifkan protokol ini setiap kali pengguna meminta:
  - *"gunakan AAI"*, *"pakai skill aai"*, *"jalankan autonomi agentic ilmiah"*;
  - pembuatan naskah karya ilmiah / riset berbasis bukti nyata (*evidence-controlled academic writing*);
  - penelusuran pustaka, verifikasi sitasi APA 7, audit fakta, dan pembuatan draf serta dokumen `.docx` akademik anti-halusinasi.

---

## 2. Pemisahan Peran Arsitektur

Agar sistem berjalan portabel di berbagai environment agen, bedakan secara tegas peran lima komponen utama:

1. **Skill (Protokol Workflow & Instruksi Kognitif):**
   Panduan aturan etika riset, alur kerja, validasi integritas data, dan heuristik penalaran yang wajib ditaati oleh agen AI. Skill **bukan mesin eksekusi** dan **bukan model runtime**.
2. **Repositori Python (Mesin Eksekusi Deterministik):**
   Kumpulan modul Python di folder `DATA BASE` (`src/`) yang mengeksekusi pemeriksaan skema (Pydantic), gate integritas akademik (`gates.py`), audit sitasi dan fakta (`audit.py`), kompilasi dokumen Word (`docx_generator.py`), pelacakan jejak run (`audit_trail.py`), serta pengemasan berkas (`export_bundle.py`).
3. **Model Provider (Komponen Opsional):**
   Penyedia inferensi LLM tambahan (seperti model lokal Ollama, vLLM, atau API eksternal). Model provider **bersifat opsional**; engine inti repositori bekerja secara deterministik tanpa mewajibkan OpenRouter atau penyedia komersial tertentu.
4. **Internet Search (Komponen Agen untuk Verifikasi Sumber):**
   Kemampuan web search / API query (Crossref, PubMed, Semantic Scholar, dsb.) milik agen AI untuk memverifikasi keberadaan publikasi nyata, mencocokkan DOI resmi, mengecek nomor volume/isu/halaman, dan memastikan kutipan bukan rekayasa.
5. **Sandbox & Terminal (Lingkungan Eksekusi):**
   Environment eksekusi lokal tempat agen dapat menjalankan perintah launcher lokal (`.\aai.bat ...` atau `python -m src ...`) dan memeriksa luaran berkas proyek (`draft.md`, `final.docx`, `runs/`, `exports/`).

---

## 3. Protokol Kerja 6 Langkah AI Agent

Ketika agen AI ditugaskan menyusun naskah akademik dengan AAI, jalankan siklus kerja berikut secara berurutan:

```
+-----------+     +-------------------+     +------------------+
| 1. CHECK  | --> | 2. WEB SEARCH     | --> | 3. COMPOSE JSON  |
| aai check |     | (Cari Sumber Riil)|     | (Skema & Review) |
+-----------+     +-------------------+     +------------------+
                                                      |
                                                      v
+-----------+     +-------------------+     +------------------+
| 6. REVISE | <-- | 5. AUDIT VERIFY   | <-- | 4. RUN AAI       |
| (Perbaiki)|     | (Baca JSON Audit) |     | aai run in.json  |
+-----------+     +-------------------+     +------------------+
```

### Langkah 1: Pemeriksaan Kesiapan Sistem
Sebelum melakukan manipulasi apa pun, agen wajib menjalankan health check sistem:
```powershell
.\aai.bat check
# atau: python -m src check
```
Pastikan menghasilkan `[OK] System health check passed` (Exit Code: 0).

### Langkah 2: Penelusuran Sumber Ilmiah Nyata (Internet Tool Agen)
Agen diperbolehkan dan **diwajibkan menggunakan tools internet search miliknya sendiri** untuk menelusuri literatur ilmiah asli:
* Cari publikasi bereputasi (Crossref, arXiv, PubMed, Google Scholar, IEEE, Springer, Elsevier).
* Catat secara presisi: Judul lengkap, nama penulis (format APA: `Family, Initials`), tahun terbit, nama jurnal/venue, volume, nomor terbitan, rentang halaman, dan tautan resolusi DOI aktif.
* Ambil teks kutipan asli secara **verbatim** langsung dari abstrak atau teks lengkap artikel.

### Langkah 3: Penyusunan Payload Input JSON
Agen menyusun berkas input JSON (misal `input_project.json`) sesuai skema Pydantic:
* `sources`: Sumber ilmiah yang ditemukan dengan status deklarasi awal yang jujur (gunakan `DOI_VERIFIED` atau `DISCOVERED`).
* `claims`: Proposisi klaim ilmiah yang ingin diajukan.
* `evidence`: Bukti empiris pendukung. Untuk klaim konsekuensial (kausal, statistik, efektivitas, arah, mekanisme, absolut), **wajib menyertakan bukti verbatim dari abstract atau full text** (`extraction_method: "VERBATIM_ABSTRACT"` atau `"VERBATIM_FULLTEXT"`), bukan hanya parafrase model.
* `outline`: Struktur bab dan subbab naskah yang memetakan claim IDs.
* `semantic_reviews`: Catatan ulasan kesesuaian makna semantik antara klaim dan bukti:
  - Wajib menyertakan 7 atribut lengkap: `claim_id`, `decision: "SUPPORTED"`, `reason`, `evidence_id`, `source_id`, `evidence_excerpt`, `location`, `reviewer`, `method`.
  - `evidence_excerpt` wajib merupakan bagian kontigu utuh (*exact contiguous substring*) dari teks bukti asli.

### Langkah 4: Eksekusi Alur Penulisan & Verifikasi
Jalankan eksekusi melalui perintah launcher:
```powershell
.\aai.bat run input_project.json
```
Repositori akan secara deterministik menjalankan:
`synthesis` ➔ `outline` ➔ `writing` ➔ `humanizer` ➔ `citation_audit` ➔ `fact_audit` ➔ `docx_generation`.

### Langkah 5: Pembacaan Wajib Audit Sitasi, Audit Fakta, & Run Trail
Agen **DILARANG menyatakan tugas berhasil sebelum memeriksa berkas audit**:
1. Buka dan baca `citation_audit.json`:
   - Pastikan `"passed": true`.
   - Pastikan `"orphan_citations": []`, `"internal_tokens": []`, `"author_year_orphans": []`.
2. Buka dan baca `fact_audit.json`:
   - Pastikan `"passed": true`, `"structural_passed": true`, `"semantic_passed": true`.
   - Pastikan `"unsupported_claims": []` dan `"rejection_reasons": []`.
3. Periksa keberadaan naskah final:
   - Pastikan `final.docx` berhasil dibuat di direktori proyek.
   - Periksa draf `draft.md` bebas dari segala token internal (`turn...`, `view...`, `search...`, `filecite`, atau `【...】`).

### Langkah 6: Tindakan Perbaikan jika Audit Gagal (Looping & Refinement)
Jika audit gagal (`passed: false` atau muncul alasan penolakan pada `fact_audit.json`):
* **DILARANG KERAS mengarang hasil, memalsukan persetujuan, atau mengubah draf manual secara sepihak.**
* Agen wajib membaca `rejection_reasons` pada laporan audit, memperbaiki cacat pada berkas input JSON (misalnya: mencari kutipan verbatim yang sesuai di teks sumber asli, memperbaiki ketidaksesuaian ID rantai bukti, melengkapi parameter ulasan semantik yang hilang, atau menambahkan *qualifier* pada klaim yang terlalu kuat/overclaiming).
* Jalankan ulang `.\aai.bat run input_project.json` hingga seluruh gerbang integritas akademik terpenuhi.

---

## 4. Perintah Cepat Launcher `aai`

Pengguna dan AI agent dapat menggunakan shortcut launcher `.\aai.bat` (atau `./aai.ps1`) di root repositori:

| Perintah | Fungsi Utama | Perintah Asli Python |
|---|---|---|
| `.\aai.bat check` | Memeriksa kesiapan sistem repositori | `python -m src check` |
| `.\aai.bat open` | Membuka monitor progress live di browser (port 8000) | Menjalankan server & buka browser |
| `.\aai.bat monitor` | Menjalankan server monitor di terminal | `python -m src monitor --port 8000` |
| `.\aai.bat run <file.json>` | Menjalankan alur penulisan akademik lengkap | `python -m src run-academic --input-json <file>` |
| `.\aai.bat runs <file.json>` | Memeriksa riwayat audit trail eksekusi | `python -m src runs --input-json <file>` |
| `.\aai.bat bundle <file.json>` | Mengekspor arsip paket run mandiri (.zip) | `python -m src export-bundle --input-json <file>` |
| `.\aai.bat help` | Menampilkan panduan ringkas bantuan | - |

---

## 5. Aturan Mutlak Integritas Akademik (Anti-Halusinasi)

1. **Anti-Fabrikasi Sumber & DOI:**
   - Dilarang mengarang nama penulis, tahun terbit, nama jurnal, volume, nomor terbitan, maupun rentang halaman.
   - Dilarang mengarang atau menebak format DOI (seperti `10.9999/...`).
2. **Status Sumber Tidak Boleh Dikarang:**
   - Flag `"state": "APPROVED"` pada payload input tidak dipercaya sebagai bukti verifikasi; seluruh sumber diverifikasi ulang via `VerificationEngine` (Crossref/OpenAlex) sebelum dokumen final dapat dibuat.
3. **Kewajiban Bukti Verbatim untuk Klaim Konsekuensial:**
   - Klaim kausal, statistik/numerik, efektivitas, arah, mekanisme, atau kata absolut tidak boleh hanya berlandaskan `MODEL_PARAPHRASE`. Wajib ada kutipan verbatim dari abstrak atau naskah lengkap sumber.
4. **Pembersihan Token Internal AI:**
   - Teks naskah final **DILARANG memuat token:** `turn...`, `view...`, `search...`, `filecite`, `citeturn`, atau kurung mentah `【...】`.
5. **Sitasi & Daftar Pustaka APA 7:**
   - Titik akhir kalimat diletakkan setelah kurung sitasi: `... adaptasi individu (Amato, 2000).`
   - Daftar pustaka wajib memuat nama jurnal, volume, nomor, halaman, dan tautan resolusi DOI aktif.

---

## 6. Humanizer & Tata Letak Dokumen Normal

Humanizer adalah tahap penyuntingan ringan sebelum DOCX final. Tujuannya membuat naskah terasa seperti tulisan mahasiswa yang rapi, bukan seperti jawaban AI yang terlalu licin. Humanizer **tidak boleh** menambah fakta, data, kutipan, DOI, halaman, sumber, atau klaim baru.

Aturan gaya:
* Gunakan bahasa Indonesia yang sederhana, natural, dan akademik secukupnya.
* Hindari pembuka template seperti "di era globalisasi", "secara keseluruhan", "dapat disimpulkan bahwa", dan frasa terlalu umum seperti "sangat penting untuk diperhatikan" jika bisa dibuat lebih pendek.
* Pakai kalimat sedang-pendek. Jangan memaksa semua paragraf terdengar formal atau bombastis.
* Pertahankan penanda jujur seperti `[perlu data pendukung]` dan `[sumber belum lengkap]`.

Aturan tabel, daftar, dan heading:
* Tabel dipakai hanya untuk data, perbandingan, rubrik, jadwal, atau ringkasan yang memang lebih mudah dibaca dalam kolom.
* Tabel normal mahasiswa biasanya ringkas: 2-4 kolom, judul kolom jelas, isi sel pendek, dan tidak berisi paragraf panjang.
* Jangan membuat tabel hanya agar dokumen terlihat ramai. Jika satu paragraf lebih jelas, gunakan paragraf.
* Bullet/nomor dipakai hanya untuk daftar nyata. Jangan mengubah seluruh esai menjadi poin-poin.
* Heading dibuat singkat dan wajar, misalnya `Pendahuluan`, `Pembahasan`, `Kesimpulan`, bukan heading promosi atau terlalu dramatis.

---

## 7. Batasan Sistem dan Keterbukaan Ilmiah (Honest Reporting)

* **Jangan Pernah Mengklaim "100% Anti-Halusinasi":**  
  Gunakan bahasa yang presisi dan jujur:
  - *"Empat bypass integritas yang diuji telah tertutup secara deterministik."*
  - *"Sumber dan metadata diverifikasi ulang terhadap basis data bibliografi resmi."*
  - *"Evidence verbatim dicocokkan secara persis dengan abstrak/teks sumber yang tersedia."*
* **Kebutuhan Human-in-the-Loop:**  
  Python Engine memvalidasi integritas mekanis dan tekstual. Namun, evaluasi kesesuaian makna ilmiah yang mendalam (*semantic fit*) atas apakah sebuah premis riset benar-benar memvalidasi kesimpulan tetap mengandalkan agen penalaran AI dan **tetap membutuhkan verifikasi akhir oleh pakar manusia (*human review*)** sebelum naskah dipublikasikan secara akademik.
