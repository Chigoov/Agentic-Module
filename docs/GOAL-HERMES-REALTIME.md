# Goal: kantor visual mengikuti aktivitas Hermes secara real time

Implementasi 10 Oktober 2026. Status: VERIFIED pada backend Desktop lokal, 6/6 tahap penerimaan lulus.

## Hasil dan pendekatan

Monitor AAI mengamati sesi Hermes Desktop lokal, menampilkan awal turn, tool yang
sedang berjalan, akhir tool, penulisan jawaban, dan status terminal. Tidak perlu
menambahkan prompt monitor pada setiap tugas. Beranda menggabungkan pekerjaan;
ruang riset mengikuti sesi pilihan. Arka, Dinda, Fajar, Salsa adalah peran visual,
bukan klaim empat agent Hermes paralel. Animasi santai tetap dekorasi.

Rencana hook/webhook awal diganti dengan transport native yang sudah tersedia:
JSON-RPC WebSocket Hermes memiliki fanout tambahan dan replay. Observer membaca
spawn ledger loopback, memperoleh token sesi dari halaman backend lokal, lalu
memakai `/api/ws`. Token hanya ada dalam memori. Tidak dibuat receiver POST baru,
sehingga gate signature webhook tidak berlaku pada pendekatan ini; autentikasi
menggunakan pemeriksaan token dan origin WebSocket milik Hermes. Source/config
Hermes, model, provider, persona, dan aturan riset tidak diubah.

## Enam tahap penerimaan

1. **Kontrak sesi/event.** `session.active_list` menemukan runtime session ID;
   `session.activate` dengan omit_messages memasang observer tambahan dan memberi
   stored session ID serta profile_name. Snapshot lazy tanpa profil ditunggu sampai
   hydration selesai. `session.events.since` menyediakan replay, seq, epoch, dan
   open_requests. Event_id menggabungkan epoch, runtime ID, seq, tahap, status.
   Tool_id membedakan tool paralel; event lama tidak mengubah keadaan yang lebih baru.
2. **Observer Desktop.** `message.start`, `tool.start`, `tool.complete`,
   `message.delta`, `message.complete` dibaca dari backend Desktop yang nyata.
   Permintaan native approval/clarify menjadi pending. Observer tidak menawarkan
   kemampuan menjawab permintaan tersebut dan tidak mengintervensi chat pengguna.
3. **Riwayat aman/korelasi.** Journal Hermes terpisah, append-only, deduplicated.
   Hanya identitas/status/nama tool disimpan; prompt, teks jawaban/penalaran,
   args/result mentah dan token tidak disimpan. Job_id yang dikembalikan helper PDF
   dikenal dipakai untuk meniadakan hitungan ganda AAI. Batas korelasi otomatis ini
   adalah helper `aai_read_pdf.py`, bukan semua perintah terminal arbitrer.
4. **Browser/reconnect.** EventSource bawaan browser menerima revisi melalui SSE;
   snapshot API memberikan keadaan terkini, polling dua detik menjadi cadangan.
   Reconnect mengambil snapshot lengkap; bukan janji replay setiap frame SSE lewat
   Last-Event-ID. Server multithread mendukung beberapa tab, heartbeat dan penutupan
   koneksi. Cache ringkasan AAI diinvalidasi oleh mtime/size log.
5. **Visual/status.** Pencarian → Dinda; pembacaan/ekstraksi → Fajar; pemeriksaan →
   Salsa; penyiapan/penulisan jawaban dan tool umum → Arka. Nama tool asli ditampilkan.
   completed/failed/cancelled/pending/unknown berbeda. Sambungan hilang atau sesi
   idle tanpa terminal menghasilkan unknown, bukan completion buatan. Semua karakter
   tetap terlihat; aktivitas dekoratif tidak menambah jumlah aktif.
6. **Bukti nyata.** Pembacaan PDF lewat helper AAI, kegagalan read_file terkontrol,
   pembatalan native, dua sesi dan dua tab, clarify pending, restart monitor,
   replay pending, terminal setelah jawaban, dedup/persistensi dan browser diperiksa.
   Target lokal p95 pengamatan-native → DOM ≤ 1 detik. Uji unit melengkapi pemeriksaan
   Desktop; fixture tidak ditulis ke riwayat kantor. Penilaian ilmiah tidak dilakukan
   oleh uji transport PDF ini. Tes penuh dan health check diperlukan.

