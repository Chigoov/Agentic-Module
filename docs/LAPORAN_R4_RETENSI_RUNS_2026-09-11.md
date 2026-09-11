# LAPORAN R4 LANJUTAN: RETENSI RUNS, PORTABLE SUMMARIES, & PERAPIAN UX GATE

**Tanggal:** 11 September 2026  
**Repositori:** `C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH\DATA BASE`  
**Status Integrasi:** **SELESAI, TERUJI REGRESI PENUH, & TER-PUSH KE GITHUB**  

---

## 1. File yang Diubah

| Berkas | Status | Rincian Perubahan |
|---|:---:|---|
| `src/workflows/audit_trail.py` | **Diubah** | Menambahkan `_compute_relpath` dan field ringkasan portable (`draft_relpath`, `docx_relpath`, `citation_audit_relpath`, `fact_audit_relpath`) relatif terhadap `project.directory`. Mempertahankan path absolut lama. |
| `src/agents/base.py` | **Diubah** | Menangkap `HumanReviewRequired` pada `BaseAgent.execute` secara terstruktur; mengisi `needs_human_review=True`, `review_prompt`, dan pesan error bersih tanpa frasa `"unhandled exception"`. |
| `src/workflows/orchestrator.py` | **Diubah** | Mengisi `needs_human_review` dan `review_prompt` di `OrchestratorAgent._make_error_response` agar eskalasi review diteruskan utuh. |
| `src/workflows/academic.py` | **Diubah** | Meneruskan `needs_human_review` dan `review_prompt` pada `AcademicWritingResponse` saat orchestrator atau gate menolak payload, serta mencatat error bersih di `run_summary.json`. |
| `src/runtime/cli.py` | **Diubah** | Menambahkan opsi `--prune` dan `--keep <N>` pada sub-command `runs`. Mengurutkan run dari terbaru ke terlama, memvalidasi `--keep` positif, menghapus folder run lama via path guard `ensure_within`, dan melaporkan JSON terstruktur. |
| `tests/test_audit_trail_regression.py` | **Diubah** | Menambahkan 3 unit regression test: (1) `test_audit_trail_portable_relpaths`; (2) `test_gate_error_clean_ux_without_unhandled_exception`; (3) `test_cli_runs_prune_behavior` (uji prune keep 2 dari 5 run, no-prune tidak menghapus apa pun, dan keep 0 ditolak). |
| `AGENTS.md` | **Diubah** | Mendokumentasikan perintah `runs`, `runs --prune --keep`, dan peringatan review manusia sebelum submit/publikasi. |
| `docs/CARA_PAKAI_UNTUK_AI_AGENT.md` | **Diubah** | Menambahkan panduan ringkas audit trail, inspeksi runs, retensi prune, dan peringatan integritas manusia. |

---

## 2. Perilaku CLI Baru

Sub-command `python -m src runs` kini mendukung 3 mode penggunaan:

1. **Daftar Riwayat Run (Default):**
   ```powershell
   python -m src runs --input-json input_edjust_mini.json
   ```
   Menampilkan daftar seluruh run yang tersimpan, diurutkan dari yang terbaru, beserta metadata status dan path luaran.

2. **Inspeksi Detail Satu Run (`--run-id`):**
   ```powershell
   python -m src runs --input-json input_edjust_mini.json --run-id <run_id>
   ```
   Menampilkan rekaman utuh `run_summary.json` dari run yang dipilih.

3. **Pemangkasan & Retensi Run Lama (`--prune --keep <N>`):**
   ```powershell
   python -m src runs --input-json input_edjust_mini.json --prune --keep 20
   ```
   - Mengurutkan run dari terbaru ke terlama.
   - Mempertahankan $N$ run terbaru dan menghapus run lama sisanya secara aman.
   - Menggunakan path guard `ensure_within` sehingga tidak dapat menghapus file di luar folder `runs/`.
   - Menolak `--keep 0` atau angka negatif.
   - Tanpa `--prune`, tidak ada folder yang dihapus.

---

## 3. Contoh Output `runs --prune --keep`

Hasil eksekusi nyata pada pengujian prune (contoh dari test fixture):
```json
{
  "success": true,
  "project_directory": "C:\\Users\\...\\academic_project",
  "total_before": 5,
  "kept": 2,
  "deleted": 3,
  "deleted_run_ids": [
    "run_20260901T000001Z_00000001",
    "run_20260901T000002Z_00000002",
    "run_20260901T000003Z_00000003"
  ]
}
```

Bila `--keep 0` atau parameter tidak valid diberikan saat `--prune`:
```json
{
  "success": false,
  "error": "--keep must be a positive integer when --prune is specified"
}
```

---

## 4. Hasil Test Suite

* **Health Check Sistem (`python -m src check`):**
  ```text
  [OK] System health check passed
     SYSTEM_ROOT: C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH\DATA BASE
     WORKSPACE_ROOT: C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH
     Spec version: 1.0
     Build phase: 18
  Exit Code: 0
  ```

