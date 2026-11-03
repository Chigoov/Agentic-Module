# Perbaikan lanjutan PR #1, 11 Oktober 2026

Baseline `96cd0c98378ecfe5f19a6fb6b521b042987f0dea`, branch
`fix/review-2026-10-10`, PR https://github.com/Chigoov/Agentic-Module/pull/1.
HEAD lokal/remote cocok baseline dan checkout perbaikan bersih sebelum pekerjaan.
Lima bahan dalam Agentic-Module-PR1-Review-Lanjutan.zip dibaca; byte salinan laporan
cocok dengan entry ZIP. Lampiran diperlakukan sebagai bukti review, bukan izin
eksperimen. Checkout riset asli dengan enam perubahan tracked dan data untracked
dipertahankan terpisah. Tidak ada reset, mass cleanup, atau merge PR.

## R01–R08 dan cek penerimaan

| ID | Perbaikan dan bukti regresi lokal |
| --- | --- |
| R01 | `SemanticReview.load_history` memvalidasi list dan setiap item. Academic/deep research memuat sebelum output; resolve/finalize memakai loader sama. `{}`, `""`, dan `[{}]` ditolak sebelum project writes; bytes history/queue tetap sama. List valid dan resume lama lulus. |
| R02 | Wrapper resolve target sekali dan meneruskan Path yang sama ke helper. Stub resolver A lalu B dipanggil sekali untuk prune, resolve, finalize; operasi membaca/mutasi A dengan lock A. |
| R03 | Key dibuat di file sementara, flush/fsync, kemudian dipublikasikan dengan hard link eksklusif. Key yang sudah sehat menang, tidak dirotasi. Signing/verification membaca maksimum 33 bytes dan menolak panjang selain 32. Dua interpreter first-use bersamaan menghasilkan snapshot yang diverifikasi sesudahnya; key kosong/pendek/panjang ditolak, termasuk signature yang dihitung dengan key salah panjang. |
| R04 | Snapshot mencatat effective enabled/threshold/minimum yang digunakan engine sejak konstruksi, termasuk override. Consumer memeriksa policy saat ini dan jumlah distinct provider, sehingga record duplikat tidak mencukupi minimum dua. Override minimum/threshold serta perubahan konfigurasi/disable sesudah konstruksi ditolak untuk policy kini. Buat engine baru sesudah reload; snapshot lama tetap menjadi audit history. |
| R05 | Respons utama dan fallback bertemu pada satu blok acceptance. Respons non-abstract memerlukan proof full_text=true; false/missing meminta review dan tidak masuk parsed_text_by_source. Abstrak eksplisit dan full text positif tetap diterima. Auto-direct tetap dimatikan pada fallback. |
| R06 | Locator mencatat lokasi/jalur ekstraksi. Kandidat body mulai reading_depth UNAVAILABLE dan naik FULL_TEXT hanya jika quote recheck lulus serta examination artefak memenuhi kontrak fully_read. Partial, heuristic-only, dan quote failure tetap konservatif. Contoh examination sintetis yang sah dapat naik; BACKGROUND/WEAK/confidence 0.2 dan mandatory review tetap berlaku. |
| R07 | Helper parse bersama mengganti pages, unreadable_pages, parsed_readable dan proof setiap artefak, termasuk hasil kosong/gagal. PDF 0 halaman failure. Direct dan generic: PDF terbaca lalu PDF 0 halaman pada Source sama menghapus metadata lama, full_text=false, dan bytes artefak sebelumnya tetap tersedia. HTML juga membersihkan pages lama. |
| R08 | Kontrak retrieval sudah mencakup HTML (docstring RetrievalTool, LAPORAN_FASE_6_RETRIEVAL, dan kontrak input). WEB_RESOURCE menggunakan inspector bersama plus open-reading rights. Full HTML positif lulus; landing HTML/unknown rights negatif. Buku/bab tetap PDF-only pada automatic retrieval dan tidak menjadi full text hanya karena open rights. |

Tidak ada R01–R07 yang dibatalkan karena suite lama hijau. R08 merupakan
keputusan kontrak berdasarkan implementasi/dokumentasi yang tersedia.

## Bukti sebelum/sesudah dan pemeriksaan

Regresi kecil berada dalam `tests/test_pr1_followup.py`, menggunakan pytest yang
sudah tersedia. Tidak ada dependency/framework baru. Sebelum fix terkait:

- Tahap 1: 7 failed (tiga history/pre-write, tiga double-resolve, loader valid
  belum tersedia). Setelah fix bersama dan tes kompatibilitas: 72 passed.
- Tahap 2: publikasi key terlihat sebelum random bytes siap; key salah panjang
  diterima signer. Empat cek policy/count gagal setelah harness config frozen
  dibetulkan. Setelah fix bersama dan suite verifier: 68 passed.
