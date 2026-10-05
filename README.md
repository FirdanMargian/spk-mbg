# SPK MBG — Sistem Pendukung Keputusan Menu Makan Bergizi Gratis

Sistem berbasis web menggunakan metode **AHP** (pembobotan kriteria) dan **SAW** (perangkingan menu).

## Cara Menjalankan

### 1. Pastikan Python 3.8+ terinstall
```bash
python --version
```

### 2. Install dependencies
```bash
pip install flask
```
atau:
```bash
pip install -r requirements.txt
```

### 3. Jalankan aplikasi
```bash
python app.py
```

### 4. Buka browser
```
http://localhost:5000
```

---

## Fitur Sistem

| Halaman | URL | Fungsi |
|---|---|---|
| Dashboard | `/` | Ringkasan, Top 3 menu, grafik |
| Data Menu | `/menu` | Tambah/hapus alternatif menu + nilai per kriteria |
| Pembobotan AHP | `/ahp` | Input matriks pairwise, hitung bobot + CR |
| Hasil SAW | `/hasil` | Tabel perangkingan lengkap dengan normalisasi |

---

## Struktur Proyek

```
spk-mbg/
├── app.py              ← Backend utama (Flask + logika AHP & SAW)
├── requirements.txt    ← Daftar package Python
├── templates/
│   ├── base.html       ← Layout utama (sidebar, navbar)
│   ├── index.html      ← Dashboard
│   ├── menu.html       ← Manajemen data menu
│   ├── ahp.html        ← Matriks AHP
│   └── hasil.html      ← Hasil SAW & ranking
└── data/               ← Folder penyimpanan JSON (otomatis dibuat)
    ├── kriteria.json   ← Daftar kriteria + tipe (benefit/cost)
    ├── menu.json       ← Alternatif menu + nilai
    └── bobot.json      ← Hasil bobot AHP + CR
```

---

## Alur Penggunaan

1. **Data Menu** → tambahkan alternatif menu beserta nilai tiap kriteria
2. **Pembobotan AHP** → isi matriks perbandingan berpasangan, klik Hitung
3. **Hasil SAW** → lihat perangkingan otomatis
4. **Dashboard** → ringkasan dan visualisasi

---

## Catatan Teknis

- Data disimpan dalam file JSON di folder `data/` (tidak butuh server database)
- Untuk produksi, ganti penyimpanan JSON dengan database seperti SQLite/MySQL
- Tambahkan login/autentikasi jika diperlukan
- CR < 0.1 diperlukan agar bobot AHP dinyatakan konsisten

---

## Tim Peneliti
Universitas Bina Insani — Penelitian PDP 2026
