# LAPORAN FASE 6 — RETRIEVAL + EVIDENCE EXTRACTION

> **Status:** ✅ SELESAI — roadmap baru Fase 6
> **Tanggal:** 2026-09-06
> **Dasar:** `BUILD_PLAN.md` Fase 6 + `00_MASTER_INSTRUCTION.md §10, §15, §22` + `AGENT_CONSTITUTION.md §8–§9`

## 1. Ringkasan

Fase 6 baru menutup gap retrieval tanpa membangun orchestrator atau agent baru.
Implementasi menambahkan `RetrievalTool` yang:

- memakai `Source.abstract` sebagai konten tersedia tanpa jaringan;
- mengambil `Source.url` melalui stdlib `urllib`;
- menyimpan raw document ke `source_documents/`;
- mem-parse HTML/plain text menjadi `parsed_text`;
- menyimpan PDF tanpa mengarang hasil parse teks;
- mengisi `Source.retrieval_path` dan memindahkan source ke `FULLTEXT_RETRIEVED`
  tanpa meregresikan source yang sudah `APPROVED`.

`EvidenceExtractor` dari fase sebelumnya tetap dipakai untuk ekstraksi verbatim
dari `parsed_text`; tidak dibuat ulang.

## 2. File

- [NEW] `src/tools/retrieval.py`
- [MODIFY] `src/tools/__init__.py`
- [NEW] `tests/test_retrieval.py`
- [MODIFY] `BUILD_PLAN.md`
- [MODIFY] `README.md`

## 3. Hasil Test

```
python -m pytest tests/test_retrieval.py -q
→ 7 passed
```

## 4. Batasan Jujur

- PDF baru disimpan sebagai raw bytes; parsing teks PDF didefer sampai ada
  parser yang benar-benar dipilih dan diuji.
- Retrieval agent, planner, dan orchestrator belum dibuat; itu roadmap Fase 7–8.

## 5. Next

Fase 7 — Research Agents.
