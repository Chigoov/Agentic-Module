# Laporan Pengujian Workflow Akademik Nyata: Kasus Edjust Mini

**Tanggal:** 10 September 2026  
**Topik Uji:** Edjust sebagai program edukasi hukum dan dukungan sosial bagi remaja 12–18 tahun dari keluarga bercerai  
**Status Eksekusi:** SUKSES (Exit Code 0)  

---

## 1. Sumber Nyata yang Digunakan

Seluruh sumber diverifikasi langsung ke metadata Crossref DOI asli:

1. **Amato, P. R. (2000)**
   - *Judul:* The Consequences of Divorce for Adults and Children
   - *Jurnal/Venue:* Journal of Marriage and Family, Vol. 62, No. 4, hlm. 1269–1287
   - *DOI:* `10.1111/j.1741-3737.2000.01269.x`
   - *URL:* https://doi.org/10.1111/j.1741-3737.2000.01269.x
   - *Relevansi:* Kerangka *divorce-stress-adjustment*; memvalidasi bahwa perceraian menjadi stresor namun adaptasi jangka panjang dimoderasi oleh faktor protektif dan daya lentur individu.

2. **Pedro-Carroll, J. L. (2005)**
   - *Judul:* Fostering resilience in the aftermath of divorce: The role of evidence-based programs for children
   - *Jurnal/Venue:* Family Court Review, Vol. 43, No. 1, hlm. 52–64
   - *DOI:* `10.1111/j.1744-1617.2005.00007.x`
   - *URL:* https://doi.org/10.1111/j.1744-1617.2005.00007.x
   - *Relevansi:* Intervensi preventif berbasis bukti berfokus anak (seperti CODIP); membuktikan efektivitas kelompok dukungan dalam meningkatkan resiliensi dan menurunkan kecemasan.

3. **McIntosh, J. (2000)**
   - *Judul:* Child-inclusive divorce mediation: Report on a qualitative research study
   - *Jurnal/Venue:* Mediation Quarterly, Vol. 18, No. 1, hlm. 55–69
   - *DOI:* `10.1002/crq.3890180106`
   - *URL:* https://doi.org/10.1002/crq.3890180106
   - *Relevansi:* Edukasi hukum dan mediasi ramah anak; menunjukkan manfaat pelibatan perspektif anak secara aman dalam transisi keluarga tanpa membebani peran orang dewasa.

---

## 2. Hasil Run CLI

Perintah eksekusi:
```powershell
python -m src run-academic --input-json input_edjust_mini.json
```

- **Exit Code:** 0
- **Tahapan Workflow yang Dilalui:**
  1. `synthesis` ✅
  2. `outline` ✅
  3. `writing` ✅
  4. `citation_audit` ✅
  5. `fact_audit` ✅
  6. `docx_generation` ✅
- **Kondisi Gate Integritas Akademik:** Lolos penuh tanpa pelanggaran referensial, tanpa orphan IDs, dan tanpa token internal.

---

## 3. Lokasi File Output

Folder Project: `C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH\TUGAS 1\edjust-mini`

1. **`draft.md`**: Naskah akademik Markdown dengan struktur heading, klaim, sitasi in-text, dan daftar pustaka.
2. **`citation_audit.json`**: Hasil audit sitasi (`passed: true`, 0 orphan citation, 0 internal tokens, 0 author-year orphans).
3. **`fact_audit.json`**: Hasil audit klaim-fakta (`passed: true`, 0 unsupported claims).
4. **`final.docx`**: Dokumen Word final hasil kompilasi draft dan daftar pustaka terformat.

---

## 4. Hasil Audit Akademik, Sitasi, Evidence, dan Etika

1. **Format Sitasi In-Text APA 7:**
   - In-text citations terformat benar: `(Amato, 2000)`, `(Pedro-Carroll, 2005)`, dan `(McIntosh, 2000)`.
   - Tidak ada duplikasi atau kegagalan perujukan nama penulis.

