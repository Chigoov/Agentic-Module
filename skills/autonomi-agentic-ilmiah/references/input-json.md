# Kontrak input AAI untuk agent dan Hermes

Kontrak ini mengikuti AcademicWritingRequest dan skema aktual di src/schemas.
[input-synthetic.json](input-synthetic.json) valid secara skema, berlabel
SYNTHETIC TEST ONLY, dan sengaja belum layak final. Kasus positif dengan artefak
lengkap diuji dalam tests/test_identity_location_claim_gates.py dan
tests/test_workflow_audit_repairs.py. Jangan gunakan fixture sebagai artikel nyata.

## Sumber, retrieval, identitas, dan pembacaan

- Metadata yang tidak tersedia tetap null. Sumber baru DISCOVERED; APPROVED
  dari input bukan bukti.
- metadata.verification_artifact berisi path dan SHA-256 snapshot JSON dari
  verification engine. Snapshot mengikat source_id, title, doi, authors, year,
  venue, verified_at, verification_policy, dan provider_records (provider dan
  record), dengan signature lokal yang dibuat engine. Hash dari input saja
  tidak membuktikan asal. Snapshot yang tidak ditandatangani, lebih dari satu
  hari, atau berbeda identitas/kebijakan harus diverifikasi ulang. Setiap
  pemanggilan verify melakukan refresh; snapshot historis tetap dipertahankan.
  Jangan menulis provider atau hasil verifikasi rekaan untuk penelitian nyata.
- retrieval_path menunjuk PDF, HTML, atau ekstraksi JSON/text nyata.
  metadata.retrieval memuat sha256, retrieved_at, retrieval_method, final_url
  atau origin. Hash dihitung dari byte file yang tersimpan.
- Identitas mengacu pada judul utama/front matter dengan normalisasi kapitalisasi,
  spasi, tanda baca, dan baris terbungkus. DOI/judul dalam isi atau References
  tidak membuktikan identitas. DOI utama bertentangan/layout ambigu memerlukan
  review. Parser deterministik konservatif tidak membuktikan pemahaman ilmiah.
- File tersedia, dapat dibaca, lengkap, legal/gratis, diperiksa penuh, dan
  kutipan terverifikasi merupakan status terpisah. FULL_TEXT bukan bukti.

examination, eligibility_review, content_inspection, rights_inspection berada
di source.metadata, mengikat source_id, artifact_sha256, reviewer, reviewed_at,
serta sections berisi excerpt dan lokasi nyata. Examination scope: full
memerlukan kutipan berbeda yang mencakup metode, hasil, dan pembahasan/kesimpulan
pada artefak yang sama. Label kompatibilitas fully_read berarti examined required
sections, bukan seluruh halaman telah dipahami. full_text menggunakan heuristik
struktur/cakupan; PDF dengan halaman kosong/tidak terbaca memerlukan pemeriksaan.
Tiga string locator tidak cukup. Eligibility memakai
decision: eligible serta criterion construct, population, design berlokasi.
Rights inspection legal_free: true mengacu pada bukti lisensi/akses nyata.
Content inspection scope: completeness, document_kind: full_text untuk layout
tidak standar tetap memerlukan bukti isi berlokasi.

## Kontrak lokasi bersama

Evidence.location, sections inspection, criteria assessment memakai page,
page_label, section, char_start, char_end, locator. Inspection/criteria boleh
memakai object location bersarang.

- page adalah nomor fisik 1-based dari parser, bukan nomor cetak yang ditebak.
  page_label harus cocok dengan peta parser.
- section harus tersedia dan kutipan berada dalam batasnya.
- char_start/char_end wajib berpasangan, 0-based/end-exclusive pada parsed
  full_text. Separator halaman ikut dihitung.
- Locator yang didukung: p. 2, page 2, halaman 2, Results, section: Results,
  §Results, p. 2, Results. body/document/retrieved content merupakan scope
  dokumen; cakupan examination tetap berasal dari lokasi kutipan sebenarnya.
- Semua koordinat diperiksa sekaligus. Page salah tidak diterima hanya karena
  section benar. Locator bebas, paragraph, anchor tanpa peta ekstraksi tetap
  belum terverifikasi. Jangan membuat lokasi pengganti.

VERBATIM_ABSTRACT memakai snapshot abstrak terverifikasi; halaman/rentang
full-text hanya boleh digunakan bila benar-benar tersedia pada artefaknya.
VERBATIM_FULLTEXT/TABULAR_VALUE memakai body berlokasi. quote_verified selalu
dicocokkan ulang; jangan menimpa abstract dengan body. Sumber diperiksa penuh
boleh memakai evidence abstrak: kedalaman pembacaan dan asal kutipan berbeda.
Containment dalam teks caller membuktikan ekstraksi, belum verifikasi snapshot.