* **Pytest Regresi (`python -m pytest -q --tb=short`):**
  ```text
  314 passed, 10 deselected in 5.13s
  Exit Code: 0
  ```
  *(100% lulus, 314 tests passed tanpa ada error).*

---

## 5. Hasil Rerun Edjust Mini

Perintah eksekusi:
```powershell
python -m src run-academic --input-json input_edjust_mini.json
```

**Verifikasi `run_summary.json` Terbaru (`run_20260911T040115Z_e3655c71`):**
```json
{
  "run_id": "run_20260911T040115Z_e3655c71",
  "started_at": "2026-09-11T04:01:15.716047+00:00",
  "finished_at": "2026-09-11T04:01:15.785251+00:00",
  "success": true,
  "command": "run-academic",
  "input_path": "input_edjust_mini.json",
  "draft_path": "c:\\Users\\HYPE AMD\\Downloads\\VIBE CODING\\AUTONOMI AGENTIC ILMIAH\\TUGAS 1\\edjust-mini\\draft.md",
  "draft_relpath": "draft.md",
  "docx_path": "c:\\Users\\HYPE AMD\\Downloads\\VIBE CODING\\AUTONOMI AGENTIC ILMIAH\\TUGAS 1\\edjust-mini\\final.docx",
  "docx_relpath": "final.docx",
  "citation_audit_path": "c:\\Users\\HYPE AMD\\Downloads\\VIBE CODING\\AUTONOMI AGENTIC ILMIAH\\TUGAS 1\\edjust-mini\\citation_audit.json",
  "citation_audit_relpath": "citation_audit.json",
  "fact_audit_path": "c:\\Users\\HYPE AMD\\Downloads\\VIBE CODING\\AUTONOMI AGENTIC ILMIAH\\TUGAS 1\\edjust-mini\\fact_audit.json",
  "fact_audit_relpath": "fact_audit.json",
  "stages": [
    "synthesis",
    "outline",
    "writing",
    "citation_audit",
    "fact_audit",
    "docx_generation"
  ],
  "error_message": null
}
```

* **Portabilitas:** Relpath terisi benar (`draft.md`, `final.docx`, `citation_audit.json`, `fact_audit.json`).
* **Integritas Akademik:** `citation_audit.json` dan `fact_audit.json` tetap `"passed": true`.
* **Zero Token Leak:** Bebas dari seluruh token internal LLM (`turn...`, `view0`, `search0`, `filecite`, dll.).

---

## 6. Contoh Respons Error Gate yang Sudah Dirapikan

Saat input memuat klaim dengan bukti tidak terdaftar (evidence palsu), respons CLI kini bersih dan informatif:
```json
{
  "success": false,
  "needs_human_review": true,
  "review_prompt": "ISSUE: Academic integrity gate rejected the payload\nCONTEXT: pre-writing integrity check\nWHY IT MATTERS: Unverifiable claims/evidence/sources must not reach an academic output; status flags alone are not proof\nOPTIONS:\n  - Fix the IDs and re-run with resolvable references\n  - Verify the cited sources before citing them\n  - Disclose conflicts via a qualifier or contradicting evidence\nRECOMMENDED ACTION: Fix the payload, then run again",
  "output": null,
  "error_message": "Academic integrity gate rejected the payload (violations=['claim clm_1 references nonexistent supporting evidence evd_nonexistent'])",
  "metadata": {},
  "stages": [],
  "draft_path": null,
  "docx_path": null,
  "run_id": "run_20260911T040500Z_abcdef12",
  "run_dir": "C:\\...\\academic_project\\runs\\run_20260911T040500Z_abcdef12"
}
```
* Frasa `"unhandled exception"` telah dieliminasi.
* `needs_human_review: true` dan `review_prompt` tersaji lengkap.
* Tidak ada dokumen `final.docx` yang tercipta.
* `run_summary.json` tetap tersimpan rapi untuk bukti diagnostik.

---

## 7. Risiko Tersisa

1. **Pembersihan Berskala Besar:** Eksekusi `--prune` berjalan deterministik menghapus folder run terlama; pengguna harus memastikan nilai `--keep` mencukupi sebelum memangkas.
2. **Ketergantungan Eksternal saat Live Search:** Pencarian live (non-mock) memerlukan akses jaringan ke provider publik (Crossref/OpenAlex/Semantic Scholar).

---

## 8. Rekomendasi Langkah Berikutnya

1. **Export Deliverable Packager (`python -m src export-bundle`):**
   Membuat berkas arsip `.zip` mandiri berisi `final.docx`, `draft.md`, laporan audit sitasi & fakta, serta `run_summary.json` portable agar naskah hasil riset mudah dikirimkan kepada reviewer atau institusi.
2. **Multi-Claim Paragraph Synthesis:**
   Membangun perangkai transisi antar-klaim dalam satu heading outline agar draft terbentuk sebagai paragraf mengalir alami, bukan kalimat-kalimat terpisah, tetap dengan jaminan zero-hallucination.
3. **Penyusunan Naskah Multi-Level (`level: 3`):**
   Mendukung hierarki Bab ➔ Sub-Bab ➔ Poin Pembahasan pada outline untuk naskah penelitian berdimensi panjang.
