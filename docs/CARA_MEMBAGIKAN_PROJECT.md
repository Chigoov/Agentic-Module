# CARA MEMBAGIKAN PROJECT
## AUTONOMI AGENTIC ILMIAH

Cara paling mudah membagikan project ini adalah lewat GitHub.

## Untuk Pengguna Biasa

1. Clone repository:

```powershell
git clone https://github.com/Chigoov/Agentic-Module.git
cd "Agentic-Module"
```

2. Install dependency:

```powershell
python -m pip install -r requirements.txt
```

3. Cek sistem:

```powershell
python -m src check
```

4. Buat plan:

```powershell
python -m src plan "topik riset"
```

## Untuk AI Agent

AI agent dapat membaca:

- `AGENTS.md`
- `docs/CARA_PAKAI_UNTUK_AI_AGENT.md`
- `skills/autonomi-agentic-ilmiah/SKILL.md`

## Sebagai Codex Skill

Folder skill ada di:

```text
skills/autonomi-agentic-ilmiah/
```

Untuk memasangnya secara lokal ke Codex, salin folder itu ke:

```text
C:\Users\<nama-user>\.codex\skills\autonomi-agentic-ilmiah
```

Setelah itu skill dapat dipanggil sebagai:

```text
$autonomi-agentic-ilmiah
```

## Rekomendasi

Untuk tahap sekarang, bagikan lewat GitHub + skill folder. PyPI/package install
belum wajib sampai project ini benar-benar perlu dipakai banyak orang dari
command `pip install`.

## Sebagai Codex Plugin Lokal

Versi plugin lokal sudah dibuat di:

```text
C:\Users\HYPE AMD\plugins\autonomi-agentic-ilmiah
```

Marketplace personal Codex sudah menunjuk ke plugin itu melalui:

```text
C:\Users\HYPE AMD\.agents\plugins\marketplace.json
```

Jika Codex belum menampilkan plugin, tutup dan buka lagi aplikasi Codex, lalu
cari **Autonomi Agentic Ilmiah** di daftar plugin personal.
