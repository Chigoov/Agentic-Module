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

## Mode Kapabilitas Lingkungan (Capability Detection)

Sebelum mengeksekusi tugas, agen harus mengenali mode lingkungannya:

1. **Full Mode (Sandbox + Terminal + Internet Search + File Write):**
   - Lakukan pencarian dan verifikasi sumber nyata via internet search (DOI, penulis, tahun, jurnal, volume, isu, halaman).
   - Susun input JSON dengan status `APPROVED`.
   - Jalankan `python -m src run-academic --input-json input.json`.
   - Pastikan audit lulus dan ekspor bundle dengan `python -m src export-bundle`.

2. **Limited Mode (Terminal atau Internet Terbatas):**
   - Jika tanpa internet: gunakan hanya sumber yang sudah tersimpan atau diverifikasi lokal.
   - Jika tanpa sandbox terminal: siapkan payload JSON yang valid dan instruksikan pengguna untuk menjalankan CLI secara manual.
   - Laporkan batas environment secara transparan; jangan mengklaim eksekusi jika tidak dijalankan.

3. **Draft-Only Mode (Tanpa Internet / Sumber Belum Diverifikasi):**
   - **DILARANG KERAS** memalsukan verifikasi, mengarang DOI, atau mengarang kutipan.
   - **DILARANG** melakukan finalisasi akademik siap publikasi.
   - Tandai status sumber sebagai `PROPOSED` atau `[sumber belum lengkap]`.
   - Hasilkan hanya draft kerja/outline konseptual dengan disclaimer belum terverifikasi.

## Batas Aman & Aturan Anti-Fabrikasi

- Agent tidak boleh mengarang referensi, DOI, nomor halaman, atau volume.
- Agent tidak boleh mengarang evidence atau kutipan.
- Agent tidak boleh membuat DOCX jika audit gagal.
- Agent tidak boleh memfinalisasi output akademik jika sumber belum diverifikasi nyata.
- OpenRouter atau model provider tertentu bukan syarat wajib; engine berjalan lokal dan deterministik.
- Jika provider/model belum dikonfigurasi, routing harus gagal aman.

## Kewajiban Output Akademik

- Jangan meninggalkan sitasi internal seperti `turn...`, `view...`,
  `search...`, atau `filecite` pada output final.
- Ubah semua sumber terverifikasi menjadi sitasi dalam teks APA 7.
- Tambahkan daftar pustaka APA 7.
- Jalankan humanizer sebelum DOCX final: sederhanakan kalimat, hapus frasa AI yang terlalu umum, dan buat gaya terasa seperti tulisan mahasiswa yang rapi.
- Humanizer tidak boleh menambah fakta, data, sumber, kutipan, DOI, nomor halaman, atau klaim baru.
- Gunakan tata letak dokumen normal:
  - heading singkat dan biasa;
  - paragraf sebagai bentuk utama untuk esai;
  - bullet/nomor hanya untuk daftar nyata;
  - tabel hanya untuk data, perbandingan, rubrik, jadwal, atau ringkasan yang lebih jelas dalam kolom;
  - tabel biasanya 2-4 kolom, isi sel pendek, dan tidak berisi paragraf panjang.
- Untuk setiap sumber data, sumber hukum, dan artikel ilmiah, tampilkan:
  nama sumber, tahun, judul, link/DOI jika ada, serta halaman/bagian jika ada.
- Jika metadata sumber belum lengkap, tulis `[sumber belum lengkap]`.

## Verifikasi Wajib

```powershell
python -m pytest -q --tb=short
python -m pytest -m integration -q --tb=short
python -m src check
```
