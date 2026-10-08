# Kantor Riset AAI

Desain kantor animasi dipasang pada monitor AAI. Buka http://127.0.0.1:8000
setelah menjalankan monitor dari folder `DATA BASE`:

```powershell
python -m src monitor --port 8000
```

Biarkan monitor berjalan, lalu jalankan tugas AAI dari terminal lain seperti biasa.
Pilih pekerjaan pada daftar di atas kantor dan klik kartu peran untuk melihat
aktivitasnya. Halaman memperbarui catatan setiap dua detik. Tombol **Gerakan**
mengatur animasi. Monitor tahapan lama tetap tersedia di `/workflow`.

## Data yang ditampilkan

- `BaseAgent.execute` menerbitkan awal dan akhir aktivitas nyata, termasuk tugas
  yang dijalankan melalui CLI dan API.
- Satu pemanggilan agent utama memiliki `job_id` baru. Agent turunannya berbagi
  identitas pekerjaan tersebut, dengan `agent_id` masing-masing.
- Empat tempat di kantor merupakan kelompok peran: koordinasi, pencarian,
  pembacaan, dan pemeriksaan. Tempat itu bukan bukti empat pekerja paralel.
- `completed` dan `success` berarti operasi selesai. `partial`, `pending`,
  `blocked`, dan `failed` ditampilkan terpisah. Penyelesaian operasi bukan
  bukti artikel sudah terverifikasi atau dokumen siap dipublikasikan.
- Angka kandidat dan dokumen berasal dari catatan operasi; tanda `—` berarti
  jumlah belum tersedia. Tidak ada persentase atau jumlah sumber yang ditebak.
- Saat koneksi terputus, gerakan bekerja berhenti, catatan terakhir dipertahankan,
  dan halaman mencoba menyambung kembali.

Hermes yang menjalankan perintah AAI melalui terminal ikut menghasilkan catatan
AAI. Aktivitas percakapan atau alat Hermes di luar AAI belum tersambung.
Source dan konfigurasi Hermes tidak diubah untuk integrasi ini.

## Pemeriksaan integrasi

Uji membaca PDF lokal melalui `RetrievalAgent` menghasilkan 9 halaman dan
63.064 karakter. Hash PDF asli tetap sama. Pengujian ini memeriksa ekstraksi
teks dan sambungan monitor; tidak melakukan verifikasi ilmiah artikel.

Bukti dan skrip pemeriksaan berada di:

```text
TUGAS 1/uji_integrasi_kantor_pembacaan_satu_pdf_lokal__monitor-integration_20261008T211725Z_73675caf/
```

File utamanya: `integration-evidence.json`, `extracted-text.txt`,
`browser-check.json`, `check-browser.py`, dan `kantor-live-desktop.png`.

Validasi source: 537 tes lulus, 12 tes dikecualikan oleh konfigurasi suite,
serta health check lulus. Pemeriksaan browser mencakup data pekerjaan asli,
pemilahan pekerjaan, kartu agent, aset gambar, layar 1024/736/320 piksel,
tema gelap, reduced motion, serta koneksi putus dan pemulihannya.

Catatan progres tetap append-only. Riwayat masih dipindai dari berkas;
indeks per pekerjaan dapat ditambahkan jika riwayat tumbuh besar.
