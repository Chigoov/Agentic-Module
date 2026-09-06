# CARA CEPAT UNTUK ORANG AWAM
## AUTONOMI AGENTIC ILMIAH

## 1. Menyalakan Monitor

Double-click file ini:

```text
OPEN_LIVE_PROGRESS.bat
```

File itu akan membuka PowerShell untuk menjalankan server, lalu membuka
dashboard di browser.

Jika ingin menjalankan monitor di jendela yang sama, double-click:

```text
START_MONITOR.bat
```

Lalu buka:

```text
http://127.0.0.1:8000
```

Jangan tutup jendela PowerShell/CMD selama monitor masih dipakai.

## 2. Memanggil Plugin di Codex

Di chat Codex, panggil:

```text
[@Autonomi Agentic Ilmiah](plugin://autonomi-agentic-ilmiah@personal)
```

Lalu tulis tugasnya dengan bahasa biasa, misalnya:

```text
Gunakan project AUTONOMI AGENTIC ILMIAH.
Cek sistem, lalu buat plan untuk topik:
"dampak perceraian orang tua terhadap remaja".
```

## 3. Prompt Paling Singkat

```text
[@Autonomi Agentic Ilmiah](plugin://autonomi-agentic-ilmiah@personal)

Jalankan check, lalu buat plan untuk topik: <isi topik saya>.
Di awal setiap jawaban, tampilkan:
Live progress: http://127.0.0.1:8000
```

## 4. Prompt Dengan Live Progress

```text
[@Autonomi Agentic Ilmiah](plugin://autonomi-agentic-ilmiah@personal)

Gunakan monitor localhost: http://127.0.0.1:8000.
Di awal setiap jawaban, tampilkan link live progress tersebut.
Jalankan check, lalu kerjakan tugas saya:
<tulis tugas di sini>
```

## 5. Untuk Melihat Progress

Double-click:

```text
OPEN_LIVE_PROGRESS.bat
```

Atau buka dashboard:

```text
http://127.0.0.1:8000
```

Progress akan muncul setelah sistem menjalankan `check`, `plan`, atau workflow.
Tampilannya berbentuk flowchart: input pengguna, intent, rencana, konteks,
tool, eksekusi, validasi, dan output akhir.

## 6. Cara Menghentikan

Klik jendela PowerShell/CMD yang menjalankan monitor, lalu tekan:

```text
Ctrl + C
```
