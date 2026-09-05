# LAPORAN FASE 5 — EVIDENCE / CLAIM ENGINE

> **Status:** ✅ SELESAI — `build_phase = 5` DIFINALISASI
> **Tanggal:** 2026-09-05
> **Bahasa:** Indonesia
> **Dasar:** [BUILD_PLAN.md](file:///c:/Users/HYPE%20AMD/Downloads/VIBE%20CODING/AUTONOMI%20AGENTIC%20ILMIAH/DATA%20BASE/BUILD_PLAN.md) Fase 5 + `00_MASTER_INSTRUCTION.md §14–§15, §19` + `AGENT_CONSTITUTION.md §6–§10, §14, §29–§30`

---

## 1. Ringkasan Eksekutif

Fase 5 (Evidence / Claim Engine) selesai. Di atas skema `Claim` dan `Evidence` yang sudah ada sejak Fase 1, kini ada **lapisan engine deterministik** yang mengubah *evidence mentah* menjadi *keputusan yang bisa diaudit*:

- **`evidence_flow.py`** — klasifikasi dukungan (SUPPORTS/PARTIALLY_SUPPORTS/CONTRADICTS/IRRELEVANT), deteksi konflik, agregasi `SupportLevel`, kalibrasi `confidence`, dan `evaluate_claim` yang menghasilkan `ClaimStatus` + alasan wajib.
- **`claim_registry.py` / `evidence_registry.py`** — persistensi `claims.json` (atomik) dan `evidence.jsonl` (append-only) per proyek, melalui lapisan storage yang sudah aman.
- **`evidence_extractor.py`** — ekstraksi **verbatim** (harus cocok persis setelah normalisasi spasi) dan **deferral jujur** untuk parafrase model (non-verbatim, tidak pernah dianggap kutipan langsung).

**Prinsip inti:** sebuah klaim tidak pernah "tampak didukung" tanpa bukti nyata; konflik diungkap, tidak disembunyikan; dan kutipan langsung hanya bisa dihasilkan dari teks yang terverifikasi persis ada di konten sumber.

---

## 2. Hasil Test (Bukti Runtime)

### 2.1 Fast suite (tanpa jaringan)
```
python -m pytest -m "not integration" -q
→ 196 passed, 10 deselected
```
- **Baseline (sebelum Fase 5): 168 passed** (196 − 28 test baru Fase 5).
- **Test baru Fase 5: +28** (`test_evidence_flow.py` 14, `test_registries.py` 9, `test_evidence_extractor.py` 5).

### 2.2 Bootstrap health check
```
python -m src --check
→ [OK] System health check passed — Build phase: 5
```

> [!NOTE]
> Fase 5 **tidak menambah test integration jaringan** — seluruh logika deterministik dan murni, sehingga diuji offline tanpa ketergantungan endpoint eksternal.

---

## 3. Capability Matrix

| Komponen | File | Status | Bukti |
|---|---|---|---|
| **Support classification** | `src/workflows/evidence_flow.py` | ✅ | `test_support_level_*`, `test_evaluate_claim` (14 test) |
| **Confidence calibration** | `src/workflows/evidence_flow.py` | ✅ | `test_confidence_*` (4 test) |
| **Claim registry** | `src/core/claim_registry.py` | ✅ | `test_claim_registry_*` (5 test) |
| **Evidence registry** | `src/core/evidence_registry.py` | ✅ | `test_evidence_registry_*` (4 test) |
| **Verbatim extractor** | `src/tools/evidence_extractor.py` | ✅ | `test_extract_verbatim_*`, `test_record_paraphrase_*` (5 test) |

---

## 4. File yang Dibuat / Diubah

### Engine & Flow
- [NEW] `src/workflows/evidence_flow.py` — `evaluate_claim`, `compute_support_level`, `calibrate_confidence`, `classify_relationship`, `EvaluationResult`

### Registries
- [NEW] `src/core/claim_registry.py` — `ClaimRegistry` (persist `claims.json`)
- [NEW] `src/core/evidence_registry.py` — `EvidenceRegistry` (append-only `evidence.jsonl`)

### Tools
- [NEW] `src/tools/evidence_extractor.py` — `EvidenceExtractor`, `extract_verbatim`, `ExtractionResult`

### Config
- [MODIFY] `src/core/config.py` — `EvidenceSection` (min sources, max evidence/claim, require verbatim, enabled)
- [MODIFY] `config/system.yaml` — section `evidence:` + `build_phase: 5`

### Registrasi & Version
- [MODIFY] `src/workflows/__init__.py` — ekspor `evidence_flow`
- [MODIFY] `src/tools/__init__.py` — ekspor `evidence_extractor`
- [MODIFY] `src/__init__.py` — `BUILD_PHASE = 5`

### Perbaikan (bug yang ditemukan saat implementasi)
- [FIX] `src/schemas/claim.py` — `is_important` dan `has_conflict` diubah dari `@computed_field` menjadi `@property` biasa. Sebelumnya kedua field turunan ini ikut terserialisasi ke `claims.json` lalu **ditolak** saat reload (`extra="forbid"`), sehingga round-trip persistensi klaim gagal.

### Tests
- [NEW] `tests/test_evidence_flow.py` (14 test, tanpa jaringan)
- [NEW] `tests/test_registries.py` (9 test, round-trip persistensi)
- [NEW] `tests/test_evidence_extractor.py` (5 test, tanpa jaringan)
- [MODIFY] `tests/test_config.py` — assertion `build_phase == 5`

---

## 5. Aturan Support-Level (Deterministik)

| Ceiling evidence terbaik | Sumber distinct | Hasil `SupportLevel` |
|---|---|---|
| WEAK | — | `WEAK` |
| MODERATE | — | `MODERATE` |
| STRONG | 1 | `MODERATE` |
| STRONG | ≥2 | `STRONG` |
| DEFINITIVE | — | `STRONG` |

> [!NOTE]
> `PARTIALLY_SUPPORTS` **menurunkan ceiling satu tingkat** lewat `Evidence.max_claim_strength()` (`00_MASTER_INSTRUCTION.md §19`), jadi klaim tidak boleh berbunyi lebih kuat daripada buktinya.

---

## 6. Acceptance Criteria — Semua LULUS

1. ✅ `evaluate_claim` deterministik & network-free (support + conflict + confidence + status).
2. ✅ Konflik diungkap (`CONFLICTED`/`REFUTED`), tidak pernah disembunyikan.
3. ✅ `ClaimRegistry` persisten `claims.json` secara atomik + round-trip valid.
4. ✅ `EvidenceRegistry` persisten `evidence.jsonl` append-only + anti-duplikat.
5. ✅ `EvidenceExtractor` hanya loloskan kutipan **verbatim**; parafrase model ditandai non-verbatim.
6. ✅ Config `evidence:` terpisah dari `verification:` untuk tuning independen.
7. ✅ Fast suite hijau (196 passed); health check `build_phase = 5`.
8. ✅ `build_phase = 5` difinalisasi setelah 1–7 lulus.

---

## 7. Catatan & Rekomendasi Lanjutan

> [!TIP]
> **Fase 6 = ClaimVerificationAgent.** Saat ini `evaluate_claim` adalah fungsi murni yang dipanggil dengan daftar evidence yang sudah diikat (oleh caller). Fase 6 akan menambahkan *agent* yang meng-orkestrasi: memuat registry, memanggil extractor, lalu `evaluate_claim`, dan menerapkan transisi status pada `Claim` — menghubungkan engine ini ke jalur eksekusi nyata.

> [!IMPORTANT]
> **`evaluate_claim` TIDAK melakukan I/O.** Ia murni logika. Integrasi ke jalur eksekusi (agent/runtime) adalah langkah berikutnya yang disengaja agar lapisan deterministik tetap dapat diuji offline.

> [!WARNING]
> **Jangan menulis klaim SUPPORTED tanpa evidence.** `Claim.transition_to(SUPPORTED)` menolak bila `evidence_required` dan `supporting_evidence` kosong, atau bila ada `contradicting_evidence`. Selalu lewat `evaluate_claim` + transisi yang teraudit.
