Live progress: http://127.0.0.1:8000

# Catatan source per file

Baseline 99a71bb. Referensi A01–A18 menunjuk LAPORAN_AUDIT.md. Catatan statis bukan klaim bebas bug.

| File | Baris | Evaluasi |
|---|---:|---|
| `src/__init__.py` | 28 | Initializer/ekspor package; tidak menambahkan workflow domain tersendiri. Tidak ditemukan blocker khusus terpisah pada inspeksi ini. |
| `src/__main__.py` | 19 | Entry point CLI; bootstrap saat tanpa subcommand. Jalur command tidak otomatis menginisialisasi logging penuh. |
| `src/agents/__init__.py` | 26 | Initializer/ekspor package; tidak menambahkan workflow domain tersendiri. Tidak ditemukan blocker khusus terpisah pada inspeksi ini. |
| `src/agents/audit.py` | 74 | A01/A02: audit fakta hanya status; audit sitasi regex machine key, tidak memvalidasi body APA/provenance. |
| `src/agents/base.py` | 139 | Boundary exception dan respons terstruktur bermanfaat; bukan implementasi planning adaptif. Tidak mengirim event monitor; human-review exception tidak diterjemahkan menjadi review terstruktur. |
| `src/agents/claim_verification.py` | 160 | Evaluator dipakai terhadap registry, tetapi tidak dipanggil orchestrator. Sync menambahkan bookkeeping tanpa membersihkan tautan lama; status evidence tetap perlu provenance. |
| `src/agents/outline.py` | 105 | Mengelompokkan writable claim sesuai section_hint; mengembalikan DRAFT; tidak menyimpan outline.json. Komentar trailing/ordering tidak selalu sesuai insertion order. |
| `src/agents/research.py` | 224 | A08/A17: planning heuristik, dedupe lokal, verification default provider kosong. Passage/locator evidence disediakan caller; bukan discovery mandiri. |
| `src/agents/synthesis.py` | 114 | A04: membaca claim, parameter evidence tidak dipakai untuk menilai isi. Flag konflik tidak menjamin disclosure. None-first sorting berlawanan dengan komentar None-last. |
| `src/agents/writer.py` | 200 | A01/A02/A04/A05/A17: tidak cek source approval/referential integrity, subsection hilang, draft overwrite, body tanpa bibliography, konflik tidak dijelaskan. |
| `src/context/__init__.py` | 32 | A18: __all__ memuat build_candidate_pool/run_dry_run/format_report/main yang tidak di-bind di package; ekspor perlu sesuai implementasi. |
| `src/context/budget.py` | 77 | Budget deterministik dapat dipertahankan; overrides belum dikonsumsi. Angka budget bukan pengukuran token actual provider. |
| `src/context/classifier.py` | 219 | Keyword substring heuristik; mayoritas kosakata Inggris, potensi salah klasifikasi bahasa Indonesia. Tidak terhubung ke planner domain. |
| `src/context/dry_run.py` | 311 | A18: pool statis, ukuran relatif cwd, relevant map hanya tiga kategori; audit menghasilkan selection kosong. |
| `src/context/loader.py` | 245 | Algoritme budget/P0 berguna; default_rules tidak otomatis menjadi candidate. Over-budget flag bergantung adanya item non-P0 yang ditolak, bukan selalu total P0 melebihi batas. |
| `src/context/manifest.py` | 112 | Manifest keputusan context cukup jelas untuk diagnosa; nama/estimasi bukan bukti konten benar-benar dikirim ke model. |
| `src/context/priority.py` | 71 | Kosakata P0-P4 sederhana; pertahankan, tidak perlu registry baru. |
| `src/core/__init__.py` | 10 | Initializer/ekspor package; tidak menambahkan workflow domain tersendiri. Tidak ditemukan blocker khusus terpisah pada inspeksi ini. |
| `src/core/claim_registry.py` | 110 | Atomic persist baik. Konstruktor menimpa duplicate ID melalui dict; add() menolak. Definisi unsupported_important berbeda dari is_writable. |
| `src/core/config.py` | 357 | A16: .env lookup secret/email tidak konsisten; setting yang tidak dikonsumsi; defaults divalidasi dengan baik. |
| `src/core/errors.py` | 135 | Hierarki error/review tersedia. HumanReviewRequired belum dipakai sebagai gate domain nyata; tidak perlu menambah subclass tanpa consumer. |
| `src/core/evidence_registry.py` | 116 | A15: append-only untuk record baru; edit ID lama tidak tersimpan secara default. new_only=False menambah ulang, bukan rewrite seperti docstring. |
| `src/core/logging.py` | 210 | Rotasi file ada; CLI subcommand tidak bootstrap logging. Handler clear saat reconfigure perlu penutupan handler; hindari payload sensitif. |
| `src/core/paths.py` | 318 | A07/A18: root harus bernama DATA BASE; guard subtree sistem tidak menyeluruh. Gunakan resolve pada kedua root/candidate untuk Windows alias. |
| `src/core/project_manager.py` | 348 | A07/A18: path absolut dimuat apa adanya; name/path belum divalidasi sebelum mkdir. Tidak ada create-project CLI dan workspace default tidak dibuat. |
| `src/core/status.py` | 51 | Status vocabulary berguna; semantik callable vs proven harus diselaraskan pada adapters, bukan enum baru. |
| `src/core/storage.py` | 196 | A05/A15: atomik text write kuat, tetapi caller overwrite dan backup collision. JSONL append tidak merupakan transaksi antarproses. |
| `src/routing/__init__.py` | 16 | Initializer/ekspor package; tidak menambahkan workflow domain tersendiri. Tidak ditemukan blocker khusus terpisah pada inspeksi ini. |
| `src/routing/model_router.py` | 182 | A17: provider client sengaja belum diimplementasikan; fail-safe baik. Mapping nama conceptual WRITING tidak otomatis diterjemahkan ke vocabulary operasional. |
| `src/routing/telemetry.py` | 31 | A11: append record sederhana; tanpa timestamp/run/cost/latency. Penolakan sebelum router _execute tidak masuk file telemetry ini. |
| `src/runtime/__init__.py` | 12 | Initializer/ekspor package; tidak menambahkan workflow domain tersendiri. Tidak ditemukan blocker khusus terpisah pada inspeksi ini. |
| `src/runtime/bootstrap.py` | 239 | Check fondasi, bukan kualitas akademik. Satu probe storage nama tetap; config yang diperiksa berasal cache global, tidak selalu paths eksplisit yang diberikan. |
| `src/runtime/cli.py` | 135 | A01/A07/A14/A15: payload parser duplikat monitor, invalid JSON tidak ditangani terstruktur, root input dipercaya, tanpa progress event. |
| `src/runtime/monitor.py` | 222 | A06/A14/A15: API stdlib nyata; CORS wildcard, arbitrary root, body tanpa guard; progress historical dan metrik dekoratif. |
| `src/runtime/progress.py` | 30 | A14/A15: append log sederhana; read seluruh file setiap polling, tidak memisahkan run, tidak recovery trailing JSON rusak. |
| `src/schemas/__init__.py` | 16 | Initializer/ekspor package; tidak menambahkan workflow domain tersendiri. Tidak ditemukan blocker khusus terpisah pada inspeksi ini. |
| `src/schemas/base.py` | 226 | extra=forbid dan assignment validation bermanfaat. Provenance optional dan history dapat diberikan input; bukan signature keaslian. |
| `src/schemas/citation.py` | 78 | Kontrak pointer/reference baik; belum mencegah duplicate key atau memastikan bibliography cocok seluruh citation. |
| `src/schemas/claim.py` | 256 | A01/A04: is_writable memeriksa ID list bukan evidence nyata. Source count default 1 tidak otomatis mengikuti research config 2. |
| `src/schemas/evidence.py` | 260 | Exact containment helper tersedia; quote_verified dan lokasi dapat disetel input. Generic locator dianggap precise, page tidak dicocokkan dokumen. |
| `src/schemas/outline.py` | 107 | Validasi duplicate claim rekursif baik; writer justru mengabaikan nesting yang sah. Field order tidak otomatis diurutkan writer. |
| `src/schemas/project.py` | 122 | A07: path string absolut tanpa validator/rebase; artifact_path menerima string umum. Kontrak artifact lebih kaya daripada output workflow. |
| `src/schemas/source.py` | 181 | State/metadata tersedia, tetapi approve/transition bisa lompat tanpa enforcement legal table. DOI/title tidak divalidasi identitas pada constructor. |
| `src/schemas/synthesis.py` | 55 | Flag conflicts_disclosed belum membuktikan disclosure tekstual. COMPLETE dapat diberikan agregasi kosong. |
| `src/schemas/task.py` | 156 | State graph masih basic same-state guard; transisi arbitrary dan tidak menjadi runtime orchestration loop. |
| `src/schemas/verification.py` | 163 | Level check berguna. _recompute_levels memasukkan str ke dict enum dan memunculkan warning serializer. Dokumen mengatakan skipped diabaikan tetapi campuran PASSED/SKIPPED menjadi UNVERIFIED. |
| `src/tools/__init__.py` | 44 | Initializer/ekspor package; tidak menambahkan workflow domain tersendiri. Tidak ditemukan blocker khusus terpisah pada inspeksi ini. |
| `src/tools/base.py` | 228 | Exception boundary baik; status() sendiri di luar try. A08: gate menolak tool implemented karena status belum proven. |
| `src/tools/citation_manager.py` | 102 | A02/A10: registry key tidak mengecek approved source; disambiguasi tidak dihubungkan ke formatter output. |
| `src/tools/crossref.py` | 173 | Live search/lookup nyata. A03/A08/A16: lookup bypass status, base URL tetap, metadata author raw belum APA; raw text cuplikan 4.000 karakter. |
| `src/tools/dedupe.py` | 111 | A18: helper tidak dipakai DiscoveryAgent. DOI vs no DOI tidak match pada fallback sebagaimana docstring. Perlu identity policy dan konflik metadata. |
| `src/tools/docx_generator.py` | 69 | A02/A05/A10: boolean audit gate, backup per detik, save langsung. Formatting Markdown dasar, bukan APA layout utuh. |
| `src/tools/evidence_extractor.py` | 179 | A13: containment benar terhadap haystack caller; bukan retrieval/provenance check. Tidak mengisi exact char span seperti janji docstring. |
| `src/tools/http_client.py` | 249 | A12: parse JSON setelah truncation; bounded retry baik, tapi baca body unlimited; tidak menghormati Retry-After. Jangan truncate data parse. |
| `src/tools/openalex.py` | 163 | Live search/lookup nyata. Abstract inverted index hanya dipertahankan, tidak direkonstruksi; status public/base URL seperti A08/A16. |
| `src/tools/publish_or_perish.py` | 659 | Subprocess argument list, timeout, stdin DEVNULL dan BOM handling baik untuk Windows. Runtime verified flag/historical capability matrix perlu dipisah dari availability laptop kini. |
| `src/tools/pubmed.py` | 156 | Live esearch/esummary nyata; fixed delay per call bukan global rate limit concurrent. PubMed api_key config tidak dikirim; author-name format perlu normalisasi aman. |
| `src/tools/reference_formatter.py` | 194 | A10: APA parsial, no alphabetical sorting/consistent suffix, missing marker berbeda, volume/issue/page metadata diabaikan. |
| `src/tools/research_tool.py` | 204 | A08: test-only verified flag menyebabkan public API menolak di proses baru. returned_count dihitung setelah mapping/filter, tidak selalu jumlah provider asli. |
| `src/tools/retrieval.py` | 191 | A13: abstrak dianggap fulltext; PDF tidak diparse; file URL diterima; HTML script/style ikut; bytes snapshot overwrite untuk source ID sama. |
| `src/tools/semantic_scholar.py` | 127 | API adapter nyata dalam source; live belum dibuktikan run ini. journal dict fallback bisa gagal validasi venue string; config/getter key perlu A16. |
| `src/tools/source_mapper.py` | 310 | Normalisasi berguna dan sebagian metadata dipertahankan. normalize_doi hanya prefix 10., bukan syntax lengkap; normalize_authors string memecah koma dalam surname, initials. |
| `src/tools/verification_tool.py` | 311 | A03: DOI mismatch lolos, candidate metadata salah dipertahankan. CONTENT unverified dilaporkan jujur; laporan belum diwajibkan sebelum writer. |
| `src/workflows/__init__.py` | 29 | Initializer/ekspor package; tidak menambahkan workflow domain tersendiri. Tidak ditemukan blocker khusus terpisah pada inspeksi ini. |
| `src/workflows/academic.py` | 84 | A01/A05/A11: assembly ke DOCX nyata, bukan search-to-paper. Tidak mempersist semua bahan dan keputusan per run. |
| `src/workflows/deep_research.py` | 72 | A17: plan + academic wrapper, tidak discovery/retrieval multi-query. Respons analyzer/planner tidak diperiksa lengkap sebelum akses task. |
| `src/workflows/evidence_flow.py` | 264 | Aturan conflict/source count deterministik berguna; hubungan/strength evidence berasal caller dan tidak membaca source content. Skor confidence bukan kalibrasi empiris. |
| `src/workflows/optimization.py` | 49 | A17: ringkas token/status dengan recommendation statis. Belum mengukur cost/latency atau menerapkan tuning; tidak perlu autoscaling untuk pribadi. |
| `src/workflows/orchestrator.py` | 95 | A01/A04/A11/A17: tahap akhir saja, no evidence verification/retry/review loop. Draft tersimpan sebelum audit final. |
| `src/workflows/validation.py` | 52 | A17: generic callable harness; cases kosong sukses, exception tanpa detail; tidak otomatis menjalankan skenario akademik. |
| `src/workflows/verification_flow.py` | 118 | Legal table terpisah tidak selalu dipakai. DISCOVERED→REJECTED dilarang meskipun engine dapat merekomendasikan rejection; agent menelan transition failure dan tetap success. |
| `src/workflows/writing_flow.py` | 90 | Tabel outline/writing lifecycle tersedia tetapi alur utama tidak menggunakannya sebagai gate approval atau revision. |

