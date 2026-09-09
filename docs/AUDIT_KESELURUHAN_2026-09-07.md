# AUDIT KESELURUHAN — AUTONOMI AGENTIC ILMIAH

**Tanggal:** 2026-09-07
**Lingkup:** Audit total & jujur untuk penggunaan pribadi multi-laptop (bukan untuk publikasi/komersial).
**Metode:** Pembacaan menyeluruh source (~12.000 LOC, 110 file Python), health check, seluruh test suite, 11 skenario uji dinamis, uji clone ke path lain, verifikasi Crossref live.
**Aturan audit:** Tidak ada kode project yang diubah. Fixture uji diletakkan di `state/audit_sandbox/` (di-gitignore) dan sandbox output `VIBE CODING/TUGAS AUDIT_SANDBOX/` (di luar workspace, boleh dihapus).

---

## 1. Executive Summary

Project ini **bukan proyek kosmetik** — inti evidence-control-nya nyata, dirancang dengan disiplin, dan sebagian gate-nya terbukti bekerja saat diuji. Tapi audit ini menemukan **satu kesenjangan besar antara dokumentasi dan kenyataan**, dan **beberapa bug nyata yang membatalkan janji utama sistem**.

**Yang jujur bisa dikatakan:**

1. ** Fondasi deterministic-nya berkualitas baik.** Schemas Pydantic dengan state machine yang dijaga, storage atomik dengan boundary check, HTTP client dengan retry/backoff yang benar, verifikasi provider (Crossref/OpenAlex) yang tidak pernah mengarang record. Ini di atas rata-rata proyek pribadi.

2. **Tapi system ini BELUM "agentic" dan BELUM end-to-end autonomous.** Workflow akademik adalah pipeline deterministic: input JSON harus sudah berisi sources/claims/evidence/outline. Agent-agent "peneliti" (Discovery, Retrieval, Evidence, Verification) ada dan berkualitas, tetapi **tidak dipanggil oleh workflow manapun**. Model router adalah stub yang selalu gagal (`PROVIDER_CLIENT_NOT_IMPLEMENTED`).

3. **Dua bug menggagalkan janji inti "output akademik yang dapat dipercaya":**
   - **P0-1:** Token sitasi internal (`turn0search5`, `view10filecite4`, `filecite`) **lolos tanpa disentuh** ke draft final dan DOCX. `citation_audit.json` tetap `passed: true`. Tidak ada gate kode sama sekali — hanya aturan di markdown.
   - **P0-2:** Dua sumber berbeda dengan author+tahun sama menghasilkan in-text citation identik `(Nashrullah, 2023; Nashrullah, 2023)` tanpa disambiguasi APA 7 (`2023a/2023b`). Audit tidak menangkapnya karena Writer dan Audit memakai algoritma key yang berbeda.

4. **P0-3 (portability):** Setelah `git clone`, repo bernama apa pun selain `DATA BASE` (default clone dari GitHub kamu: `Agentic-Module`) **gagal total** — 29 test gagal, health check exit 1. Ini mematahkan requirement #1 kamu: "kemudahan setup setelah git clone".

5. **Fase 7–18: selesai secara kode, belum selesai secara substansi.** Saya jabarkan per fase di §5.

**Kesimpulan satu kalimat:** Project ini **nyaman dipakai pribadi HANYA jika** kamu (a) selalu menamai folder `DATA BASE`, (b) selalu menyiapkan input JSON secara manual, dan (c) **mau memeriksa draft final secara manual** — karena gate otomatis untuk hal-hal yang paling kamu takutkan (token internal, sitasi ganda, marker `[sumber belum lengkap]`) **belum ada di kode**.

---

## 2. Status Kesehatan Project

| Check | Hasil |
|---|---|
| `python -m src check` (laptop asli) | ✅ Lulus — spec 1.0, build phase 18 |
| `python -m pytest -q` | ✅ 272 passed, 10 deselected (2.38s) |
| `python -m pytest -m integration -q` | ✅ 10 passed (15.21s) |
| `python -m src check` (clone di path lain, folder `DATA BASE`) | ✅ Lulus |
| `python -m src check` (clone, folder `Agentic-Module`) | ❌ Gagal — system root tidak ditemukan |
| Monitor `http://127.0.0.1:8000` | ⚠️ Tidak berjalan; saat dinyalakan manual, GET OK, POST path-invalid crash |
| Dependency | ✅ Minimal (4 runtime dep), pinned, `requires-python >=3.11` (teruji jalan di 3.14) |
| Git | ✅ 158 file tracked; ⚠️ `dist/*.zip` ikut tracked |

**Kondisi "sehat tapi rapuh":** sehat di konfigurasi laptop kamu, rapuh terhadap perubahan nama folder lokasi.

---

## 3. Hasil Test

**Test suite bawaan:** 272 unit + 10 integration, semua lulus, sangat cepat. Kualitas test bawaan baik untuk yang diuji.

**Tapi hasil 11 skenario dinamis menunjukkan test suite TIDAK menguji hal-hal yang paling penting:**

