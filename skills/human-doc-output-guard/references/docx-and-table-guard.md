# Panduan Tata Letak DOCX, Tabel, & Spreadsheet
**Pelengkap Kebijakan `human-doc-output-guard`**

Dokumen ini memuat standar teknis untuk menghasilkan luaran berkas Word (`.docx`), tabel markdown, dan data lembar kerja (spreadsheet/Excel/CSV) yang rapi, sesuai norma perkuliahan/akademik, dan bebas dari ornamen berlebihan.

---

## 1. Standar Format Dokumen DOCX Akademik

Format naskah akademik mahasiswa Indonesia memiliki pakem yang sederhana dan konsisten. Hindari format berlebihan yang meniru brosur pemasaran atau laporan korporat tahunan.

### A. Tipografi & Tata Ruang
1. **Ukuran Kertas & Margin:**
   - Standar: Ukuran A4.
   - Margin: Umumnya 4 cm (kiri), 3 cm (atas, kanan, bawah) untuk skripsi/tesis; atau 2.54 cm (1 inci di semua sisi) untuk makalah/laporan tugas.
2. **Font & Ukuran:**
   - Font akademik standar: Times New Roman (12 pt), Arial (11 pt), atau Calibri (11 pt).
   - Heading 1: 14 pt (Tebal).
   - Heading 2: 12 pt (Tebal).
   - Spasi baris: 1.15 hingga 1.5 spasi. Jarak antar-paragraf secukupnya (after: 6 pt), tidak perlu enter ganda kosong berulang kali.
3. **Penyelarasan Teks (Alignment):**
   - Paragraf utama: Rata kiri (*Left*) atau Rata kanan-kiri (*Justify*) yang rapi tanpa spasi antar-kata yang renggang.
   - Judul & Subjudul: Mengikuti hierarki baku tanpa hiasan garis bawah warna-warni.

### B. Larangan Elemen "Brochure-Like"
Kecuali pengguna secara eksplisit meminta desain majalah, infografis, atau poster promosi:
- **DILARANG:** Menambahkan cover warna-warni berpola geometris jika hanya tugas esai biasa.
- **DILARANG:** Menambahkan bingkai halaman dekoratif (*page borders*).
- **DILARANG:** Menggunakan callout box warna ungu/biru terang dengan ikon emoji atau simbol modernis AI.
- **DILARANG:** Mengubah seluruh paragraf esai menjadi kartu-kartu mini atau diagram kotak yang tidak diminta.

---

## 2. Standar Tabel yang Wajar (Table Guard)

Tabel dibuat untuk mempermudah perbandingan data, bukan untuk memperpanjang halaman secara artifisial.

### A. Format Tabel yang Dianjurkan
1. **Lebar Kolom Proporsional (2–4 Kolom):**
   Tabel tugas mahasiswa umumnya terdiri atas 2 sampai 4 kolom, misalnya:
   - `No | Aspek | Teori A | Teori B`
   - `No | Indikator | Definisi Operasional | Sumber Data`
   - `No | Parameter | Nilai Observasi | Keterangan`
2. **Isi Sel Ringkas:**
   - Isi sel berupa kata kunci, angka, parameter, atau poin ringkas (1–2 kalimat pendek).
   - **JANGAN** menumpuk esai 3 paragraf panjang ke dalam satu sel tabel sempit. Jika penjelasannya panjang, letakkan di paragraf pembahasan di bawah tabel.
3. **Gaya Border Bersih:**
   - Gunakan format tabel formal: garis horizontal atas header, bawah header, dan penutup paling bawah (gaya tabel APA). Hindari garis vertikal tebal warna-warni.

### B. Larangan Penambahan Kolom Subjektif AI
- Jangan menambahkan kolom:
  - `Skor Efektivitas Menurut AI (1-10)`
  - `Tingkat Kepentingan (High/Medium/Low)`
  - `Rekomendasi Tambahan`
  kecuali jika kolom-kolom tersebut diminta secara spesifik oleh pengguna.

---

## 3. Perlindungan Format Data Spreadsheet (Excel / CSV / Tabular)

Ketika mengolah atau menghasilkan data tabel tabular:

1. **Format Identitas & Angka Awalan Nol (Leading Zeros):**
   - **NIM / NIK / Kode Pos / Nomor Responden:** Simpan selalu sebagai tipe teks (`text`/`string`). Jangan biarkan aplikasi spreadsheet memotong angka `0` di awal (contoh: `0812345` menjadi `812345`).
   - **Nomor HP / WhatsApp:** Pastikan diawali tanda kutip satu atau string jika diperlukan agar format `08...` atau `+62...` tidak rusak menjadi notasi ilmiah (misal: `8.12E+09`).

2. **Format Mata Uang & Tanggal Indonesia:**
   - Nilai Rupiah: Gunakan format `Rp1.500.000` atau angka bulat dengan header kolom menyebutkan satuan mata uang: `Pendapatan (Rp)`.
   - Tanggal: Format tanggal yang jelas (misal: `DD/MM/YYYY` atau `18 September 2026`), hindari format ambigu seperti `09/12/2026` tanpa penjelas.

3. **Integritas Sel Kosong (Zero Data Hallucination):**
   - Jika suatu data tidak ditemukan di file sumber, **BIARKAN KOSONG** atau isi dengan `-` / `N/A`.
   - Dilarang menebak angka rata-rata, mengarang persentase, atau menyisipkan estimasi tanpa persetujuan pengguna.

---

## 4. Prinsip "Micro-Surgery" pada Revisi Dokumen

Ketika pengguna meminta revisi pada dokumen DOCX atau lembar kerja yang sudah ada:
1. **Identifikasi Node Target:** Tentukan dengan presisi paragraf, baris tabel, atau sel mana yang diminta untuk diperbaiki.
2. **Jangan Rebuild Seluruh Dokumen:** Lakukan pembaruan hanya pada teks target. Membangun ulang seluruh berkas berisiko menghilangkan gaya penomoran khusus, catatan kaki, gambar, atau format margin yang sebelumnya sudah diatur oleh pengguna.
3. **Verifikasi Integritas Pasca-Edit:** Pastikan referensi silang (nomor tabel, nomor gambar) dan nomor halaman tidak berantakan setelah revisi disisipkan.