## Dokumen dan operasi

| File/kelompok | Catatan |
|---|---|
| `README.md`, `BUILD_PLAN.md`, `ARCHITECTURE.md`, `WORKFLOW.md` | Pisahkan visi, acceptance dan kemampuan runtime aktual; fase selesai minimal belum sama dengan seluruh deliverable. |
| `SYSTEM_RULES.md`, `AGENT_CONSTITUTION.md`, `00_MASTER_INSTRUCTION.md` | Prinsip integritas kuat sebagai spec; beberapa belum menjadi gate kode. |
| `SYSTEM_INDEX.md`, `ENGINEERING_PROTOCOL.md` | Jujur menyatakan registry optional belum ada; jangan membangunnya hanya untuk melengkapi daftar. |
| `docs/LAPORAN_FASE_*.md`, laporan historis | Bukti milestone historis; tidak otomatis bukti readiness commit sekarang. Fokus crosscheck fase 7–18 dan panduan aktif. |
| `docs/CARA_MEMBAGIKAN_PROJECT.md` | Fresh clone default tidak sesuai deteksi root; lokasi plugin lokal komputer developer bukan dependency portable. |
| `docs/CARA_CEPAT_UNTUK_ORANG_AWAM.md` | Klaim progress muncul dari CLI check/plan tidak sesuai instrumentasi. |
| `docs/CARA_MENGGUNAKAN_CODE.md`, `docs/CARA_PAKAI_UNTUK_AI_AGENT.md` | Perlu satu contoh runnable dari fresh setup dan beda draft/final; jangan mengandalkan agent menulis status approved manual. |
| `requirements.txt`, `pyproject.toml` | Pin selaras dan clean install berhasil pada Python 3.14.5. Dua sumber daftar dependency bisa drift; README requirements melewatkan python-docx. |
| `config/system.yaml` | Banyak disabled/NOT_IMPLEMENTED historis dan flag tidak dikonsumsi; laporkan status efektif per capability. |
| `.gitignore` | .env dan runtime umum diabaikan; system.local.yaml tidak diabaikan. Git tidak membackup sibling workspace. |
| `START_MONITOR.bat`, `OPEN_LIVE_PROGRESS.bat`, `OPEN_LIVE_PROGRESS.ps1` | Quoting root sudah membantu spasi; gunakan venv interpreter, cek readiness identitas aplikasi, tangani port/dependency error. |
| `skills/autonomi-agentic-ilmiah/SKILL.md`, `references/input-json.md` | Instruksi host AI; shape data belum contoh penelitian terverifikasi yang lengkap. |
| `dist/autonomi-agentic-ilmiah-skill.zip` | Dua file instruksi, bukan runtime standalone; isi SKILL cocok repo saat audit. |
| `prompts/README.md`, `.gitkeep` | Placeholder bukan prompt reasoning engine yang aktif. |
| `docs/_extract_docx.py`, `_master_task_extract.txt` | Utilitas/hasil ekstraksi dokumen master; tidak berada pada execution path akademik utama. |
| `docs/AUDIT_KESELURUHAN_2026-09-07.md` | Sudah untracked saat mulai; dipertahankan, tidak digunakan menggantikan verifikasi independen. |

