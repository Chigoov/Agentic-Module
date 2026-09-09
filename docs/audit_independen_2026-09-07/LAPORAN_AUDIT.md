Live progress: http://127.0.0.1:8000

# Audit independen AUTONOMI AGENTIC ILMIAH

Tanggal: 7 September 2026. Fokus: pemakaian pribadi pada beberapa laptop Windows.
Baseline: `99a71bb2eb8e453c3cd94a03a5df71810ad45ae8`. HEAD lokal sama dengan HEAD origin yang diperiksa langsung melalui Git. Remote: https://github.com/Chigoov/Agentic-Module.git.

Ini laporan temuan awal sebelum perbaikan production. Tidak ada source, test bawaan, konfigurasi, launcher, atau dokumentasi lama yang diubah. Berkas audit lama `docs/AUDIT_KESELURUHAN_2026-09-07.md` yang sudah untracked saat audit dimulai dipertahankan. Audit menghasilkan laporan, inventaris, dan probe terpisah. Dokumen adversarial ditempatkan di direktori sementara dan diberi label AUDIT FIXTURE, bukan sumber atau hasil akademik yang boleh digunakan.

## 1. Executive Summary

**Belum nyaman dan belum cukup dapat dipercaya untuk penggunaan pribadi multi-device tanpa pengawasan teknis.** Fondasi program bekerja; jaminan akademik dan pengalaman fresh clone belum bekerja sesuai klaim.

Temuan paling menentukan:

1. Semua test pada checkout utama lulus, tetapi salinan bersih memiliki dua test gagal. Test saat ini bukan bukti kesiapan laptop lain.
2. CLI publik menghasilkan `success=true` dan DOCX untuk klaim penting dengan ID evidence yang tidak ada, tanpa sumber, serta token sitasi internal. Ini kebocoran gate yang nyata, bukan sekadar kekurangan prompt.
3. DOI nyata dengan judul yang sama sekali tidak cocok tetap mendapat `DOI_VERIFIED`, dengan nilai kemiripan judul **0.0**.
4. Pengulangan workflow menimpa perubahan manual pada `draft.md`; pemindahan manifest tidak memperbarui direktori output.
5. Localhost API menerima Origin asing, tidak meminta token, dan menerima direktori output dari request. Loopback merupakan perlindungan jaringan yang berguna, tetapi bukan autentikasi.
6. Fase 7–18 adalah implementasi minimal dengan cakupan yang sangat berbeda. Provider model belum diimplementasikan; deep research belum mencari sumber sendiri.
7. Tidak ditemukan gate etik khusus remaja pada source. Program belum memadai sebagai pengaman operasional pengumpulan data sensitif Edjust.

Yang sudah layak dipertahankan: Pydantic dengan field tambahan ditolak; operasi tulis teks atomik; pemisahan core/schema/tools; adapter bibliografi yang menghasilkan respons jaringan nyata; pemeriksaan kutipan terhadap teks masukan; dan kegagalan eksplisit router saat provider belum tersedia. Tidak perlu menulis ulang seluruh sistem.

**Prioritas bukan menambah jumlah agent. Prioritas adalah membuat output salah ditolak, hasil lama terlindungi, dan fresh clone benar-benar dapat dijalankan.**

## 2. Status Kesehatan Project

| Pemeriksaan | Hasil aktual | Makna |
|---|---|---|
| `python -m src check` pada checkout utama | Exit 0, `[OK]`, build phase 18 | Spec/config/storage dasar lulus; bukan verifikasi mutu penelitian |
| Python | 3.14.5, Windows | Belum membuktikan semua versi Python 3.11+ yang diiklankan |
| Inventaris source | 72 file Python, 10.817 baris | Termasuk initializer dan entry point |
| Import | 71 modul diperiksa, 0 gagal | `__main__` dikecualikan sebagai import karena memiliki efek eksekusi |
| Default model routing | `PENDING_CONFIGURATION`, provider kosong | Selain konfigurasi, client model memang belum ada |
| Adapter bibliografi | PoP, Crossref, OpenAlex, PubMed lolos test integrasi | Tidak membuktikan public `execute()` siap di proses berikutnya |
| Semantic Scholar | Tidak tercakup test integrasi live pada run ini | Status live sekarang tidak diasumsikan dari laporan lama |
| Monitor 8000 awal audit | Connection refused | Link yang ditampilkan belum berarti server hidup |
| Monitor setelah dinyalakan | `/api/check` HTTP 200, success true | Server aktif untuk sesi audit ini |
| Pencarian pola secret terbatas | Tidak ditemukan pola secret yang diperiksa pada source/config/docs/skills | Bukan audit seluruh Git history atau jaminan tidak ada secret |

`health_check()` terutama memeriksa keberadaan spec, validitas config, membuat direktori, dan satu probe tulis pada `state`. Ia tidak mencoba menulis setiap storage, menguji seluruh provider, memeriksa file output, atau menjalankan evaluasi sitasi. Label “system ready” perlu dibatasi menjadi “fondasi lokal siap”.

## 3. Hasil Test

| Perintah/skenario | Hasil |
|---|---|
| `python -m pytest -q --tb=short` | **272 passed, 10 deselected**, 2,52 detik |
| `python -m pytest -m integration -q --tb=short` | **10 passed, 272 deselected**, 19,01 detik |
| Clone GitHub ke direktori baru bernama `Agentic-Module`, environment AUTONOMI dibersihkan | Clone berhasil, health check **gagal**, exit 1 |
| Clone tersebut dengan `AUTONOMI_SYSTEM_ROOT` eksplisit | Health check berhasil |
| Isi commit yang sama di direktori `DATA BASE` dengan parent mengandung spasi | Health check berhasil |
| Virtual environment baru + install requirements | **Berhasil**, exit 0 |
| Test pada salinan bersih `DATA BASE`, menggunakan environment baru | **270 passed, 2 failed, 10 deselected**, 3,48 detik |

Dua kegagalan salinan bersih:

- `tests/test_paths.py:53`: mengharuskan `TUGAS 1`/`TUGAS 2` sudah ada di parent checkout.
- `tests/test_paths.py:62`: mengharuskan direktori `TUGAS 1` ada secara fisik.

Folder workspace tersebut tidak ikut repository. Jadi masalah ini bukan dependency gagal dipasang. Lingkungan baru dibuat pada laptop yang sama; belum dilakukan pengujian fisik di laptop kedua, Windows versi lain, atau semua versi Python yang diiklankan.

### Skenario tambahan di luar test bawaan

“Lolos” di tabel ini berarti diterima program, bukan valid secara ilmiah.

