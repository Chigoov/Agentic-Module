# LAPORAN PENGUATAN SISTEM ANTI-HALUSINASI DAN FACT AUDIT BERBASIS MAKNA SEMANTIK

**Tanggal Pelaksanaan:** 12 September 2026  
**Repositori:** `AUTONOMI AGENTIC ILMIAH` (`DATA BASE`)  
**Status Eksekusi:** SELESAI, TERVERIFIKASI REGRESI, TANPA COMMIT/PUSH SESUAI BATASAN  

---

## 1. Kondisi Git Sebelum dan Sesudah

### A. Kondisi Git Sebelum Pekerjaan
- **Branch:** `main` (sinkron dengan `origin/main` pada commit `4416290`)
- **Working Tree:** Bersih (`nothing to commit, working tree clean`)
- **Baseline Test:**
  - `python -m src check`: `[OK] System health check passed` (Exit code: 0)
  - `python -m pytest -q --tb=short`: 321 passed, 10 deselected (Exit code: 0)
  - `python -m pytest -m integration -q --tb=short`: 10 passed, 321 deselected (Exit code: 0)

### B. Kondisi Git Sesudah Pekerjaan
- **Branch:** `main` (tetap pada baseline commit `4416290`)
- **Working Tree:** Perubahan kode dan penambahan tes tersimpan lokal di working tree tanpa dilakukan `git commit`, `git push`, atau PR sesuai instruksi mutlak.
- **Status Berkas (`git status -sb`):**
  ```text
  ## main...origin/main
   M input_edjust_mini.json
   M src/agents/audit.py
   M src/runtime/cli.py
   M src/runtime/monitor.py
   M src/schemas/claim.py
   M src/tools/citation_manager.py
   M src/workflows/academic.py
   M src/workflows/orchestrator.py
  ?? docs/LAPORAN_PENGUATAN_ANTI_HALUSINASI_FACT_AUDIT_2026-09-12.md
  ?? tests/test_semantic_fact_audit_regression.py
  ```

---

## 2. Akar Masalah

Sebelum perbaikan ini, `FactAuditAgent` (`src/agents/audit.py`) hanya melakukan pemeriksaan struktural sederhana:
```python
unsupported = [claim.id for claim in request.claims if claim.is_important and not claim.is_writable]
```
Di mana properti `claim.is_writable` hanya memeriksa:
1. `claim.status in WRITABLE_STATUSES` (`SUPPORTED`, `PARTIALLY_SUPPORTED`, `CONFLICTED`).
2. `claim.supporting_evidence` tidak kosong jika `claim.evidence_required` bernilai `True`.

### Dampak Celah:
- Klaim dengan teks apa pun (misalnya klaim palsu *"Diet ketogenik menyembuhkan Alzheimer secara permanen"*) dapat diluluskan audit fakta dan mencapai dokumen final `final.docx` asalkan diberi status `SUPPORTED` dan dikaitkan dengan ID evidence apa pun (meskipun isi evidence membahas konsumsi kopi).
- Sistem tidak memeriksa apakah isi teks evidence benar-benar mendukung makna semantik klaim.
- Tidak ada mekanisme untuk memeriksa klaim yang tidak memiliki penilaian semantik dari AI agent pemeriksa (*Antigravity/external agent*).
- Klaim berlebihan (*overclaiming*) dengan kata-kata sebab-akibat mutlak (*membuktikan, menjamin, menyebabkan*) tidak ditandai meskipun hanya didukung bukti pilot atau observasional tanpa kualifikasi (*qualifier*).

---

## 3. File dan Fungsi yang Diubah