| # | Skenario | Hasil | Verdict |
|---|---|---|---|
| 1 | Topik sederhana via `plan` | EXIT 0, plan JSON valid | ✅ |
| 2 | Topik PKM-RSH Edjust via `plan` | EXIT 0, mode terdeteksi ACADEMIC_WRITING | ✅ (tapi mode detection hanya cek kata "deep") |
| 3 | `run-academic` happy path (sumber valid, evidence verbatim) | EXIT 0, draft + citation_audit + fact_audit + DOCX | ✅ |
| 4 | Dua sumber collision author+tahun | Draft memuat `(Nashrullah, 2023; Nashrullah, 2023)` — identik; audit `passed: true` | ❌ **BUG** |
| 5 | Token internal `turn0search5`, `view10filecite4`, `filecite` di claim & evidence | Token lolos utuh ke draft & DOCX; audit `passed: true` | ❌ **BUG** |
| 6 | Sumber metadata tidak lengkap (tanpa author/tahun/DOI) | Draft `(Laporan, n.d.)`; reference list berisi `[missing: author]` dll.; DOCX dibuat; `[sumber belum lengkap]` TIDAK muncul | ⚠️ Setengah benar |
| 7 | DOI palsu via `lookup_by_doi` | `IntegrationError` crash — kontrak "return None" dilanggar | ❌ **BUG** |
| 8 | DOI valid via `lookup_by_doi` | Metadata nyata dari Crossref (Nature 2013) | ✅ |
| 9 | Claim penting tanpa evidence (evidence bertentangan/absen) | Workflow GAGAL dengan benar — DOCX ditolak | ✅ Gate bekerja |
| 10 | Monitor: GET endpoints, POST valid, POST path-invalid | GET OK; POST valid 200; POST path-invalid → koneksi diputus tanpa JSON | ⚠️ |
| 11 | Clone ke path lain | Folder `Agentic-Module` → total gagal; rename `DATA BASE` → check OK, 2 test gagal (butuh `TUGAS 1` fisik) | ❌ **BUG** |
| — (bonus) | Payload kosong (tanpa claims/sources/outline) | `success: true`, draft hampir kosong, DOCX tidak dibuat karena outline None | ⚠️ Perilaku dipertanyakan |

**Kesimpulan test:** Test suite memberi rasa aman palsu untuk aspek anti-halusinasi output — tidak ada satu pun test untuk token internal, disambiguasi sitasi, atau marker sumber belum lengkap.

---

## 4. Temuan Bug/Risiko Berdasarkan Prioritas

### P0 — Wajib diperbaiki sebelum dipercaya

**P0-1. Tidak ada gate token sitasi internal di kode.**
- **File:** `src/agents/audit.py` (CitationAuditAgent, seluruh file); `src/tools/citation_manager.py` (hanya mendeteksi orphan key `smith2012`).
- **Masalah:** Aturan "final output tidak boleh memuat `turn...`, `view...`, `search...`, `filecite`" hanya hidup di AGENTS.md/SKILL.md. Tidak ada satu baris kode pun yang men-scan draft untuk pola ini.
- **Bukti:** Skenario 5 — draft final berisi `Menurut turn0search5 dan view10filecite4...` dan `> "Scores improved (turn0search5, filecite chunk_3)."`, `citation_audit.json` = `{"passed": true}`.
- **Dampak:** Melanggar langsung AGENT_CONSTITUTION & rules kamu; output "final" bisa membawa artefak token ChatGPT ke dokumen akademik.
- **Rekomendasi:** Tambah check di `CitationAuditAgent`: scan draft dengan regex `\b(turn|view|search|filecite)[a-zA-Z]*\d+\b` + token `filecite`; jika match → `passed=false` + daftar token. Murah (±15 baris + test).

**P0-2. Disambiguasi sitasi tidak konsisten: Writer dan Audit pakai algoritma berbeda.**
- **File:** `src/tools/citation_manager.py` baris ~30-45 (`register_source`: collision → suffix `a, b, c...` berurutan) vs `src/agents/audit.py` baris ~40 (`known = {citation_key_for(source)}` — tanpa disambiguasi) vs `src/tools/reference_formatter.py` (`citation_key_for`: tidak pernah menghasilkan suffix).
- **Masalah:** Writer mendaftarkan dua sumber `Nashrullah, 2023` sebagai `nashrullah2023a` dan `nashrullah2023b`, tapi **menulis in-text human-form yang identik** `(Nashrullah, 2023)` untuk keduanya (writer.py `_citations_for` memakai `format_in_text_author_year`, bukan key yang sudah di-disambiguasi). Audit memakai key tanpa suffix sehingga `nashrullah2023a` di draft akan dianggap **orphan** (false positive) — dan human-form identik lolos (false negative). Dua arah salah sekaligus.
- **Bukti:** Skenario 4 — draft `(Nashrullah, 2023; Nashrullah, 2023)`, audit passed. (Skenario audit tidak memicu false-positive orphan hanya karena draft human-form tidak memuat key mesin.)
- **Dampak:** Pelanggaran APA 7 (2023a/2023b wajib); pembaca tidak bisa membedakan dua sumber; audit memberi jaminan palsu.
- **Rekomendasi:** Satukan logika key: `format_in_text_author_year` harus menerima suffix disambiguasi dari CitationManager; Writer render `Nashrullah, 2023a`; Audit derive key yang sama dari draft.