| Skenario | Perilaku aktual | Penilaian |
|---|---|---|
| Topik sederhana | Plan JSON berhasil, satu query berbasis kata kunci | Berfungsi sebagai planner minimal |
| PKM-RSH Edjust | Plan berhasil, tetapi pemotongan delapan keyword membuang konteks perceraian pada query uji | Kurang untuk rencana penelitian substantif; tidak ada pemeriksaan etik |
| Sumber valid | Metadata `Deep learning` diambil langsung dari Crossref menggunakan DOI nyata; DOCX berhasil | Adapter nyata; APA belum lengkap |
| Sumber tanpa metadata lengkap | DOCX sukses dengan penanda `[missing: ...]` dan `n.d.` | Tidak menerapkan `[sumber belum lengkap]` yang diwajibkan |
| DOI tidak valid pada sumber `REJECTED` | Tetap masuk DOCX jika claim dinyatakan supported | Gagal menolak input buruk pada workflow |
| DOI negatif yang tidak ditemukan, melalui VerificationEngine live | `NEEDS_HUMAN_REVIEW`, metadata/content unverified | Perilaku konservatif benar pada jalur engine ini |
| DOI nyata dipasangkan dengan judul berbeda | `DOI_VERIFIED`, title similarity 0.0 | Bug corroboration serius |
| Evidence ID tidak ada | CLI publik exit 0, success true, DOCX dibuat | Gagal referential-integrity gate |
| Evidence bertentangan | Claim conflicted tetap ditulis tanpa uraian pertentangan | Gagal menjaga disclosure dalam naskah |
| Kutipan dan halaman dinyatakan verified oleh input | Fixture kutipan/page diteruskan ke DOCX tanpa membaca dokumen sumber | Provenance dipercaya dari flag |
| Token internal | Bentuk `turn0search0`, `view0`, `search0`, `filecite` bertahan pada output | Tidak ada gate otomatis yang diminta |
| Sitasi nama–tahun tanpa sumber | Citation audit passed | Regex mengaudit format berbeda dari hasil writer |
| Data akademik kosong | `final.docx` hanya berisi kerangka/judul, success true | “Berhasil” tidak mengukur kecukupan hasil |
| Outline bertingkat | Klaim pada subsection hilang, success true | Kehilangan isi diam-diam |
| Rerun setelah edit manual draft | Sentinel edit hilang, tidak ada backup draft | Risiko kehilangan kerja nyata |
| Backup dua kali pada detik sama | Nama backup sama; salinan pertama hilang | Backup tidak menjamin versi unik |
| Manifest disalin ke direktori baru | `ProjectManager.load()` tetap mengembalikan path lama | Output bisa kembali ke lokasi lama |
| Localhost POST dengan Origin asing, tanpa token | HTTP 200 dan menulis artifact pada folder fixture pilihan request | Kontrol akses lokal belum cukup |
| POST JSON rusak | Koneksi ditutup tanpa respons JSON terstruktur | Pengalaman kegagalan buruk; server induk tetap hidup |
| Progress satu run academic via API | Hanya `academic/running` dan `academic/success` | Bukan rekaman seluruh stage |
| Public Crossref di proses baru | `NOT_IMPLEMENTED`, success false | Test integrasi menembus wrapper dengan `_execute()` |
| JSON provider valid >200.000 karakter | Terpotong sebelum parse, kemudian dianggap INVALID_JSON | Bug ukuran respons |
| Retrieval abstrak saja | State menjadi `FULLTEXT_RETRIEVED` | Label bukti terlalu tinggi |
| Retrieval `file:` pada file fixture aman | Konten file lokal terbaca | Perlu batas skema URL dan mode impor lokal eksplisit |
| API key dummy hanya di `.env` | Nama env setting dimuat, nilai key tidak ditemukan | Loader `.env` tidak memasok getter key |
| Context dry-run untuk audit | Daftar file terpilih kosong | Kebijakan context hanya terhubung untuk beberapa kategori |
| Validator tanpa kasus | success true, passed/failed kosong | Harness kosong bukan validasi E2E |
| Skill ZIP | Berisi dua file instruksi; SKILL sama dengan repository | Tidak membawa runtime/dependency/bootstrap |

Bukti mentah: `probe_results.json`, `portability.json`, `packaging.json`, `import_check.json`. Probe dasar dapat diulang dengan `python docs/audit_independen_2026-09-07/reproduce.py`. Sebagian probe tambahan pada tabel dicatat terpisah selama audit; script dasar bukan suite regression lengkap dan menjalankannya ulang akan mengganti file hasil probe dasar.

## 4. Temuan Bug/Risiko Berdasarkan Prioritas

Definisi: **P0** darurat/kegagalan katastrofik terbukti; **P1** wajib sebelum pemakaian rutin yang dipercaya; **P2** perbaikan penting pada stabilisasi berikut; **P3** penyederhanaan/kenyamanan. Tidak ditemukan P0 yang cukup terbukti dalam lingkup lokal ini. Tidak ada klaim remote code execution atau kebocoran data nyata.

### A01 — P1: Status claim/source/evidence dari input melewati verifikasi

**File:** `src/runtime/cli.py:74`, `src/workflows/orchestrator.py:48`, `src/schemas/claim.py:162`, `src/agents/writer.py:87`, `src/agents/audit.py:69`.

**Masalah:** Orchestrator langsung synthesis → outline → writer. Tidak menjalankan verification, retrieval, atau claim verification. Claim penting cukup mempunyai daftar ID supporting evidence yang tidak kosong; ID tersebut tidak harus merujuk evidence nyata. Writer juga tidak menolak source `REJECTED`. Flag `quote_verified` dan locator dipercaya tanpa membaca sumber.

**Dampak:** Input dari manusia atau AI lain dapat membawa fakta/kutipan/sumber salah sampai final dengan status lolos audit. Sistem tidak menciptakan data palsu sendiri pada probe, tetapi melegitimasinya sebagai output terverifikasi.

**Perbaikan minimal:** Satu validasi bersama sebelum writer: ID unik; referensi claim→evidence→source benar; sumber memenuhi status dan bukti verifikasi; quotation diverifikasi ulang terhadap snapshot teks; source count diterapkan. Status input bukan bukti. Gunakan evaluator dan registry yang sudah ada, dengan pemeriksaan provenance sebelum evaluasi.

**Acceptance:** Payload CLI probe ID tidak ada, sumber ditolak, quote flag tanpa snapshot harus gagal sebelum menghasilkan final. Status supported tidak dapat ditentukan hanya dengan mengedit JSON.

### A02 — P1: Citation audit tidak mengaudit format yang ditulis

**File:** `src/tools/citation_manager.py:25`, `src/agents/audit.py:43`, `src/agents/writer.py:173`, `src/tools/docx_generator.py:34`.

**Masalah:** Regex mencari kunci seperti `smith2012`, sementara writer menghasilkan `(Smith, 2012)`. Sitasi nama–tahun tanpa sumber lolos. Tidak ada pemeriksaan token internal di body, judul, heading, kutipan, maupun reference list. DOCX hanya mempercayai dua boolean audit.

**Dampak:** Gate tampak kuat tetapi tidak memeriksa kategori kesalahan yang paling mungkin berasal dari output AI.

