# CARA PAKAI UNTUK AI AGENT

Project ini bisa dipakai oleh Codex, GPT, Claude, Gemini, atau agent lain yang
bisa menjalankan perintah Python.

## Entry Point

Semua agent harus masuk lewat folder:

```powershell
cd "C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH\DATA BASE"
```

## Perintah Standar

```powershell
python -m src check
python -m src plan "topik riset"
python -m src run-academic --input-json input.json
```

`python -m src --check` tetap didukung untuk kompatibilitas lama.

## Format Kerja

1. Gunakan `plan` untuk membuat rencana riset awal.
2. Siapkan JSON berisi `project`, `sources`, `claims`, `evidence`, dan `outline`.
3. Jalankan `run-academic`.
4. Baca output JSON:
   - `success`
   - `stages`
   - `draft_path`
   - `docx_path`
5. Jalankan `check` dan test setelah mengubah code.

## Batas Aman

- Agent tidak boleh mengarang referensi.
- Agent tidak boleh mengarang evidence.
- Agent tidak boleh membuat DOCX jika audit gagal.
- Jika provider/model belum dikonfigurasi, routing harus gagal aman.

## Verifikasi Wajib

```powershell
python -m pytest -q --tb=short
python -m pytest -m integration -q --tb=short
python -m src check
```