**P0-3. Clone dengan nama folder default GitHub gagal total.**
- **File:** `src/core/paths.py` (`SYSTEM_ROOT_DIRNAME = "DATA BASE"`, `_looks_like_system_root` menuntut nama persis).
- **Bukti:** Skenario 11 — clone ke `Repo Uji Kedua`: 29 test failed, 15 errors, `python -m src check` exit 1. Rename ke `DATA BASE` → pulih.
- **Dampak:** Requirement utama kamu (setup mudah setelah `git clone`) gagal untuk siapa pun yang tidak tahu harus rename folder — termasuk kamu sendiri di laptop baru 6 bulan lagi.
- **Rekomendasi:** (a) Halaman utama README: satu perintah clone yang sekaligus rename (`git clone ... DATA BASE`); (b) perbaiki error message agar menyebut solusinya ("rename folder to DATA BASE, or set AUTONOMI_SYSTEM_ROOT"); (c) pertimbangkan fallback: kalau root kandidat memuat spec files wajib tapi namanya bukan `DATA BASE`, terima dengan warning.

### P1 — Penting, perbaiki segera setelah P0

**P1-1. Workflow akademik tidak terhubung ke verification/discovery/retrieval/evidence engine.**
- **File:** `src/workflows/orchestrator.py` (hanya memanggil Synthesis→Outline→Writer→Audit); `src/agents/research.py` (DiscoveryAgent, VerificationAgent, RetrievalAgent, EvidenceAgent — tidak dipanggil siapa pun kecuali test); `src/tools/verification_tool.py` (VerificationEngine utuh).
- **Masalah:** "Mencari sumber, memverifikasi, menarik evidence" adalah modul terbaik di project ini, tapi pipeline CLI hanya menerima semuanya jadi dari input JSON. Verifikasi provider hanya bisa dijalankan kalau pemanggil memanggilnya sendiri.
- **Dampak:** Klaim README "DISCOVER → VERIFY → RETRIEVE → ... → AUDIT" hanya terjadi di 3 tahap terakhir. Segmen awal rantai adalah pustaka, bukan pipeline.
- **Rekomendasi:** Tambahkan perintah `python -m src research --input-json` yang menjalankan Discovery→Verification→Retrieval→Evidence→ClaimVerification→(lalu AcademicWorkflow). Ini perubahan orkestrasi, bukan kode baru.

**P1-2. Marker `[sumber belum lengkap]` tidak diimplementasikan; `[missing: field]` berbahasa Inggris dan hanya ada di daftar pustaka.**
- **File:** `src/tools/reference_formatter.py` (marker `[missing: ...]`), `src/agents/writer.py` (tidak pernah menulis marker di badan teks).
- **Bukti:** Skenario 6 — sumber tanpa author/tahun menghasilkan in-text `(Laporan, n.d.)` (dari slug judul — terlihat seperti sitasi sah) dan daftar pustaka `[missing: author] (n.d.). ...`. Tidak ada `[sumber belum lengkap]` di mana pun.
- **Dampak:** Teks terlihat lengkap padahal sumbernya gapan — justru melawan tujuan anti-halusinasi; dan tidak sesuai kontrak di AGENTS.md.
- **Rekomendasi:** Writer: jika `source` gagal metadata minimum (author atau title), render sitasi sebagai `[sumber belum lengkap]` dan jangan registrasi ke reference list; atau masukkan entry dengan marker eksplisit ke DOCX.

**P1-3. Monitor POST `/api/run-academic` crash tanpa response pada input bermasalah.**
- **File:** `src/runtime/monitor.py`, `do_POST` (tanpa try/except di sekitar workflow dan tanpa validasi `project_path`).
- **Bukti:** Skenario 10 — POST dengan `project_path` drive tak ada: koneksi ditutup tanpa JSON. Juga terbukti monitor menerima **path absolut bebas** (fixture saya membuat folder di luar workspace tanpa peringatan) — `Path(...).resolve(); mkdir(parents=True)` di `_project_from_payload`.
- **Dampak:** Kegagalan diam; dan endpoint localhost bisa dipakai menulis folder di lokasi mana pun di disk (dari browser page mana pun berkat CORS `*` — lihat P1-4).
- **Rekomendasi:** Bungkus handler dengan try/except → JSON error + HTTP 500; validasi `project_path` harus di dalam `workspace_root` (pakai `paths.workspace_path`); batasi hanya path yang sudah ada atau di bawah WORKSPACE_ROOT.

**P1-4. Monitor: CORS `*` + tanpa autentikasi.**
- **File:** `src/runtime/monitor.py` `_send` (`Access-Control-Allow-Origin: *`).
- **Dampak:** Semua website di browser kamu bisa mengirim request ke `http://127.0.0.1:8000` dan men-trigger workflow yang menulis file (DRIVE-BY local API). Untuk penggunaan pribadi ini risiko nyata, meski kecil.
- **Rekomendasi:** Minimal: hapus CORS header (UI-nya served same-origin, tidak butuh), atau batasi ke `http://127.0.0.1:8000`; tambah token statis dari `.env` untuk POST.