**Perbaikan minimal:** Pertahankan ledger sitasi terstruktur saat rendering, cocokkan sumber dan bibliography melalui ID yang sama; tambahkan detektor token internal bersama pada seluruh teks yang diekspor. Jangan sekadar mengganti token menjadi sitasi APA atau menghapus token otomatis karena sumbernya mungkin tidak diketahui.

**Acceptance:** Seluruh varian token internal dan citation orphan ditolak di jalur CLI/API/export. Satu sumber sah menghasilkan citation dan reference yang konsisten.

### A03 — P1: DOI lookup mengabaikan kecocokan metadata

**File:** `src/tools/verification_tool.py:198`, `src/tools/verification_tool.py:150`, `src/tools/verification_tool.py:240`.

**Masalah:** Cabang DOI langsung mengembalikan record lookup. Threshold judul hanya dipakai pada cabang bibliographic search. Semua corroboration dicatat PASSED dan nilai kandidat lebih diutamakan saat merge.

**Bukti:** DOI artikel nyata dengan judul fixture yang tidak cocok mendapat `DOI_VERIFIED`; similarity 0.0. Tahun kandidat yang salah tetap dipertahankan dalam corroborated metadata.

**Dampak:** DOI valid milik artikel lain dapat menjadi legitimasi metadata salah. Keberadaan DOI tidak identik dengan identitas artikel yang diklaim.

**Perbaikan minimal:** Berlakukan pembandingan identitas pada kedua cabang; periksa judul, penulis, tahun dan DOI. Ketidaksesuaian material menghasilkan review, bukan backfill seolah benar. Simpan record provider dan perbedaannya.

### A04 — P1: Konflik dan kekuatan evidence tidak menjadi pembatas naskah

**File:** `src/schemas/claim.py:89`, `src/agents/synthesis.py:78`, `src/agents/writer.py:118`, `src/workflows/evidence_flow.py:159`.

**Masalah:** `CONFLICTED` dan `PARTIALLY_SUPPORTED` termasuk writable. Qualifier opsional. Synthesis memberi flag konflik tetapi writer tidak memakai temuan synthesis untuk menguraikan dua sisi; bukti kontradiktif nonkutipan dapat tidak muncul sama sekali. Nilai confidence dihitung dari aturan bobot, bukan kalibrasi empiris atas kebenaran semantik.

**Dampak:** Naskah dapat menyatakan kesimpulan tegas ketika evidence terbatas/bertentangan. Dua record source dari publikasi yang sama juga tidak otomatis merupakan dua sumber independen.

**Perbaikan minimal:** Wajibkan qualifier/disclosure terstruktur atau human review untuk konflik material. Jangan menyatakan `conflicts_disclosed` sebelum disclosure masuk naskah. Jelaskan confidence sebagai skor heuristik, bukan probabilitas kebenaran.

### A05 — P1: Rerun dapat menghilangkan output dan mengaburkan versi

**File:** `src/agents/writer.py:148`, `src/agents/audit.py:48`, `src/core/storage.py:183`, `src/tools/docx_generator.py:42`.

**Masalah:** Draft dan audit ditulis dengan overwrite; draft sudah disimpan sebelum audit selesai. DOCX mempunyai backup, tetapi nama backup hanya sampai detik dan DOCX ditulis langsung ke target. Run gagal berikutnya dapat meninggalkan final lama di sebelah audit baru yang gagal.

**Dampak:** Edit pengguna hilang; output dari run berbeda bercampur; kegagalan saat menyimpan DOCX berpotensi merusak file target. Tidak dilakukan pemutusan listrik nyata; risiko DOCX terputus disimpulkan dari operasi write langsung.

**Perbaikan minimal:** Folder output per run atau backup unik sebelum semua penggantian file pengguna; tulis DOCX ke sibling temp lalu replace. Satu manifest run mengikat input, audit, dan output. Jangan mempromosikan final sebelum seluruh gate berhasil. Mulai dengan satu writer per project.

### A06 — P1: Localhost API menerima penulisan tanpa autentikasi dan batas root tepercaya

**File:** `src/runtime/monitor.py:120`, `src/runtime/monitor.py:146`, `src/runtime/monitor.py:186`, `src/schemas/project.py:105`.

**Masalah:** CORS `*`, OPTIONS permisif, tidak ada token/Origin/Host guard; root output diambil dari request. `ensure_within(path, root=project.directory)` tidak melindungi apabila root itu sendiri ditentukan request tidak tepercaya.

**Bukti:** HTTP POST dengan Origin asing dan tanpa token berhasil menulis artifact ke direktori fixture di luar workspace yang dikonfigurasi. Hanya folder sementara milik audit yang digunakan.

**Dampak:** Proses lokal lain dapat membuat/menimpa nama artifact pada folder yang dapat ditulis pengguna. Akses dari halaman web bergantung juga pada pembatasan browser; audit ini membuktikan kelemahan server, bukan eksploitasi browser lintas-origin pada seluruh browser.

**Perbaikan minimal:** Tetap loopback; token acak lokal untuk endpoint sensitif; allowlist Origin/Host; root project ditetapkan server; validasi path sebelum mkdir. Hilangkan wildcard CORS jika tidak diperlukan. Tidak perlu akun pengguna, OAuth, atau deployment publik.

### A07 — P1: Panduan clone dan format manifest belum portable

**File:** `src/core/paths.py:72`, `docs/CARA_MEMBAGIKAN_PROJECT.md:10`, `src/core/project_manager.py:196`, `src/schemas/project.py:105`, `tests/test_paths.py:48`.

**Masalah:** Root dideteksi berdasarkan nama `DATA BASE`; panduan menggunakan folder default `Agentic-Module`. Manifest menyimpan path absolut dan load tidak rebase. Test mengandalkan sibling workspace lokal.

**Dampak:** Setup awam gagal; pemindahan data dapat tetap menulis ke lokasi lama atau membuat ulang path lama. Git clone saja tidak membawa hasil penelitian di luar repository.

**Perbaikan minimal:** Pilih satu kontrak root yang konsisten—deteksi marker repo atau launcher menyetel root dirinya sendiri—dan revisi panduan. Saat load, direktori manifest aktual menjadi dasar output; simpan pointer project/retrieval relatif. Buat workspace lewat langkah setup eksplisit; test membuat workspace temporary sendiri.

### A08 — P1: Public research tools tetap ditolak setelah test integrasi sukses

**File:** `src/tools/research_tool.py:117`, `src/tools/base.py:136`, `src/tools/publish_or_perish.py:316`, `src/agents/research.py:142`.

**Masalah:** Status HTTP research tool bergantung flag class yang diubah test; proses baru kembali NOT_IMPLEMENTED. Test jaringan memakai `_execute()`, melewati public wrapper. VerificationAgent default sengaja memakai `VerificationEngine(providers=[])`. Sebaliknya lookup langsung dapat memakai jaringan tanpa menghormati `enabled=false`.

**Dampak:** README “VERIFIED” benar untuk run historis/adaptor, tetapi tidak sama dengan siap dipanggil pengguna. Konfigurasi disabled dan keberhasilan test memiliki arti tidak konsisten.

