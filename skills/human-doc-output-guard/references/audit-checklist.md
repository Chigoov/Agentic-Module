# Daftar Periksa Verifikasi Cepat (Audit Checklist)
**Daftar Verifikasi Modul `human_style_audit` / `natural_student_output_guard`**

Sebelum menyatakan pengerjaan dokumen selesai atau mengompilasi berkas akhir (`draft.md`, `final.docx`, lembar tabel), agen wajib memeriksa seluruh butir dalam daftar periksa ini.

---

## 1. Daftar Periksa 5 Gerbang Kualitas

### Gerbang 1: Pengecekan Batasan Permintaan (Scope & Boundary)
- [ ] Apakah seluruh bab, subbab, atau jawaban yang ditulis memang diminta oleh pengguna?
- [ ] Apakah ada ringkasan eksekutif, kata pengantar, cover, atau kesimpulan yang "ditambahkan sepihak" oleh AI padahal tidak diinstruksikan?
- [ ] Jika ini revisi: apakah bagian di luar permintaan tetap utuh tanpa perubahan diam-diam?
- [ ] Jika ada klausul "jangan ubah bagian X": apakah teks X terkonfirmasi 100% sama dengan aslinya?

### Gerbang 2: Pengecekan Frasa Klise AI (Natural Tone Check)
- [ ] Apakah teks bersih dari frasa pembuka usang seperti *"Pada era globalisasi..."* atau *"Di tengah kemajuan pesat..."*?
- [ ] Apakah kata *"secara komprehensif"*, *"dalam konteks ini"*, *"penting untuk digarisbawahi"* sudah dihapus atau diganti?
- [ ] Apakah variasi kalimat mengalir wajar, tidak terasa seperti template terjemahan bahasa Inggris?
- [ ] Apakah nuansa tulisan mencerminkan mahasiswa yang santun, logis, dan akademik wajar?

### Gerbang 3: Pengecekan Tata Letak & Struktur (Structure & Layout)
- [ ] Apakah kedalaman heading wajar (tidak beranak pinak sampai level 4 atau 5 untuk esai pendek)?
- [ ] Apakah tidak ada callout box berwarna neon, emoji hiasan, atau ikon dekoratif yang menyerupai pamflet?
- [ ] Apakah poin-poin (*bullet points*) hanya digunakan untuk daftar nyata, bukan menggantikan seluruh paragraf pembahasan esai?
- [ ] Jika berupa dokumen DOCX: apakah format heading, margin, dan spasi sudah seragam dan formal?

### Gerbang 4: Pengecekan Tabel & Spreadsheet (Table Sanity)
- [ ] Apakah tabel tidak melebihi 2–4 kolom kecuali memang tabel data mentah multi-variabel?
- [ ] Apakah tidak ada teks esai berparagraf panjang di dalam sel tabel sempit?
- [ ] Apakah tidak ada kolom analisis subjektif/skor buatan AI yang tidak diminta?
- [ ] Apakah format angka sensitif (NIM, nomor telepon, kode pos) tidak kehilangan angka nol di depan?
- [ ] Apakah sel tanpa data tetap kosong / strip, bukan diisi dengan angka rekaan?

### Gerbang 5: Pengecekan Kejujuran Fakta & Sumber (Honesty & Grounding)
- [ ] Apakah setiap sumber rujukan nyata dan memiliki metadata yang benar?
- [ ] Apakah tidak ada DOI fiktif (seperti `10.9999/...`) atau nama jurnal karangan?
- [ ] Apakah sumber yang belum lengkap telah ditandai secara jujur dengan `[sumber belum lengkap]`?
- [ ] Apakah klaim kausal atau statistik didukung bukti empiris, bukan asumsi penulis semata?

---

## 2. Format Laporan Hasil Audit (`human_style_audit.json`)

Ketika proses audit dijalankan, sistem menghasilkan status terstruktur:

```json
{
  "passed": true,
  "audit_name": "human_style_audit",
  "checked_artifacts": ["draft.md", "final.docx"],
  "unrequested_additions": [],
  "ai_style_markers": [],
  "excessive_structure": false,
  "complex_tables": false,
  "fabricated_sources_or_data": false,
  "remediation_applied": [],
  "notes": "Dokumen memenuhi seluruh standar kewajaran gaya mahasiswa dan fidelitas instruksi."
}
```

---

## 3. Prosedur Perbaikan Terkecil (Smallest Safe Remediation)

Jika salah satu parameter bernilai `false` atau terdeteksi pelanggaran:
1. **Dilarang Menulis Ulang dari Awal (No Total Regeneration):**
   Jangan membuang seluruh naskah dan meminta model membuat draft baru dari nol, karena hal ini berisiko memunculkan halusinasi baru atau mengubah bagian yang sudah disetujui.
2. **Potong Tambahan yang Tidak Diminta (Strip Bloat):**
   Hapus langsung heading atau paragraf liar yang tidak diperintahkan.
3. **Penyuntingan Bedah Teks (Surgical Phrase Replacement):**
   Ganti frasa klise AI yang terdeteksi dengan kalimat langsung atau padanan wajar sesuai panduan `student-style-guide.md`.
4. **Sederhanakan Format Tabel:**
   Hapus kolom spekulatif, sesuaikan lebar sel, dan pastikan data tabular mudah dibaca.
