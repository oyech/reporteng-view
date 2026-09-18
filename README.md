# ReportEng — Flask

Aplikasi baca laporan engineering dari Supabase. Tabel menampilkan Tanggal,
Area Kerja, Unit/Area, Pekerjaan, Status, PIC, dan Foto. Tersedia filter gabungan,
pencarian, pagination, preview foto, ringkasan status, dan export Excel `.xlsx`
untuk seluruh hasil filter, bukan hanya halaman yang terlihat.

## Menjalankan

Python 3.9 atau lebih baru.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Instalasi baru saja: salin .env.example ke .env dan isi key.
python app.py
```

Buka http://127.0.0.1:5000. File `.env` di workspace ini sudah berisi koneksi
pengguna dan nama tabel `report_eng`; file tersebut tidak masuk Git.

## Pemetaan struktur asli

| Tampilan | Sumber |
|---|---|
| Tanggal | `created_date`, ditampilkan dalam zona UTC |
| Area Kerja | `area_kerja` pada laporan induk |
| PIC | `pic` pada laporan induk |
| Unit/Area | Key `unit_area` dalam setiap `report_items` |
| Pekerjaan | Key `pekerjaan` dalam setiap `report_items` |
| Status | Key `status` dalam setiap `report_items` |
| Foto | Key `foto` dalam setiap `report_items` |

Satu laporan induk dapat menghasilkan beberapa baris pekerjaan. `report_items`
berisi array kosong menghasilkan nol baris pekerjaan. `created_at`, `updated_at`,
dan `user_id` tidak digunakan untuk tanggal laporan maupun ditampilkan.

Contoh format isi `report_items` yang didukung (ilustrasi, bukan data asli):

```json
[
  {
    "unit_area": "Chiller",
    "pekerjaan": "Pemeriksaan pompa",
    "status": "Selesai",
    "foto": ["https://example.com/foto.jpg"]
  }
]
```

Key JSON tidak membedakan kapitalisasi, spasi, garis bawah, atau slash;
`Unit/Area`, `unitArea`, dan `unit_area` dikenali sebagai nama yang sama.
Alias tambahan: unit (`unit`, `area`, `unit_name`), pekerjaan (`description`,
`job`, `work`, `deskripsi`, `activity`), foto (`photos`, `photo`, `photo_url`,
`photo_urls`, `images`, `image_url`). Jika key berbeda, atur `COL_UNIT_AREA`,
`COL_PEKERJAAN`, `COL_STATUS`, `COL_FOTO` pada `.env`, kemudian mulai ulang Flask.
Objek bersarang memerlukan penyesuaian berdasarkan contoh JSON aslinya.

Foto mendukung URL HTTP(S), daftar URL, atau objek berisi `url`/`publicUrl`.
Path relatif Storage perlu menjadi URL terlebih dahulu. Bucket privat membutuhkan
URL bertanda tangan yang belum kedaluwarsa. Excel menyertakan URL foto dan tautan
klik pada foto pertama; gambar tidak ditanam ke workbook.

## Periode dan filter

- Default periode: awal bulan sampai hari ini. Kosongkan tanggal untuk seluruh
  periode dan klik **Terapkan filter**.
- Filter tanggal dikirim ke Supabase pada `created_date` dan mengikuti
  UTC. Tanggal akhir inklusif: batas sebelum pukul 00.00
  hari berikutnya. Urutan laporan memakai `created_date.desc,id.desc`.
- Area, unit, status, PIC, dan pencarian digabungkan setelah item diuraikan.
- Export mengikuti filter yang sudah diterapkan pada tabel.
- Semua halaman Supabase diambil. Batas 100.000 laporan/item menghasilkan pesan
  untuk mempersempit periode; data tidak diekspor separuh secara diam-diam.
- Data dibaca ulang saat export. Perubahan database saat pembacaan berlangsung
  dapat menghasilkan perbedaan dari tampilan terakhir karena REST bukan snapshot
  transaksi.

## Koneksi dan pengujian

Verifikasi struktur asli berhasil: endpoint dengan `id,created_date,pic,
area_kerja,report_items` mengembalikan HTTP 200 dan `[]`. Sampel JSON nyata belum
tersedia. Respons kosong dapat berarti tabel belum berisi data atau kebijakan
RLS tidak memperlihatkan baris pada role `anon`.

Aplikasi memakai publishable key dan access token pengguna di backend. Token
dikirim sebagai Bearer ke Supabase agar RLS mengenali pengguna yang login.
Secret key tidak diperlukan. Aplikasi hanya membaca laporan.

```bash
python -m unittest discover -s tests -v
# Deployment dengan WSGI:
gunicorn --bind 127.0.0.1:8000 --workers 2 --timeout 120 app:app
```

19 pengujian menggunakan respons Supabase tiruan: login, CSRF, anggota/nonanggota,
sesi berakhir, logout, penolakan API/export anonim, serta penguraian `report_items`,
pewarisan PIC/area, tanggal Jakarta, pagination, filter gabungan, validasi,
export Excel, serta pencegahan formula dari isi database.
Policy database belum diterapkan atau diuji pada proyek Supabase; pengujian
Python menggunakan mock dan tidak membuktikan hasil RLS di database sebenarnya.


## Login untuk membaca seluruh laporan tim

1. Jalankan versi terbaru `supabase/team_access.sql` melalui SQL Editor proyek
   Supabase. SQL ini mengganti policy laporan lama yang memakai
   `reporteng_team_members` menjadi pemeriksaan `profiles`.
2. Akun harus tersedia di Supabase Auth dan mempunyai baris di `public.profiles`
   dengan `profiles.id = auth.users.id`. Kolom `profiles.id` sudah diverifikasi
   tersedia; relasi nilainya harus sesuai akun login.
3. Buka `/login` dan masuk dengan email/password akun tersebut. Tidak perlu
   mendaftarkan akun lagi ke tabel anggota terpisah.

Setiap pemilik profil diberi akses seluruh laporan tim. Ini mengasumsikan semua
akun dalam `profiles` memang anggota organisasi yang boleh membaca laporan.
Aplikasi memverifikasi identitas lewat Supabase Auth lalu mencari profil dengan
ID persis pengguna itu; profil pengguna lain tidak dapat memberi akses.

Policy baru memberi izin pengguna membaca profilnya sendiri, membatasi SELECT
laporan pada akun yang punya profil, dan menolak akses anonim. Policy restrictive
lain tetap berlaku; tinjau bila data masih tidak terlihat. SQL tidak menghapus
`reporteng_team_members` atau mengubah policy tulis laporan. Policy berlaku juga
bagi aplikasi lain yang membaca tabel yang sama.

Migrasi SQL belum dijalankan dari workspace; publishable key tidak bisa menerapkan
perubahan schema. Setelah menjalankannya, uji akun dengan profil, akun tanpa
profil, dan akses tanpa login. Pengujian Python tidak menggantikan uji RLS nyata.

## Penyimpanan sesi

- Cookie HttpOnly bertanda tangan hanya menyimpan ID sesi, CSRF, dan penanda
  persistent. Cookie diperpanjang pada setiap request (masa simpan 10 tahun).
- Access token dan refresh token disimpan di `instance/sessions.sqlite3` dengan
  izin file 0600; keduanya tidak dikirim ke JavaScript atau disimpan dalam cookie.
- Token diperbarui menjelang kedaluwarsa atau setelah penolakan token pertama.
  Rotasi diserialisasi dengan transaksi SQLite agar beberapa tab/worker tidak
  memakai refresh token yang sama secara bersamaan.
- Error jaringan atau autentikasi tidak menghapus sesi dan tidak memaksa browser
  pindah halaman. Akses data tetap memerlukan verifikasi pengguna dan profil.
  Tombol Keluar menghapus sesi aplikasi pengguna tersebut saja.
- Migrasi menambahkan kolom refresh token tanpa menghapus sesi lama. Sesi lama
  tanpa refresh token tetap dipakai selama token masih valid; setelah kedaluwarsa
  pengguna perlu login sekali untuk memperoleh refresh token.
- Pencabutan sesi/akses atau kebijakan sesi Supabase tetap berlaku dan dapat
  mengharuskan autentikasi ulang; aplikasi tidak melewati pemeriksaan akses.
- Pertahankan `FLASK_SECRET_KEY` yang sama saat restart dan pada seluruh worker
  supaya cookie yang sudah ada tetap valid. Gunakan `COOKIE_SECURE=true` pada HTTPS.
- Seluruh worker satu server memakai SQLite yang sama. Beberapa host membutuhkan
  session store bersama yang mendukung penguncian rotasi token.

Referensi: [Supabase RLS](https://supabase.com/docs/guides/database/postgres/row-level-security)
dan [login email/password](https://supabase.com/docs/reference/python/auth-signinwithpassword).

## Kalender tanggal laporan

Filter dan tampilan `created_date` mengikuti UTC secara
default, sesuai kalender tanggal aplikasi sumber. Contoh: `7 September 17:00 UTC`
tetap masuk periode sampai 7 September; tidak digeser menjadi 8 September Jakarta.
Tanggal akhir inklusif sampai sebelum 00:00 hari berikutnya. `created_at` dan
`updated_at` bukan tanggal pekerjaan dan tidak dipakai sebagai penggantinya.
Setelah perubahan backend ini, mulai ulang proses Flask pada server port 8080.

Waktu tabel dan Excel memakai format `YYYY-MM-DD HH:mm:ss` dalam UTC, termasuk
detik, sesuai nilai `created_date` Supabase. Pecahan detik hanya disimpan di data API.

## Pencarian kode item

Buka `/kode-item` atau menu **Kode Item** setelah login. Pencarian mendukung
kode lengkap/potongan kode dan beberapa kata nama, merek, atau ukuran tanpa
membedakan kapital. Hasil ditampilkan 25 baris per halaman dan tersedia tombol
salin kode. Pada HTTP yang membatasi clipboard, tombol membuka kode terpilih
agar bisa disalin manual.

Katalog berasal dari `Kode Item.xlsx`: 8.486 baris, 2.337 kode unik, dan 2.356
pasangan kode–nama. Data sumber disimpan dalam `data/items.json`, bukan aset
publik; pasangan identik diringkas hanya saat pencarian. Variasi nama untuk
kode sama tetap ditampilkan. Katalog merupakan salinan saat impor, bukan tautan
langsung ke file Downloads. Setelah mengganti JSON, restart worker untuk
memperbarui cache katalog.

Deployment fitur ini menyertakan `item_catalog.py`, `data/items.json`,
`templates/items.html`, `templates/_sidebar.html`, `static/items.css`,
`static/items.js`, serta perubahan `app.py` dan `templates/index.html`. Restart
proses Flask dengan konfigurasi secret dan penyimpanan sesi yang sama.
## Pricelist pekerjaan

Menu **Pricelist Pekerjaan** tersedia di `/pricelist` setelah login. Data dari
`Pricelist FLT.xlsx` disimpan di `data/pricelist.json`, sehingga aplikasi tidak
bergantung pada file di folder Downloads.

- Pekerjaan & material: 299 rincian dari Lampiran 3, dengan pencarian, filter
  kategori, volume, kode GP, harga jasa/material, total, dan pembulatan.
- Tarif & klasifikasi jasa: 25 kode dari Lampiran 1–2, harga B/A/A+, klasifikasi,
  serta contoh pekerjaan.
- Periode sumber: April 2019–Maret 2020. Nilai kosong, `By Approval`, dan angka
  pembulatan asli dipertahankan. Harga tidak diperbarui ke periode saat ini.

Untuk mengimpor ulang workbook dengan struktur yang sama:

```bash
python scripts/import_pricelist.py "/path/to/Pricelist FLT.xlsx"
```

Restart aplikasi setelah impor agar cache katalog diperbarui.

## Laporan DW

Halaman `/laporan-dw` menggunakan template, filter, pencarian, pagination, foto,
auto-refresh, mode presentasi, dan ekspor Excel yang sama dengan laporan Engineering.
Menu tersedia di sidebar dan navigasi ponsel. Pengguna tetap harus login ke aplikasi.

Konfigurasi sumber DW di `.env` terpisah dari konfigurasi Engineering:

```dotenv
DW_SUPABASE_URL=https://hgdaqniceqhmijjyyeij.supabase.co
DW_SUPABASE_KEY=isi_anon_key_proyek_dw
DW_SUPABASE_TABLE=daily_reports
```

Tabel DW menggunakan kolom `title` sebagai Area Kerja, `pic` sebagai PIC laporan,
serta `report_items` untuk pekerjaan, lokasi, status, dan `imagePaths` untuk foto.
Periode menggunakan `created_at` dalam zona waktu laporan, sama dengan Engineering.
API `/api/dw/reports` dan ekspor `/laporan-dw/export` hanya membaca proyek DW.
Ekspor bernama `laporan_dw_*.xlsx` dengan sheet `Laporan DW`.

Permintaan DW memakai anon key proyek DW di server; token login proyek Engineering
tidak dikirim ke proyek DW. Akses data mengikuti izin SELECT role anon pada proyek
DW. Key disimpan di `.env` yang diabaikan Git dan tidak disisipkan ke HTML/JavaScript.
Restart proses aplikasi setelah memperbarui konfigurasi.

### Halaman Tabel Supabase

Buka `/tabel-supabase` atau menu **Tabel Supabase** setelah login. Halaman ini membaca proyek tambahan dengan konfigurasi terpisah dari laporan Engineering dan DW:

```dotenv
TABLE_SUPABASE_URL=https://eibnrigeisychgfwowrx.supabase.co
TABLE_SUPABASE_KEY=your_anon_key
TABLE_SUPABASE_TABLES=logsheets
```

Isi `TABLE_SUPABASE_TABLES` dengan nama tabel yang dipisahkan koma untuk menyediakan pilihan dan membuka tabel pertama secara default. Nama tabel juga dapat dimasukkan langsung di halaman. Restart aplikasi setelah mengubah `.env`. Data dimuat 50 baris per halaman, dengan kolom mengikuti sumber dan tampilan detail untuk JSON. `logsheets` diurutkan berdasarkan tanggal terbaru dan kunci log; tabel lain mengikuti urutan respons API sumber. Perubahan data saat berpindah halaman dapat menggeser baris.

Kunci disimpan di server dan tidak disertakan dalam HTML. Akses memakai role anon proyek tambahan, sehingga tabel memerlukan izin SELECT dan kebijakan RLS yang sesuai. Daftar tabel tidak memerlukan akses metadata atau service-role key. Kesalahan akses/koneksi ditampilkan di halaman; tabel kosong dapat berarti tidak ada baris yang diizinkan RLS.

Untuk `logsheets`, pilih tanggal dan shift lalu klik **Tampilkan**. Rincian `payload` ditampilkan sebagai tabel **Kelompok / Item pemeriksaan / Nilai atau kondisi**. Nama petugas berada pada ringkasan catatan. Pencarian nama item, filter kelompok, dan opsi **Hanya item terisi** berlaku pada logsheet yang dipilih; nilai nol tetap dihitung terisi. Pilihan catatan mengikuti pagination 50 logsheet per halaman.
