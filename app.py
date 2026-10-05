from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import json, os, math
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'spk-mbg-secret-2026'

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

def load_json(f, d):
    p = os.path.join(DATA_DIR, f)
    return json.load(open(p)) if os.path.exists(p) else d

def save_json(f, d):
    json.dump(d, open(os.path.join(DATA_DIR, f), 'w'), indent=2, ensure_ascii=False)

def init_data():
    if not os.path.exists(os.path.join(DATA_DIR, 'kriteria.json')):
        save_json('kriteria.json', [
            {"id":1,"nama":"Energi","tipe":"benefit","satuan":"kkal"},
            {"id":2,"nama":"Protein","tipe":"benefit","satuan":"gram"},
            {"id":3,"nama":"Karbohidrat","tipe":"benefit","satuan":"gram"},
            {"id":4,"nama":"Lemak","tipe":"benefit","satuan":"gram"},
            {"id":5,"nama":"Serat","tipe":"benefit","satuan":"gram"},
            {"id":6,"nama":"Pangan Lokal","tipe":"benefit","satuan":"skor 1-5"},
            {"id":7,"nama":"Efisiensi Biaya","tipe":"cost","satuan":"Rp"},
        ])
    if not os.path.exists(os.path.join(DATA_DIR, 'menu.json')):
        save_json('menu.json', [
            {"id":1,"nama":"Nasi + Ayam + Sayur","deskripsi":"","nilai":[650,28,80,20,7,4,15000]},
            {"id":2,"nama":"Nasi + Ikan + Sayur","deskripsi":"","nilai":[600,32,75,18,8,5,14000]},
            {"id":3,"nama":"Nasi + Telur + Sayur","deskripsi":"","nilai":[580,25,90,22,6,4,12000]},
            {"id":4,"nama":"Nasi + Ikan + Tahu + Sayur","deskripsi":"","nilai":[630,30,85,19,9,4,16000]},
            {"id":5,"nama":"Nasi + Ayam + Tempe + Sayur","deskripsi":"","nilai":[610,29,78,17,7.5,5,13500]},
        ])
    if not os.path.exists(os.path.join(DATA_DIR, 'bobot.json')):
        # Default: bobot dari Excel (sudah diverifikasi)
        save_json('bobot.json', {
            "bobot": [0.246373,0.386450,0.127534,0.107660,0.056741,0.045275,0.029968],
            "bobot_fuzzy": [
                [0.1475,0.2434,0.4085],[0.2503,0.3967,0.6070],[0.0738,0.1273,0.2128],
                [0.0630,0.1044,0.1819],[0.0334,0.0559,0.0948],[0.0259,0.0433,0.0777],
                [0.0189,0.0290,0.0494]
            ],
            "cr": 0.04836, "valid": True, "metode": "fuzzy_ahp_buckley"
        })

init_data()

# ═══════════════════════════════════════════════════════
# KONSTANTA
# ═══════════════════════════════════════════════════════
SKALA_LINGUISTIK = {"EI":(1,1,1),"WI":(1,3,5),"SI":(3,5,7),"FI":(5,7,9),"AI":(7,9,9)}
SKALA_LABEL = {"EI":"Sama Penting","WI":"Sedikit Lebih Penting",
               "SI":"Cukup Lebih Penting","FI":"Sangat Lebih Penting","AI":"Mutlak Lebih Penting"}

# TFN Buckley (Sheet 04 Excel): Saaty integer → (l, m, u)
TFN_BUCKLEY = {
    1:(1,1,1), 2:(1,2,3), 3:(2,3,4), 4:(3,4,5),
    5:(4,5,6), 6:(5,6,7), 7:(6,7,8), 8:(7,8,9), 9:(9,9,9)
}
RI = {1:0.0,2:0.0,3:0.58,4:0.90,5:1.12,6:1.24,7:1.32,8:1.41,9:1.45,10:1.49}

def parse_fraction(s):
    s = str(s).strip()
    if '/' in s:
        a, b = s.split('/')
        return float(a) / float(b)
    return float(s)

