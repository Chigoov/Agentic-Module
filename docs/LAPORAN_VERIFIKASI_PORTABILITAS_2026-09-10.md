# Laporan Verifikasi Portabilitas Multi-Device (Windows)
Tanggal: 10 September 2026
Metode: salinan checkout ke folder temp Windows dengan **path berspasi** dan **nama folder bukan `DATA BASE`** — persis skenario yang gagal pada audit baseline (`portability.json`: clone `Agentic-Module` → health check exit 1).
Laporan audit baseline tidak diubah.

---

## 1. Ringkasan
| Butir instruksi | Hasil |
|---|---|
| Lokasi folder salinan | `C:\Users\HYPE AMD\AppData\Local\Temp\Riset Agentic Module\Agentic-Module-Copy` (ada spasi; nama folder **bukan** `DATA BASE`; 115 file .py; tanpa `.git`/`cache`/`state`/`logs`) |
| Health check di salinan | ✅ **LULUS** — exit 0, tanpa env override apa pun |
| Unit test di salinan | ✅ **303 passed, 10 deselected** (setelah 3 test diperbaiki — lihat §5) |
| Integration test di salinan | ✅ **10 passed, 303 deselected** (18,0 s — jaringan live: Crossref/OpenAlex/PubMed/verification, dijalankan dari salinan) |
| Run akademik positif dari salinan | ✅ **LULUS** — exit 0, 4 file output lengkap |
| Kebocoran path absolut komputer utama | File runtime/output: **BERSIH 100%**. Dokumentasi setup: 2 file bocor → sudah dipatch. Dokumen historis: menyebut path sebagai rekaman (dipertahankan, bukan instruksi). |
| Kegagalan akibat nama folder bukan `DATA BASE` | **Tidak ada** pada kode/runtime. Ditemukan pada 3 *test* lama yang masih hardcode nama folder → diperbaiki. |

## 2. Lokasi dan Cara Menyalin
```powershell
$src  = "...\AUTONOMI AGENTIC ILMIAH\DATA BASE"
$dst  = "$env:TEMP\Riset Agentic Module\Agentic-Module-Copy"
robocopy $src $dst /E /XD .git .pytest_cache __pycache__ cache state logs ".venv" /XF .env
```
Enam spec files kanonik (`00_MASTER_INSTRUCTION.md` … `BUILD_PLAN.md`) terverifikasi lengkap di salinan.

## 3. Health Check di Salinan — LULUS
```powershell
# cwd = folder salinan, TANPA AUTONOMI_SYSTEM_ROOT / AUTONOMI_WORKSPACE_ROOT
python -m src check
```
```
[OK] System health check passed
   SYSTEM_ROOT: C:\Users\HYPE AMD\AppData\Local\Temp\Riset Agentic Module\Agentic-Module-Copy
   WORKSPACE_ROOT: C:\Users\HYPE AMD\AppData\Local\Temp\Riset Agentic Module
   Spec version: 1.0
   Build phase: 18
```
Ini membuktikan fix A07 (root discovery berbasis marker spec files) bekerja pada: nama folder arbitrer, path dengan spasi, dan lokasi di luar drive-folder kerja biasa — tanpa trik apa pun. Pada baseline audit, skenario identik menghasilkan `Could not locate the 'DATA BASE' system root` (exit 1).

## 4. Hasil Test di Salinan
| Perintah | Hasil pertama | Setelah fix test | 
|---|---|---|
| `python -m pytest -q --tb=short` | 3 failed, 300 passed | ✅ **303 passed, 10 deselected** |
| `python -m pytest -m integration -q --tb=short` | — | ✅ **10 passed, 303 deselected** (18,0 s, jaringan live) |

## 5. Temuan dan Perbaikan Selama Verifikasi
1. **3 test masih hardcode nama `DATA BASE`** (sisa A07 yang terlewat di test suite, bukan di kode runtime):
   - `test_get_paths_discovers_system_root` — assert `system_root.name == "DATA BASE"`
   - `test_get_paths_derives_workspace_root` — assert `workspace_root / "DATA BASE"`
   - `test_workspace_path_rejects_system_root` — memanggil `workspace_path("DATA BASE")`
   *Patch terkecil:* test kini agnostik nama (identitas root = spec files; penolakan system root memakai `paths.system_root.name`). Diperbaiki di checkout utama `tests/test_paths.py` → disalin ke salinan → unit test hijau penuh di kedua lokasi. **Ini satu-satunya patch yang diperlukan.**
