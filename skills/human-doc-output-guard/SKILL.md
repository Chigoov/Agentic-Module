---
name: human-doc-output-guard
description: Internal policy and guard for AAI to ensure academic texts, DOCX files, tables, spreadsheets, reports, proposals, essays, summaries, and student assignments in Indonesian maintain natural student-like style, strict instruction fidelity, zero unrequested bloat, and zero fabricated sources or data. Make sure to use this skill whenever generating or revising Indonesian academic documents, DOCX outputs, tables, or student coursework, especially when the user asks to "make it natural", "jangan seperti AI", or edit an existing template.
metadata:
  short-description: Guard output akademik & dokumen agar natural, minim penambahan tak berdasar, dan setia instruksi
---

# HUMAN DOC OUTPUT GUARD (`human-doc-output-guard`)
**Internal Policy & Quality Guard untuk AUTONOMI AGENTIC ILMIAH (AAI)**

Skill dan kebijakan internal ini wajib dipatuhi oleh seluruh agen AAI setiap kali memproduksi, memodifikasi, atau merevisi output naskah akademik, dokumen DOCX, tabel markdown, berkas spreadsheet, laporan riset, proposal, makalah, ringkasan materi, maupun jawaban tugas perkuliahan berbahasa Indonesia.

---

## 1. Tujuan & Filosofi Inti

Tujuan utama guard ini adalah:
1. **Mencegah "AI Overhang" & Bloat:** Menghilangkan kebiasaan AI yang gemar menambah subbab, teori pembuka yang tidak diminta, callout dekoratif, cover berlebihan, atau tabel analisis yang tidak diinstruksikan pengguna.
2. **Kewajaran Gaya Mahasiswa (Natural Student Tone):** Menjaga agar bahasa Indonesia yang digunakan terdengar wajar, lugas, santun, dan akademik sebagaimana tulisan manusia/mahasiswa sungguhan, bukan teks AI yang terlalu simetris, seragam, atau bombastis.
3. **Kesetiaan Sempit pada Instruksi (Strict Instruction Fidelity):** Jika diminta mengubah satu bab, ubah hanya bab tersebut. Jika diminta format sederhana, jangan gunakan tata letak majalah/brosur.
4. **Kejujuran Terhadap Sumber & Data:** Tidak mengarang data, kutipan, nomor halaman, nama penulis, tahun, maupun angka.

> **Batasan Etis Penting:**
> Skill ini **BUKAN** untuk menipu dosen, bukan alat bypass AI detector dengan sengaja memasukkan salah ketik (typo) palsu, bukan untuk menyamarkan plagiarisme, dan bukan untuk memalsukan sitasi. Kebijakan ini semata-mata menjaga kewajaran gaya penulisan, kepatuhan instruksi, kesederhanaan format, dan integritas dokumen.

---

## 2. Kapan Skill Ini Wajib Digunakan (Triggers)

Agen wajib mengaktifkan dan mengonsultasikan guard ini setiap kali:
- Menyusun atau merevisi `draft.md` dan `final.docx` dalam alur AAI.
- Menjawab tugas kuliah, soal studi kasus, atau menyusun laporan/makalah/proposal mahasiswa.
- Membuat atau menyunting tabel data, ringkasan perbandingan, atau format tabular/spreadsheet.
- Menangani instruksi yang mengandung kata kunci:
  - *"jangan seperti AI"*, *"buat yang natural"*, *"gaya mahasiswa biasa"*;
  - *"ikuti template ini persis"*, *"hanya revisi bagian ini"*, *"jangan diubah bagian lain"*;
  - *"tulis ringkas/secukupnya"*, *"jangan lebay"*, *"format sederhana saja"*.

---

## 3. Delapan Aturan Utama Output Guard

### Aturan 1: Ikuti Instruksi Pengguna Secara Sempit
- **Tanpa Tambahan Tak Diminta:** Jangan menambah bagian baru, subbab tambahan, tabel ekstra, teori pendahuluan, lembar cover, abstrak, dekorasi warna, ikon, atau catatan kesimpulan panjang jika pengguna tidak memintanya.
- **Revisi Terisolasi:** Jika pengguna meminta revisi paragraf 2 atau Bab 3 saja, ubah **hanya** bagian tersebut. Pertahankan bagian lainnya secara utuh.
- **Hormati Perintah "Jangan Diubah":** Jika pengguna menandai suatu teks dengan instruksi "jangan diubah" atau "pertahankan ini", dilarang memparafrase, meringkas, atau melakukan "perbaikan gaya" secara diam-diam.
- **Template Sebagai Patokan Absolut:** Jika pengguna menyertakan dokumen acuan, ikuti tata urutan, gaya penomoran, dan pola heading template tersebut.