2. **Daftar Pustaka APA 7:**
   - Semua entri memuat Penulis, Tahun, Judul, Nama Jurnal/Venue, dan tautan resolusi DOI (`https://doi.org/...`).
   - Tidak ada penanda `[missing: ...]` atau `[sumber belum lengkap]`.

3. **Kesesuaian Evidence terhadap Claim:**
   - Seluruh klaim terhubung 1:1 dengan evidence berstatus `supports`.
   - Evidence disarikan dari temuan abstrak artikel yang diverifikasi, bukan hasil fabrikasi.

4. **Kekuatan Klaim (Claim Strength):**
   - Klaim diformulasikan secara terukur menggunakan bahasa probabilitas akademis (*hedging*), menghindari klaim deterministik ekstrem (misal: tidak mengklaim "semua remaja perceraian mengalami gangguan mental").

5. **Ketiadaan Token Internal:**
   - `citation_audit.json` mengonfirmasi `internal_tokens: []`.
   - Tidak ada token bocor seperti `turn...`, `view...`, `search...`, `filecite`, `citeturn`, atau kurung CJK `【】`.

6. **Keamanan Etika bagi Remaja Usia 12–18:**
   - Tidak menggunakan subjek individu atau data pribadi/identifikasi siswa/remaja.
   - Tidak menyusun instrumen lapangan tanpa persetujuan etik.
   - Fokus konten murni pada literasi hukum preventif dan penguatan psikososial yang adaptif.

---

## 5. Masalah yang Ditemukan

Meskipun alur kerja berhasil 100% dan lulus audit teknis, ditemukan 2 detail tipografis/format akademik:

1. **Penempatan Tanda Baca Titik pada In-Text Citation:**
   - Pada `draft.md`, jika kalimat klaim pada input JSON diakhiri tanda titik, `WriterAgent` langsung menempelkan sitasi di belakangnya:
     `...adaptasi individu. (Amato, 2000)`
   - Standar APA 7 menganjurkan tanda titik diletakkan *setelah* kurung sitasi pada akhir kalimat:
     `...adaptasi individu (Amato, 2000).`

2. **Detail Volume, Issue, dan Halaman pada Venue:**
   - Saat ini `Source` hanya memiliki field tunggal `venue: str` tanpa struktur terpisah untuk `volume`, `issue`, dan `pages` (atau pengguna harus menggabungkannya secara manual di dalam string `venue`, misal: `"Journal of Marriage and Family, 62(4), 1269–1287"`).
   - Akibatnya, jika hanya menulis nama jurnal, referensi belum mencakup nomor volume dan halaman secara otomatis.

---

## 6. Rekomendasi Patch Terkecil Berikutnya

1. **Patch Penempatan Tanda Titik di `WriterAgent._render_section` (`src/agents/writer.py`):**
   - Jika `claim.claim_text` diakhiri dengan tanda titik `.` dan ada `citations`, strip tanda titik akhir sebelum menempelkan sitasi, lalu tambahkan titik di akhir:
     ```python
     if citations and statement.endswith("."):
         statement = statement[:-1] + citations + "."
     else:
         statement = f"{statement}{citations}"
     ```
   - Ini memastikan tipografi sitasi in-text APA 7 selalu presisi tanpa bergantung pada cara input kalimat pengguna.


---

## 7. Status Patch Perbaikan (10 September 2026)

- **Patch Diterapkan pada:** `src/agents/writer.py`
- **Regression Test:** `tests/test_audit_fix_regression.py::test_terminal_punctuation_placed_after_in_text_citation` (Passed)
- **Hasil Rerun:**
  - `draft.md` dan `final.docx` menghasilkan:
    - `... kemampuan adaptasi individu (Amato, 2000).`
    - `... risiko kecemasan pasca-perceraian (Pedro-Carroll, 2005).`
    - `... konflik orang tua (McIntosh, 2000).`
  - `citation_audit.json`: `passed: true`
  - `fact_audit.json`: `passed: true`
  - Token internal: 0 (bersih)