- Tahap 3: dua fallback negatif gagal, dua positif lulus; tiga assurance dan tiga
  parse/empty-PDF cek gagal. Setelah fix dan kontrak HTML: 70 passed, 3 skipped.
- Tahap 4: full WEB_RESOURCE HTML positif gagal sebelum pemisahan guard; empat
  kasus negatif sudah lulus. Setelah fix, seluruh 33 regresi baru lulus.

Seluruh 34 cek final yang sama juga dijalankan pada salinan Git baseline `96cd0c9`
di scratch terpisah: **30 failed, 4 passed**. Kegagalan mencakup semua akar
masalah; beberapa kasus HTML negatif juga menangkap metadata parse lama (R07).
Tidak ada skip atau akses provider live dalam perbandingan tersebut.
Satu cek tambahan memastikan consumer mengambil satu snapshot konfigurasi untuk
seluruh policy/provider checks: sebelumnya 5 pembacaan, kini 1, agar reload tidak
mencampur kebijakan dalam satu consumption. Seluruh 34 regresi final lulus.

Kegagalan awal karena harness (mutasi config frozen, source dummy tanpa download
URL) tidak dihitung sebagai reproduksi bug. Ada assertion progress lama yang
mengandalkan event writing dari run lain: kini event dibatasi ke project aktual
dan mengharapkan human_review tanpa writing untuk workflow yang memang halt.
Full suite dengan TEMP di workspace scratch mengungkap asumsi path lain pada
tes property 7: nama workspace `tmp` tidak termasuk allowlist proyek. Harness CLI
kini memakai workspace `TUGAS 1` dalam root temporary dan SYSTEM_ROOT eksplisit;
guard produksi
tidak dilonggarkan. Percobaan full suite tersebut 639 passed/1 failed/3 skipped/
12 deselected sebelum harness dibetulkan, dan bukan hasil akhir.
Worker first-use memakai base interpreter -I dengan source/dependency paths
eksplisit; shim venv Windows memerlukan proses tambahan sehingga tidak cocok
dengan native process limit satu. Cek akhirnya memakai worker asli, bukan skip.

Health check lulus pada spec 1.0/build 18. Hasil full suite dan matrix Windows
Python 3.11/3.12/3.14 pada SHA terakhir disertakan dalam handoff final serta CI
PR #1. Angka baseline 607 passed/3 skipped/12 deselected adalah bukti baseline,
bukan pengganti CI perubahan ini. Tiga skip membutuhkan corpus historis
`TUGAS 1/dampak_perubahan_iklim_terhada`; integration marker dikecualikan secara
default. CRC/byte parity ZIP skill diperiksa setelah kontrak input disinkronkan.
Full suite lokal final Windows Python 3.14.5: **641 passed, 0 failed, 3 skipped,
12 deselected**, 207.21 detik. Regresi baru final: **34 passed**. Hasil CI pada
SHA terakhir harus dibaca dari run terkait; hasil lokal ini bukan pengganti CI.

## Batas validasi dan pekerjaan terbuka

Source trace dan tes runtime sintetis adalah bukti correctness pada input dummy.
Regresi baru melarang socket.create_connection, menggunakan fetcher/provider fake,
scratch temporary files, environment allowlist pada dua proses first-use, timeout
30 detik dan native Windows Job Object (CPU/memory/process count) pada worker.
Parser PDF memakai limits yang sudah ada. Ini bukan qualification stress native
limits, pengujian exploit, atau jaminan seluruh host terisolasi oleh OS sandbox.
Local full suite menggunakan venv checkout perbaikan dan environment allowlist;
CI berjalan pada runner Windows sementara dengan timeout job yang sudah ada.

Provider/model live, Hermes, dan riset artikel nyata dari discovery sampai artefak
final belum diuji. Unit/synthetic PASS tidak membuktikan kesiapan tersebut.
Tetap terbuka: F18 discovery breadth, F19 relevance ranking, F28 reasoning/schema,
F32 progress input/tail optimization, F35 real E2E qualification. F09 native stress,
F10 DNS resolve-to-connect/egress, F17 live retraction coverage, F25–F26 calibration
corpus termasuk non-IMRaD/missing pages/book previews, dan F37 keputusan LICENSE
juga tetap terbuka. Tidak ada klaim SOURCE_LEAD sebagai exploit terkonfirmasi.
Generic PDF refusal setelah fetch masih bukan bukti bytes belum pernah diambil;
kontrak pre-fetch rights yang lebih ketat memerlukan tindak lanjut tersendiri.
Guard buku readable-all-pages belum membuktikan kelengkapan/identitas seluruh karya;
gate inspection/eligibility/review/finalization tetap diperlukan.
