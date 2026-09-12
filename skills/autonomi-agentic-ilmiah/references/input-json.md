# Spesifikasi Skema Input JSON (`run-academic`)

Perintah `python -m src run-academic --input-json <path>` menerima berkas JSON yang memetakan lima entitas utama: `project`, `sources`, `claims`, `evidence`, dan `outline`.

Seluruh objek divalidasi langsung oleh model Pydantic di `src/schemas/`.

---

## 1. Struktur Skema Lengkap & Tipe Data

```json
{
  "project": {
    "schema_version": "1.0",
    "name": "edjust-mini",
    "workspace": "TUGAS 1",
    "path": "c:\\Users\\HYPE AMD\\Downloads\\VIBE CODING\\AUTONOMI AGENTIC ILMIAH\\TUGAS 1\\edjust-mini",
    "title": "Edjust: Edukasi Hukum dan Dukungan Sosial bagi Remaja Pasca-Perceraian",
    "citation_style": "APA7",
    "language": "id"
  },
  "sources": [
    {
      "id": "src_amato_2000",
      "schema_version": "1.0",
      "title": "The Consequences of Divorce for Adults and Children",
      "authors": ["Amato, P. R."],
      "year": 2000,
      "venue": "Journal of Marriage and Family",
      "volume": 62,
      "issue": 4,
      "pages": "1269–1287",
      "doi": "10.1111/j.1741-3737.2000.01269.x",
      "url": "https://doi.org/10.1111/j.1741-3737.2000.01269.x",
      "source_type": "JOURNAL_ARTICLE",
      "state": "APPROVED"
    }
  ],
  "claims": [
    {
      "id": "clm_divorce_stress",
      "schema_version": "1.0",
      "claim_text": "Perceraian orang tua berpotensi menimbulkan distres dan beban penyesuaian bagi anak, namun dampaknya bervariasi tergantung pada ketersediaan faktor protektif dan kemampuan adaptasi individu.",
      "importance": 3,
      "status": "SUPPORTED",
      "support_level": "STRONG",
      "supporting_sources": ["src_amato_2000"],
      "supporting_evidence": ["evd_amato_2000"],
      "required_source_count": 1
    }
  ],
  "evidence": [
    {
      "id": "evd_amato_2000",
      "schema_version": "1.0",
      "claim_id": "clm_divorce_stress",
      "source_id": "src_amato_2000",
      "evidence_text": "Penelitian empiris menunjukkan bahwa dampak perceraian terhadap kesejahteraan anak bervariasi secara substansial, di mana faktor moderasi dan sumber daya penanganan masalah berperan penting dalam adaptasi.",
      "relationship": "supports",
      "extraction_method": "MODEL_PARAPHRASE",
      "verbatim": false,
      "quote_verified": false,
      "location": {
        "locator": "abstract"
      }
    }
  ],
  "outline": {
    "schema_version": "1.0",
    "title": "Edjust: Kerangka Edukasi Hukum dan Dukungan Sosial bagi Remaja Pasca-Perceraian",
    "sections": [
      {
        "schema_version": "1.0",
        "title": "Tantangan Penyesuaian Remaja Pasca-Perceraian",
        "level": 1,
        "claim_ids": ["clm_divorce_stress"]
      }
    ]
  }
}
```

---

## 2. Penjelasan Bidang Kunci per Objek

### A. Objek `project`
- `name` (string, wajib): Nama folder proyek yang akan dibuat di dalam workspace.
- `workspace` (string, opsional): Nama workspace target (default: `"TUGAS 1"`).
- `path` (string, wajib): Path absolut folder tempat luaran akan disimpan.
- `title` (string, wajib): Judul naskah dokumen akademik.
- `citation_style` (string): Gaya sitasi, gunakan `"APA7"`.
- `language` (string): Kode bahasa, gunakan `"id"` untuk Bahasa Indonesia.