**P1-5. `lookup_by_doi` melempar exception untuk DOI tidak ditemukan (kontrak dilanggar).**
- **File:** `src/tools/crossref.py` `lookup_by_doi` (docstring: "Returns ``None`` for a missing or malformed DOI") + `src/tools/http_client.py` (HTTP 404 → IntegrationError).
- **Bukti:** Skenario 7 — DOI palsu → traceback IntegrationError.
- **Dampak:** Pemanggil langsung crash. `VerificationEngine._lookup` kebetulan menangkap exception, jadi pipeline verifikasi selamat — tapi itu perlindungan tidak disengaja.
- **Rekomendasi:** Di `lookup_by_doi`, tangkap `IntegrationError` dengan `status == 404` → return None; biarkan error lain naik.

**P1-6. Model router = stub. "Multi-model AI" belum ada.**
- **File:** `src/routing/model_router.py` `_execute` → selalu `ModelResponse.failure(PROVIDER_CLIENT_NOT_IMPLEMENTED)`; `config/system.yaml` `model_routing.status: PENDING_CONFIGURATION`.
- **Dampak:** Semua bagian yang menunggu model (paraphrase, narrative synthesis, verifikasi konten) tidak bisa hidup. Untuk target Gemini kamu: belum ada adapter sama sekali.
- **Rekomendasi:** Implementasi adapter Gemini (REST `generateContent`, key dari env `GEMINI_API_KEY` via `api_key_env`) dengan kontrak `ModelRequest/ModelResponse` yang sudah ada. Ini pekerjaan ±1 file + test, dan membuka seluruh fase 16-18.

### P2 — Diperbaiki untuk kenyamanan & ketahanan

- **P2-1. Dua test butuh kondisi laptop asli.** `tests/test_paths.py::test_project_workspaces_discovered` & `test_workspace_path_resolves_correctly` gagal di clone fresh karena menuntut `TUGAS 1` fisik di workspace root. (Bukti: skenario 11.) Fix: gunakan tmp fixture workspace, bukan kondisi global.
- **P2-2. `dist/autonomi-agentic-ilmiah-skill.zip` tracked di git.** Artefak build di repo; akan selalu stale. Fix: gitignore `dist/`, buat skrip build.
- **P2-3. Empty payload `success: true`.** `run-academic` dengan 0 claims & 0 sources menghasilkan "laporan" hampir kosong. Fix: validasi minimum (≥1 source & ≥1 claim) → error jelas.
- **P2-4. Mode detection terlalu naif.** `TaskAnalyzerAgent`: `mode = DEEP_RESEARCH if "deep" in text.lower()` — satu kata. "deep learning" akan salah terdeteksi DEEP_RESEARCH. Fix: keyword eksplisit ("deep research") atau parameter CLI.
- **P2-5. Non-ASCII artifacts di output.** Ditemukan `Â§` di draft (dari `§Results` fixture) — extraction/formatting dengan encoding tidak konsisten (PS 5.1 console ikut terlibat; perlu verifikasi Python-side murni, tapi indikasi kuat: pilih satu encoding dan normalisasi § saat render).
- **P2-6. `tools` config status semua `NOT_IMPLEMENTED`/`enabled: false` sementara adapter-nya ada dan (untuk Crossref) jalan.** Status ini menyesatkan pembaca config; adapter Crossref dipakai default oleh VerificationEngine tanpa melihat `enabled`. Jelaskan di config comment bahwa status tools ini adalah *konfigurasi* bukan *capability*, atau sinkronkan.
- **P2-7. `Pydantic` deprecation & `StrEnum`** — `requires-python >=3.11` tapi `datetime.UTC` butuh 3.11+ (OK) dan `StrEnum` 3.11+ (OK). Laptop lain harus minimal Python 3.11 — catat di README; pertimbangkan naik ke `>=3.11,<3.14` eksplisit.

### P3 — Kesopanan engineering

- `state/` dan `logs/` menggumpal tanpa rotasi untuk `progress.jsonl` (append-only, tidak pernah dipangkas).
- `monitor.py` `log_message` di-silence — request tidak ter-audit.
- `README.md` License TBD — untuk pemakaian pribadi tidak mendesak.
- Duplicated `_project_from_payload` antara `cli.py` dan `monitor.py` — satu sumber kebenaran.

---

## 5. Jawaban Pertanyaan Audit Kritis

**1. Apakah sistem ini benar-benar "agentic"?**
**Tidak — saat ini adalah workflow deterministic + pustaka agent yang tidak terhubung.** Definisi agentic yang jujur: sistem yang memutuskan sendiri tool apa dipanggil kapan, mengiterasi hasil, dan menilai langkah berikutnya. Yang ada: pipeline tetap (synthesis→outline→write→audit) dengan gate deterministic. Agents di `research.py` punya bentuk agentic (koordinasi, isolasi failure) tapi tidak ada orchestrator yang memanggilnya dengan keputusan. Ini bukan hal buruk untuk tujuan kamu — deterministic lebih aman — tapi jangan sebut agentic sampai `research` command (P1-1) dan model router (P1-6) hidup.