| Berkas | Fungsi / Komponen | Perubahan Teknis |
|---|---|---|
| `src/schemas/claim.py` | `SemanticDecision`, `SemanticReview`, `Claim` | Menambahkan enum `SemanticDecision` (`SUPPORTED`, `PARTIALLY_SUPPORTED`, `REFUTED`, `NEEDS_HUMAN_REVIEW`, `NOT_RUN`) dan model `SemanticReview` (memuat `claim_id`, `decision`, `reason`, `evidence_id`, `source_id`, `evidence_excerpt`, `location`, `reviewer`, `method`, `timestamp`). Menambahkan atribut opsional `semantic_review` pada `Claim`. |
| `src/agents/audit.py` | `FactAuditRequest`, `FactAuditResponse`, `FactAuditAgent._execute` | Memperluas request dengan `evidence`, `sources`, dan `semantic_reviews`. Memisahkan hasil menjadi `structural_passed`, `semantic_passed`, dan `passed` (`passed = structural_passed and semantic_passed`). Memvalidasi kelengkapan evidence aktual, lokasi presisi, verifikasi sumber, deteksi kata overclaiming (`STRONG_CLAIM_TERMS`), deteksi bukti awal (`PRELIMINARY_EVIDENCE_TERMS`), dan keselarasan kutipan semantik. |
| `src/workflows/orchestrator.py` | `OrchestratorRequest`, `OrchestratorAgent._execute` | Meneruskan `evidence`, `sources`, dan `semantic_reviews` ke `FactAuditAgent`. Memperbarui pesan penolakan agar menyertakan rincian alasan kegagalan audit fakta. |
| `src/workflows/academic.py` | `AcademicWritingRequest`, `AcademicWritingWorkflow._execute` | Meneruskan `semantic_reviews` dari request alur penulisan ke `OrchestratorRequest`. |
| `src/runtime/cli.py` | `_cmd_run_academic` | Membaca list `semantic_reviews` dari payload input JSON dan meneruskannya ke `AcademicWritingRequest`. |
| `src/runtime/monitor.py` | `do_POST` | Membaca list `semantic_reviews` dari payload POST endpoint `/api/run-academic`. |
| `src/tools/citation_manager.py` | `detect_orphan_author_year_citations` | Memperbaiki pencocokan lead author dua penulis (`Author1 & Author2, Year`) pada tabel `known` agar pemindaian orphan sitasi presisi untuk multi-penulis. |
| `input_edjust_mini.json` | Payload data Edjust | Menambahkan 3 rekaman `semantic_reviews` terverifikasi oleh `antigravity_agent` untuk klaim Edjust mini. |
| `tests/test_semantic_fact_audit_regression.py` | Test suite baru | 10 unit regression test offline yang memverifikasi 9 skenario wajib ditambah pengujian overclaim. |

---

## 4. Perilaku Sebelum dan Sesudah

| Aspek | Sebelum Perbaikan | Sesudah Perbaikan |
|---|---|---|
| **Pemeriksaan Makna Semantik** | Tidak ada. Hanya mencocokkan apakah string ID evidence ada di list `supporting_evidence`. | Wajib. Klaim penting diverifikasi kesesuaian maknanya dengan evidence melalui rekaman `SemanticReview`. |
| **Klaim Penting Tanpa Review** | Lolos otomatis jika status `SUPPORTED`. | Ditolak aman (`semantic_status="NOT_RUN"`, `passed=False`, `docx_generation` diblokir). |
| **Pemisahan Status Audit** | Hanya field tunggal `passed: bool`. | Dipisahkan transparan: `structural_passed: bool`, `semantic_passed: bool`, dan `passed = structural_passed and semantic_passed`. |
| **Klaim Parsial (`PARTIALLY_SUPPORTED`)** | Lolos sebagai klaim penuh tanpa syarat. | Ditolak jika tidak disertai `qualifier` pembatas ruang lingkup klaim. |
| **Klaim Ditolak (`REFUTED`)** | Lolos jika status `is_writable` tidak dimodifikasi. | Ditolak seketika oleh audit fakta dengan pencatatan alasan penolakan. |
| **Klaim Berlebihan (*Overclaim*)** | Tidak terdeteksi. Kata mutlak seperti *membuktikan* atau *menjamin* lolos bebas. | Ditandai oleh `overclaim_findings` dan ditolak jika hanya bersumber dari bukti pilot/observasional tanpa qualifier. |
| **Lokasi Bukti Ilmiah** | Lokasi bukti boleh kosong. | Diwajibkan memiliki lokasi yang dapat diverifikasi (`locator`, `page`, atau `section`) untuk klaim penting/sebab-akibat. |
| **Metadata Sumber Tidak Lengkap** | Tidak dicatat dalam audit fakta. | Dicatat dalam `bibliographic_findings` dengan penanda `[sumber belum lengkap]`. |

---

