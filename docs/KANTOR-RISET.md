# Kantor Riset AAI

Desain kantor animasi dipasang pada monitor AAI. Buka http://127.0.0.1:8000
setelah menjalankan monitor dari folder `DATA BASE`:

```powershell
python -m src monitor --port 8000
```

Halaman utama sekarang merupakan **Beranda AAI**, terpisah dari pekerjaan
riset tertentu. Kantor dan karakter tetap tampil dengan gerakan ringan saat
menunggu; gerakan menunggu bukan tanda pekerjaan sedang berlangsung.
Beranda menampilkan ringkasan pekerjaan berjalan, pekerjaan yang perlu
ditinjau, dan agent aktif dari catatan pekerjaan di workspace. Proyek dari
fixture pengujian otomatis dipisahkan berdasarkan jalur asalnya.

Biarkan monitor berjalan, lalu jalankan tugas AAI dari terminal lain seperti biasa.
Klik pekerjaan pada beranda untuk membuka `/riset?job_id=...`, atau pilih
**Kantor riset** untuk membuka `/riset`. Pilih pekerjaan pada daftar di atas kantor dan klik kartu peran untuk melihat
aktivitasnya. Halaman memperbarui catatan setiap dua detik. Tombol **Gerakan**
mengatur animasi. Monitor tahapan lama tetap tersedia di `/workflow`.
Tautan lama `/?job_id=...` tetap membuka rincian pekerjaan yang sama.

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

Pemeriksaan tambahan untuk beranda: 538 tes source lulus, 12 dikecualikan.
Bukti browser berada di
`TUGAS 1/beranda_kantor_animasi_di_luar_room_riset__home-integration_20261008T212742Z_63aa8663/`.

Catatan progres tetap append-only. Riwayat masih dipindai dari berkas;
indeks per pekerjaan dapat ditambahkan jika riwayat tumbuh besar.

## Nama, aktivitas santai, dan progres

Empat karakter memiliki nama tetap pada beranda dan kantor riset:

| Nama | Peran visual | Aktivitas ketika tidak bekerja |
| --- | --- | --- |
| Arka | Koordinator | Menikmati kopi |
| Dinda | Pencarian | Membaca buku |
| Fajar | Pembacaan | Peregangan ringan |
| Salsa | Reviewer | Bersantai sejenak |

Semua karakter selalu terlihat, termasuk saat belum ada tugas, pekerjaan
selesai, perlu ditinjau, gagal, atau koneksi terputus. Pose santai berasal dari
aset transparan `src/runtime/static/research-team-chibi-v4.png`, dibuat melalui
built-in imagegen dengan identitas dan pakaian karakter sebelumnya. Gerakan
santai merupakan dekorasi; jumlah agent aktif tetap berasal dari aktivitas
pekerjaan nyata. Klik karakter atau kartunya untuk memilih anggota tim.

Panel progres menampilkan identitas pekerjaan, status akhir, jumlah tahap
tercatat yang selesai, penanda tahap berwarna, dan daftar tahap terbaru.
Jumlah tahap tercatat bukan perkiraan total tahap riset. Catatan tahap yang
masih berjalan ketika pekerjaan berakhir tidak otomatis dianggap selesai.
Beranda memakai kartu pekerjaan dengan status dan waktu aktivitas terakhir.
Reduced motion dan tombol Gerakan menghentikan animasi pada kedua halaman.

Pemeriksaan browser untuk revisi ini dapat dijalankan dari `DATA BASE`:

```powershell
python "../TUGAS 1/nama_karakter_aktivitas_santai_dan_desain_progres__visual-upgrade_20261009T044144_afb6791a/check-visual.py"
```

Folder tersebut menyimpan `browser-check.json`, tangkapan layar beranda,
progres pekerjaan PDF nyata, tampilan ponsel/gelap, dan `image-prompt.txt`.
`contoh-progres-browser.png` menggunakan data uji yang hanya berada dalam
browser; data itu tidak ditulis ke riwayat pekerjaan.