**2. Apakah fase 7–18 selesai substansial?**
Per fase (berdasarkan kode + uji):
- **F7 (research agents):** kode ada, tidak terhubung pipeline. *Setengah.*
- **F8 (orchestrator):** bekerja untuk segmen writing. *Ya, terbatas.*
- **F9 (telemetry):** nyata tapi hanya event routing yang selalu gagal. *Formal.*
- **F10-12 (audit):** fact audit bekerja (terbukti skenario 9); citation audit bocor (P0-1, P0-2). *Sebagian.*
- **F13 (DOCX):** bekerja, backup otomatis, heading sederhana. *Ya, minimal.*
- **F14 (academic mode):** end-to-end bekerja — terbukti skenario 3. *Ya.*
- **F15 (deep research):** hanya wrapper yang menambah kata "deep" lalu jalankan academic mode yang sama; tidak ada iterasi discovery. *Simulatif.*
- **F16-18 (optimization/monitor/packaging):** monitor berfungsi sebagian (P1-3/P1-4); skill packaging = instruksi markdown + zip; optimization tidak ditemukan substansinya. *Sebagian/simulatif.*

**3. Apakah "mencari sumber, mensitasi, membuat daftar pustaka" end-to-end?**
**Tidak.** Mensitasi & daftar pustaka: ya (dengan caveat P0-2). Mencari sumber: tool-nya nyata (Crossref live terbukti) tapi tidak dipanggil workflow. Karena input JSON mensyaratkan sources sudah ada, "mencari" tidak pernah terjadi di pipeline utama.

**4. Apakah plugin/skill cukup untuk orang awam?**
Sebagai **skill untuk AI agent** (Kiro/Claude dll.): cukup baik — SKILL.md jelas, rules konsisten. Sebagai **package untuk orang awam**: tidak — orang awam tidak akan bisa menyiapkan `input.json` yang valid (skema strict, `extra="forbid"`), tidak ada generator template, tidak ada `init` command. Skill hanyalah instruksi + satu zip statis yang stale (P2-2).

**5. Apakah monitor merekam SEMUA tahap kerja agent?**
**Tidak.** `record_progress` hanya dipanggil di: `check`, `plan`, `run-academic` (mulai/selesai di monitor.py) — dan tidak dipanggil sama sekali oleh CLI `run-academic` (hanya via monitor POST). Tahap synthesis/outline/writing/audit/docx **tidak merekam event individual**. Dashboard HTML menampilkan 8 node (instruction→academic) yang **selalu "waiting"** untuk event yang tidak pernah direkam — dashboard-nya lebih optimistis daripada datanya.

**6. Apakah output akademik punya gate otomatis menolak `turn.../view.../search.../filecite`?**
**Tidak.** Terbukti eksperimen (skenario 5). Hanya aturan dokumentasi. Ini P0-1.

**7. Apakah model routing & provider integration nyata?**
**Routing = interface + telemetry nyata, provider client = tidak ada.** `status()` yang jujur (turun ke PENDING_CONFIGURATION bila prasyarat kurang) adalah desain baik. Untuk Gemini: nol kode adapter. Klaim "Phase 2 wires real providers" di docstring belum terjadi.

**8. Batas minimal agar layak dipakai pribadi di beberapa laptop?**
1. P0-3 (clone naming) — tanpa ini, setup laptop kedua gagal.
2. P0-1 + P0-2 — tanpa ini, kamu harus proofread token & sitasi manual di setiap output (mengalahkan tujuan sistem).
3. P1-3 (monitor crash) — opsional jika kamu tidak pakai monitor.
4. Satu perintah setup (`pip install -r requirements.txt`) sudah cukup baik hari ini.
Sisanya (P2+) adalah kenyamanan.

**9. Bagian paling berisiko untuk pengguna awam?**
(1) Menyiapkan `input.json` — salah skema = error yang tidak ramah; (2) mempercayai `passed: true` pada citation_audit padahal bocor (P0-1/2); (3) monitor yang menerima path bebas (P1-3) — orang awam tidak akan sadar folder dibuat di luar workspace.

**10. Perubahan paling kecil yang membuat project jauh lebih dapat dipercaya?**
**Tambahkan `INTERNAL_TOKEN_PATTERN` scan ke `CitationAuditAgent` + 3 test.** Sekitar 20 baris. Setelah itu, klaim "final output bebas token internal" baru benar-benar dijaga kode, bukan harapan.

**11. Localhost API cukup aman untuk pribadi?**
**Cukup untuk laptop pribadi yang dipakai hati-hati, TIDAK cukup stand "aman".** Tiga lubang: CORS `*` (website mana pun bisa memanggil API), tanpa token, POST menerima path absolut. Perbaikan minimal: hapus CORS wildcard + validasi path di dalam WORKSPACE_ROOT + token statis opsional dari `.env` untuk POST. Total ±30 baris.

**12. Bisa dipakai di laptop lain setelah `git clone` tanpa path khusus?**
**Hanya jika folder hasil clone diberi nama `DATA BASE`.** Selain itu: gagal total (P0-3). Dependency-nya aman (stdlib-heavy, pinned, Python ≥3.11). Config portable (env override + system.local.yaml). Setelah rename: check lulus; tinggal 2 test yang butuh kondisi laptop asli (P2-1) — tidak memblokir penggunaan.

