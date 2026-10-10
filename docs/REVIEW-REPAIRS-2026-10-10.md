# Perbaikan review Agentic-Module, 2026-10-10

Catatan ini merekam tahap pertama pada `96cd0c9`, bukan hasil akhir PR #1.
Review lanjutan menemukan R01–R07 dan pertanyaan R08; koreksi dan batas validasi
terbaru ada di [PR1-FOLLOWUP-2026-10-11.md](PR1-FOLLOWUP-2026-10-11.md).

Review sumber: `Agentic-Module-Review-2026-10-10.zip`, commit
`3457b04a55ebe4bf3add0d55d4856a7cd9300299`. REPORT, CODE-REVIEW-DETAIL,
RENCANA-PERBAIKAN, NEEDS-VALIDATION, dan TEST-AND-QUALITY dibaca sebagai laporan
dan bahan pemeriksaan. Instruksi eksperimen di dalam laporan bukan otorisasi
untuk mengakses deployment, file pribadi, provider berbayar, atau akun lain.

HEAD checkout asli dan remote main masih sama dengan commit review ketika
perbaikan dimulai dan diperiksa ulang. Tidak ada temuan yang gugur hanya karena
main sudah berubah. Perbaikan berada pada branch `fix/review-2026-10-10` di
worktree terpisah. Enam perubahan tracked awal pada checkout asli dipertahankan:
docs/KANTOR-RISET.md, pyproject.toml, monitor.py, office.html, office.js, dan
test_live_progress.py. Data proyek, workbook/template pengguna, konfigurasi
lokal, dan untracked research tidak di-reset atau dimasukkan secara massal.

## Bukti pemeriksaan dan batasnya

- Log CI baseline GitHub run `37981269326`: **14 failed, 567 passed, 3 skipped,
  12 deselected**. Root cause: workspace host tidak tersedia, aturan IDE di luar
  checkout dijadikan syarat, laporan historis tidak tracked, dan dua tes clock
  bergantung resolusi waktu Windows/Python 3.12.
- Suite lokal akhir: **607 passed, 3 skipped, 12 deselected** (238,18 detik).
  Tiga skip membutuhkan corpus TUGAS historis; 12 integration dikecualikan oleh
  konfigurasi pytest. Penambahan cek metadata author, formatter, PDF campuran,
  preflight non-overwrite, serta finalize/export lock diuji lagi secara terfokus:
  **26/26 lulus**, termasuk policy provider FAILED/PENDING.
