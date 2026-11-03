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
  verification_policy mencatat enabled, threshold, dan minimum provider yang
  benar-benar dipakai engine (tetap sejak konstruksi, termasuk override).
  Consumer mensyaratkan policy saat ini dan jumlah provider berbeda yang cukup;
  setelah konfigurasi berubah, buat engine baru untuk re-verifikasi. Key lokal
  harus tepat 32 bytes, dipublikasikan lengkap tanpa mengganti key yang sehat.
  Jangan menulis provider atau hasil verifikasi rekaan untuk penelitian nyata.
- retrieval_path menunjuk PDF, HTML, atau ekstraksi JSON/text nyata.
  metadata.retrieval memuat sha256, retrieved_at, retrieval_method, final_url
  atau origin. Hash dihitung dari byte file yang tersimpan.
- WEB_RESOURCE boleh HTML lengkap atau PDF yang lolos inspector bersama,
  identitas/provenance/cakupan, dan hak baca terbuka. Landing HTML tetap parsial.
  BOOK/BOOK_CHAPTER otomatis masih mensyaratkan PDF terbaca pada semua halaman
  serta hak akses terbuka; hak terbuka saja tidak membuktikan full text.
  Metadata parse diganti per artefak, termasuk hasil kosong; PDF 0 halaman gagal.
- Identitas mengacu pada judul utama/front matter dengan normalisasi kapitalisasi,
  spasi, tanda baca, dan baris terbungkus. DOI/judul dalam isi atau References
  tidak membuktikan identitas. DOI utama bertentangan/layout ambigu memerlukan
  review. Parser deterministik konservatif tidak membuktikan pemahaman ilmiah.
- File tersedia, dapat dibaca, lengkap, legal/gratis, diperiksa penuh, dan
  kutipan terverifikasi merupakan status terpisah. FULL_TEXT bukan bukti.
  Kandidat evidence otomatis dari body mulai UNAVAILABLE; hanya recheck kutipan
  yang lulus bersama examination artefak dapat memberi reading_depth FULL_TEXT.
  extraction_method mencatat jalur ekstraksi, bukan jaminan reading assurance.
  Kandidat tetap BACKGROUND/WEAK, confidence rendah, dan wajib review.

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


## Kontrak operasional QC 3 November 2026

- Engine menjalankan validasi deterministik. Agent pengarah menilai relevansi,
  metode, dan makna klaim. ModelRouter dan ContextLoader belum menjadi jalur
  penalaran workflow utama. Provider model opsional. Telemetri engine tidak
  mengukur token/biaya/waktu berpikir agent luar; jangan mengklaim persentase hemat.
- `python -m src check` memeriksa kesehatan struktural. Gunakan
  `python -m src check --for research` (atau `run-academic`, `finalize`, `plan`)
  untuk kesiapan konfigurasi per perintah. Konfigurasi siap bukan integrasi VERIFIED.
- Monitor hanya loopback. `GET /api/check` dan `GET /api/plan` ditolak.
  Gunakan `POST /api/check`, `POST /api/plan`, `POST /api/run-academic` dengan
  header `X-Autonomi-Token` dari instalasi lokal. Jangan menonaktifkan Host/Origin/token.
- Review klaim harus menamai reviewer sebenarnya. Contoh AI:
  `python -m src review-queue <project> --resolve <exact_review_id> --decision SUPPORTED --notes "alasan berdasarkan bukti" --reviewer "nama-agent" --reviewer-type ai`.
  Pakai `human` hanya untuk pemeriksa manusia yang benar-benar melakukan penilaian.
  Jangan menyatakan gelar pakar atau persetujuan manusia tanpa bukti.
- Review JSON eksternal wajib mengisi `input_fingerprint` yang dihitung dengan
  `SemanticReview.fingerprint(claim, evidence, sources)` atas isi yang benar-benar
  dinilai. Nilai ini adalah pengikatan versi, bukan bukti penilaian manusia.
  Review legacy tanpa fingerprint harus dinilai ulang; jangan diisi retroaktif.
- `evidence.jsonl` menyimpan history. `current_evidence.json` menjadi input finalisasi
  terkini; snapshot immutable tiap run tetap tersedia. Revisi isi evidence perlu
  ID baru. Ulang input yang sama tidak menambah baris history.
- `search_options` menerima `queries`, `concepts`, `year_start`, `year_end`,
  `source_types`, `max_results_per_query` (1–200), `target_sources` (1–1000), dan
  `request_budget` (1–100). Crossref mendukung pagination offset sampai anggaran
  habis. Provider lain satu halaman per query. Seluruh kandidat dan alasan filter
  disimpan; lexical ranking bukan persetujuan relevansi ilmiah.
- Kapasitas lokal: dua workflow aktif lintas proses dan 16 request HTTP.
  Deadline kooperatif 900 detik diperiksa saat agent/tool/verifikasi berikutnya
  dimulai. Panggilan yang sedang berjalan tetap memakai timeout tool sendiri.
  Kapasitas penuh ditolak, bukan antrean tak berbatas. Lock proses terputus
  harus diperiksa sebelum pemulihan manual. Belum merupakan bukti soak produksi.


### Koreksi empat temuan review ulang

- Gate dukungan sumber memakai pemetaan alias publikasi yang sama dengan dedupe,
  termasuk record lintas provider tanpa DOI. DOI atau ISBN yang saling bertentangan
  tidak boleh digabung otomatis. Metadata bibliografis yang belum lengkap tetap
  memerlukan pemeriksaan; pencocokan identitas deterministik bukan review ilmiah.
- Konflik evidence ID diperiksa sebelum mengganti berkas input terkini. Penolakan
  revisi mempertahankan input sebelumnya. Revisi sah memakai evidence ID baru dan
  run immutable baru; jangan mengubah isi dengan ID lama untuk membuka blocker.
- Jika `search_options.concepts` diberikan, target discovery menghitung publikasi
  unik yang memuat seluruh konsep pada judul/abstrak (pencocokan literal tanpa
  membedakan huruf besar/kecil). Kandidat lain tetap disimpan untuk screening,
  tetapi tidak membuat target terpenuhi. Sinonim/variasi query harus dinyatakan
  oleh agent pengarah; kecocokan literal bukan persetujuan relevansi ilmiah.
- Tanpa konsep terstruktur, target masih berdasarkan filter tahun/jenis. Review
  kuantitatif memakai target discovery awal sedikitnya 40 kandidat, kecuali
  `target_sources` ditentukan eksplisit. Log menyatakan `target_candidate_count`
  dan `target_criteria`; tetap periksa jumlah sumber yang benar-benar layak.

### Integritas run saat ekspor

Run baru menyimpan `integrity_manifest.json` dengan hash dan lokasi relatif.
Ekspor menolak snapshot/sumber/output yang berubah, hilang, bertambah, atau
belum memiliki manifest penutupan. Run lama tanpa manifest perlu revisi/resume
menjadi run baru; jangan menambahkan hash retroaktif. Lokasi relatif artefak
memungkinkan ekspor proyek lengkap setelah dipindahkan. Ekspor tidak mengubah
run sumber; manifest ZIP terpisah berada dalam `exports/`.

Kegagalan snapshot awal menyertakan identitas run dan status gagal pada respons.
Ringkasan gagal dan workbook tersedia bila media dapat ditulis; kegagalan tulis
yang berlanjut dilaporkan jujur dan memerlukan pemeriksaan penyimpanan. Ini
bukan jaminan transaksi atomik seluruh berkas, ketahanan hard crash, atau bukti
anti-manipulasi jika manifest dan berkas sama-sama diganti.