**13. Struktur folder, spasi di nama, launcher Windows cukup portable?**
**Struktur: ya. Spasi: ya** (semua akses via pathlib; launcher pakai `cd /d "%~dp0"` dan `-LiteralPath` yang benar). **Launcher: hampir** — `OPEN_LIVE_PROGRESS.ps1` bagus (cek port dulu), `START_MONITOR.bat` tidak mendeteksi Python tidak ada (user awam dapat error cryptic). Tidak ada launcher untuk setup awal (`setup.bat` yang membuat venv + install deps akan menaikkan kenyamanan drastis).

**14. Perlu GitHub Actions/CI?**
**Ya, sepadan — bahkan untuk repo pribadi.** Ini satu-satunya cara test portability (P0-3, P2-1) tertangkap otomatis: workflow Ubuntu+Windows matrix yang `pip install -r requirements.txt && python -m src check && pytest -q` akan gagal di PR kalau ada regresi path/nama folder. Biaya: satu file YAML, gratis untuk repo privat/public kecil.

**15. Apakah audit trail cukup membuktikan sumber/evidence/sitasi tidak dikarang?**
**Untuk evidence: kuat.** `Evidence.quote_verified` butuh exact containment; `mark_quote_verified` bisa berubah false saat re-check; candidates/search_log/evidence.jsonl append-only; VerificationReport menyimpan provider & confidence; `_raw` PoP dipertahankan. **Untuk sitasi: ada celah** — draft tidak menyimpan mapping sitasi→source_id (human-form saja), sehingga pembuktian "sitasi X berasal dari source Y" bergantung pada reconstruct manual. Tambahkan sidecar `citation_map.json` dari Writer (key → source_id + annotated span) untuk menutup rantai bukti.

**16. Apakah safeguard etik topik remaja 12–18 cukup kuat?**
**Tidak ditemukan safeguard spesifik topik remaja di kode.** Yang ada: general human-review escalation (`needs_human_review`) dan claim gating. Tidak ada klasifikasi topik sensitif, tidak ada flag penelitian pada anak/remaja (mis. memerlukan persetujuan etik), tidak ada blocklist. Jika requirement ini penting bagimu (PKM-RSH Edjust menyentuh pendidikan), perlu: kata-kunci sensitif → force `needs_human_review` + disclaimer di dokumen. Saat ini kepatuhan etik **sepenuhnya bergantung pada penggunanya**.

---

## 6. Catatan Source Code Per File

**Kuat (pertahankan):**
- `core/paths.py` — desain discovery bagus, env override, cache. (Satu cacat: nama folder dipersyaratkan — P0-3.)
- `core/storage.py` — atomic write, boundary check, backup timestamp: contoh terbaik di repo.
- `core/config.py` — layering YAML→local→.env→env dengan validasi ketat & provenance. Extra="forbid" menangkap typo. Sangat baik.
- `tools/http_client.py` — retry + jitter + truncated raw body + structured errors: kelas dunia untuk stdlib-only.
- `tools/verification_tool.py` — tidak pernah pass tanpa korroborasi provider; degradasi jujur.
- `schemas/` — state machine terjaga (transition guards), evidence verbatim enforcement, outline anti-duplicate.
- `tools/evidence_extractor.py` — exact containment, tidak ada percobaan "pintar".

**Bermasalah:**
- `agents/audit.py` — audit hanya orphan-detection; tidak ada token scan (P0-1), key derivation beda dari writer (P0-2).
- `agents/writer.py` — in-text human form tidak pakai disambiguated key (P0-2); tidak ada marker sumber belum lengkap (P1-2); tidak menulis citation sidecar (§5.15).
- `agents/research.py` — agent bagus, mati (P1-1); TaskAnalyzer naif (P2-4).
- `routing/model_router.py` — stub jujur tapi masih stub (P1-6).
- `runtime/monitor.py` — no auth, CORS *, path bebas, crash handler (P1-3/4); dashboard > data.
- `runtime/cli.py` + `monitor.py` — duplikasi `_project_from_payload`.
- `tools/crossref.py` — lookup_by_doi kontrak rusak (P1-5); `_search` bagus.
- `tools/docx_generator.py` — heading/quote sederhana tapi benar; tidak menulis reference list entry `[missing: ...]` dengan penanda berbeda (semua paragraf polos).

**Test yang kurang:** token internal scan, disambiguasi APA, marker metadata, monitor POST error path, lookup_by_doi 404, clone fresh workspace (test_paths kondisi global).

---

## 7. Evaluasi Arsitektur

**Lapisan bersih dan disiplin:** core (infra) → schemas (kontrak) → tools (kapabilitas) → agents (koordinasi) → workflows (orkestrasi) → runtime (bootstrap/CLI/monitor). Dependency arah satu arah. Nama "agents" untuk banyak komponen deterministic agak oversell, tapi pemisahan tool vs agent (stateless vs decision) dipertahankan konsisten.