**Perbaikan minimal:** Pisahkan “implemented/configured/callable” dari “pernah diverifikasi live”. Public execute boleh mencoba ketika dikonfigurasi; sukses/failed mencatat hasil aktual per run. Hormati enabled di jalur search maupun lookup. VerificationAgent gunakan provider aktif yang tersedia; beri kegagalan jelas bila tidak ada.

### A09 — P1 khusus penggunaan lapangan Edjust: Safeguard etik belum operasional

**File:** `src/agents/research.py:63`, `src/schemas/project.py:61`, `src/workflows/academic.py:40`, `AGENT_CONSTITUTION.md`.

**Masalah:** Tidak ditemukan field/gate yang membedakan penelitian literatur dengan pengumpulan data remaja, consent/assent, kerahasiaan, distress response, retensi data, atau persetujuan etik. Istilah remaja pada test CLI hanya menjadi topik plan.

**Dampak:** Pengguna awam dapat mengira aturan anti-halusinasi juga mencakup perlindungan partisipan. Risiko meningkat bila respons pribadi anak dikirim ke model/cloud atau direkam utuh di log.

**Perbaikan minimal:** Profil penelitian sensitif dan checklist operasional yang wajib dipenuhi sebelum materi siap dipakai untuk pengumpulan data; anonim/pseudonim sesuai desain, izin relevan dan assent, hak melewati pertanyaan/berhenti, penanganan distress dan rujukan, batas akses/retensi, review pembimbing/etik. Tidak perlu workflow persetujuan partisipan untuk sekadar eksplorasi literatur; bedakan tahapnya.

### A10 — P2: Formatting belum memenuhi APA 7 secara utuh

**File:** `src/tools/reference_formatter.py:40`, `src/tools/reference_formatter.py:95`, `src/tools/reference_formatter.py:116`, `src/tools/reference_formatter.py:163`, `src/tools/docx_generator.py:45`.

**Masalah:** Nama penulis dari provider tidak dinormalisasi menjadi bentuk reference APA; `.title()` mengubah kapitalisasi seperti LeCun. Volume/issue/pages yang ada pada metadata diabaikan. Semua jenis sumber memakai satu template. Tidak ada urutan alfabet, pemetaan suffix tahun konsisten untuk penulis/tahun sama, italics atau hanging indent. Collision resolution manager tidak dipakai oleh formatter; dua reference dapat memiliki key sama. Kasus >20 penulis masih menyisipkan ampersand sesudah ellipsis. `[sumber belum lengkap]` belum diterapkan. Draft Markdown tidak membawa reference list; daftar pustaka hanya ditambahkan saat DOCX export.

**Dampak:** Dokumen terlihat mempunyai sitasi, tetapi rujukan ambigu/tidak lengkap. Naskah `--no-docx` tidak memenuhi paket final sitasi + daftar pustaka.

**Perbaikan minimal:** Batasi dahulu jenis sumber yang benar-benar didukung, gunakan metadata yang telah tersedia, satu pemetaan ID→label untuk body dan reference, penanda sumber belum lengkap yang konsisten, serta renderer reference bersama untuk Markdown/DOCX. Jangan menebak nama keluarga atau halaman ketika metadata tidak memadai.

### A11 — P2: Artefak audit trail tidak disimpan utuh pada jalur akademik

**File:** `src/workflows/orchestrator.py:48`, `src/workflows/academic.py:40`, `src/schemas/project.py:34`, `src/routing/telemetry.py:13`.

**Masalah:** Run probe menghasilkan hanya draft, dua audit, dan final. Input, research plan, verified sources, claims/evidence, outline, snapshot retrieval dan identitas run tidak otomatis tersimpan bersama. Telemetry model tidak memuat waktu/durasi/cost/run ID dan tidak mencatat penolakan router yang terjadi sebelum `_execute()`.

**Dampak:** Audit JSON passed tidak cukup untuk merekonstruksi dasar klaim atau membuktikan sitasi bukan hasil input yang dikarang. Kolom provenance yang tersedia belum menjadi rantai bukti wajib.

**Perbaikan minimal:** Snapshot input tervalidasi, record provider utuh, dokumen asli, hash, relasi ID, lokasi evidence, alasan keputusan, versi kode dan output per run. Hash membuktikan konsistensi berkas, bukan dengan sendirinya kebenaran sumber. Tidak perlu blockchain atau database terdistribusi.

### A12 — P2: JSON provider valid dipotong sebelum parsing

**File:** `src/tools/http_client.py:177`, `src/tools/http_client.py:206`.

**Masalah:** Body dipotong pada 200.000 karakter, lalu `get_json()` mencoba parse string terpotong. Respons test valid dengan payload 210.000 karakter menjadi INVALID_JSON. `response.read()` sebelumnya tidak dibatasi, sehingga pemotongan ini juga bukan pembatas konsumsi memori jaringan.

**Dampak:** Search lebih besar gagal meskipun API normal.

**Perbaikan minimal:** Pisahkan payload untuk parse dan cuplikan log. Terapkan batas ukuran baca eksplisit dengan error `RESPONSE_TOO_LARGE`, jangan membuat JSON valid menjadi invalid secara diam-diam.

### A13 — P2: Retrieval belum memberikan tingkat bukti yang dijanjikan

**File:** `src/tools/retrieval.py:90`, `src/tools/retrieval.py:114`, `src/tools/retrieval.py:130`, `src/tools/evidence_extractor.py:70`, `src/agents/research.py:205`.

**Masalah:** Abstrak didahulukan meskipun URL full text ada, kemudian diberi state FULLTEXT_RETRIEVED. PDF disimpan tetapi tidak diparse. HTML parser menggabungkan semua text termasuk script/style. Extractor tidak menghitung char offsets walaupun docstring mengklaim exact span; locator default “retrieved content” diterima sebagai precise. Skema URL, redirect, private addresses, dan ukuran respons tidak dibatasi.

**Dampak:** Abstract dapat disalahartikan sebagai full text; lokasi evidence tidak benar-benar presisi; halaman/script tidak relevan masuk teks; retrieval agent dapat melaporkan success walau PDF tidak menghasilkan teks.

**Perbaikan minimal:** Bedakan abstract/fulltext/parsed, simpan asal dan lokasi sebenarnya, blockquote hanya untuk locator yang dapat diverifikasi. Tambahkan parser PDF hanya ketika penggunaan PDF nyata memerlukannya. URL remote hanya http/https dengan batas alamat/ukuran yang sesuai; impor file lokal menjadi jalur eksplisit dan terbatasi.

### A14 — P2: Dashboard mencampurkan history dengan status run aktif

**File:** `src/runtime/monitor.py:91`, `src/runtime/monitor.py:104`, `src/runtime/monitor.py:171`, `src/runtime/progress.py:29`, `src/runtime/cli.py:123`.