## 5. Test yang Ditambahkan

Sepuluh regression test offline ditambahkan di `tests/test_semantic_fact_audit_regression.py`:

1. `test_claim_supported_status_but_evidence_mismatch_rejected`: Menguji klaim status `SUPPORTED` tetapi isi evidence membahas hal lain; semantic review menandai `REFUTED` ➔ Ditolak aman (`passed=False`).
2. `test_important_claim_without_semantic_review_final_rejected`: Menguji klaim penting tanpa rekaman penilaian semantik ➔ Dokumen `final.docx` ditolak/diblokir, hanya draft dan laporan kegagalan yang dihasilkan.
3. `test_claim_with_fake_evidence_id_rejected`: Menguji klaim dengan ID evidence fiktif ➔ Ditolak oleh gate/audit fakta.
4. `test_refuted_claim_rejected`: Menguji klaim berstatus `REFUTED` ➔ Ditolak aman.
5. `test_partially_supported_claim_without_qualifier_rejected`: Menguji klaim `PARTIALLY_SUPPORTED` tanpa qualifier pembatas ➔ Ditolak.
6. `test_fully_supported_claim_with_valid_source_evidence_location_and_review_passes`: Menguji klaim yang didukung penuh oleh sumber terverifikasi, evidence dengan lokasi presisi, dan semantic review `SUPPORTED` ➔ Lolos (`passed=True`, `structural_passed=True`, `semantic_passed=True`, dokumen Word terbuat).
7. `test_incomplete_author_metadata_marked_sumber_belum_lengkap`: Menguji sumber tanpa penulis lengkap ➔ Dicatat dalam temuan bibliografi dengan marker `[sumber belum lengkap]`.
8. `test_output_containing_internal_tokens_rejected`: Menguji draft mengandung token `turn0search1`, `view5filecite2`, `【turn2search0】`, `filecite` ➔ Ditolak oleh output scan.
9. `test_safe_legacy_workflow_operates_according_to_contract`: Menguji alur kerja klaim aman berbobot sedang (`MEDIUM`) ➔ Berjalan normal sesuai kontrak alur kerja repositori.
10. `test_overclaim_with_preliminary_evidence_rejected`: Menguji klaim berkosakata kuat (*membuktikan*, *menjamin*) yang hanya didukung studi pilot observasional tanpa qualifier ➔ Ditolak dalam `overclaim_findings`.

---

## 6. Hasil Health Check dan Seluruh Test

### A. Health Check Repositori (`python -m src check`)
```text
[OK] System health check passed
   SYSTEM_ROOT: C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH\DATA BASE
   WORKSPACE_ROOT: C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH
   Spec version: 1.0
   Build phase: 18
Exit Code: 0
```

### B. Fast Unit & Regression Tests (`python -m pytest -q --tb=short`)
```text
........................................................................ [ 21%]
........................................................................ [ 43%]
........................................................................ [ 65%]
........................................................................ [ 87%]
...........................................                              [100%]
331 passed, 10 deselected in 6.73s
Exit Code: 0
```
*Hasil:* **331 passed** (bertambah 10 test baru dari 321 test sebelumnya), 0 failed.

### C. Live Integration Tests (`python -m pytest -m integration -q --tb=short`)
```text
..........                                                               [100%]
10 passed, 331 deselected in 21.57s
Exit Code: 0
```
*Hasil:* **10 passed**, 0 failed.

---

## 7. Hasil Empat Probe Workflow

Pengujian probe dilakukan secara langsung menggunakan skrip verifikasi `cache/run_4_probes.py`:

| Probe | Deskripsi Skenario | Hasil Alur Kerja | Status DOCX Final | Hasil Audit Fakta | Alasan Penolakan / Status |
|---|---|:---:|:---:|:---:|---|
| **Probe 1 (Valid)** | Klaim didukung bukti empiris abstrak Vaswani (2017) dengan lokasi halaman dan semantic review `SUPPORTED`. | `success: True` | **DIBUAT** | `passed: True`<br>`structural: True`<br>`semantic: True` | Lolos seluruh kriteria integritas. |
| **Probe 2 (Overclaim)** | Klaim *"Metode ini menjamin penghapusan stres secara total dan membuktikan kesembuhan permanen"* pada bukti pilot lemah tanpa qualifier. | `success: False` | **DITOLAK** | `passed: False`<br>`semantic: False` | `strong claim ('membuktikan') supported only by preliminary evidence without qualifier`<br>`strong claim ('menjamin') supported only by preliminary evidence without qualifier` |
| **Probe 3 (No Review)** | Klaim penting berstatus `SUPPORTED` namun tidak memiliki rekaman penilaian semantik dari AI agent pemeriksa. | `success: False` | **DITOLAK** | `passed: False`<br>`semantic: False` | `important claim has no semantic review record` |
| **Probe 4 (Mismatch)** | Klaim gawai dan memori kerja, namun evidence membahas konsumsi energi listrik industri (review: `REFUTED`). | `success: False` | **DITOLAK** | `passed: False`<br>`semantic: False` | `claim is REFUTED by semantic review: Isi evidence membahas energi listrik industri, sama sekali tidak memuat data gawai atau memori kerja.` |
| **Probe Gabungan** | Seluruh 4 klaim diajukan bersamaan dalam satu outline naskah. | `success: False` | **DITOLAK** | `passed: False`<br>`unsupported_claims: 3` | Hanya klaim valid yang berstatus `PASSED`. Ketiga klaim cacat ditolak dan naskah `final.docx` dicegah dari penerbitan. |

**Kesimpulan Bukti Empiris:** Terbukti secara konsisten bahwa **hanya klaim valid yang dapat mencapai status final**.

---

## 8. Contoh Ringkas `fact_audit.json`

Diambil dari hasil eksekusi nyata pada probe gabungan:
```json
{
  "passed": false,
  "structural_passed": true,
  "semantic_passed": false,
  "unsupported_claims": [
    "clm_mismatch",
    "clm_no_review",
    "clm_overclaim"
  ],
  "rejection_reasons": [
    "claim clm_overclaim: strong claim ('membuktikan') supported only by preliminary/observational evidence without qualifier",
    "claim clm_overclaim: strong claim ('menjamin') supported only by preliminary/observational evidence without qualifier",
    "claim clm_no_review: important claim has no semantic review record",
    "claim clm_mismatch: claim is REFUTED by semantic review: Isi evidence membahas energi listrik industri, sama sekali tidak memuat data gawai atau memori kerja."
  ],
  "assessments": [
    {
      "claim_id": "clm_valid",
      "claim_text": "Model transformer memproses ketergantungan urutan data tanpa jaringan rekuren.",
      "importance": "HIGH",
      "structural_status": "PASSED",
      "semantic_status": "PASSED",
      "decision": "SUPPORTED",
      "reason": "Makna klaim bersesuaian dengan temuan empiris dalam abstrak sumber Vaswani (2017).",
      "evidence_id": "evd_valid",
      "evidence_text": "Model transformer memproses ketergantungan urutan data tanpa jaringan rekuren.",
      "evidence_location": "p. 6000",
      "source_id": "src_attention",
      "reviewer": "antigravity_agent",
      "method": "semantic_evaluation",
      "timestamp": "2026-09-12T08:45:32.283741+00:00",
      "rejection_reasons": []
    },
    {
      "claim_id": "clm_overclaim",
      "claim_text": "Metode ini menjamin penghapusan stres secara total dan membuktikan kesembuhan permanen.",
      "importance": "HIGH",
      "structural_status": "PASSED",
      "semantic_status": "FAILED",
      "decision": "SUPPORTED",
      "reason": "Evaluasi pilot.",
      "evidence_id": "evd_pilot",
      "evidence_text": "Penelitian observasional pilot pada sampel kecil menunjukkan indikasi awal penurunan stres.",
      "evidence_location": "abstract",
      "source_id": "src_attention",
      "reviewer": "antigravity_agent",
      "method": "semantic_evaluation",
      "timestamp": "2026-09-12T08:45:32.386379+00:00",
      "rejection_reasons": [
        "strong claim ('membuktikan') supported only by preliminary/observational evidence without qualifier",
        "strong claim ('menjamin') supported only by preliminary/observational evidence without qualifier"
      ]
    },
    {
      "claim_id": "clm_no_review",
      "claim_text": "Intervensi edukasi hukum meningkatkan pemahaman hak anak secara terukur.",
      "importance": "HIGH",
      "structural_status": "PASSED",
      "semantic_status": "NOT_RUN",
      "decision": "NOT_RUN",
      "reason": "Klaim penting belum memiliki rekaman penilaian semantik dari AI agent pemeriksa",
      "evidence_id": "evd_valid_3",
      "evidence_text": "Intervensi edukasi hukum meningkatkan pemahaman hak anak secara terukur.",
      "evidence_location": "abstract",
      "source_id": "src_attention",
      "reviewer": null,
      "method": null,
      "timestamp": null,
      "rejection_reasons": [
        "important claim has no semantic review record"
      ]
    },
    {
      "claim_id": "clm_mismatch",
      "claim_text": "Penggunaan gawai berlebih menyebabkan penurunan memori kerja jangka pendek secara langsung.",
      "importance": "HIGH",
      "structural_status": "PASSED",
      "semantic_status": "REFUTED",
      "decision": "REFUTED",
      "reason": "Isi evidence membahas energi listrik industri, sama sekali tidak memuat data gawai atau memori kerja.",
      "evidence_id": "evd_irrelevant",
      "evidence_text": "Pertumbuhan konsumsi energi listrik pada sektor industri manufaktur di Asia Tenggara.",
      "evidence_location": "abstract",
      "source_id": "src_attention",
      "reviewer": "antigravity_agent",
      "method": "semantic_evaluation",
      "timestamp": "2026-09-12T08:45:32.529179+00:00",
      "rejection_reasons": [
        "claim is REFUTED by semantic review: Isi evidence membahas energi listrik industri, sama sekali tidak memuat data gawai atau memori kerja."
      ]
    }
  ],
  "bibliographic_findings": [],
  "overclaim_findings": [
    {
      "claim_id": "clm_overclaim",
      "term": "membuktikan",
      "reason": "preliminary evidence without qualifier"
    },
    {
      "claim_id": "clm_overclaim",
      "term": "menjamin",
      "reason": "preliminary evidence without qualifier"
    }
  ]
}
```

