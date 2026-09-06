# BUILD PLAN
## AUTONOMI AGENTIC ILMIAH v1.0

Roadmap eksekusi pengembangan sistem, **disinkronkan** dengan
`Master_Task_Setiap_Fase_AUTONOMI_AGENTIC_ILMIAH.docx` (2026-09-05).

Dokumen master tersebut **merombak penomoran fase lama** dan menambah fase
baru (Retrieval full-text, Research Agents, Orchestrator, Model Routing aktif,
Optimization). Tabel di bawah adalah **satu-satunya acuan status roadmap**;
`build_phase` di config/kode hanya marker ringkas fase roadmap terakhir yang
selesai.

The system is built incrementally.

## STATUS LEGEND

- ✅ `SELESAI` — sudah dibangun & diuji
- 🔶 `SEBAGIAN` — sebagian dikerjakan, sisanya masih terbuka
- ▶ `NEXT` — fase yang dikerjakan berikutnya
- ⬜ `RENCANA` — belum dikerjakan

## ROADMAP & STATUS

| Fase | Nama Fase | Task Utama | Output / Deliverable | Status |
|---|---|---|---|---|
| 0 | Workspace Discovery | Periksa workspace, environment, Python, Node.js, Git, Publish or Perish, folder, dan file yang sudah ada. | Laporan environment, system root, tool availability, dependency status. | ✅ SELESAI |
| 1 | Foundation | Bangun path manager, config loader, logging, storage, project manager, schema dasar, base agent/tool, bootstrap, dan test. | Core foundation, schema, config, bootstrap, test suite. | ✅ SELESAI |
| 2 | Publish or Perish Integration | Integrasikan PoP melalui adapter/tool, jalankan pencarian nyata, parse output, normalisasi menjadi Source. | PoP adapter, parser, normalized Source, integration test. | ✅ SELESAI |
| 3 | Research Discovery Tools | Tambahkan Crossref, OpenAlex, PubMed, Semantic Scholar/penyedia lain, lalu normalisasi dan deduplikasi hasil. | Research tools, source mapper, deduplication, candidates.jsonl. | ✅ SELESAI |
| 3A | Architecture Stabilization | Audit repository, rapikan layering, hapus abstraksi yang belum digunakan, sinkronkan dokumentasi, perbaiki bug struktur/path. | Repository audit, refactor aman, regression tests, dokumentasi sinkron. | ✅ SELESAI |
| 3B | Context Intelligence | Bangun TaskClassifier, ContextLoader, ContextPriority, ContextBudget, ContextManifest; verifikasi layer benar-benar dipakai di execution boundary. | Context layer + dry-run integration gate. | ✅ SELESAI |
| 4 | Verification Engine | Verifikasi keberadaan publikasi, metadata, DOI, publisher/venue, dan buat VerificationReport. | VerificationReport, verified_sources, DOI/metadata checks, integration tests. | ✅ SELESAI |
| 5 | Evidence + Claim Engine | Bangun Claim Registry, Evidence Registry, relasi supports/partially/contradicts/irrelevant, confidence, conflict detection. | claims.json, evidence.jsonl, claim-evidence mapping, conflict status. | ✅ SELESAI |
| 6 | Retrieval + Evidence Extraction | Ambil full text/PDF/HTML/abstract yang tersedia, parse isi, ekstrak evidence beserta lokasi halaman/section. | Source documents, parsed text, evidence dengan page/section/location. | ✅ SELESAI |
| 7 | Research Agents | Bangun TaskAnalyzerAgent, ResearchPlannerAgent, DiscoveryAgent, VerificationAgent, RetrievalAgent, EvidenceAgent, ClaimAgent. | Concrete research agents dengan input/output contract dan tests. | ✅ SELESAI |
| 8 | Orchestrator | Bangun pengatur alur yang menghubungkan agent dan tool, termasuk retry, failure loop, dan human review gate. | Workflow engine/orchestrator, retry policy, review gate. | ✅ SELESAI |
| 9 | Model Provider & Routing | Aktifkan ModelRouter dan provider abstraction; dukung 9Router sebagai salah satu provider (bukan dependency wajib); fallback + telemetry token. | Provider interfaces, routing policy, fallback, token/cost telemetry. | ✅ SELESAI |
| 10 | Synthesis + Outline | Kelompokkan evidence, lihat kesepakatan/perbedaan antar studi, buat sintesis dan outline. | Synthesis artifact, conflict summary, outline.json. | ✅ SELESAI |
| 11 | Writing Engine | Bangun writer yang hanya menulis berdasarkan approved claims, verified evidence, dan outline. | draft.md / structured draft, citation placeholders/links. | ✅ SELESAI |
| 12 | Citation + Fact Audit | Jalankan CitationAudit dan FactAudit pada draft. | citation_audit.json, fact_audit.json, revision loop. | ✅ SELESAI |
| 13 | DOCX Generation | Konversi draft yang lolos audit menjadi dokumen Word dengan format sitasi yang dapat dikonfigurasi. | final.docx, format APA 7 default + style lain. | ✅ SELESAI |
| 14 | Academic Writing Mode | Satukan pipeline ringan untuk tugas sehari-hari (makalah, artikel, PKM, proposal). | End-to-end Academic Writing workflow. | ✅ SELESAI |
| 15 | Deep Research Mode | Aktifkan multi-query, multi-source, dedup, deeper verification, full-text, conflict handling, synthesis mendalam. | End-to-end Deep Research workflow. | ✅ SELESAI |
| 16 | End-to-End Validation | Uji seluruh sistem dengan kasus nyata (sederhana, teori klasik, literatur terbaru, DOI palsu, evidence bertentangan). | E2E test reports, failure-case evidence, readiness decision. | ✅ SELESAI |
| 17 | Optimization | Optimalkan token, context, model routing, caching, concurrency, search efficiency, reliability, cost. | Performance metrics, token telemetry, routing/budget tuning, optimization report. | ✅ SELESAI |

> [!NOTE]
> **Penomoran ulang.** Synthesis/Writing dulu bernomor 6 (lama) kini 10–11; Audit dulu 7 kini 12; DOCX dulu 8 kini 13. Fase 6–9 (Retrieval, Agents, Orchestrator, Model Routing) adalah fase **baru** yang sebelumnya tidak eksplisit.
>
> **Urutan sudah diselaraskan.** Fase 7–17 sekarang SELESAI dalam scope minimal yang sudah diuji.

---

## ATURAN WAJIB SETIAP FASE

Setiap fase mengikuti alur: **Architecture Review → Pre-Implementation Gate → Implementation Plan → Implementasi → Tests → Integration Test (jika relevan) → Import Check → Bootstrap → Architecture Audit → Dokumentasi → Report → STOP**.

Fase berikutnya **hanya boleh dimulai** setelah fase sebelumnya lolos acceptance criteria. Tujuan utama tetap **kualitas dan keterlacakan ilmiah**, bukan banyaknya fitur atau banyaknya kode.

---

## DEVELOPMENT RULE

Complete and test one phase before relying on it in a later phase.

Do not rebuild completed phases without cause.

Every phase should produce:
- implementation;
- tests;
- documentation;
- status report;
- known limitations;
- next action.