**Masalah:** Event hanya ditulis endpoint check/plan/academic. CLI dan nested agents tidak merekam progress. Status Running ditentukan dari adanya event running mana pun dalam history, termasuk run yang sudah success. Persentase berasal dari jumlah stage sukses historis dibagi delapan stage gambar; bukan jumlah tahap run sekarang. “Efisiensi” menggunakan angka yang sama dan animasi dekoratif. Seluruh JSONL dibaca ulang sebelum diambil 100 terakhir. Breakpoint responsif disetel 1 px.

**Dampak:** Dashboard dapat tampak bekerja/efisien ketika tidak ada kerja aktif, atau tidak memperlihatkan kerja CLI. Data lama bercampur dengan run baru; tampilannya belum nyaman pada layar sempit.

**Perbaikan minimal:** Instrumentasi di titik eksekusi bersama yang sudah ada, `run_id`, stage start/end, waktu dan latest status per run; tampilkan hanya metrik terukur. Perbaiki breakpoint. Jangan memasukkan naskah/respons remaja ke progress log. Label manual audit event dengan jelas.

### A15 — P2: API error handling dan operasi bersamaan belum kuat

**File:** `src/runtime/monitor.py:186`, `src/runtime/bootstrap.py:89`, `src/core/storage.py:137`, `src/core/evidence_registry.py:74`.

**Masalah:** Parse Content-Length/JSON/schema di luar error boundary; request malformed menutup koneksi tanpa error JSON. Tidak ada batas body, timeout baca, atau penguncian run per project. Threading server dapat menulis path yang sama. Probe health memakai nama file tetap; JSONL tidak toleran trailing line yang terputus dan baca seluruh file. Evidence registry skip ID yang sudah tersimpan, sehingga perubahan record di memori dapat tidak dipersist melalui `save()` default.

**Dampak:** Klik/panggilan ganda, file log terputus, dan input salah menghasilkan status rancu atau race/lost update. Concurrency/power-loss belum diuji destruktif pada data pengguna; risiko tersebut berasal dari struktur kode.

**Perbaikan minimal:** Respons 400/413 terstruktur; batas payload; satu run aktif per project dengan pesan busy; idempotency/run ID sederhana; probe file unik; definisikan immutable evidence atau versioned correction. Jangan menambah queue terdistribusi untuk kebutuhan pribadi.

### A16 — P2: Konfigurasi `.env` dan flag tidak konsisten dengan perilaku

**File:** `src/core/config.py:167`, `src/core/config.py:187`, `src/core/config.py:316`, `config/system.yaml:44`, `src/tools/crossref.py:45`, `src/tools/pubmed.py:66`.

**Masalah:** `.env` dibaca untuk overlay prefiks AUTONOMI, tetapi getter key/email hanya membaca `os.environ`. API key dummy yang hanya ada di `.env` tidak ditemukan. Beberapa flag evidence/writing tidak dibaca consumer; base_url API hardcoded mengabaikan config; request timeout tidak selalu diterapkan; API key PubMed tidak dikirim oleh adapter.

**Dampak:** Setting terlihat tersedia tetapi tidak memengaruhi runtime. Ini menyulitkan troubleshooting antar laptop dan integrasi model.

**Perbaikan minimal:** Satu sumber konfigurasi efektif termasuk secret lookup, tanpa mencetak key; uji dengan nilai dummy. Hapus setting yang tidak didukung atau hubungkan consumer yang nyata.

### A17 — P2: Fase dinyatakan selesai melampaui fungsi aktual

**File:** `BUILD_PLAN.md:37`, `src/routing/model_router.py:160`, `src/workflows/deep_research.py:42`, `src/workflows/validation.py:35`, `src/workflows/optimization.py:30`, `src/agents/writer.py:110`.

**Masalah:** Provider client tidak ada; deep research adalah plan + academic wrapper; validator adalah runner boolean, bahkan kosong sukses; optimization hanya agregasi sederhana; orchestrator tanpa research/retry/revision loop. Writer tidak berjalan ke subsections sehingga klaim hilang walaupun schema mendukung nesting.

**Dampak:** Pemakai awam membaca “SELESAI” sebagai kemampuan substantif lengkap. Banyak test membuktikan kontrak/fungsi minimal, bukan acceptance yang ditulis di roadmap.

**Perbaikan minimal:** Perbaiki silent omission subsection; deklarasikan cakupan per capability secara jujur. Label writer sebagai assembler dan deep research sebagai scaffold hingga discovery→evidence→audit benar-benar terhubung. Tolak validasi tanpa kasus.

### A18 — P2/P3: Batas path tambahan, duplikasi, context dan packaging

**File:** `src/core/project_manager.py:145`, `src/core/paths.py:216`, `src/tools/dedupe.py:87`, `src/agents/research.py:114`, `src/context/dry_run.py:154`, `src/context/__init__.py`, `OPEN_LIVE_PROGRESS.ps1:1`, `dist/autonomi-agentic-ilmiah-skill.zip`.

**Masalah dan dampak:**

- P2: ProjectManager tidak memvalidasi `name`/path project sebelum membuat direktori; nama dengan traversal dapat menimbulkan efek filesystem sebelum guard pada write. Workspace hanya menolak exact SYSTEM_ROOT, bukan seluruh turunannya. Perlu containment sebelum mkdir, validasi nama Windows, dan batas system subtree.
- P3: Discovery memakai dedupe sendiri yang lebih lemah daripada helper existing. Helper existing juga tidak menyatukan record DOI vs tanpa DOI walau docstring mengklaim demikian. Identitas publikasi harus disatukan tanpa menyembunyikan konflik metadata.
- P3: Context dry-run hanya memetakan tiga kategori; audit/verification/writing dapat memilih nol berkas. Ukuran dibaca relatif cwd, sementara default rules lain tidak dipakai oleh dry-run; beberapa ekspor `__all__` tidak di-bind. Layer ini belum terhubung ke provider model. Hindari menambah registry memory sebelum kebutuhan runtime ada.
- P2 kenyamanan: Launcher memakai `python` global, pemeriksaan port hanya TCP, jeda tetap dua detik, tidak memastikan layanan di port adalah Autonomi, tidak memberi setup venv/dependency diagnostics. Port terisi aplikasi lain dianggap monitor sudah hidup.
- P3: Plugin lokal berada di luar checkout dan manifest hanya menunjuk skill, tanpa runtime. ZIP hanya SKILL dan input reference. Instalasi skill tidak memasang Python/dependency atau menentukan checkout pada laptop baru.
- P2 dokumentasi akademik: `docs/CARA_MENGGUNAKAN_CODE.md` memberi contoh sumber generik dan mengatur APPROVED, SUPPORTED serta quote_verified secara manual tanpa verifikasi. Contoh harus diberi label fixture yang tidak boleh menjadi penelitian, dan panduan pemakaian nyata harus menunjukkan cara mendapatkan status dari bukti, bukan mengisi flag.

**Perbaikan minimal:** Reuse helper nyata setelah memperbaiki edge case; satukan parsing payload CLI/API; gunakan interpreter venv eksplisit dan readiness `/api/check` yang mempunyai identitas layanan; satu panduan setup multi-device. Tidak perlu installer komersial, PyPI, marketplace publik, atau framework orchestration baru.