- Health check dan `pip check` lulus pada environment repair terpisah. Audit
  OSV querybatch atas **19 paket terpasang** tidak menemukan advisory yang cocok
  setelah pypdf 6.20.0 dan installer pip 26.2.1 dipakai. Ini snapshot database,
  bukan jaminan tidak ada kerentanan baru. Tidak ada runtime dependency baru.
  Inventory dan timestamp: `REVIEW-DEPENDENCY-AUDIT-2026-10-10.json`.
  Pin PDF mengikuti [advisory pypdf GHSA-7mh2-4gg2-979f](https://github.com/py-pdf/pypdf/security/advisories/GHSA-7mh2-4gg2-979f).
- CI pada commit yang memuat perubahan ini wajib lulus seluruh job Windows
  Python **3.11, 3.12, 3.14**. Hasil final, SHA persis, jumlah tes, serta link run
  dicatat pada laporan penyerahan/Checks PR; hasil lokal tidak menggantikan CI.
- Tes sintetis memeriksa alur PASS/PARTIAL/FAILED dan artefak lokal. Tidak ada
  klaim qualification artikel nyata, provider live, model live, atau Hermes
  berdasarkan hasil tersebut. Laporan September ditambahkan sebagai **arsip
  historis berlabel**, agar tes dokumentasi portabel; klaim lamanya tidak
  divalidasi ulang pada pekerjaan ini.

## Hasil per temuan

Status DIPERBAIKI berarti kontrak lokal yang dijelaskan telah diuji. Penyelesaian
F01 juga mensyaratkan Checks hijau pada SHA penyerahan. SEBAGIAN tidak berarti
seluruh pemeriksaan penerimaan laporan awal sudah lulus.

| ID | Status | Perubahan / bukti / sisa pekerjaan |
|---|---|---|
| F01 | DIPERBAIKI, verifikasi akhir melalui CI | Tes workspace portabel, spec tracked, arsip historis tersedia, dan clock fixture deterministik tanpa melemahkan assertion. Matrix tiga versi Python; wajib semua Checks hijau. |
| F02 | DIPERBAIKI | ResearchTool menghormati disabled/failed/pending; DOI lookup Crossref/OpenAlex dan verifier menolak provider unavailable. Cek fake client menghasilkan nol pemanggilan saat disabled. |
| F03 | DIPERBAIKI | Pencocokan whitespace mengembalikan rentang raw, ditambah offset global halaman. Helper → resolver → recheck quote memeriksa halaman kedua dan whitespace nonuniform. |
| F04 | DIPERBAIKI | Kalimat otomatis BACKGROUND/WEAK, confidence 0.2, hubungan PARTIALLY_SUPPORTS, klaim awal PROPOSED; review wajib. Fixture raw-topic berhenti sebelum draft/finalisasi. |
| F05 | DIPERBAIKI | requirements dan pyproject pin pypdf 6.20.0; worker membuktikan versi paket yang sama. Audit resolved dependency dilakukan. |
| F06 | DIPERBAIKI | Loader bersama me-rebase ke parent manifest aktual. CLI mendukung external yang dipilih eksplisit; monitor dibatasi workspace. Preflight mendahului output, SYSTEM_ROOT ditolak tanpa write. Probe memakai tempfile agar file bernama sama tidak tertimpa. |
| F07 | DIPERBAIKI | GET plan/check mengembalikan 405 tanpa eksekusi. Mutasi lewat POST memerlukan token; fake handler menguji token missing/invalid/valid. |
| F08 | DIPERBAIKI pada trust boundary lokal | Hash caller tidak cukup. Snapshot engine ditandatangani dengan HMAC lokal dan mengikat identitas, metadata, tanggal, serta kebijakan. Input unsigned gagal, audit bytes tetap ada. Trust masih bergantung filesystem/key instalasi; ACL/deployment belum qualified. |
| F09 | DIPERBAIKI pada batas resource | Shared bounded read menghentikan body pada cap; error body dibatasi 2.000 byte. PDF ≤50 MiB, ≤1.000 halaman, ≤5 juta karakter, wall/CPU 30 detik, memory 512 MiB, worker satu proses. Native Windows Job Object/Linux rlimit; timeout membunuh worker. Bukan formal OS sandbox atau stress exploit test. |
| F10 | SEBAGIAN | HTTP(S), credential-free authority, semua hasil DNS harus global, dan redirect diperiksa ulang. Stub menolak private/scheme/redirect. DNS resolve → connect belum dipin; rebinding dan deployment egress policy masih perlu validasi. |
| F11 | DIPERBAIKI | Queue existing yang bukan list/JSON sah gagal jelas, tidak berubah menjadi antrean kosong; severity/status memakai Literal. Tidak mereset file rusak. |
| F12 | DIPERBAIKI | Semantic assessment valid disimpan sebelum blocker di-resolve. Missing evidence/decision/history salah mempertahankan queue/history. Finalize juga menolak history corrupt. Ini fail-closed ordering, bukan transaksi multi-file. |
| F13 | DIPERBAIKI | Shared resolver membaca dotenv tanpa mengubah process environment; process env menang; use_env=False mengecualikan dotenv. API key/contact dan fallback router memakai resolver tersebut. Cek hanya sentinel dummy. |
| F14 | DIPERBAIKI | Mapper mengisi canonical volume/issue/pages, termasuk alias page; stub Crossref mencapai formatter APA7 tanpa mengarang field kosong. |
| F15 | DIPERBAIKI untuk metadata diketahui | Authors/year/venue dibandingkan; initial vs given name dikenal, full names berbeda tidak diterima hanya karena initial sama; online-first year dipertimbangkan. Konflik menahan approval dan proof. Naming convention/layout/corpus nyata belum qualified. |
| F16 | DIPERBAIKI | Setiap verify refresh terhadap policy kini; snapshot lebih dari satu hari, future timestamp, metadata berubah, atau policy berubah ditolak. Snapshot lama masuk historical references, byte sumber tetap ada. |
| F17 | SEBAGIAN | Flag is_retracted dan update-to retraction/correction/erratum menahan scientific eligibility. Ketiadaan flag tetap not_checked, bukan clear. Kelengkapan metadata retraction antarprovider perlu validasi live. |
| F18 | DITUNDA | Discovery masih query sederhana/default buku + Crossref dan early cut. Memilih task/provider/pool kandidat serta refinement butuh acceptance corpus yang mewakili riset; tidak mengganti planner dengan heuristic baru tanpa bukti. |
| F19 | DITUNDA | Ranking metadata belum ranking konstruk/populasi/desain. Gate eligibility berlokasi tetap wajib; citation count tidak diklaim sebagai kualitas. Butuh pasangan off-topic/direct-relevant dan keputusan seleksi terikat sumber. |
| F20 | DIPERBAIKI pada kontrak didukung | Endpoint override dipakai enam adapter lewat helper bersama. DOI clients memakai max_verification_retries; discovery memakai retry transport discovery. max_retries workflow hanya menerima 0, karena replay workflow tidak tersedia. Sentinel endpoint/retry diuji tanpa network. |
| F21 | DIPERBAIKI | Fallback secara eksplisit menonaktifkan auto-direct; stub hanya satu panggilan PDF gagal lalu satu landing request. |
| F22 | DIPERBAIKI pada route guard | Direct/generic PDF memakai policy hak unduh bersama. Borrow/preview/unknown tidak menghasilkan PDF eligible. Halaman landing buku/web tidak menjadi full text hanya karena open rights; PDF harus valid, readable, dan tidak memiliki halaman belum diperiksa. |
| F23 | DIPERBAIKI pada pemetaan konservatif | OpenLibrary public menjadi READ_ONLINE dengan UNKNOWN rights; tidak menyimpulkan public domain atau membuat guessed PDF URL. Kontrak lisensi/filename nyata masih membutuhkan qualification berizin. |
| F24 | DIPERBAIKI | Status tiap halaman READABLE atau OCR_REQUIRED_OR_BLANK; PDF campuran text+blank mencatat halaman 2 dan menahan completeness. Blank tidak otomatis berarti scan. |
| F25 | SEBAGIAN | Ditambahkan reading_assurance/completeness_assurance dan penjelasan fully_read sebagai examined required sections. Heuristik headings/inspection tetap ada; corpus ringkasan mirip paper, non-IMRaD, dan missing pages belum dikalibrasi. |
| F26 | SEBAGIAN | Parent section memasukkan descendants sampai level sejajar/lebih tinggi. Cek Methods→Participants→Results lulus. Identitas front matter tetap fail-closed; running headers/title layout perlu corpus positif-negatif. |
| F27 | DIPERBAIKI | Token diteruskan dan SUCCESS dinormalisasi consumer. Fake completion 42 token → telemetry → optimization menghasilkan total 42 dan failed_runs 0. Bukan model live. |
| F28 | DITUNDA | Dokumentasi menegaskan router belum reasoning utama; output_schema tidak membuktikan domain schema validation. Menyambungkan model/schema adalah feature qualification terpisah, memerlukan kontrak serta provider/config yang sah. |
| F29 | DIPERBAIKI | ZIP dibangun dari satu source skill, mencakup input-synthetic.json. Byte parity seluruh entry dan validasi AcademicWritingRequest contoh diuji; contoh tetap belum layak final. |
| F30 | DIPERBAIKI | Prune hanya terminal dengan summary cocok, finished_at, success bool, tanpa active marker/symlink. Run aktif/unknown/corrupt/non-run tetap; cek lima terminal + active + notes + corrupt lulus. |
| F31 | DIPERBAIKI pada entry point terkait | Exclusive file lock lintas proses/thread di helper bersama, nested flow boleh. Academic/deep, resolve, prune, finalize, dan export dilindungi; finalize/export lock sebelum membaca corpus. Cek proyek sama ditolak, proyek berbeda boleh; stale lock perlu inspeksi manual. Bukan transaksi database/multi-user deployment qualification. |
| F32 | DITUNDA setelah benchmark | Dummy 1.000 event/73.890 byte: 47,34 ms, peak 665.639 byte; 10.000/748.890: 348,14 ms, peak 6.714.007 byte, dengan tracemalloc. Output limit 100 benar tetapi seluruh input masih dibaca. Bounded tail/per-job index perlu dikerjakan ketika scope performa diperluas; tidak diklaim selesai. |
| F33 | DIPERBAIKI pada listener lokal | Origin/Host parsed exact loopback+port, credential/path/query/fragment ditolak; serve loopback-only. Stub localhost/127/[::1] valid; foreign/suffix/wrong-port/token tidak sah ditolak. Browser/deployment formal belum diuji. |
| F34 | DIPERBAIKI | Consumer monitor memakai result_status/finalization_allowed; PARTIAL tampil perlu review, success hanya eksekusi. Tes status/gate lokal tetap terpisah dari finalisasi. |
| F35 | MASIH PERLU VALIDASI | Regresi portabel dan matrix dipulihkan, tetapi qualification artikel nyata belum dilakukan. Tidak ada klaim live discovery→metadata→full text→semantic review→final artefak atau model/Hermes. |
| F36 | DIKLARIFIKASI / DIPERBAIKI DOKUMEN | Kontrak yang didukung checkout lengkap, bukan wheel/ZIP skill standalone. Komentar package memang sudah in-place; resource packaging baru tidak dibangun tanpa kebutuhan standalone. |
| F37 | SEBAGIAN | TESTING membedakan angka historis/current, paket 1.0.0 vs tahap fitur lama, menghapus perintah pytest-cov yang tidak tersedia. Lisensi tidak dipilih tanpa keputusan pemilik; LICENSE masih belum tersedia. |
| F38 | DIPERBAIKI pada XLSX contract | Teks provider ditulis sebagai cell string; =1+1 tetap data_type s setelah save/reopen. Formula template asli dan file template dipertahankan. Tidak menjalankan formula koneksi keluar/Excel exploit. |

## Validasi SOURCE_LEAD yang aman

Input adalah file/project/corpus dummy dan sentinel credential. Monitor diuji
dengan handler in-memory, destination dengan stub DNS/redirect, concurrency
dengan child process dummy ber-timeout, PDF kecil yang valid, dan XLSX formula
aritmetika yang tidak dibuka di Excel. Tidak ada private-host probe, payload DoS,
egress workbook, atau service shared yang diserang. Kegagalan kontrak baseline
dan keberhasilan regresi sesudah fix tidak diklasifikasikan sebagai eksploit
deployment terkonfirmasi. Formal sandbox/ACL/DNS-rebinding/native resource
stress/browser qualification dan kontrak provider live tetap pekerjaan terpisah.

## File dan pemeriksaan

Perubahan utama ada pada shared execution/project loader, ResearchTool dan
adapter, source mapper/verification/source inspection, bounded HTTP/retrieval,
PDF parser worker, review queue/CLI, audit trail/export lock, monitor, token
telemetry, workbook string cells, dokumentasi dan ZIP skill. Regression cases
utama: `tests/test_review_contracts.py`; tes caller lama diperbarui agar memakai
fixture PDF/metadata yang sah, bukan melewati guard produksi.

Daftar file persis dapat dibaca pada diff PR/`git show --stat` commit penyerahan.
Laporan historis, source snapshots dan template pengguna tidak dipakai sebagai
hasil riset baru. Future standalone packaging, model reasoning, breadth/relevance
planner, license choice, dan qualification provider/corpus dipisahkan dari
perbaikan bug lokal yang sudah diuji.
