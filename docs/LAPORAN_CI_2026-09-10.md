# Laporan CI — GitHub Actions Windows (Health Check + Unit Test)
Tanggal: 10 September 2026
Tujuan: regresi portabilitas cepat ketahuan via CI otomatis di setiap push/PR ke `main`.
Batasan dipatuhi: tanpa dashboard, tanpa deployment, tanpa PyPI/installer, tanpa mengubah workflow akademik, tanpa integration test di CI.

---

## 1. Isi File Workflow (`.github/workflows/ci.yml`)
```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  windows-check-and-test:
    name: Windows health check + unit tests
    runs-on: windows-latest
    timeout-minutes: 15
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Setup Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: pip

      - name: Install dependencies
        run: python -m pip install -r requirements.txt

      - name: Health check
        run: python -m src check

      - name: Unit tests
        run: python -m pytest -q --tb=short
```
Validasi: YAML ter-parse bersih (trigger `push`+`pull_request` ke `main`; runner `windows-latest`; 5 step).

## 2. Mengapa Integration Test Tidak Dijalankan di CI
1. **Bergantung jaringan/provider live** — integration suite memanggil Crossref, OpenAlex, PubMed, dan VeriﬁcationEngine live. Hasilnya bisa berubah karena rate-limit atau gangguan provider, membuat CI merah tanpa ada regresi kode (flaky).
2. **Unit suite sudah dirancang untuk ini** — `pyproject.toml` menetapkan `addopts = -m "not integration"`, sehingga `python -m pytest -q` di CI otomatis menjalankan **303 test tanpa jaringan** yang menutup semua fix R1–R3 (termasuk regresi portabilitas yang dulu: test hardcode nama folder kini sudah agnostik).
3. **Prinsip audit** — integration/PoP dijalankan manual/terpisah (perintahnya: `python -m pytest -m integration -q --tb=short`); CI kecil tetap cepat (~2–4 menit) dan stabil.
4. `timeout-minutes: 15` menjaga CI mati sendiri bila ada yang menggantung.

## 3. Cara Melihat Hasil di GitHub
1. Buka https://github.com/Chigoov/Agentic-Module
2. Tab **Actions** (di baris atas halaman repo).
3. Pilih run terbaru bernama **"CI"** — job **"Windows health check + unit tests"**.
4. ✅ centang hijau = lulus; ❌ X merah = gagal; klik job untuk melihat step mana yang gagal (Health check / Unit tests) beserta outputnya.
5. Badge hasil juga tampil di halaman daftar commit (centang/X di samping setiap commit).
6. Workflow baru **aktif setelah commit ini di-push** ke GitHub (Actions membaca `.github/workflows/ci.yml` dari remote).

## 4. Commit
| Commit | Isi |
|---|---|
| `5c89213` | `fix: enforce academic integrity gates, output safety, and multi-device portability (A01-A07, A12, A15)` — 37 file (9.367+/113−): seluruh fix R1–R3 + uji + laporan sesi + baseline audit |
| `3f6bd95` | `ci: add Windows health check and test workflow` — 1 file (`.github/workflows/ci.yml`, 31 baris) — pesan persis seperti diminta |

Working tree bersih setelah keduanya; hanya `git push` yang tersisa untuk mengaktifkan CI.

## 5. Validasi Lokal Sebelum Commit
Perintah persis yang dijalankan CI, dijalankan lokal dulu:
- `python -m src check` → exit 0
- `python -m pytest -q --tb=short` → **303 passed, 10 deselected**, exit 0
Selain itu YAML divalidasi via `yaml.safe_load`.

## 6. Risiko Tersisa
1. **Python 3.12 vs 3.14 lokal** — CI memakai 3.12 (stabil, sesuai instruksi); lokal 3.14.5. Semua test diperkirakan lulus di 3.12 (tanpa API khusus versi baru), tetapi kepastiannya baru terlihat pada run CI pertama setelah push. Jika ingin jaminan ekstra, tambahkan matrix `["3.11", "3.12"]` di `strategy.python-version`.
2. **Run pertama bisa butuh penyesuaian kecil** — mis. cache pip cold atau warning baru; umumnya bukan kegagalan.
3. **Integration test tetap di luar CI** — berarti kerusakan jaringan/provider tidak terdeteksi otomatis; jalankan manual sebelum checkpoint besar.
4. **CI hanya melindungi yang masuk Git** — output riset (`TUGAS 1/`) tetap butuh backup manual/cloud terpisah.
5. **Push belum dilakukan** — origin masih di `5c89213`; commit CI (`3f6bd95`) baru aktif di GitHub setelah push.

## 7. Rekomendasi Langkah Berikutnya
```powershell
git push origin main          # aktifkan CI + sinkron laptop kedua
# lalu cek tab Actions pada run pertama
```
Opsional (menyusul, bila run pertama hijau): matrix Python `["3.11", "3.12"]` untuk bukti klaim dukungan multi-versi README.