## File test yang dijalankan

- `tests/test_agents_base.py`
- `tests/test_audit_agents.py`
- `tests/test_citation_manager.py`
- `tests/test_claim_verification_agent.py`
- `tests/test_cli.py`
- `tests/test_config.py`
- `tests/test_context.py`
- `tests/test_context_integration.py`
- `tests/test_dedupe.py`
- `tests/test_docx_generator.py`
- `tests/test_evidence_extractor.py`
- `tests/test_evidence_flow.py`
- `tests/test_http_client.py`
- `tests/test_model_telemetry.py`
- `tests/test_monitor.py`
- `tests/test_orchestrator.py`
- `tests/test_outline_schema.py`
- `tests/test_paths.py`
- `tests/test_phase_14_17_workflows.py`
- `tests/test_project_manager.py`
- `tests/test_publish_or_perish_integration.py`
- `tests/test_reference_formatter.py`
- `tests/test_registries.py`
- `tests/test_research_agents.py`
- `tests/test_research_tools.py`
- `tests/test_research_tools_integration.py`
- `tests/test_retrieval.py`
- `tests/test_routing_smoke.py`
- `tests/test_schemas.py`
- `tests/test_source_mapper.py`
- `tests/test_storage.py`
- `tests/test_synthesis_agent.py`
- `tests/test_tools.py`
- `tests/test_verification.py`
- `tests/test_verification_integration.py`
- `tests/test_writer.py`
- `tests/test_writing_flow.py`
