# GOAL PLAN FASE 7-13
## AUTONOMI AGENTIC ILMIAH v1.0

> **Status awal:** Fase 0-6 sudah selesai. Fase 10-11 sudah selesai lebih awal
> dari urutan roadmap baru. Plan ini menjaga timeline agar pengembangan berikutnya
> tetap bergerak dari Fase 7 sampai Fase 13 tanpa membangun fitur di luar fase.

## Ringkasan Timeline

| Fase | Goal Utama | Status Target |
|---|---|---|
| 7 | Research Agents | Agent konkret untuk analisis, planning, discovery, verification, retrieval, evidence, dan claim |
| 8 | Orchestrator | Alur kerja end-to-end terkontrol dengan retry dan human review gate |
| 9 | Model Provider & Routing | Routing model aktif, fallback, dan telemetry token/cost |
| 10 | Synthesis + Outline | Sudah selesai; sinkronkan ke orchestrator bila perlu |
| 11 | Writing Engine | Sudah selesai; sinkronkan ke orchestrator bila perlu |
| 12 | Citation + Fact Audit | Audit draft dan loop revisi |
| 13 | DOCX Generation | Dokumen Word final setelah audit lolos |

---

## Fase 7 — Research Agents

### Goal
Membuat agent konkret yang membungkus tool dan logika deterministik yang sudah ada,
tanpa membuat orchestrator penuh.

### Scope
- `TaskAnalyzerAgent`
- `ResearchPlannerAgent`
- `DiscoveryAgent`
- `VerificationAgent`
- `RetrievalAgent`
- `EvidenceAgent`
- `ClaimAgent`

### Output
- Agent request/response contract.
- Agent menjalankan satu tanggung jawab jelas per file.
- Unit test untuk setiap agent.
- Laporan Fase 7.

### Acceptance Criteria
- Agent tidak menyimpan logika provider langsung.
- Agent memakai tool/schema/registry yang sudah ada.
- Agent gagal secara eksplisit jika capability belum tersedia.
- Fast test suite hijau.
- Bootstrap OK.

### Batasan
- Jangan membangun orchestrator global.
- Jangan mengaktifkan model provider sebelum Fase 9.

---

## Fase 8 — Orchestrator

### Goal
Menghubungkan agent menjadi workflow yang bisa berjalan berurutan dan terkontrol.

### Scope
- Workflow stage: plan, discover, verify, retrieve, extract, claim-check,
  synthesize, outline, write, audit.
- Retry policy terbatas.
- Human review gate.
- Project artifact checks.

### Output
- Orchestrator workflow.
- State transition tests.
- Failure-path tests.
- Laporan Fase 8.

### Acceptance Criteria
- Tidak ada silent success.
- Failure kembali ke stage yang benar.
- Project artifact ditulis di folder project, bukan `DATA BASE/`.
- Fast test suite hijau.
- Bootstrap OK.

### Batasan
- Jangan membuat UI.
- Jangan membuat DOCX output sebelum Fase 13.

---

## Fase 9 — Model Provider & Routing

### Goal
Mengaktifkan `ModelRouter` agar agent bisa meminta capability model tanpa
terikat pada satu provider.

### Scope
- Provider config.
- Capability map: planning, research, reasoning, writing, auditing.
- Fallback terkontrol.
- Token/cost telemetry minimal.
- 9Router optional sebagai provider, bukan dependency wajib.

### Output
- Provider abstraction aktif.
- Routing policy.
- Connectivity test.
- Telemetry artifact sederhana.
- Laporan Fase 9.

### Acceptance Criteria
- Provider tidak hardcoded di agent.
- Status tetap `PENDING_CONFIGURATION` jika credential tidak ada.
- Tidak klaim provider `VERIFIED` tanpa real call.
- Integration test diberi marker `integration`.
- Fast test suite tetap hijau tanpa credential.

### Batasan
- Jangan menaruh API key di repo.
- Jangan membuat fallback yang mengarang hasil.

---

## Fase 10 — Synthesis + Outline

### Goal
Memakai implementasi yang sudah selesai sebagai stage resmi di orchestrator.

### Scope
- Review ulang `SynthesisAgent` dan `OutlineAgent`.
- Pastikan input dari Fase 8/9 cocok.
- Tambah adapter kecil hanya jika dibutuhkan.

### Output
- Integration point ke orchestrator.
- Regression test.
- Catatan sinkronisasi Fase 10.

### Acceptance Criteria
- Tidak rewrite agent yang sudah hijau.
- Klaim non-writable tetap dieksklusi.
- Konflik tetap diungkap.
- Fast test suite hijau.

### Batasan
- Jangan memperindah prosa di fase ini.

---

## Fase 11 — Writing Engine

### Goal
Memakai `WriterAgent` yang sudah selesai sebagai stage resmi setelah outline.

### Scope
- Hubungkan writer ke orchestrator.
- Pastikan writer menerima outline, claims, evidence, dan sources dari artifact nyata.
- Simpan `draft.md`.

### Output
- Writer stage integration.
- Draft artifact.
- Regression test.
- Catatan sinkronisasi Fase 11.

### Acceptance Criteria
- Writer hanya menulis klaim writable.
- Citation pointer tidak orphan.
- Draft tersimpan di folder project.
- Fast test suite hijau.

### Batasan
- Jangan finalisasi dokumen sebelum audit Fase 12.

---

## Fase 12 — Citation + Fact Audit

### Goal
Memeriksa draft sebelum finalisasi: sitasi harus valid dan klaim tidak boleh
lebih kuat daripada evidence.

### Scope
- `CitationAuditAgent`
- `FactAuditAgent`
- `citation_audit.json`
- `fact_audit.json`
- Revision loop minimal.

### Output
- Audit reports.
- Unsupported/orphan citation detection.
- Overclaim detection.
- Laporan Fase 12.

### Acceptance Criteria
- Audit failure tidak bisa menjadi success.
- Setiap citation key harus map ke source.
- Klaim penting harus punya evidence.
- Overclaim masuk revision/review.
- Fast test suite hijau.
- Bootstrap OK.

### Batasan
- Jangan generate DOCX jika audit belum pass.

---

## Fase 13 — DOCX Generation

### Goal
Mengubah draft yang sudah lolos audit menjadi `final.docx`.

### Scope
- DOCX generation tool.
- APA7 default.
- Struktur heading, body, quotation, dan references.
- Output validation.

### Output
- `final.docx`.
- Optional render/check artifact jika tersedia.
- Test generasi dokumen.
- Laporan Fase 13.

### Acceptance Criteria
- DOCX hanya dibuat setelah citation audit dan fact audit pass.
- Referensi berasal dari `ReferenceList`, bukan dibuat ulang bebas.
- File lama tidak dioverwrite diam-diam tanpa backup/versioning.
- Fast test suite hijau.
- Bootstrap OK.

### Batasan
- Jangan membuat template kompleks sebelum format dasar stabil.

---

## Urutan Eksekusi Wajib Per Fase

1. Architecture Review
2. Pre-Implementation Gate
3. Implementasi minimal sesuai scope
4. Unit tests
5. Integration tests jika relevan
6. Import check
7. Bootstrap check
8. Dokumentasi/laporan fase
9. STOP sebelum fase berikutnya

## Prinsip Penjaga Timeline

- Fase 7 tidak boleh diam-diam menjadi Fase 8.
- Fase 8 tidak boleh diam-diam mengaktifkan model routing.
- Fase 9 tidak boleh mengklaim provider verified tanpa real call.
- Fase 12 harus selesai sebelum Fase 13.
- Fase 13 hanya menghasilkan DOCX dari draft yang sudah lolos audit.
