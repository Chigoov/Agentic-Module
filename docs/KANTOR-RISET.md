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
aktivitasnya. Halaman menerima pemberitahuan langsung melalui SSE; polling dua detik menjadi cadangan. Tombol **Gerakan**
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

Aktivitas Hermes Desktop kini dibaca langsung dari backend lokal yang sama dengan
aplikasi Desktop, termasuk chat dan tool di luar AAI. Observer memakai koneksi
WebSocket yang diautentikasi oleh Hermes; source dan konfigurasi Hermes tidak
perlu diubah. Sesi aktif pada profil default maupun asistenriset dikenali dari
snapshot native setelah identitas profil tersedia. Monitor hanya mengamati;
permintaan persetujuan tetap dijawab melalui Hermes.

Runtime monitor membutuhkan paket `websockets`. Pada komputer ini runtime Python
yang sudah memiliki paket tersebut dipakai untuk menjalankan monitor. Untuk
instalasi lain, extra yang disediakan repository adalah `pip install -e ".[monitor]"`.
Jika paket atau Hermes Desktop tidak tersedia, AAI tetap berjalan dan menampilkan
status sambungan yang sebenarnya. Dukungan langsung ini khusus backend Desktop
lokal yang ditemukan di spawn ledger; CLI dan Hermes di komputer lain belum diamati.

Catatan Hermes berada di `state/hermes-events.jsonl`, terpisah dari catatan AAI.
Catatan hanya berisi identitas sesi/profil, nama tool, urutan event, waktu pengamatan,
dan status. Isi prompt, jawaban, penalaran, argumen, hasil dokumen, dan token tidak
disimpan di sana. Pemanggilan helper `aai_read_pdf.py` dikorelasikan melalui job_id
hasil operasi agar pekerjaan AAI tersebut tidak dihitung dua kali.

Status selesai, gagal, dibatalkan, menunggu jawaban, dan status belum diketahui
memiliki label berbeda. Hilangnya sambungan tidak berarti tugas selesai. SSE
memberi tanda revisi, lalu browser mengambil snapshot terbaru; setelah reconnect
snapshot memulihkan keadaan terbaru tanpa perlu mengandalkan setiap frame SSE.
Riwayat AAI memakai cache berdasarkan perubahan log untuk menghindari pembacaan
ulang pada setiap event Hermes.

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

Layout menggunakan lebar jendela. Tombol **Fokus kantor** menyembunyikan panel
progres dan panel samping untuk memperbesar ruang; **Tampilkan panel**
mengembalikan keduanya. Karakter idle bergantian mengikuti rute pendek di
lantai dan bereaksi ketika karakter atau kartunya diklik. Aktivitas bekerja
mengambil alih posisi idle. Rute dekoratif tidak menulis event pekerjaan dan
tidak menambah jumlah agent aktif. Gerakan berhenti ketika tab tersembunyi,
koneksi putus, tombol Gerakan dimatikan, atau reduced motion aktif.

Target sambungan langsung ke Hermes, sumber event yang diperiksa, serta
syarat uji end-to-end ada di [GOAL-HERMES-REALTIME.md](GOAL-HERMES-REALTIME.md).
Dokumen goal mencatat kontrak native, batas pengujian, dan bukti implementasinya.

Pemeriksaan browser untuk revisi ini dapat dijalankan dari `DATA BASE`:

```powershell
python "../TUGAS 1/nama_karakter_aktivitas_santai_dan_desain_progres__visual-upgrade_20261009T044144_afb6791a/check-visual.py"
```

Folder tersebut menyimpan `browser-check.json`, tangkapan layar beranda,
progres pekerjaan PDF nyata, tampilan ponsel/gelap, dan `image-prompt.txt`.
`contoh-progres-browser.png` menggunakan data uji yang hanya berada dalam
browser; data itu tidak ditulis ke riwayat pekerjaan.


## Verifikasi sambungan Hermes Desktop, 10 Oktober 2026

Sambungan native telah lulus pemeriksaan dua profil, PDF AAI nyata, tool gagal,
pembatalan, clarify menunggu jawaban, dua tab, restart monitor dan replay.
P95 native WebSocket teramati ke DOM adalah 519,01 ms pada run lokal ini.
Source suite: 586 lulus, 12 dikecualikan; health check lulus.
Bukti dan skrip ulang berada di
`TUGAS 1/hermes_realtime__bridge_20261010T211437_836bd8de/implementation-check.json`.
Lihat goal untuk kontrak, rincian dan batas dukungan Desktop lokal.

## Dashboard per bot dan aktivitas Bengkel

Beranda `/` tetap merangkum semua pekerjaan. `/riset` memilih pekerjaan
AAI/Asisten Riset, sedangkan `/bengkel` memilih hanya profil Bengkel.
Kartu beranda mengarah ke halaman bot pemiliknya. URL
`?session_id=<durable Hermes session ID>` mengunci panel pada sesi sendiri;
`?job_id=<job ID>` juga tetap didukung. Pilihan pekerjaan tidak berganti
karena aktivitas baru dari bot atau sesi lain.

Bengkel disesuaikan dengan SOUL.md, bengkel-workflow, laporan transfer bug
dua caller, dan diagnosis read-only arsipnya. Arka mengoordinasikan,
Dinda memeriksa/menelusuri kode, Fajar memperbaiki kode, dan Salsa menjalankan
tes/build. Ini peran visual dari event alat, bukan empat bot baru.
Panel Bengkel menampilkan inspeksi, kode, pengujian, build, dan laporan
berdasarkan aktivitas yang tercatat. Tahap yang tidak dijalankan tetap
"Belum tercatat"; kompilasi file uji bukan bukti APK atau perangkat.