## Kontrak pemetaan

| Frame native | Catatan kantor |
| --- | --- |
| message.start | job running, model running |
| tool.start: tool_id, name, args | tool running dan visual_role; args dibuang |
| tool.complete: tool_id, name, result | tool completed/failed, model running; result dibuang |
| message.delta | menulis jawaban satu kali; teks dibuang |
| message.complete: status complete/error/interrupted | completed/failed/cancelled |
| request approval/clarify | pending; pertanyaan/jawaban tidak disimpan |
| transport hilang/native idle tanpa terminal | unknown; tidak ada klaim selesai |

Sumber kontrak yang dibaca pada instalasi lokal: `tui_gateway/ws.py`,
`session_transports.py`, `event_replay.py`, `methods_session.py`, `server.py`,
`contracts/events.py`, `contracts/sessions.py`, `contracts/server_requests.py`.

Bukti run unik:
`TUGAS 1/hermes_realtime__bridge_20261010T211437_836bd8de/`.
File: `native-desktop-check.json`, `native-recovery-check.json`,
`native-event-trace.json`, `native-desktop-latency.json`, screenshot, dan dua
skrip pemeriksaan native. Trace hanya menyimpan jenis/seq/nama/status/waktu,
bukan payload pribadi. `native-normalized-examples.json` berisi contoh aman.

## Batas aktual

Observer satu backend Desktop lokal yang ditemukan di ledger. Tidak mengamati CLI,
server remote, atau semua backend Desktop sekaligus. Snapshot sesi native dapat
memuat inflight di memori sementara meskipun omit_messages aktif; field tersebut
segera dibuang. Replay native memiliki ring terbatas; bila terminal sudah hilang dan
snapshot tak dapat membuktikan outcome, status unknown dipertahankan. Identitas profil pada proyeksi memakai pengamatan native terbaru untuk sesi/runtime
yang sama; koreksi pengamatan lazy lama tidak menggandakan pekerjaan atau menulis
ulang journal. Sesi idle yang
belum pernah diamati tidak dibuka untuk menghindari menahan seluruh riwayat Desktop.
Sesi yang sudah diamati tetap terpasang selama koneksi observer hidup.

Pengukuran waktu dimulai ketika observer menerima event, bukan ketika pengguna
menekan Kirim atau waktu provider memproses model. Pekerjaan sangat singkat tetap
tercatat dalam timeline walaupun browser dapat menggabungkan revisi tampilan.

## Hasil pemeriksaan akhir

- `native-desktop-check.json`: dua profil dikenali, PDF nyata berkorelasi dengan
  AAI, kegagalan tool terkontrol dan pembatalan native tercatat.
- `native-recovery-check.json`: dua tab, status clarify pending, restart monitor,
  replay pending, completion sesudah jawaban, catatan tersimpan dan dedup lulus.
- `native-wire-latency.json`: p95 native WebSocket teramati → DOM 519,01 ms;
  p95 observer → DOM 512,97 ms. Operasi read_file 1.457,05 ms menghasilkan
  terminal yang tercatat; operasi PDF terminal sekitar 11,6 detik.
- `browser-state-check.json`: fixture khusus browser memastikan turn baru
  membersihkan aktivitas lama yang dibatalkan, unknown tidak dianggap selesai,
  empat karakter tetap terlihat dan kontrol gerakan bekerja. Tidak menulis
  fixture ke riwayat kantor dan tidak menggantikan pengujian native di atas.
- Source suite 586 passed, 12 deselected; health check dan diff whitespace lulus.
- `implementation-check.json` merangkum bukti 6/6. Sesi pengguna tidak dibatalkan;
  pembatalan/persetujuan percobaan hanya dilakukan dalam sesi uji milik run ini.

VERIFIED berlaku pada hasil lokal ini dan batasnya, bukan jaminan pengukuran yang
sama pada setiap mesin/model atau deployment publik.