**Keputusan arsitektur yang benar:** (1) storage atomik + append-only JSONL untuk audit; (2) konfigurasi berlapis dengan validasi; (3) status integrasi tidak pernah diklaim tanpa bukti runtime (`_integration_verified` hanya diset test nyata); (4) no-fabrication ditegakkan di tipe data, bukan hanya konvensi.

**Kelemahan struktural:** (1) pipeline utama tidak memanfaatkan modul terkuatnya (verifikasi/discovery); (2) tidak ada satu "registry of stages" — tahap dipanggil manual di orchestrator, sehingga menambah tahap = edit orchestrator (rawan lupa audit baru); (3) monitor & CLI duplikasi logic; (4) tidak ada CI.

**Penyederhanaan yang mungkin:** hapus `runtime_dir` alias setelah migrasi selesai; gabungkan `_project_from_payload`; pertimbangkan menghapus `optimization.py` jika tidak dipanggil (cek import).

---

## 8. Evaluasi Workflow Akademik

**Alur nyata:** JSON → Project → Synthesis (writable-only) → Outline (auto bila tidak ada) → Writer (gated) → CitationAudit → FactAudit → DOCX (hanya jika audit lulus) → draft.md + final.docx + JSON audit di project dir.

**Yang bekerja nyata:** gate claim penting tanpa evidence memblokir DOCX (terbukti); reference list dari CitationManager (tanpa invent); excluded_claims dilaporkan; verbatim quotes hanya jika `is_citable_quotation` (verbatim+verified+precise locator).

**Yang setengah jadi:** (1) input JSON harus "sudah diperiksa" — tak ada jalur dari pencarian nyata; (2) draft = skeleton, bukan prosa akademik — tanpa model router tidak akan pernah menjadi prosa; jujur di docstring, tapi user akhir mungkin mengharapkan naskah; (3) `CitationAuditAgent` menulis audit JSON bahkan ketika gagal, tapi `OrchestratorAgent` hanya mengembalikan `error_message="Audit failed"` tanpa detail ke pemanggil CLI (audit files perlu dibaca manual — tambahkan ringkasan gagalan di response).

**Deep research:** wrapper tipis; plan hampir sama dengan academic; tidak ada loop discovery-evidence. Simulatif.

---

## 9. Evaluasi Sitasi, Evidence, Anti-Halusinasi

**Anti-halusinasi di level data: kuat.** Source tanpa title dibuang; tidak ada generate-metadata; year None → "n.d."; page/location hanya dari data nyata; evidence verbatim wajib exact match; paraphrase terpisah dan non-citable.

**Anti-halusinasi di level output: bocor di 3 titik.**
1. Token internal lolos (P0-1).
2. Collision author-year tanpa disambiguasi (P0-2) — menghasilkan sitasi ambigu yang tidak bisa di-resolve pembaca = hilangnya traceability.
3. Metadata tidak lengkap ditampilkan seolah sitasi sah (`(Laporan, n.d.)` dari slug judul) — pembaca tidak diberi tahu sumbernya gapan (P1-2).

**Audit trail:** append-only JSONL + report per tahap + `_raw` preservation + telemetry routing. Untuk pemakaian pribadi: cukup untuk rekonstruksi manual, dengan tambahan citation sidecar (rekomendasi §5.15) menjadi sangat kuat.

**Etika topik sensitif (remaja):** tidak ada — lihat §5.16.

---

## 10. Evaluasi Localhost Monitor

**Berfungsi:** GET `/`, `/api/progress`, `/api/check`, `/api/plan`; POST `/api/run-academic` (happy path); progress persisten (JSONL); dashboard menarik; launcher PS1 dengan port-check.

**Tidak berfungsi/berisiko:**
- Dashboard 8 node menampilkan status tahap yang tidak pernah direkam — **pantulan visual, bukan rekaman**. Record hanya 3 event.
- POST path-invalid → koneksi putus tanpa JSON (P1-3).
- CORS `*` tanpa auth (P1-4).
- `python -m src run-academic` (CLI) tidak merekam progress sama sekali — monitor buta terhadap sesi CLI.
- Tidak ada `GET /api/history` atau filter — hanya last 100 events.
- Tidak ada graceful shutdown / port-in-use handling yang informatif.

**Rekomendasi minimal:** record_progress di tiap stage orchestrator (synthesis/outline/writing/audits/docx) — ±8 baris; try/except POST; CORS same-origin. Setelah itu baru dashboard jujur.

---

## 11. Evaluasi Plugin/Skill

**SKILL.md:** jelas, kompatibel Kiro, rules konsisten dengan AGENTS.md. `references/input-json.md` ada. Zip dist: ada tapi akan stale.

**Kekurangan sebagai produk orang awam:** (1) tidak ada command `init`/`example` yang menghasilkan input.json template valid; (2) skema strict membuat trial-and-error menyakitkan; (3) tidak ada penjelasan di skill tentang kesalahan umum (workspace tidak ada → ProjectError hanya di log); (4) zip ter-track git (P2-2).

**Verdict:** cukup untuk *kamu sendiri + AI agent*; belum cukup untuk "orang awam" sungguhan tanpa P2-3 (template generator) dan error yang ramah.

---