---

## 9. Keterbatasan yang Masih Tersisa

Secara jujur dan transparan, proyek ini **tidak diklaim 100% anti-halusinasi**. Masih terdapat batasan nyata:
1. **Ketergantungan pada Agen Penilai Semantik:** Kode Python bertindak sebagai gatekeeper, validator skema, dan pemeriksa konsistensi referensial. Pemahaman makna mendalam teks tetap bergantung pada integritas penalaran agen pemeriksa (*Antigravity/AI agent*). Jika agen pemeriksa salah menilai kutipan sebagai `SUPPORTED` dan kutipan tersebut memiliki irisan kata yang cukup, Python validator akan meloloskannya.
2. **Keterbatasan Heuristik Overclaiming:** Pendeteksian klaim berlebihan menggunakan daftar frasa kunci leksikal (*STRONG_CLAIM_TERMS*) dan indikator bukti awal (*PRELIMINARY_EVIDENCE_TERMS*). Heuristik kata ini bukan pengganti metodologi telaah kritis (*critical appraisal*) manusia terhadap desain studi penelitian (seperti RCT vs kohort retrospektif).
3. **Pemeriksaan Manusia Tetap Wajib:** Sistem ini meminimalkan risiko halusinasi faktual pada lapisan automasi, namun verifikasi akhir oleh peneliti manusia sebelum publikasi tetap tidak dapat dihilangkan.

---

## 10. Daftar File yang Belum Di-Commit (Working Tree)

Sesuai instruksi batasan *"Jangan commit, push, membuat PR, atau menghapus file"*, seluruh perubahan berikut tetap berada dalam working tree:

### File Dimodifikasi:
1. `input_edjust_mini.json`
2. `src/agents/audit.py`
3. `src/runtime/cli.py`
4. `src/runtime/monitor.py`
5. `src/schemas/claim.py`
6. `src/tools/citation_manager.py`
7. `src/workflows/academic.py`
8. `src/workflows/orchestrator.py`

### File Baru (Untracked):
1. `docs/LAPORAN_PENGUATAN_ANTI_HALUSINASI_FACT_AUDIT_2026-09-12.md`
2. `tests/test_semantic_fact_audit_regression.py`