### B. Objek `sources`
- `id` (string, wajib): Identifier unik lokal (misal: `"src_amato_2000"`).
- `title` (string, wajib): Judul lengkap karya ilmiah asli (tidak boleh dikarang).
- `authors` (array of string, wajib): Daftar nama penulis terstandardisasi, misal `["Amato, P. R."]`.
- `year` (integer, wajib): Tahun publikasi resmi.
- `venue` (string, wajib): Nama jurnal, prosiding, atau penerbit.
- `volume` (integer/string, opsional): Nomor volume jurnal.
- `issue` (integer/string, opsional): Nomor terbitan/isu jurnal.
- `pages` (string, opsional): Rentang halaman artikel, misal `"1269–1287"`.
- `doi` (string, opsional tapi sangat disarankan): Digital Object Identifier resmi (misal: `"10.1111/j.1741-3737.2000.01269.x"`).
- `url` (string, opsional): Tautan canonical resolusi DOI aktif.
- `source_type` (string): Klasifikasi tipe sumber (`"JOURNAL_ARTICLE"`, `"BOOK"`, `"CONFERENCE_PAPER"`, dll).
- `state` (string, wajib): Posisi dalam siklus verifikasi. Gunakan `"APPROVED"` untuk sumber yang telah diverifikasi keabsahannya.

#### Penanganan `[sumber belum lengkap]`:
Bila suatu karya ilmiah belum dapat diverifikasi salah satu metadata pentingnya (misal: volume atau nomor halaman tidak terlacak di basis data resmi):
* Jangan pernah mengarang angka halaman atau volume!
* Biarkan field yang hilang bernilai `null`.
* Jika nama penulis atau tahun tidak ditemukan, sistem audit dan writer akan menandai sitasi dengan penanda eksplisit `[sumber belum lengkap]`.

### C. Objek `claims`
- `id` (string, wajib): Identifier unik klaim (misal: `"clm_divorce_stress"`).
- `claim_text` (string, wajib): Pernyataan faktual yang ingin diajukan dalam naskah.
- `importance` (integer, 1–4): Derajat kepentingan klaim (3 = `HIGH`, 4 = `CRITICAL`).
- `status` (string, wajib): Status pembuktian (`"SUPPORTED"`, `"PARTIALLY_SUPPORTED"`, `"CONFLICTED"`).
- `support_level` (string): Bobot dukungan bukti (`"STRONG"`, `"MODERATE"`, `"WEAK"`).
- `supporting_sources` (array of string): Daftar `id` sumber yang mendukung klaim ini.
- `supporting_evidence` (array of string): Daftar `id` evidence yang membuktikan klaim ini.

### D. Objek `evidence`
- `id` (string, wajib): Identifier unik evidence (misal: `"evd_amato_2000"`).
- `claim_id` (string, wajib): ID klaim yang dibuktikan oleh evidence ini.
- `source_id` (string, wajib): ID sumber tempat evidence ini ditemukan.
- `evidence_text` (string, wajib): Teks kutipan langsung atau ringkasan temuan empiris.
- `relationship` (string): Relasi ke klaim (`"supports"`, `"partially_supports"`, `"contradicts"`).
- `extraction_method` (string): Metode ekstraksi (`"MODEL_PARAPHRASE"`, `"VERBATIM_FULLTEXT"`, `"VERBATIM_ABSTRACT"`).
- `location` (object): Lokasi penemuan dalam teks asli (`locator`, `page`, atau `section`).

### E. Objek `outline`
- `title` (string, wajib): Judul dokumen yang akan dicetak sebagai Heading 1.
- `sections` (array of section objects):
  - `title` (string, wajib): Judul sub-bab (Heading 2).
  - `level` (integer): Tingkat heading (default: 1).
  - `claim_ids` (array of string, wajib): Daftar klaim yang akan dinarasikan di dalam sub-bab ini.

---

## 3. Luaran Minimal yang Dihasilkan

Setelah payload JSON berhasil diproses oleh alur kerja, folder proyek akan memuat:
1. `draft.md`: Naskah naskah lengkap dalam format Markdown beserta in-text citation APA 7.
2. `final.docx`: Dokumen Microsoft Word resmi hasil kompilasi.
3. `citation_audit.json`: Rekam audit sitasi (0 orphan, 0 internal tokens).
4. `fact_audit.json`: Rekam audit fakta dan evidence.
5. `runs/<run_id>/`: Jejak audit trail per-run lengkap (snapshot input, sumber, klaim, evidence, outline, dan `run_summary.json`).
6. `exports/bundle_<run_id>.zip`: Arsip mandiri jika sub-command `export-bundle` dijalankan.