## 12. Evaluasi Kesiapan Multi-Device Pribadi

| Aspek | Status |
|---|---|
| Git clone → jalan | ❌ harus rename `DATA BASE` (P0-3) |
| Dependency | ✅ pip install -r requirements.txt cukup |
| Path portability (runtime) | ✅ env override + discovery dinamis |
| Path portability (data) | ⚠️ projects di luar repo (TUGAS x) — tidak ikut clone; backup manual per laptop |
| Config per-laptop | ✅ `system.local.yaml` + `.env` di-gitignore |
| Database/cache/log | ✅ di-gitignore, auto-created |
| Test di lokasi baru | ⚠️ 2 test butuh TUGAS 1 (P2-1) |
| Launcher | ✅ .bat/.ps1 bekerja; ⚠️ tidak ada setup.bat untuk venv |

**Kebutuhan nyata:** dokumen "cara setup laptop baru" 5 langkah + P0-3 diperbaiki = multi-device nyaman. Data project (TUGAS x) perlu strategi sync (folder share/OneDrive/git terpisah) — sekarang tidak ada.

---

## 13. Rekomendasi Perbaikan (bertahap)

### Tahap 1 — Wajib (P0, ±1 hari kerja)
1. Token internal gate di CitationAuditAgent + test. *(P0-1)*
2. Unifikasi citation key (disambiguasi di in-text + audit) + test collision. *(P0-2)*
3. README quick-start: `git clone https://github.com/Chigoov/Agentic-Module.git "DATA BASE"` + error message yang menyarankan solusi. *(P0-3)*
4. `setup.bat` (venv + pip install) dan perbaiki 2 test_paths agar tidak butuh TUGAS 1 fisik. *(P2-1 ikut di sini)*

### Tahap 2 — Penting (P1, ±2-4 hari)
5. `python -m src research` pipeline: Discovery→Verification→Retrieval→Evidence→ClaimVerification→Academic. *(P1-1)*
6. Marker `[sumber belum lengkap]` di writer & reference list. *(P1-2)*
7. Monitor: try/except + validasi path + CORS same-origin + optional token. *(P1-3/4)*
8. Crossref lookup_by_doi 404 → None. *(P1-5)*

### Tahap 3 — Multi-model (P1-6, ±2-5 hari)
9. Adapter Gemini (REST, api_key_env `GEMINI_API_KEY`), capability_map di config, retry/timeout bermartabat; test dengan fake transport. Setelah jalan: sambungkan paraphrase & narrative synthesis (fase 16).

### Tahap 4 — Kualitas akademik (P2)
10. Citation sidecar (key→source_id mapping). 11. Mode detection diperbaiki. 12. Minimum payload validation. 13. Encoding normalisasi §/non-ASCII. 14. Sinkronisasi status tools config vs adapter. 15. `record_progress` di tiap stage.

### Tahap 5 — Opsional
16. GitHub Actions (Windows+Ubuntu) untuk check+pytest. 17. Template input.json generator (`python -m src init`). 18. Untrack dist/. 19. Safeguard topik sensitif (remaja) → force human review. 20. Rotasi progress.jsonl.

---

## 14. Roadmap Lanjutan

**Minggu ini:** Tahap 1 penuh → project jadi *trustworthy by default* untuk penggunaan pribadi.
**2 minggu:** Tahap 2 → klaim "mencari sumber" jadi nyata; monitor jujur.
**Bulan depan:** Tahap 3 (Gemini) → narrative writing hidup; fase 16-18 substansial.
**Setelahnya:** Tahap 4-5 sesuai selera; mulai pertimbangkan GitHub Actions sejak Tahap 1 selesai (mencegah regresi).

---

## 15. Kesimpulan Akhir

**Apakah project ini sudah nyaman dipakai pribadi di beberapa laptop?**

**Belum — tapi jaraknya dekat dan jelas.**

- Untuk **kamu sendiri, di laptop utama, hari ini**: ya, bisa dipakai — dengan dua syarat disiplin: folder bernama `DATA BASE`, dan **proofread manual draft final** untuk token internal/sitasi ganda (karena gate-nya belum ada).
- Untuk **laptop kedua**: belum, sampai P0-3 dibereskan (5 menit perbaikan README + 1 baris error message; plus rename folder saat clone).
- Untuk **mempercayai output tanpa membaca**: belum — P0-1 dan P0-2 harus turun dulu.

**Nilai terbesar project ini** justru pada bagian yang tidak terlihat user: evidence registry, verification engine, storage safety, dan kejujuran status integrasi. **Ancaman terbesar** bagi kredibilitasnya adalah gap antara dokumentasi (yang menjanjikan gate) dan kode (yang belum menjaga). Tutup gap itu dengan Tahap 1, dan klaim-klaim utamamu mulai benar secara teknis — bukan hanya secara niat.

---

*Lampiran lokasi bukti: sandbox uji `VIBE CODING/TUGAS AUDIT_SANDBOX/` (draft & audit JSON skenario A-F), fixture `DATA BASE/state/audit_sandbox/`, log monitor `DATA BASE/state/progress.jsonl`. Keduanya aman dihapus setelah laporan ini dibaca.*