def val_to_tfn(v):
    """Nilai crisp Saaty (bisa pecahan) → TFN Buckley."""
    if v >= 1:
        key = min(TFN_BUCKLEY.keys(), key=lambda k: abs(k - v))
        return TFN_BUCKLEY[key]
    else:
        key = min(TFN_BUCKLEY.keys(), key=lambda k: abs(k - 1/v))
        l, m, u = TFN_BUCKLEY[key]
        return (round(1/u, 8), round(1/m, 8), round(1/l, 8))

def kode_to_tfn(kode):
    return SKALA_LINGUISTIK.get(kode, (1,1,1))

# ═══════════════════════════════════════════════════════
# FUZZY AHP — METODE BUCKLEY (GEOMETRIC MEAN)
# Referensi: Buckley (1985), sesuai Excel Sheet 05-06
# ═══════════════════════════════════════════════════════
def hitung_fuzzy_ahp_buckley(tfn_upper, n):
    """
    tfn_upper[i][j] = TFN (l,m,u) untuk i < j.
    Menggunakan geometric mean per baris (metode Buckley).
    """
    # Bangun matriks TFN lengkap
    tfn = [[(1.0,1.0,1.0)]*n for _ in range(n)]
    crisp = [[1.0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i == j:
                tfn[i][j] = (1.0,1.0,1.0); crisp[i][j] = 1.0
            elif i < j:
                t = tfn_upper[i][j]
                tfn[i][j] = t; crisp[i][j] = t[1]
            else:
                t = tfn_upper[j][i]
                inv = (round(1/t[2],8), round(1/t[1],8), round(1/t[0],8))
                tfn[i][j] = inv; crisp[i][j] = inv[1]

    # Geometric mean tiap baris → fuzzy weight baris
    gm = []
    for i in range(n):
        ls = [tfn[i][j][0] for j in range(n)]
        ms = [tfn[i][j][1] for j in range(n)]
        us = [tfn[i][j][2] for j in range(n)]
        gl = math.prod(ls)**(1/n)
        gm_val = math.prod(ms)**(1/n)
        gu = math.prod(us)**(1/n)
        gm.append((gl, gm_val, gu))

    # Jumlah total & invers
    total_l = sum(g[0] for g in gm)
    total_m = sum(g[1] for g in gm)
    total_u = sum(g[2] for g in gm)

    # Fuzzy weight: wi = gm_i ⊗ (Σgm)^-1
    fw = [(round(g[0]/total_u,8), round(g[1]/total_m,8), round(g[2]/total_l,8)) for g in gm]

    # Defuzzifikasi CoA: (l+m+u)/3, lalu normalisasi
    defuzz = [(f[0]+f[1]+f[2])/3 for f in fw]
    total_d = sum(defuzz)
    bobot_crisp = [round(d/total_d, 8) for d in defuzz]
    bobot_fuzzy = [[round(f[0],6), round(f[1],6), round(f[2],6)] for f in fw]

    # CR dari nilai crisp (m) — AHP klasik
    cs = [sum(crisp[i][j] for i in range(n)) for j in range(n)]
    nc = [[crisp[i][j]/cs[j] for j in range(n)] for i in range(n)]
    wc = [sum(nc[i])/n for i in range(n)]
    lam = sum(sum(crisp[i][j]*wc[j] for j in range(n))/wc[i] for i in range(n))/n
    ci = (lam - n)/(n - 1)
    cr = round(ci / RI.get(n, 1.49), 6)

    # TFN matrix serializable
    tfn_s = [[list(tfn[i][j]) for j in range(n)] for i in range(n)]
    gm_s  = [[round(g[0],6),round(g[1],6),round(g[2],6)] for g in gm]

    return bobot_crisp, bobot_fuzzy, cr, tfn_s, gm_s

# ═══════════════════════════════════════════════════════
# SAW
# ═══════════════════════════════════════════════════════
def hitung_saw(menu_list, kriteria_list, bobot):
    nm = len(menu_list); nk = len(kriteria_list)
    nilai = [m['nilai'] for m in menu_list]
    norm = []
    for i in range(nm):
        row = []
        for j in range(nk):
            col = [nilai[k][j] for k in range(nm)]
            row.append(nilai[i][j]/max(col) if kriteria_list[j]['tipe']=='benefit'
                       else min(col)/nilai[i][j])
        norm.append(row)
    hasil = []
    for i, m in enumerate(menu_list):
        v = sum(bobot[j]*norm[i][j] for j in range(nk))
        hasil.append({"id":m['id'],"nama":m['nama'],"deskripsi":m['deskripsi'],
                      "nilai_asli":m['nilai'],
                      "nilai_norm":[round(x,6) for x in norm[i]],
                      "skor":round(v,6),"rank":0})
    hasil.sort(key=lambda x: x['skor'], reverse=True)
    for i, h in enumerate(hasil): h['rank'] = i+1
    return hasil

# ═══════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════
@app.route('/')
def index():
    menu=load_json('menu.json',[]); kriteria=load_json('kriteria.json',[]); bobot=load_json('bobot.json',{})
    hasil = hitung_saw(menu, kriteria, bobot['bobot']) if menu else []
    return render_template('index.html', menu=menu, kriteria=kriteria, bobot=bobot,
        top3=hasil[:3], total_menu=len(menu), now=datetime.now().strftime('%d %B %Y'))

@app.route('/menu')
def halaman_menu():
    return render_template('menu.html',
        menu=load_json('menu.json',[]), kriteria=load_json('kriteria.json',[]))

@app.route('/menu/tambah', methods=['POST'])
def tambah_menu():
    menu=load_json('menu.json',[]); kriteria=load_json('kriteria.json',[])
    new_id = max((m['id'] for m in menu), default=0)+1
    nilai = [float(request.form.get(f'nilai_{k["id"]}', 0)) for k in kriteria]
    menu.append({"id":new_id,"nama":request.form['nama'],
                 "deskripsi":request.form.get('deskripsi',''),"nilai":nilai})
    save_json('menu.json', menu)
    flash('Menu berhasil ditambahkan!','success')
    return redirect(url_for('halaman_menu'))

@app.route('/menu/hapus/<int:mid>', methods=['POST'])
def hapus_menu(mid):
    menu = [m for m in load_json('menu.json',[]) if m['id'] != mid]
    save_json('menu.json', menu)
    flash('Menu dihapus.','info')
    return redirect(url_for('halaman_menu'))

# ── AHP ──────────────────────────────────────────────
@app.route('/ahp')
def halaman_ahp():
    kriteria = load_json('kriteria.json',[]); bobot = load_json('bobot.json',{})
    n = len(kriteria)
    skala_matrix  = bobot.get('skala_matrix')  or [['EI']*n for _ in range(n)]
    crisp_matrix  = bobot.get('crisp_matrix')  or [['1']*n  for _ in range(n)]
    mode = bobot.get('mode','crisp')

    cells = []
    for i in range(n):
        row = []
        for j in range(n):
            if i == j:
                row.append({'type':'diag','i':i,'j':j})
            elif i < j:
                kode = skala_matrix[i][j]
                if isinstance(kode, str) and kode.startswith('INV_'): kode='EI'
                crisp_val = crisp_matrix[i][j] if isinstance(crisp_matrix[i][j], str) \
                            else str(crisp_matrix[i][j])
                row.append({'type':'upper','i':i,'j':j,'kode':kode,'crisp':crisp_val})
            else:
                kode = skala_matrix[j][i]
                if isinstance(kode, str) and kode.startswith('INV_'): kode='EI'
                cv = crisp_matrix[j][i]
                crisp_src = cv if isinstance(cv, str) else str(cv)
                # Tampilan invers
                if '/' in crisp_src:
                    parts = crisp_src.split('/')
                    inv_display = f"{parts[1]}/{parts[0]}" if len(parts)==2 else crisp_src
                elif crisp_src == '1':
                    inv_display = '1'
                else:
                    inv_display = f"1/{crisp_src}"
                row.append({'type':'lower','i':i,'j':j,'kode':kode,'crisp_inv':inv_display})
        cells.append(row)

    tfn_display = {'EI':'(1,1,1)','WI':'(1,3,5)','SI':'(3,5,7)','FI':'(5,7,9)','AI':'(7,9,9)'}
    inv_label   = {'EI':'EI','WI':'1/WI','SI':'1/SI','FI':'1/FI','AI':'1/AI'}
    inv_tfn     = {'EI':'(1,1,1)','WI':'(⅕,⅓,1)','SI':'(⅐,⅕,⅓)','FI':'(⅑,⅐,⅕)','AI':'(⅑,⅑,⅐)'}

    return render_template('ahp.html', kriteria=kriteria, bobot=bobot, n=n,
        cells=cells, mode=mode,
        skala_label=SKALA_LABEL, skala_keys=list(SKALA_LINGUISTIK.keys()),
        tfn_display=tfn_display, inv_label=inv_label, inv_tfn=inv_tfn)

@app.route('/ahp/hitung', methods=['POST'])
def hitung_ahp_route():
    kriteria = load_json('kriteria.json',[]); n = len(kriteria)
    mode = request.form.get('mode','crisp')

    skala_matrix = [['EI']*n for _ in range(n)]
    crisp_matrix = [['1']*n  for _ in range(n)]
    tfn_upper    = [[(1.0,1.0,1.0)]*n for _ in range(n)]

    for i in range(n):
        for j in range(i+1, n):
            if mode == 'linguistic':
                kode = request.form.get(f's_{i}_{j}','EI')
                skala_matrix[i][j] = kode; skala_matrix[j][i] = kode
                t = kode_to_tfn(kode)
                tfn_upper[i][j] = t
                crisp_matrix[i][j] = str(t[1])
                crisp_matrix[j][i] = f'1/{t[1]}' if t[1]!=1 else '1'
            else:  # crisp
                raw = request.form.get(f'c_{i}_{j}','1').strip()
                val = parse_fraction(raw)
                crisp_matrix[i][j] = raw
                # Tampilan invers
                if '/' in raw:
                    p = raw.split('/')
                    crisp_matrix[j][i] = f"{p[1]}/{p[0]}"
                elif raw == '1':
                    crisp_matrix[j][i] = '1'
                else:
                    crisp_matrix[j][i] = f'1/{raw}'
                tfn_upper[i][j] = val_to_tfn(val)
                # Perkiraan kode linguistik terdekat
                best = min(SKALA_LINGUISTIK.keys(),
                           key=lambda k: abs(SKALA_LINGUISTIK[k][1]-val))
                skala_matrix[i][j] = best; skala_matrix[j][i] = best

    bc, bf, cr, tfn_s, gm_s = hitung_fuzzy_ahp_buckley(tfn_upper, n)
    valid = cr < 0.1
    save_json('bobot.json', {
        "bobot": bc, "bobot_fuzzy": bf, "cr": cr, "valid": valid,
        "metode": "fuzzy_ahp_buckley", "mode": mode,
        "skala_matrix": skala_matrix, "crisp_matrix": crisp_matrix,
        "tfn_matrix": tfn_s, "gm_matrix": gm_s
    })
    flash(f'Fuzzy AHP (Buckley) berhasil! CR={cr} '
          f'{"✓ Konsisten" if valid else "✗ Tidak konsisten, harap revisi"}',
          'success' if valid else 'warning')
    return redirect(url_for('halaman_ahp'))

# ── Hasil ─────────────────────────────────────────────
@app.route('/hasil')
def halaman_hasil():
    menu=load_json('menu.json',[]); kriteria=load_json('kriteria.json',[]); bobot=load_json('bobot.json',{})
    if not menu or not bobot.get('bobot'):
        flash('Data belum tersedia.','warning'); return redirect(url_for('index'))
    return render_template('hasil.html',
        hasil=hitung_saw(menu,kriteria,bobot['bobot']), kriteria=kriteria, bobot=bobot)

@app.route('/api/hasil')
def api_hasil():
    menu=load_json('menu.json',[]); kriteria=load_json('kriteria.json',[]); bobot=load_json('bobot.json',{})
    return jsonify(hitung_saw(menu, kriteria, bobot['bobot']))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