### Aturan 2: Jaga Gaya Bahasa Manusia / Mahasiswa
- **Bahasa yang Lugas & Natural:** Gunakan bahasa Indonesia akademik yang baku namun mengalir wajar, tidak kaku seperti terjemahan mesin dan tidak meluap-luap.
- **Hindari Frasa Klise AI:** Jangan gunakan atau batasi seketat mungkin frasa tipikal AI, seperti:
  - `secara komprehensif` ➔ ganti dengan `secara menyeluruh` atau jelaskan langsung substansinya.
  - `dalam konteks ini` ➔ potong atau ganti dengan transisi wajar (`pada situasi tersebut`, `dalam penelitian ini`).
  - `penting untuk digarisbawahi bahwa` ➔ potong langsung ke poin intinya.
  - `berdasarkan uraian di atas, dapat disimpulkan bahwa` ➔ gunakan `kesimpulannya`, `dengan demikian`, atau langsung ke inti temuan.
  - `memiliki peran yang sangat signifikan / krusial` ➔ gunakan `berperan penting` atau `berpengaruh besar`.
  - `pada era modern/globalisasi saat ini` ➔ hapus pembuka klise ini, mulai langsung pada subjek pembahasan.
- **Variasi Ritme Kalimat:** Buat variasi panjang kalimat (gabungan kalimat pendek dan sedang). Hindari paragraf yang polanya terlalu simetris (misal setiap paragraf selalu 4 kalimat dengan panjang yang sama persis).
- **Sopan dan Proporsional:** Untuk tugas mahasiswa, tunjukkan penalaran runtut tanpa bersikap menggurui pembaca.

### Aturan 3: Jangan Mengarang (Zero Fabrication)
- **Data & Sitasi Terverifikasi:** Dilarang mengarang nama peneliti, tahun, judul buku/jurnal, DOI, nomor halaman, persentase statistik, atau hasil wawancara.
- **Penanda Kejujuran:** Jika data pendukung belum lengkap dari pengguna atau repositori, cantumkan penanda transparan:
  - `[sumber belum lengkap]`
  - `[perlu data empiris dari instansi/responden]`
- **Pemisahan Entitas:** Bedakan secara tegas antara temuan fakta dari literatur terverifikasi, interpretasi logis mahasiswa, dan poin yang membutuhkan verifikasi manusia (*human-in-the-loop*).

### Aturan 4: Jaga Format Dokumen DOCX
- **Desain Minimalis & Fungsional:** Naskah akademik dan tugas kuliah harus berformat dokumen standar (kertas A4, margin wajar, font standar seperti Times New Roman / Calibri / Arial ukuran 11-12 pt, spasi 1.15-1.5, teks rata kiri atau justify wajar).
- **Dilarang Format Brosur/Promosi:** Jangan menambahkan bingkai warna-warni, background sel gelap, callout box berdekorasi, ikon emoji, atau elemen presentasi majalah kecuali jika tugasnya spesifik meminta infografis/katalog.
- **Konsistensi dengan Template Acuan:** Pertahankan struktur heading (`Heading 1`, `Heading 2`), jenis penomoran (`1.1`, `A.`, atau `1.`), dan format tabel agar selaras dengan file acuan.
- **Revisi DOCX Bersifat Bedah Mikro:** Untuk revisi berkas `.docx`, ubah hanya paragraf target. Jangan me-rebuild atau merusak style dokumen yang sudah rapi.
- **Pemeriksaan Pasca-Generasi:** Sebelum menyerahkan file `.docx`, periksa kembali: apakah heading sesuai, tidak ada teks placeholder yang tertinggal, kutipan rapi, dan tabel tidak terpotong.

### Aturan 5: Jaga Output Tabel & Spreadsheet
- **Tabel Ringkas & Fungsional:** Gunakan tabel sederhana (umumnya 2–4 kolom) dengan nama header jelas. Isi sel berupa data ringkas, bukan paragraf esai yang dipaksakan masuk ke sel tabel.
- **Tanpa Kolom Analisis Tambahan:** Jangan menambahkan kolom skor buatan AI, kolom evaluasi subjektif, atau kolom formula canggih jika pengguna hanya meminta tabel tabulasi data biasa.
- **Pelestarian Format Data Sensitif:**
  - **NIM / NIK / ID:** Pertahankan sebagai teks agar angka nol di depan (`0123...`) tidak hilang.
  - **Nomor Telepon / WhatsApp:** Pertahankan format internasional/nasional (`0812...` atau `+62...`).
  - **Tanggal & Mata Uang:** Gunakan format standar Indonesia (misal: `Rp150.000` atau `15 September 2026`).
- **Data Kosong Tetap Jujur:** Jangan mengisi sel kosong dengan estimasi rekaan. Tulis tanda strip (`-`), `N/A`, atau catatan kaki singkat.

