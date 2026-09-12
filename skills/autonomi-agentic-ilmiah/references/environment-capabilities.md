# Protokol Deteksi Kapabilitas Lingkungan (Environment Capabilities)

Dokumen ini menjelaskan cara AI agen mendeteksi kapabilitas lingkungan kerjanya sebelum mengoperasikan repositori **AUTONOMI AGENTIC ILMIAH**, serta batasan operasional yang berlaku pada setiap mode.

---

## 1. Matriks Kapabilitas Lingkungan

| Kapabilitas | Fungsi dalam Alur Kerja | Komponen Alternatif jika Tidak Ada |
|---|---|---|
| **Sandbox & Terminal Execution** | Menjalankan CLI Python (`python -m src ...`), gate integritas, audit otomatis, dan kompilasi DOCX. | Mode Asistensi Manual: Agen menyiapkan payload JSON dan memandu pengguna menjalankannya di terminal lokal. |
| **File Read / Write** | Membaca skema repositori dan menulis berkas luaran (`draft.md`, `final.docx`, `runs/`, `exports/`). | Mode Tampilan Percakapan: Agen menampilkan draft dan payload langsung di jendela chat. |
| **Internet Search / Web Query** | Menemukan publikasi ilmiah riil, memverifikasi metadata Crossref/DOI, dan mengekstrak temuan empiris nyata. | **TIDAK ADA ALTERNATIF UNTUK VERIFIKASI**. Jika internet tidak ada, sistem wajib masuk ke **Draft-Only Mode**. |
| **Model Provider (LLM)** | Opsional: Membantu perumusan rencana riset atau parafrase kreatif jika dikonfigurasi. | Engine inti bekerja secara deterministik tanpa LLM eksternal (OpenRouter bukan syarat wajib). |

---

## 2. Tiga Mode Operasional Agen

### Mode 1: Full Mode (Sandbox + Terminal + Internet Search + File Write)
* **Karakteristik:** Lingkungan kerja ideal di mana agen memiliki akses shell terminal, izin menulis berkas lokal, dan kemampuan web search/query internet.
* **Prosedur Kerja:**
  1. Agen memverifikasi integritas repositori: `python -m src check`.
  2. Agen menggunakan internet search untuk mencari literatur ilmiah riil (misal via Crossref, PubMed, SAGE, Wiley, Google Scholar).
  3. Agen memverifikasi nomor DOI resmi, nama penulis, tahun, volume, isu, dan rentang halaman.
  4. Agen menyusun berkas input JSON yang valid dengan status sumber `APPROVED`.
  5. Agen mengeksekusi `python -m src run-academic --input-json <path>`.
  6. Agen memverifikasi bahwa audit sitasi dan fakta lulus (`passed: true`), lalu mengemas berkas final: `python -m src export-bundle`.
* **Status Luaran:** Karya ilmiah terverifikasi, aman, dan siap ditelaah manusia.

---

### Mode 2: Limited Mode (Salah Satu Komponen Terbatas)
* **Kasus A — Terminal & Sandbox Ada, tetapi Internet Terbatas / Diblokir:**
  * **Batasan:** Agen **tidak dapat mencari atau memverifikasi publikasi ilmiah baru**.
  * **Aturan:** Agen hanya boleh memproses sumber data yang berkas aslinya atau metadata lengkapnya **sudah tersimpan secara lokal** di perangkat (misal file PDF/JSON yang disediakan pengguna).
  * **Larangan:** Dilarang mengarang metadata publikasi baru hanya untuk membuat pipeline berjalan.
* **Kasus B — Internet Ada, tetapi Eksekusi Terminal Diblokir (Environment Read-Only / Chat-Only):**
  * **Batasan:** Agen tidak dapat menjalankan script Python secara langsung.
  * **Aturan:** Agen bertindak sebagai *asisten persiapan riset*:
    1. Agen memverifikasi sumber ilmiah secara nyata melalui internet search.
    2. Agen menyusun berkas `input.json` yang presisi dan valid.
    3. Agen memberikan instruksi baris perintah yang siap disalin oleh pengguna ke terminal komputernya:
       ```powershell
       python -m src run-academic --input-json input.json
       ```
  * **Transparansi:** Agen harus jujur menyatakan bahwa kompilasi naskah dan audit belum dijalankan karena ketiadaan sandbox terminal.

---

### Mode 3: Draft-Only Mode (Tidak Ada Internet / Sumber Belum Terverifikasi)
* **Karakteristik:** Lingkungan agen tidak memiliki internet search, dan tidak ada sumber terverifikasi yang disediakan oleh pengguna.
* **Aturan Mutlak Pencegahan Halusinasi:**
  1. **Dilarang keras melakukan finalisasi akademik.** Jangan pernah mengklaim dokumen sebagai artikel terverifikasi atau hasil riset valid.
  2. **Dilarang keras mengarang DOI.** Jangan membuat string DOI rekaan (misal `10.1000/xyz`) atau meniru format DOI yang tidak terdaftar di Crossref.
  3. **Dilarang keras mengarang nomor halaman, nomor volume, atau daftar pustaka fiktif.**
  4. Seluruh sumber wajib diberi penanda eksplisit `[sumber belum lengkap]`.
  5. Status klaim pada skema JSON wajib diset ke `PROPOSED` atau `INSUFFICIENT_EVIDENCE`.
  6. Dokumen luaran hanya boleh berupa *outline konseptual / draft kerja hipotetis*, dan agen wajib menyertakan peringatan bahwa seluruh rujukan belum diverifikasi secara empiris.

---

## 3. Checklist Sebelum Finalisasi Akademik

Sebelum agen menyatakan bahwa naskah akademik telah selesai dibuat, periksa kepatuhan berikut:

- [ ] Apakah setiap sumber memiliki DOI atau tautan canonical yang nyata dan terverifikasi?
- [ ] Apakah setiap klaim terikat dengan bukti empiris nyata (bukan ringkasan fiktif)?
- [ ] Apakah teks luaran bebas dari token internal LLM (`turn...`, `view...`, `search...`, `filecite`, `citeturn`, atau `【...】`)?
- [ ] Apakah sitasi in-text menggunakan format APA 7 (`... (Penulis, Tahun).`)?
- [ ] Apakah daftar pustaka menyertakan volume, isu, halaman, dan tautan resolusi DOI aktif?
- [ ] Apakah `citation_audit.json` dan `fact_audit.json` bernilai `passed: true`?
- [ ] Apakah ada peringatan bahwa telaah kritis oleh manusia tetap wajib dilakukan?