## 5. Jawaban Pertanyaan Audit Kritis

| Pertanyaan | Jawaban jujur |
|---|---|
| Benar-benar agentic? | Pada runtime repo: **workflow deterministik dengan wrapper bernama agent**. Nama kelas bukan masalah; belum ada pemilihan aksi adaptif, evaluasi hasil pencarian, replanning, atau loop model/tool. Host AI seperti Codex dapat bertindak agentic di luar repo; itu bukan kemampuan otonom engine ini. |
| Fase 7–18 selesai secara substansi? | **Tidak secara keseluruhan.** Ada modul konkret dan test minimal; lihat tabel fase di bagian 7. Fase 9 belum provider-ready, 15 belum deep research E2E, 16 harness, 17 agregator, 18 monitor parsial. |
| Mencari sumber → sitasi → daftar pustaka E2E? | **Belum.** Search adapter nyata dan formatter nyata ada, tetapi CLI academic mulai dari JSON yang sudah disediakan dan melewati verifikasi provenance. |
| Plugin cukup bagi orang awam? | Skill instruction package yang sah dan berguna untuk host AI, **belum paket aplikasi mandiri**. Memerlukan repo, Python, dependency, setup root, dan host AI. |
| Monitor merekam semua tahap? | **Tidak.** Terbukti hanya dua event academic pada satu run API. CLI tidak mengirim event sendiri. |
| Ada gate token internal? | **Tidak.** Kebijakan dokumentasi belum menjadi validasi export. |
| Model/provider nyata? | **Belum.** Bahkan setelah config diisi, `_execute()` mengembalikan PROVIDER_CLIENT_NOT_IMPLEMENTED. |
| Minimal layak pribadi multi-device? | Fresh setup konsisten; test tidak bergantung folder lokal; root/manifest portable; output per run/backup; gate provenance/citation; localhost terbatasi; dokumentasi runtime vs scaffold jujur. |
| Risiko terbesar bagi awam? | Mempercayai `success=true`, `audit passed`, atau dashboard animasi sebagai bukti sumber/klaim benar dan naskah siap diserahkan. |
| Perubahan terkecil paling berdampak? | Gate terpusat sebelum export untuk relasi source/evidence/claim, token internal, dan kecukupan input; lalu perlindungan rerun. Regex token saja membantu tetapi tidak menutup kebocoran evidence. |
| API perlu token lokal? | **Ya, ringan**, mengingat endpoint menulis berkas dan CORS terbuka. Token + root server + Origin/Host allowlist sudah proporsional. |
| Clone tanpa path khusus? | Tidak mengikuti panduan default saat ini. Override root atau nama DATA BASE mengatasi bootstrap, tetapi manifest/workspace masih perlu dibenahi. |
| Spasi dan launcher Windows portable? | Spasi berjalan pada uji. Nama root, interpreter global, readiness port, dan manifest absolut adalah masalah sebenarnya. Unicode/UNC/long path dan laptop fisik lain belum diuji. |
| Perlu GitHub Actions? | **Ya, kecil saja.** Test offline + check pada clean checkout Windows; integration jaringan/PoP terpisah dan kondisional. Tidak ada workflow CI yang dilacak pada commit ini. |
| Audit trail membuktikan tidak dikarang? | **Belum.** Struktur provenance ada, tetapi snapshot, relasi, lokasi, verifikasi dan output belum diwajibkan/diikat per run. |
| Safeguard remaja cukup? | **Belum untuk data lapangan.** Aturan akademik umum tidak menggantikan rancangan etik, izin/assent, privasi dan distress protocol. |

## 6. Catatan Source Code Per File

Inventaris lengkap semua 72 file source, hash baseline dan lokasi simbol ada di `source_inventory.json`. Catatan substantif per file ada di `CATATAN_PER_FILE.md`, termasuk source yang tidak mempunyai finding blocker. Catatan tidak menyatakan file bebas bug; pemeriksaan statis dan skenario terpilih bukan pembuktian formal semua input.

37 file test diinspeksi melalui peta cakupan/skenario; seluruh suite 282 kasus terdaftar dijalankan dalam dua kelompok. Test paling kuat saat ini meliputi schema, path helper dan storage atomik. Gap utama: adversarial public CLI/API, citation formatter vs citation auditor, input status forgery, clone bersih, snapshot provenance, output rerun dan kasus penelitian sensitif. Integration yang memakai `_execute` tidak cukup menguji kontrak pemakaian publik.

## 7. Evaluasi Arsitektur

Pemisahan direktori sudah masuk akal dan dependency runtime kecil. Masalah terbesarnya bukan ukuran file, melainkan **komponen yang masing-masing tampak benar tetapi jaminannya tidak tersambung pada jalur publik**.

Alur aktual:

```text
CLI/API menerima Project + Sources + Claims + Evidence + Outline
  → Synthesis deterministik (membaca status claim)
  → Outline deterministik / memakai outline input
  → Writer menyusun teks dan menyimpan draft
  → Citation audit regex + fact audit status
  → DOCX bila dua boolean lolos
```

Search, metadata verification, retrieval, evidence extraction, claim verification dan context selection tersedia sebagai komponen terpisah, tetapi tidak terangkai otomatis pada alur di atas. State-transition tables tersedia tetapi sebagian jalur memanggil schema transition langsung; workflow task state, review dan resume belum menjadi kontrol eksekusi yang menyeluruh.

| Fase | Status substantif berdasarkan kode |
|---|---|
| 7 Research Agents | Koordinator konkret minimal. Planner heuristik; discovery hanya dedupe kandidat input; verification default tanpa provider. |
| 8 Orchestrator | Merangkai tahap akhir. Tidak melaksanakan research/retry/revision/human-review loop sebagaimana deliverable roadmap. |
| 9 Model Provider & Routing | Kontrak, lookup mapping dan telemetry kegagalan; **client provider/fallback belum ada**. |
| 10 Synthesis + Outline | Agregasi record dan pengelompokan claim; belum sintesis semantik lintas studi. Artifact tidak otomatis dipersist oleh alur utama. |
| 11 Writing Engine | Assembler nyata; bukan penulis akademik model-driven; gate input dan subsection bermasalah. |
| 12 Citation + Fact Audit | JSON audit nyata, pemeriksaan substantif tidak mencukupi; tidak ada revision loop. |
| 13 DOCX | Export dasar nyata; bukan formatter APA lengkap atau transaksional. |
| 14 Academic Writing | E2E **dari input yang sudah disiapkan ke DOCX**, bukan dari topik ke penelitian terverifikasi. |
| 15 Deep Research | Wrapper plan + academic; tidak melakukan multi-provider discovery/fulltext/conflict synthesis sendiri. |
| 16 E2E Validation | Harness callable boolean; test minimal menggunakan lambda; bukan benchmark kasus akademik nyata yang diwajibkan. |
| 17 Optimization | Ringkasan token/status dan saran tetap; tidak mengukur/mengoptimalkan latency, quality, caching, concurrency atau biaya aktual. |
| 18 Monitor | API nyata, visualisasi parsial/dekoratif; belum observability semua tahap. |