### Aturan 6: Memahami Makna Permintaan "Jangan Seperti AI"
Ketika pengguna meminta naskah dibuat *"jangan seperti AI"*, *"buat lebih manusiawi"*, atau *"natural"*, agen harus menerjemahkan instruksi ini secara akurat:

| Makna yang Benar | Makna yang Salah (Dilarang) |
|---|---|
| Kalimat lebih mengalir dan natural | Sengaja membuat salah ketik (*typo*) atau ejaan rusak |
| Tidak menggunakan frasa klise pembuka AI | Mengurangi bobot argumen ilmiah secara sengaja |
| Tidak menambah subbab atau teori yang tidak diminta | Memalsukan nama penulis atau membuat referensi fiktif |
| Tata letak sederhana dan tidak artifisial | Menghilangkan sitasi valid demi terlihat "santai" |
| Menjawab tepat sasaran sesuai pertanyaan | Berpura-pura menjadi entitas lain atau menyamarkan plagiarisme |

---

## 4. Alur Kerja Standar Agen (Workflow 3 Tahap)

```
[Tahap 1: Pra-Penulisan]       [Tahap 2: Eksekusi Penulisan]      [Tahap 3: Guard & Audit Akhir]
- Tentukan jenis output         - Tulis secukupnya                 - Cek penambahan liar
- Petakan batas instruksi       - Ikuti acuan struktur              - Cek frasa klise AI
- Baca template / file acuan    - Terapkan gaya natural mahasiswa  - Cek tabel & format DOCX
- Pilih format paling ringkas   - Kunci data & fakta sumber         - Cek data/sitasi rekaan
```

### Tahap 1: Pra-Penulisan (Pre-Execution Scoping)
1. **Identifikasi Format:** Apakah permintaan berupa esai DOCX, tabel markdown, jawaban soal 1-5, laporan praktikum, atau draf naskah AAI?
2. **Kunci Batasan:** Apa saja yang diminta? Catat bagian mana yang **tidak** diminta agar tidak ditulis secara berlebihan.
3. **Telaah Acuan:** Jika ada file template (`#File`), periksa susunan bab, gaya heading, dan font sebelum mulai menulis.

### Tahap 2: Eksekusi Penulisan (Disciplined Drafting)
1. Tulis langsung ke inti jawaban/pembahasan.
2. Gunakan kosakata akademis yang proporsional bagi mahasiswa, tanpa istilah bombastis yang kosong makna.
3. Pastikan setiap klaim penting merujuk pada sumber terverifikasi atau data yang diberikan.

### Tahap 3: Guard & Verifikasi Sebelum Finalisasi
Sebelum menyerahkan teks atau mengompilasi `.docx`:
1. **Check 1 (Unrequested Additions):** Apakah ada bab/tabel/poin kesimpulan yang tidak diminta? Jika ada, hapus.
2. **Check 2 (AI Phrasing Check):** Apakah ada frasa seperti *"secara komprehensif"*, *"dalam konteks ini"*, *"penting untuk digarisbawahi"*? Jika ada, ganti dengan kalimat langsung.
3. **Check 3 (Structure & Table Sanity):** Apakah tabelnya wajar dan sederhana? Apakah heading tidak terlalu dalam (maksimal level 2-3)?
4. **Check 4 (Fact & Data Integrity):** Apakah ada angka atau sumber yang dikarang? Pastikan semua referensi nyata.

---

## 5. Pemeriksaan Audit Sistem: `human_style_audit`

Dalam pipeline otomatis AAI, guard ini direpresentasikan oleh modul audit:
`human_style_audit` (alias: `natural_student_output_guard`).

Laporan audit ini disimpan sebagai `human_style_audit.json` dengan format ringkas:

```json
{
  "passed": true,
  "unrequested_additions": [],
  "ai_style_markers": [],
  "excessive_structure": false,
  "complex_tables": false,
  "fabricated_sources_or_data": false,
  "remediation_applied": []
}
```

Jika ditemukan kegagalan:
- **Tindakan Perbaikan:** Lakukan intervensi minimal (*minimal surgical edit*). Hapus bagian berlebih, ganti frasa klise, dan pulihkan susunan dokumen sesuai instruksi awal pengguna tanpa merombak total dokumen.

---

## 6. Berkas Referensi Terkait

Untuk panduan mendalam, pelajari berkas di folder `references/`:
1. `references/student-style-guide.md` — Panduan kosa kata, variasi kalimat, dan alternatif frasa klise AI dalam bahasa Indonesia.
2. `references/docx-and-table-guard.md` — Spesifikasi tata letak dokumen DOCX rapi, format tabel mahasiswa, dan perlindungan spreadsheet.
3. `references/audit-checklist.md` — Daftar periksa verifikasi cepat sebelum finalisasi berkas.
