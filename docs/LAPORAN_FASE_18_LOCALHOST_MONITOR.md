# LAPORAN FASE 18
## Localhost API + Workflow Monitor

> **Status:** SELESAI — `build_phase = 18` DIFINALISASI

## Tujuan

Fase ini menambahkan jalur pemakaian lokal agar sistem tidak hanya dipakai
lewat CLI, tetapi juga bisa dipantau dari browser dan dipanggil oleh AI agent
lain melalui endpoint `localhost`.

## Implementasi

- Menambahkan progress log append-only di `state/progress.jsonl`.
- Menambahkan server stdlib Python melalui `python -m src monitor --port 8000`.
- Menambahkan halaman monitor animasi di `http://127.0.0.1:8000`.
- Menambahkan endpoint:
  - `GET /api/progress`
  - `GET /api/check`
  - `GET /api/plan?topic=topik%20riset`
  - `POST /api/run-academic`
- Menambahkan CORS lokal agar endpoint lebih mudah dipanggil oleh tool/agent.

## Batas Aman

- Server default hanya bind ke `127.0.0.1`, jadi tidak dibuka ke jaringan luar.
- Tidak ada dependency baru.
- Monitor tidak mengarang sumber, DOI, kutipan, evidence, atau nomor halaman.
- `run-academic` tetap melewati workflow dan audit yang sama.

## File Berubah

- `src/runtime/progress.py`
- `src/runtime/monitor.py`
- `src/runtime/cli.py`
- `tests/test_monitor.py`
- `tests/test_cli.py`
- `config/system.yaml`
- `src/__init__.py`
- `tests/test_config.py`
- `README.md`
- `BUILD_PLAN.md`
- `docs/CARA_MENGGUNAKAN_CODE.md`
- `docs/CARA_PAKAI_UNTUK_AI_AGENT.md`
- `skills/autonomi-agentic-ilmiah/SKILL.md`

## Cara Menjalankan

```powershell
python -m src monitor --port 8000
```

Buka:

```text
http://127.0.0.1:8000
```

## Verifikasi

Fase ini diverifikasi dengan:

```powershell
python -m pytest tests/test_monitor.py tests/test_cli.py tests/test_config.py -q
python -m src check
```

## Keputusan

Fase 18 dinyatakan selesai dalam scope minimal. Untuk kebutuhan multi-user
atau akses publik, langkah berikutnya bukan menambah kode lokal, tetapi
menentukan mekanisme deployment dan autentikasi.