Saya merekomendasikan label `SEBAGIAN` atau `MINIMAL` dengan acceptance yang belum terpenuhi, bukan menghapus pekerjaan yang sudah ada. Deterministic workflow sendiri tetap bisa sangat berguna untuk penggunaan pribadi bila jaminan input/output benar.

## 8. Evaluasi Workflow Akademik

Pekerjaan yang masih manual: menyusun research question; mengelola strategi query; memilih sumber sah; memperoleh isi; memilih passage; menilai relevansi dan inferensi; memberi label hubungan evidence; menetapkan claim status; memastikan locator; menyiapkan JSON dan memeriksa hasil Word.

Untuk topik sederhana, `plan` berguna sebagai representasi tugas awal, tetapi belum menghasilkan rumusan masalah, kriteria inklusi, strategi tahun, atau pencarian. Untuk Edjust, query terpotong dapat kehilangan konteks inti. Jangan mengubah judul penelitian yang telah disetujui hanya karena planner heuristik menghasilkan keyword lain; simpan judul/input asli dan revisi query secara terpisah.

Syarat minimum naskah final: setidaknya ada isi relevan; klaim yang masuk tercakup outline termasuk subsection; sumber terverifikasi dan evidence dapat diakses; tidak ada claim penting yang melampaui evidence; semua kutipan punya lokasi nyata; semua citation punya reference; metadata kurang ditandai; audit dan output berasal dari run yang sama. Mode draft boleh menampung kekurangan, tetapi tidak boleh disebut final approved.

## 9. Evaluasi Sitasi, Evidence, dan Anti-Halusinasi

Ada tiga tingkat berbeda yang saat ini mudah tercampur: **publikasi ditemukan**, **metadata cocok**, dan **isi mendukung klaim**. DOI lookup hanya membantu dua tingkat pertama; string containment hanya memastikan kutipan terdapat di teks masukan; tidak membuktikan teks masukan itu asli, locator benar, atau klaim terdukung.

Gate minimum yang diperlukan:

1. Identitas sumber cocok dengan respons provider yang disimpan; ketidaksesuaian material tidak ditimpa diam-diam.
2. Evidence menunjuk snapshot dengan hash dan lokasi yang benar. Kutipan langsung dicocokkan ulang terhadap snapshot tersebut.
3. Hubungan support/contradiction dinilai secara eksplisit; label input AI bukan bukti independen. Wording tidak lebih kuat daripada evidence.
4. Citation dibangun dari source ID yang sama untuk body dan bibliography; tidak ada collision author–year yang ambigu.
5. Semua area export dipindai terhadap token internal. Yang tidak bisa dilengkapi ditandai **`[sumber belum lengkap]`**, bukan diberi DOI/page tebak-tebakan.
6. Finalisasi ditolak apabila masih ada kegagalan wajib. Simpan draft diagnostik secara terpisah.

