# Contoh Alur Dry-Run Akademik (Dry-Run Academic Prompt)

Dokumen ini mendemonstrasikan contoh interaksi lengkap antara Pengguna dan AI Agen dalam menjalankan protokol riset akademik **AUTONOMI AGENTIC ILMIAH** dari awal hingga pengemasan luaran.

---

## 1. Skenario & Permintaan Pengguna

**Prompt Pengguna:**
> "Saya membutuhkan tinjauan pustaka ilmiah mengenai peran program edukasi hukum dan dukungan sosial bagi remaja usia 12–18 tahun dari keluarga yang bercerai (studi kasus Edjust). Tolong carikan sumber nyata, buatkan draf akademis dengan sitasi APA 7, jalankan audit integritas di repositori, dan siapkan dokumen Word resminya."

---

## 2. Alur Penalaran & Tindakan Agen AI

### Langkah 1: Deteksi Kapabilitas Lingkungan (Capability Detection)
Agen memeriksa environment:
* Sandbox terminal: Tersedia (dapat mengeksekusi perintah shell PowerShell).
* Akses berkas: Tersedia (dapat membuat dan membaca berkas di workspace).
* Internet Search: Tersedia (dapat melakukan pencarian web dan verifikasi API).
* **Kesimpulan Mode:** **Full Mode Aktif**.

### Langkah 2: Verifikasi Awal Repositori
Agen menjalankan health check di root folder `DATA BASE`:
```powershell
python -m src check
```
*Respons:* `[OK] System health check passed` (Spec version: 1.0, Build phase: 18).

### Langkah 3: Penemuan & Verifikasi Sumber Nyata (Anti-Halusinasi)
Agen melakukan pencarian web ke basis data resmi (Crossref / PubMed) dan mencatat metadata faktual:
1. **Paul R. Amato (2000):**
   * Judul: *The Consequences of Divorce for Adults and Children*
   * Jurnal: *Journal of Marriage and Family*, Vol. 62, No. 4, hlm. 1269–1287.
   * DOI: `10.1111/j.1741-3737.2000.01269.x` (Terverifikasi aktif).
2. **JoAnne L. Pedro-Carroll (2005):**
   * Judul: *Fostering resilience in the aftermath of divorce: The role of evidence-based programs for children*
   * Jurnal: *Family Court Review*, Vol. 43, No. 1, hlm. 52–64.
   * DOI: `10.1111/j.1744-1617.2005.00007.x` (Terverifikasi aktif).
3. **Jennifer McIntosh (2000):**
   * Judul: *Child-inclusive divorce mediation: Report on a qualitative research study*
   * Jurnal: *Mediation Quarterly*, Vol. 18, No. 1, hlm. 55–69.
   * DOI: `10.1002/crq.3890180106` (Terverifikasi aktif).

*(Catatan Etika: Tidak ada data pribadi subjek remaja yang digunakan; fokus murni pada evaluasi program dan teori resiliensi).*

### Langkah 4: Penyusunan Payload Input JSON
Agen menyusun berkas `input_edjust_mini.json` sesuai skema Pydantic:
* `project`: Mengarahkan path absolut ke `TUGAS 1\edjust-mini`.
* `sources`: Memasukkan ketiga sumber dengan `state: "APPROVED"` dan atribut `volume`, `issue`, `pages`, dan `doi` lengkap.
* `claims`: Menyusun proposisi terukur dengan bahasa akademis (*hedging*), terhubung 1:1 dengan sumber pendukung.
* `evidence`: Menyajikan ringkasan temuan empiris abstrak dengan locator `"abstract"`.
* `outline`: Memetakan bab dan sub-bab sesuai klaim.

### Langkah 5: Eksekusi Alur Penulisan & Audit Akademik
Agen mengeksekusi pipeline di terminal:
```powershell
python -m src run-academic --input-json input_edjust_mini.json
```
*Hasil:* Alur otomatis menyelesaikan 6 tahapan:
1. `synthesis` ✅
2. `outline` ✅
3. `writing` ✅
4. `citation_audit` ✅
5. `fact_audit` ✅
6. `docx_generation` ✅

### Langkah 6: Pemeriksaan Integritas & Pengemasan Berkas
Agen melakukan verifikasi artefak yang dihasilkan:
1. Meninjau `draft.md`: Memastikan sitasi in-text presisi (`... (Amato, 2000).`) dan daftar pustaka lengkap.
2. Memeriksa `citation_audit.json`: `passed: true`, 0 token internal, 0 orphan citation.
3. Memeriksa `fact_audit.json`: `passed: true`, 0 unsupported claims.
4. Mengemas seluruh berkas dan audit trail per-run ke dalam arsip ZIP portabel:
   ```powershell
   python -m src export-bundle --input-json input_edjust_mini.json
   ```
   *Hasil:* Terbentuk berkas `exports/bundle_run_<timestamp>_<id>.zip`.

---

## 3. Contoh Tanggapan Akhir Agen kepada Pengguna

> "Tinjauan pustaka ilmiah mengenai program edukasi hukum dan dukungan sosial bagi remaja pasca-perceraian telah selesai disusun dan diverifikasi secara utuh:
> 
> 1. **Sumber Terverifikasi (Crossref DOI):**
>    - Amato, P. R. (2000). *The Consequences of Divorce for Adults and Children*. *Journal of Marriage and Family*, 62(4), 1269–1287.
>    - Pedro-Carroll, J. L. (2005). *Fostering resilience in the aftermath of divorce*. *Family Court Review*, 43(1), 52–64.
>    - McIntosh, J. (2000). *Child-inclusive divorce mediation*. *Mediation Quarterly*, 18(1), 55–69.
> 
> 2. **Hasil Audit Otomatis:**
>    - Audit Sitasi: Lulus (`passed: true`, bebas token internal LLM).
>    - Audit Fakta: Lulus (`passed: true`, seluruh klaim terbukti secara empiris).
> 
> 3. **Berkas Luaran yang Dihasilkan:**
>    - Naskah Microsoft Word: `TUGAS 1\edjust-mini\final.docx`
>    - Draft Markdown: `TUGAS 1\edjust-mini\draft.md`
>    - Berkas Arsip Mandiri: `TUGAS 1\edjust-mini\exports\bundle_<run_id>.zip`
> 
> *Peringatan Integritas:* Naskah ini siap ditelaah dan diverifikasi secara kritis oleh Anda sebelum diserahkan atau dipublikasikan."
