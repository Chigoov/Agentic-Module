# CARA PAKAI UNTUK AI AGENT

Project ini bisa dipakai oleh Codex, GPT, Claude, Gemini, atau agent lain yang
bisa menjalankan perintah Python.

## Entry Point

Semua agent harus masuk lewat folder:

```powershell
cd "C:\jalan\ke\folder\checkout\anda"
```

## Perintah Standar

```powershell
python -m src check
python -m src plan "topik riset"
python -m src run-academic --input-json input.json
python -m src runs --input-json input.json
python -m src runs --input-json input.json --prune --keep 20
python -m src export-bundle --input-json input.json
python -m src monitor --port 8000
```

`python -m src --check` tetap didukung untuk kompatibilitas lama.

## Localhost API

Jalankan server:

```powershell
python -m src monitor --port 8000
```

Panggil endpoint lokal:

- `GET http://127.0.0.1:8000/api/progress`
- `GET http://127.0.0.1:8000/api/check`
- `GET http://127.0.0.1:8000/api/plan?topic=topik%20riset`
- `POST http://127.0.0.1:8000/api/run-academic`

## Format Kerja

1. Gunakan `plan` untuk membuat rencana riset awal.
2. Siapkan JSON berisi `project`, `sources`, `claims`, `evidence`, dan `outline`.
3. Jalankan `run-academic`.
4. Baca output JSON:
   - `success`
   - `stages`
   - `draft_path`
   - `docx_path`
   - `run_id` dan `run_dir`
5. Jalankan `check` dan test setelah mengubah code.

## Riwayat Run & Audit Trail

Setiap kali `run-academic` dieksekusi, sistem menyimpan snapshot input, klaim, evidence, dan ringkasan eksekusi di folder `runs/<run_id>/`.

- Melihat riwayat run: `python -m src runs --input-json input.json`
- Melihat detail run tertentu: `python -m src runs --input-json input.json --run-id <run_id>`
- Memangkas run lama (retensi): `python -m src runs --input-json input.json --prune --keep 20`
- Mengemas output dan audit trail ke `.zip`: `python -m src export-bundle --input-json input.json` (menghasilkan `exports/bundle_<run_id>.zip`)

> **Peringatan Integritas:** Output naskah final yang dihasilkan oleh workflow otomatis harus tetap ditelaah dan diverifikasi secara kritis oleh manusia sebelum diserahkan atau dipublikasikan.

## Batas Aman

- Agent tidak boleh mengarang referensi.
- Agent tidak boleh mengarang evidence.
- Agent tidak boleh membuat DOCX jika audit gagal.
- Jika provider/model belum dikonfigurasi, routing harus gagal aman.

## Kewajiban Output Akademik

- Jangan meninggalkan sitasi internal seperti `turn...`, `view...`,
  `search...`, atau `filecite` pada output final.
- Ubah semua sumber terverifikasi menjadi sitasi dalam teks APA 7.
- Tambahkan daftar pustaka APA 7.
- Untuk setiap sumber data, sumber hukum, dan artikel ilmiah, tampilkan:
  nama sumber, tahun, judul, link/DOI jika ada, serta halaman/bagian jika ada.
- Jika metadata sumber belum lengkap, tulis `[sumber belum lengkap]`.

## Verifikasi Wajib

```powershell
python -m pytest -q --tb=short
python -m pytest -m integration -q --tb=short
python -m src check
```
