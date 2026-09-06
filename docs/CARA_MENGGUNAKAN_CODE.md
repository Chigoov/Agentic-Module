# CARA MENGGUNAKAN CODE
## AUTONOMI AGENTIC ILMIAH

Panduan ini menjelaskan cara menjalankan code yang sudah selesai sampai Fase 17.

## 1. Masuk ke Folder Sistem

Jalankan semua perintah dari folder:

```powershell
cd "C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH\DATA BASE"
```

## 2. Install Dependency

```powershell
python -m pip install -r requirements.txt
```

## 3. Cek Sistem

```powershell
python -m src check
```

Hasil sehat akan menampilkan:

```text
[OK] System health check passed
Build phase: 17
```

## 4. Jalankan Test

Fast test:

```powershell
python -m pytest -q --tb=short
```

Integration test:

```powershell
python -m pytest -m integration -q --tb=short
```

## 5. Cara Memakai Workflow dari Python

Saat ini sistem dipakai sebagai library Python. Contoh minimal di bawah
menjalankan Academic Writing Mode sampai menghasilkan `draft.md` dan `final.docx`.

```python
from pathlib import Path

from src.schemas.claim import Claim, ClaimStatus, SupportLevel
from src.schemas.evidence import Evidence, EvidenceLocation
from src.schemas.outline import Outline, OutlineSection
from src.schemas.project import Project
from src.schemas.source import Source, SourceState
from src.workflows.academic import AcademicWritingRequest, AcademicWritingWorkflow

project_dir = Path(r"C:\Users\HYPE AMD\Downloads\VIBE CODING\AUTONOMI AGENTIC ILMIAH\TUGAS 1\contoh_run")
project_dir.mkdir(parents=True, exist_ok=True)

project = Project(
    name="contoh_run",
    workspace="TUGAS 1",
    path=str(project_dir),
    title="Contoh Makalah",
    citation_style="APA7",
    language="id",
)

source = Source(
    title="Paper",
    authors=["Smith, J."],
    year=2024,
    state=SourceState.APPROVED,
)

claim = Claim(
    claim_text="Program meningkatkan kehadiran peserta.",
    supporting_sources=[source.id],
    supporting_evidence=["evd_1"],
    status=ClaimStatus.SUPPORTED,
    support_level=SupportLevel.STRONG,
)

evidence = Evidence(
    id="evd_1",
    claim_id=claim.id,
    source_id=source.id,
    evidence_text="Program meningkatkan kehadiran peserta.",
    location=EvidenceLocation(locator="abstract"),
    quote_verified=True,
)

outline = Outline(
    title="Contoh Makalah",
    sections=[OutlineSection(title="Temuan", claim_ids=[claim.id])],
)

response = AcademicWritingWorkflow().execute(
    AcademicWritingRequest(
        project=project,
        claims=[claim],
        evidence=[evidence],
        sources=[source],
        outline=outline,
    )
)

print(response.success)
print(response.draft_path)
print(response.docx_path)
```

## 6. Cara Memakai Deep Research Mode

Deep Research Mode memakai planner dan workflow akademik yang sama, tetapi mode
risetnya diset ke `DEEP_RESEARCH`.

```python
from src.workflows.deep_research import DeepResearchRequest, DeepResearchWorkflow

response = DeepResearchWorkflow().execute(
    DeepResearchRequest(
        project=project,
        user_request="topik riset yang ingin dikaji",
        claims=[claim],
        evidence=[evidence],
        sources=[source],
        outline=outline,
    )
)

print(response.success)
print(response.plan)
print(response.docx_path)
```

## 7. Output Utama

Output workflow disimpan di folder project, misalnya:

- `draft.md`
- `citation_audit.json`
- `fact_audit.json`
- `final.docx`
- `e2e_validation.json`
- `optimization_report.json`

## 8. Catatan Penting

- Sistem tidak akan membuat sumber, DOI, kutipan, atau nomor halaman palsu.
- DOCX hanya dibuat kalau citation audit dan fact audit lulus.
- Model provider nyata belum otomatis aktif. Jika provider/model belum
  dikonfigurasi, routing akan gagal secara aman dan tercatat di telemetry.
- Untuk pemakaian sehari-hari yang nyaman, langkah berikutnya adalah membuat
  CLI sederhana di atas workflow ini.

## 9. Cara Pakai Lewat CLI

Buat rencana:

```powershell
python -m src plan "dampak perceraian orang tua terhadap remaja"
```

Jalankan Academic Writing Mode dari JSON:

```powershell
python -m src run-academic --input-json input.json
```

Panduan khusus AI agent ada di `docs/CARA_PAKAI_UNTUK_AI_AGENT.md`.
