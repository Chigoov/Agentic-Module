---
name: aai
description: Short alias for AUTONOMI AGENTIC ILMIAH (AAI). Evidence-controlled academic research and writing protocol. Enforces verified sources, verbatim evidence, semantic reviews, citation audits, and fact audits before generating academic papers.
metadata:
  short-description: Evidence-controlled academic research and writing protocol (AAI alias)
---

# SKILL AAI — AUTONOMI AGENTIC ILMIAH

Skill ini adalah alias pendek untuk **AUTONOMI AGENTIC ILMIAH (AAI)**.

Protokol ini diaktifkan saat pengguna meminta:
- *"skill aai"*, *"gunakan AAI"*, *"pakai Autonomi Agentic Ilmiah"*, atau penulisan riset akademik anti-halusinasi.

---

## Ringkasan Cepat Protokol Kerja AI Agent

1. **Check Kesiapan Sistem:**
   Jalankan `.\aai.bat check` (atau `python -m src check`). Pastikan status `[OK]`.
2. **Cari Sumber Nyata:**
   Gunakan tools internet search milik agen (Crossref, PubMed, arXiv, Scholar). Ambil judul, penulis, tahun, venue, DOI, dan kutipan verbatim dari abstrak/teks lengkap asli. Dilarang mengarang metadata.
3. **Susun Input JSON:**
   Buat payload JSON (`sources`, `claims`, `evidence`, `outline`, `semantic_reviews`). Untuk klaim penting/konsekuensial (kausal, statistik, efektivitas), wajib sertakan bukti verbatim dan ulasan semantik lengkap dengan kutipan persis (*exact contiguous substring*).
4. **Jalankan Alur AAI:**
   Jalankan `.\aai.bat run <input.json>` (atau `python -m src run-academic --input-json <input.json>`).
5. **Humanizer Singkat:**
   Pastikan draf akhir memakai bahasa Indonesia yang sederhana, natural, dan seperti tulisan mahasiswa yang rapi. Hapus frasa AI yang terlalu umum, tetapi jangan menambah fakta, data, sumber, kutipan, DOI, atau halaman.
6. **Wajib Periksa Berkas Audit:**
   Sebelum menyatakan berhasil, agen wajib memeriksa:
   - `citation_audit.json` ➔ harus `"passed": true`.
   - `fact_audit.json` ➔ harus `"passed": true`.
   - Naskah akhir bebas dari token internal (`turn...`, `view...`, `search...`, `filecite`, `【...】`).
   - Berkas `final.docx` berhasil terbuat.
7. **Perbaiki Input jika Gagal:**
   Jika audit menolak (`passed: false`), baca alasan penolakan di `fact_audit.json`, lalu perbaiki input JSON. Dilarang memalsukan draf manual.

---

## Perintah Launcher Cepat

- `.\aai.bat check` : Health check sistem
- `.\aai.bat open` : Buka live dashboard di browser
- `.\aai.bat monitor` : Jalankan server monitor di terminal (port 8000)
- `.\aai.bat run <input.json>` : Jalankan alur penulisan akademik lengkap
- `.\aai.bat runs <input.json>` : Periksa riwayat run & audit trail
- `.\aai.bat bundle <input.json>` : Ekspor berkas paket terkompresi (.zip)

---

## Catatan Keterbukaan Ilmiah

* Sistem deterministik ini menutup celah bypass yang diuji dan memverifikasi ulang sumber/kutipan.
* **Jangan klaim "100% anti-halusinasi"**; penilaian kesesuaian makna ilmiah (*semantic fit*) tetap memerlukan tinjauan pakar manusia (*Human-in-the-loop*).
* Tabel, bullet, dan heading harus terasa seperti dokumen mahasiswa normal: tabel hanya untuk data/perbandingan/rubrik, biasanya 2-4 kolom, isi sel pendek, heading singkat, dan bullet hanya untuk daftar nyata.

Untuk dokumentasi lengkap, lihat:
`skills/autonomi-agentic-ilmiah/SKILL.md`.
