---
name: aai
description: Short alias for AUTONOMI AGENTIC ILMIAH (AAI). Evidence-controlled academic research and writing protocol. Enforces verified sources, verbatim evidence, semantic reviews, citation audits, and fact audits before generating academic papers.
metadata:
  short-description: Evidence-controlled academic research and writing protocol (AAI alias)
---

# SKILL AAI — AUTONOMI AGENTIC ILMIAH

Skill ini adalah alias pendek untuk **AUTONOMI AGENTIC ILMIAH (AAI)**.

Untuk payload dan gerbang terbaru, **baca lebih dahulu**
[kontrak input bersama](../autonomi-agentic-ilmiah/references/input-json.md).
Contoh [input sintetis](../autonomi-agentic-ilmiah/references/input-synthetic.json)
valid secara skema tetapi sengaja PARTIAL; bukan penelitian/provider nyata.
Kontrak mencakup verification_artifact, retrieval/hash, examination,
eligibility_review, assessment berlokasi, output_type/required_sections,
require_free_full_text, quantitative_review, resume, dan bundle per run_id.

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
5. **Humanizer & Output Guard (`human-doc-output-guard`):**
   Terapkan kebijakan `human-doc-output-guard`. Pastikan draf akhir memakai bahasa Indonesia yang sederhana, natural, dan seperti tulisan mahasiswa yang rapi. Hindari frasa AI klise ("secara komprehensif", "dalam konteks ini", "penting untuk digarisbawahi", "berdasarkan uraian di atas"), jangan menambah bagian/tabel tak diminta, dan jangan menambah fakta, data, sumber, kutipan, DOI, atau halaman rekaan.
6. **Wajib Periksa Berkas Audit:**
   Sebelum menyatakan berhasil, agen wajib memeriksa:
   - `citation_audit.json` ➔ harus `"passed": true`.
   - `fact_audit.json` ➔ harus `"passed": true`.
   - `human_style_audit.json` ➔ harus `"passed": true` (bebas dari tambahan tak diminta, frasa klise AI, dan tabel berlebihan).
   - Naskah akhir bebas dari token internal (`turn...`, `view...`, `search...`, `filecite`, `【...】`).
   - Baca metadata `execution_success`, `result_status`, `finalization_allowed`,
     `needs_human_review` dan `runs/<run_id>/run_summary.json` aktual. PASS final
     memerlukan workbook/scoring yang final, quality gate, serta review queue
     bebas item yang memblokir. PARTIAL boleh disimpan/diekspor; jangan menuntut
     atau mengaku memiliki `final.docx` ketika finalisasi belum diizinkan.
7. **Perbaiki Input jika Gagal:**
   Jika audit menolak, baca alasan dan `claim_screening.json`, lalu perbaiki input
   serta outline. Revisi memakai project aktual dan `--resume`, bukan membuat
   tugas baru. Ekspor/riwayat pilih `--run-id` yang benar. Dilarang memalsukan review.

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
- `skills/autonomi-agentic-ilmiah/SKILL.md`
- `skills/human-doc-output-guard/SKILL.md`