## Klaim, outline, dan semantic review

ID corpus asli diperiksa sebelum screening akses. Evidence.claim_id harus
sesuai claim yang merujuknya. Outline merujuk klaim tersedia dan layak ditulis.
Dukungan hilang dicatat dalam runs/<run_id>/claim_screening.json, response
metadata, dan run summary. Dukungan tersisa dinilai ulang melalui evaluate_claim;
semantic review untuk dukungan lama tidak dianggap masih berlaku.
HIGH/CRITICAL memerlukan review/revisi sebelum final. Input asli dan corpus
tetap tersimpan.

Jika klaim sengaja dikeluarkan, gunakan transisi WITHDRAWN dengan history nyata
(to_state, reason, actor, at) dan revisi outline. Jangan menghapus record untuk
menyembunyikan ID rusak. Klaim yang masih dibutuhkan dan kehilangan dukungan
tetap menghalangi finalisasi. HIGH/CRITICAL, angka, kausalitas, arah, mekanisme,
efektivitas, atau klaim absolut tetap membutuhkan semantic review nyata lengkap:
claim_id, decision, reason, evidence_id, source_id, evidence_excerpt, location,
reviewer, method, timestamp.

## Project dan workbook

- project.output_type: literature_review memerlukan bagian Pendahuluan, Metode,
  Hasil/Pembahasan, Keterbatasan, Kesimpulan, Referensi yang terisi.
  Metode Penelusuran Literatur dan Keterbatasan Literatur merupakan alias
  exact dari schemas/outline.py; heading tidak berkaitan tidak diterima.
  Isi subseksi dihitung pada induk. required_sections menghormati template;
  output lain mengikuti kontraknya sendiri.
- require_free_full_text di request atau project.research_options adalah
  kebijakan proyek. Sumber final harus memenuhi konstruk/populasi/desain
  serta akses full-text legal gratis yang diperoleh dan terbaca.
  source.metadata.version mencatat version_of_record/published_version,
  accepted_manuscript, atau preprint sesuai artefak aktual.
  Metode dan keterbatasan harus mengungkap pembatasan akses gratis.
- quantitative_review: true memakai template standar pengguna. Record membawa
  source_snapshot dan assessment: source_id, artifact_sha256, reviewer,
  reviewed_at, criteria berisi pillar sesuai rubrik, score, lokasi,
  evidence_excerpt. Total harus cocok dengan jumlah skor terverifikasi.
  Ranking final memerlukan pemeriksaan penuh berlokasi dan rubrik lengkap.
  Placeholder bobot/anchor berarti scoring belum final.
- Empat puluh target awal, bukan maksimum. Semua artikel lolos dan peringkat
  berlanjut. quantitative_review_exact_count/best_count hanya sesuai instruksi;
  artikel terbaik tanpa jumlah menghasilkan klarifikasi terstruktur.
  Corpus dan alasan tidak dipilih tetap ada.

## Status, resume, dan run yang benar

success mempertahankan kontrak lama. Baca metadata.execution_success,
result_status (PASS/PARTIAL/FAILED), finalization_allowed, needs_human_review.
Exit code saja tidak menentukan hasil ilmiah. PARTIAL dapat disimpan/diekspor;
workbook PARTIAL, bagian kosong, audit gagal, review PENDING yang memblokir
mencegah final.docx.

Dari DATA BASE, gunakan interpreter proyek dan periksa tools yang diperlukan.
Health check lokal tidak membuktikan provider/model.

```powershell
python -m src check
python -m src run-academic --input-json input.json
# Revisi: gunakan project/path aktual dari response, pertahankan opsi.
python -m src run-academic --input-json revision.json --resume
python -m src runs --input-json revision.json --run-id <run_id>
python -m src finalize <project_aktual>
python -m src export-bundle --input-json revision.json --run-id <run_id>
```

Tugas baru membuat project unik; revisi membuat run baru dalam project sama.
Periksa run_summary.json, snapshot audit sitasi/fakta/gaya, document_quality,
review queue, claim_screening, status workbook, artefak aktual, hash, dan ZIP
berdasarkan run_id. Jangan membaca final.docx/run lama sebagai hasil terbaru.
Manifest checksum ZIP terpisah menghindari circular checksum.