Klasifikasi hanya memakai nama alat dan argumen sementara di observer.
Argumen/perintah, hasil mentah, dan reasoning tidak disimpan dalam log.
Gerakan membaca, menelusuri, mengetik, menjalankan tes, dan build berbeda.
Semua karakter tetap terlihat dan bersantai saat idle.
Progres Hermes dihitung dari giliran tugas terbaru dalam sesi, dengan setiap
operasi alat dihitung terpisah. Exit code gagal tidak dianggap berhasil,
dan perintah background tanpa exit code tetap belum terkonfirmasi.

Preferensi USER.md untuk Asisten Riset dan Bengkel membuka URL per bot
dengan HERMES_SESSION_ID sendiri. Ini instruksi kepada model, bukan hook
deterministik. Pada uji native, Bengkel mematuhinya; Asisten Riset mengabaikannya
pada dua tugas baca singkat. Membuka link/panel secara manual tetap bekerja.
Perubahan preferensi dimuat pada sesi Hermes baru.

Verifikasi revisi: 587 tes source lulus, 12 dikecualikan; health check lulus.
Uji native Bengkel mencatat tes gagal, patch fungsi bersama, tes berhasil,
dan kompilasi berhasil. Animasi tes nyata tertangkap di browser.
Pemisahan bot, empat karakter setelah selesai, rute kartu, ukuran ponsel,
kontrol Gerakan/reduced motion, dan console browser lulus pemeriksaan.
Rendering panel di jendela aplikasi Hermes pengguna belum diverifikasi.
Bukti: `TUGAS 1/dashboard_bengkel__20261010T222926_990c0bcb/dashboard-acceptance.json`;
skrip ulang tanpa tugas model baru: `check-dashboard.py` pada folder itu.

## Posisi karakter dan lapisan meja

Ketiga kantor menggunakan titik lantai yang sama, pose duduk transparan
`research-team-seated-v5.png` (atlas 2x2), dan pose idle lama (atlas 4x2).
Margin transparan setiap karakter dikalibrasi agar dasar kursi/kaki sejajar
dengan titik lantai. Panel depan meja berasal dari gambar ruangan yang sama,
dipotong dengan CSS agar tubuh tidak menembus panel dan wajah tetap terlihat.
Ini tampilan 2.5D; ruangan belum berupa mesh 3D atau animasi skeletal.

Saat bekerja, kepala bergerak halus dan indikator mengikuti aktivitas alat;
kursi dan tubuh tetap pada meja. Beralih bekerja/idle tidak menggeser kursi.
Keempat karakter tetap terlihat saat idle dengan rute pendek di lantai.
Gerakan bisa dimatikan, menghormati reduced motion, dan berhenti saat tab
tidak terlihat. Putusnya koneksi monitor membekukan pose terakhir sampai
status kembali tersedia, tanpa menciptakan aktivitas pekerjaan baru.

Pemeriksaan browser (data simulasi hanya di halaman uji, tanpa tugas Hermes):

```powershell
python tests/office_scene_check.py --output "folder-bukti"
```

Uji ini memeriksa ketiga kantor, keempat pose, akhir tugas, gerakan idle,
putus/sambung koneksi, kontrol gerakan, reduced motion, dan ukuran ponsel.

Kartu Bengkel "Perintah tes/build berhasil" dapat diklik untuk membuka
rincian pemeriksaan pada giliran tugas yang dipilih. Angka A/B berarti A
perintah terkonfirmasi berhasil dari B operasi yang sudah berakhir;
perintah berjalan ditampilkan terpisah. Satu tool ID dihitung sekali,
sedangkan percobaan ulang dengan tool ID baru merupakan operasi lain.
Daftar dapat difilter berdasarkan berhasil, gagal, belum terkonfirmasi,
atau berjalan, dengan jenis tes/build, nama alat, waktu, dan identitas operasi.
Tidak ada rekonstruksi nama kasus tes atau alasan kegagalan dari ringkasan
observer; rincian tersebut perlu diperiksa pada laporan/chat Hermes.

## Workflow live per tugas

Kantor Riset dan Bengkel menampilkan urutan operasi alat dari giliran tugas
yang dipilih. Aktivitas sejenis yang berurutan digabung dalam satu kartu;
aktivitas sejenis yang muncul lagi setelah aktivitas lain menjadi langkah
baru sehingga pengulangan diagnosis/kode/tes tetap terlihat. Klik kartu
untuk membuka nama alat, status, waktu, dan identitas setiap operasi.
"Langkah terbaru" menuju kartu terakhir. Urutan ini adalah jejak pelaksanaan,
bukan daftar rencana atau bukti hubungan sebab-akibat antara dua operasi.
Tes/build selesai tanpa hasil terkonfirmasi tetap dibedakan dari berhasil.
Mulai giliran baru membersihkan alur giliran sebelumnya tanpa menghapus log.
Riwayat tugas yang dipilih dikirim lengkap agar awal giliran dan hitungan
operasi tidak hilang setelah 1.000 aktivitas. Ringkasan seluruh tugas tetap
dibatasi pada 1.000 aktivitas terakhir.