Untuk Edjust, temuan keberadaan safeguard repo didasarkan pada inspeksi source, bukan asumsi legal. Rekomendasi etik mengacu pada UNICEF yang menekankan ethics review, safeguarding, meaningful consent/assent, privacy dan data management; pedoman tersebut relevan sebagai acuan desain, bukan klaim bahwa repo sudah mematuhi suatu sertifikasi. Lihat [UNICEF, Policy on Ethics in Evidence Activities Involving People as Participants or Subjects](https://www.unicef.org/documents/policy-ethics-evidence-activities-involving-people-as-participants-subjects) dan [UNICEF Innocenti, Researching Sensitive Topics Involving Children](https://www.unicef.org/innocenti/reports/researching-sensitive-topics-involving-children).

Hak melewati pertanyaan/berhenti, bahasa tidak menyalahkan atau menstigma, wawancara aman, penanganan distress dan rujukan harus dirancang manusia sebelum pengumpulan data. Pengecualian persetujuan/konflik wali tidak diputuskan otomatis oleh agent; itu perlu prosedur institusi yang relevan. Jangan mengirim identitas atau cerita sensitif anak ke beberapa model secara default.

## 10. Evaluasi Localhost Monitor

Monitor bermanfaat sebagai API lokal dan tampilan log ringan. Ia belum membuktikan bahwa agent otonom sedang memilih tool. Tulisan “Web, Python, API”, feedback loop, dan efisiensi tidak berasal dari capability/measurement aktual.

Pada audit ini server 8000 awalnya tidak aktif, kemudian dinyalakan dan health endpoint diverifikasi. Skenario penulisan Origin asing dan malformed JSON menggunakan server uji terpisah di port ephemeral, sehingga tidak menulis output penelitian pengguna melalui server aktif. Event audit manual diberi `origin=manual_audit_update`; itu bukan bukti instrumentasi otomatis.

Prioritas monitor: akses lokal terbatasi → error yang jelas → latest status per run → stage nyata → kenyamanan tampilan. Tidak perlu realtime websocket; polling sederhana cukup. Pengujian kali ini memverifikasi HTTP, event dan source JavaScript; tidak mengklaim pengujian visual pada semua resolusi atau browser.

## 11. Evaluasi Plugin/Skill

Skill repo dan ZIP berisi instruksi operasional yang berguna: check, plan, run-academic, monitor dan aturan anti-fabrikasi. ZIP diperiksa dan SKILL-nya sama dengan repo. Plugin terpasang lokal yang diperiksa berada di luar repo; manifest hanya mendeklarasikan `skills`, dan tidak membawa integrasi runtime tambahan.

Karena itu, pengalaman sebenarnya adalah **host AI membaca instruksi lalu mengoperasikan repo dengan tool milik host**. Kemampuan Codex mengakses shell/web bukan kemampuan yang tiba-tiba dimiliki engine setelah skill dipasang.

Untuk beberapa laptop pribadi, cukup satu panduan instalasi Python + venv + clone + root + optional PoP + skill location. Berikan contoh JSON runnable memakai sumber nyata yang diambil sendiri saat contoh dijalankan, atau fixture jelas yang tidak pernah dipromosikan sebagai penelitian. Tidak perlu marketplace publik, lisensi komersial, installer berbayar, PyPI, ataupun service cloud untuk menutup temuan audit ini.

## 12. Evaluasi Kesiapan Multi-Device Pribadi

**Kode relatif mudah dipindahkan; state/output belum cukup portable.** Path dengan spasi berhasil pada pengujian. Root berbasis nama directory, manifest absolut dan workspace di luar Git merupakan hambatan konkret.

Batas minimum operasional:

- Setiap laptop memakai venv sendiri; launcher memilih interpreter itu secara eksplisit.
- Root ditentukan otomatis dari checkout atau sekali melalui setup yang jelas; tidak ada path username developer sebagai syarat.
- Output lama dimuat berdasarkan lokasi manifest saat ini, bukan drive laptop asal.
- Kode disinkronkan melalui Git; data/output disalin atau dibackup secara terpisah karena tidak berada di repo. Jangan menganggap `git push` membackup hasil penelitian.
- Edit satu project pada satu laptop pada satu waktu dahulu. Jika perlu berbagi file, gunakan transfer/backup yang diverifikasi; jangan menjalankan dua writer pada folder sinkronisasi yang sama.
- Credential lokal per perangkat, tidak dimasukkan ke Git. Tambahkan ignore untuk `config/system.local.yaml` bila dipakai sebagai konfigurasi khusus laptop.
- PoP opsional: testnya tidak boleh menjadi syarat lulus laptop yang hanya memakai HTTP tools. Laptop yang memerlukan PoP harus memasangnya dan menjalankan probe terpisah.

Solusi setup sementara yang sudah diuji untuk bootstrap adalah clone ke folder bernama `DATA BASE` atau set `AUTONOMI_SYSTEM_ROOT` ke lokasi clone aktual. Ini hanya workaround root; tidak memperbaiki gate akademik, manifest, dan ketergantungan test pada workspace.

## 13. Rekomendasi Perbaikan

| Kelompok | Pekerjaan | Wajib sebelum |
|---|---|---|
| Wajib: kepercayaan | A01–A04; relasi provenance; token gate; DOI metadata mismatch; conflict/qualifier | Menganggap DOCX sebagai naskah akademik final |
| Wajib: keselamatan output | A05, output/run manifest dan backup unik | Rerun rutin atau mengedit draft manual |
| Wajib: localhost | A06 dan bagian input handling A15 | Memakai endpoint penulisan secara rutin |
| Pribadi multi-device | A07, test workspace mandiri, venv launcher, backup data terpisah | Memakai laptop kedua |
| Research nyata | A08, A12, A13 dan snapshot A11 | Mengandalkan pencarian→verifikasi secara otomatis |
| Multi-model | A16 lalu client provider minimal A17 | Menyatakan ada routing/model integration aktif |
| Akademik/sitasi | A10, ledger A11, disclosure konflik, review substansi | Penyerahan laporan/proposal final |
| Edjust sensitif | A09, desain instrumen dan prosedur etik manusia | Materi dipakai untuk mengumpulkan data partisipan |
| Opsional | Perbaikan context, dedupe, UI, distribusi skill | Sesuai kebutuhan yang sudah terbukti |

Strategi multi-model minimal: implementasikan satu provider nyata dulu melalui kontrak existing; uji request sukses, timeout, error, output schema dan missing key; kemudian tambahkan provider kedua hanya bila dibutuhkan. Routing berdasarkan kemampuan/tugas, bukan nama model tetap. Transformasi mekanis tetap deterministik. Review evidence, konflik dan klaim berisiko tinggi mendapat model yang sesuai dan review manusia; model kedua bukan bukti bahwa fakta benar. Catat model/provider/versi, waktu, token, retry/fallback dan schema output. Jika key/capability tidak ada, berhenti secara eksplisit; jangan memakai completion simulatif.

CI yang proporsional: clean Windows checkout + install requirements + unit tests + health check. Tambahkan versi Python minimum yang didukung dan versi kerja utama; sesuaikan janji dukungan dengan hasilnya. Test internet/PoP dijalankan manual/terpisah, dengan skip dan alasan saat capability opsional tidak tersedia. Tidak diperlukan deploy job.

## 14. Roadmap Lanjutan

Roadmap memakai acceptance, bukan target tanggal spekulatif.

| Tahap | Hasil yang harus dicapai | Bukti kelulusan |
|---|---|---|
| R0 — Laporan awal (selesai pada audit ini) | Baseline, temuan, probe, roadmap; source belum diubah | Laporan dan evidence audit ini tersedia |
| R1 — Tutup kebocoran final | Gate source/evidence/claim + token + metadata mismatch + konflik; label draft/final jelas | Semua negative public CLI/API probe menolak; positive fixture sah tetap menghasilkan output |
| R2 — Lindungi kerja dan localhost | Run folder/backup, DOCX atomik, token/root guard, error JSON, single active project run | Rerun tidak menimpa edit; request asing/path di luar root ditolak; input rusak terlapor |
| R3 — Laptop kedua | Root discovery/setup konsisten, rebase manifest, interpreter venv, workspace tests mandiri | Clean clone arbitrary folder + spasi lulus; pindah project menulis hanya di lokasi baru; CI hijau |
| R4 — Research dan sitasi menyatu | Public tools callable, verification→retrieval→evidence tersambung, snapshot, APA konsisten | Topik sederhana + source valid/invalid + konflik punya jejak lengkap hingga output; daftar pustaka cocok body |
| R5 — Multi-model yang benar-benar dibutuhkan | Satu client nyata, kemudian provider kedua, batas biaya dan fallback terukur | Request live dan failure paths dicatat; tidak ada klaim siap saat provider absent |
| R6 — Kenyamanan dan Edjust | Monitor stage nyata, contoh user flow, review etik untuk penggunaan lapangan | Pengguna mengikuti panduan tanpa edit path komputer developer; prosedur riset sensitif terkonfirmasi |

R1–R3 adalah prioritas pribadi. R4 diperlukan untuk janji akademik end-to-end. R5 boleh ditunda bila AI host tetap melakukan reasoning di luar engine, asalkan batas itu dinyatakan jujur. R6 bagian etik tidak boleh ditunda melewati awal pengumpulan data remaja.

Ukuran perbaikan dijaga kecil: perbaiki titik bersama, reuse storage/registry/evaluator, hapus duplikasi payload CLI/API dan label metrik dekoratif. Jangan menambah abstract provider factory, event bus, registry baru, microservice, database terdistribusi atau mekanisme publik hanya untuk menutup bug lokal.

## 15. Kesimpulan

**Belum layak disebut nyaman dan dapat dipercaya untuk pemakaian pribadi di beberapa laptop secara rutin.** Ia sudah merupakan fondasi perangkat bantu yang dapat dijalankan dan diuji pada laptop utama, tetapi bukan autonomous academic researcher yang telah selesai dari topik sampai sumber/evidence/sitasi final.

Pembenahan yang paling bernilai adalah gate akademik yang benar, perlindungan output, akses localhost ringan, dan kontrak path/setup yang portable. Setelah syarat tersebut terpenuhi, arsitektur existing cukup untuk pemakaian pribadi; komersialisasi dan distribusi publik tidak diperlukan.

Audit ini tidak menyatakan seluruh bug sudah ditemukan, semua provider tersedia di setiap jaringan, format DOCX sudah diverifikasi visual penuh, atau safeguard etik sudah disetujui institusi. Kesimpulan didasarkan pada kode commit tersebut, eksekusi test, clone bersih, probe negatif dan respons live yang direkam. Tidak ada sumber, DOI, kutipan, halaman atau hasil riset fixture yang direkomendasikan untuk dipakai sebagai referensi akademik.