2. **Dokumentasi setup membawa path absolut komputer utama** (`docs/CARA_MENGGUNAKAN_CODE.md`, `docs/CARA_PAKAI_UNTUK_AI_AGENT.md` — contoh `cd "C:\Users\HYPE AMD\..."`). Di laptop kedua ini menyesatkan.
   *Patch terkecil:* contoh diganti `cd "C:\jalan\ke\folder\checkout\anda"` + catatan "nama folder bebas, tidak harus DATA BASE"; contoh `project_dir` Python juga diganti placeholder. Terverifikasi 0 kemunculan tersisa di kedua panduan.
3. **Bukan kegagalan:** dokumen historis (`LAPORAN_FASE_0_1.md`, `PHASE_1_REPORT.md`, `AUDIT_KESELURUHAN_2026-09-07.txt`, `LAPORAN_UJI_WORKFLOW_CLI_2026-09-09.md`) menyebut path absolut sebagai **rekaman** — dipertahankan apa adanya (audit melarang mengubah laporan baseline/laporan historis).

## 6. Run Akademik Positif dari Salinan — LULUS
Input: `input_portabel.json` di folder salinan (sumber nyata LeCun/Bengio/Hinton 2015 *Deep learning* Nature, DOI 10.1038/nature14539, state `DOI_VERIFIED`; claim–evidence–outline terhubung; path project menunjuk workspace salinan sendiri).
```powershell
python -m src run-academic --input-json input_portabel.json
```
| File output (di `...\Riset Agentic Module\TUGAS 1\uji-portabel\`) | Status |
|---|---|
| `draft.md` (295 B) | ✅ Klaim + `(LeCun et al., 2015)` + daftar referensi |
| `citation_audit.json` | ✅ `passed: true`, semua scan kosong |
| `fact_audit.json` | ✅ `passed: true` |
| `final.docx` (35,5 KB) | ✅ Terbaca normal; token internal **nol**; heading `References` tepat 1× |

Output tertulis **di workspace salinan sendiri** — bukan di lokasi komputer utama.

## 7. Kebocoran Path Absolut
| Area | Hasil |
|---|---|
| File runtime hasil run (`draft.md`, `*.json`, `final.docx`, `state/`, log) | **BERSIH** — tidak ada satu pun string `C:\Users\HYPE AMD\Downloads\...` |
| Kode `src/` & `tests/` | **BERSIH** |
| Dokumentasi setup (2 file) | Bocor → **sudah dipatch** |
| Dokumen historis/laporan (4 file) | Menyebut path sebagai rekaman — dipertahankan sesuai instruksi baseline |

## 8. Rekomendasi Patch Terkecil (status)
| Rekomendasi | Status |
|---|---|
| `tests/test_paths.py` agnostik nama folder | ✅ Sudah diterapkan |
| `docs/CARA_MENGGUNAKAN_CODE.md` & `CARA_PAKAI_UNTUK_AI_AGENT.md` bebas path absolut | ✅ Sudah diterapkan |
| (Opsional, menyusul) GitHub Actions "clean checkout Windows + install + test + check" agar regresi portabilitas terdeteksi otomatis | Belum — tidak dibutuhkan untuk lulus uji ini |
| (Opsional) Ganti 2 kemunculan nama workspace default `"TUGAS 1"` bila kelak ingin full-i18n | Tidak menghambat; hanya nama default |

## 9. Kesimpulan
**Portabilitas multi-laptop Windows terverifikasi nyata**: salinan di path berspasi bernama arbitrer, tanpa Git metadata, tanpa state, tanpa env override — lulus health check, 303 unit test, 10 integration test live, dan satu run akademik positif lengkap dengan output bersih di lokasinya sendiri. Satu-satunya kegagalan awal bersumber dari *test* (bukan kode) yang masih mengasumsikan nama `DATA BASE`, dan sudah diperbaiki. Suite checkout utama tetap hijau (**303 passed**, `python -m src check` exit 0).

Bukti mentah tetap tersedia di folder salinan (`%TEMP%\Riset Agentic Module\`) sampai dibersihkan; folder temp ini aman dihapus kapan pun.
