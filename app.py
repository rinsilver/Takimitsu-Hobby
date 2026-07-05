import os
import sqlite3
import json
import webbrowser
import csv
import io
from threading import Timer
from hashids import Hashids
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Response

app = Flask(__name__)
app.secret_key = 'wolves_master_system_ultimate_v7'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- BẢO MẬT COOKIE & SESSION ---
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 1 ngày tự động đăng xuất

csrf = CSRFProtect(app)
hashids = Hashids(salt="takimitsu_hobby_sieu_bao_mat", min_length=8)

# --- KHIÊN CHỐNG BRUTE-FORCE (Spam đăng nhập) ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

SETTINGS_FILE = 'settings.json'

def get_settings():
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            "ten_web": "TAKIMITSU HOBBY", "logo_url": "", "mau_chu_dao": "#e60012",
            "banner_1": "", "banner_2": "", 
            "thong_tin_footer": "Shop online chuyên sản phẩm mô hình chính hãng",
            "dia_chi": "TP. Hồ Chí Minh", "dien_thoai": "091.416.5278", "email": "0914165278",
            "ma_so_thue": "",
            "link_fb": "#", "link_ig": "#", "link_yt": "#",
            "cs_cua_hang": "", "cs_doi_tra": "", "cs_van_chuyen": "", "hd_mua_hang": "",
            "video_trang_chu": "HGCsAcFzaFw",
            "topic_1_img": "", "topic_1_title": "Đợt hàng S.H.F tháng 6 đã cập bến!", "topic_1_date": "20/06/2026", "topic_1_link": "/san-pham",
            "topic_2_img": "", "topic_2_title": "Hàng Hot Pre-order đang trả khách", "topic_2_date": "15/06/2026", "topic_2_link": "/san-pham",
            "topic_3_img": "", "topic_3_title": "Nendoroid & Figma về ngập kho", "topic_3_date": "10/06/2026", "topic_3_link": "/san-pham"
        }
        save_settings(default_settings)
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: 
        return json.load(f)

def save_settings(settings_data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings_data, f, ensure_ascii=False, indent=4)

# HÀM LẤY MENU ĐỘNG TỪ DATABASE
def get_mega_menu():
    conn = ket_noi_db()
    try:
        items = conn.execute('SELECT * FROM menu_item ORDER BY cot ASC, id ASC').fetchall()
    except:
        # Nếu thiếu bảng, tự động tạo và bơm dữ liệu mẫu
        conn.execute('CREATE TABLE IF NOT EXISTS menu_item (id INTEGER PRIMARY KEY AUTOINCREMENT, cot INTEGER, nhom TEXT, icon_nhom TEXT, ten_link TEXT, url TEXT, badge_html TEXT)')
        defaults = [
            (1, 'BANDAI SPIRITS', 'fas fa-robot', 'S.H.Figuarts', '/san-pham?hang_sx=Bandai', ''),
            (1, 'BANDAI SPIRITS', 'fas fa-robot', 'Mô hình khớp cử động', '/san-pham?danh_muc=Action Figure', ''),
            (2, 'THƯƠNG HIỆU KHÁC', 'fas fa-chess-knight', 'Good Smile Company', '/san-pham?hang_sx=Good Smile', ''),
            (2, 'THƯƠNG HIỆU KHÁC', 'fas fa-chess-knight', 'Nendoroid & Figma', '/san-pham?hang_sx=Figma', ''),
            (3, 'HOT TREND', 'fas fa-fire', 'Hàng có sẵn', '/san-pham?kieu_hang=Co san', '<span class="badge bg-success rounded-circle p-1 me-1" style="font-size:0.4rem;"> </span>'),
            (3, 'HOT TREND', 'fas fa-fire', 'Hàng Pre-order', '/san-pham?kieu_hang=Pre-order', '<span class="badge bg-warning text-dark p-1 me-1" style="font-size:0.5rem;"><i class="fas fa-hourglass-half"></i></span>')
        ]
        conn.executemany('INSERT INTO menu_item (cot, nhom, icon_nhom, ten_link, url, badge_html) VALUES (?,?,?,?,?,?)', defaults)
        conn.commit()
        items = conn.execute('SELECT * FROM menu_item ORDER BY cot ASC, id ASC').fetchall()
    conn.close()
    
    cots = {}
    for row in items:
        cot = row['cot']
        if cot not in cots:
            cots[cot] = {'nhom': row['nhom'], 'icon': row['icon_nhom'], 'links': []}
        cots[cot]['links'].append(row)
    return cots

@app.context_processor
def inject_data():
    gio_hang = session.get('gio_hang', [])
    so_luong = 0
    if isinstance(gio_hang, list):
        for item in gio_hang:
            if isinstance(item, dict) and 'so_luong' in item:
                so_luong += item['so_luong']
    return dict(
        so_luong_gio_hang=so_luong, 
        is_admin='admin_id' in session, 
        is_khach='khach_id' in session, 
        khach_ten=session.get('khach_ten', ''),
        settings=get_settings(),
        mega_menu=get_mega_menu(), # <-- BƠM MENU VÀO GIAO DIỆN
        encode_id=lambda id: hashids.encode(id)
    )

def ket_noi_db():
    conn = sqlite3.connect('database_v5.db')
    conn.row_factory = sqlite3.Row
    return conn

def tao_bang():
    conn = ket_noi_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS san_pham (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ten TEXT, the_loai TEXT, hang_sx TEXT, 
        gia_nhap REAL, gia_ban REAL, so_luong INTEGER, hinh_anh TEXT, mo_ta TEXT, 
        kieu_hang TEXT DEFAULT 'Co san', tien_coc REAL DEFAULT 0, ngay_phat_hanh TEXT,
        nguon_nhap_id INTEGER, tien_da_tra_nguon REAL DEFAULT 0, 
        trang_thai_nhap TEXT DEFAULT 'Còn nợ', ngay_du_kien_ve TEXT)''')
    
    conn.execute('CREATE TABLE IF NOT EXISTS danh_muc (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_danh_muc TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS nguon_nhap (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_nguon TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS hang_sx_list (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_hang TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS hinh_anh_sp (id INTEGER PRIMARY KEY AUTOINCREMENT, san_pham_id INTEGER, du_ong_dan TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS khach_hang (id INTEGER PRIMARY KEY AUTOINCREMENT, tai_khoan TEXT UNIQUE, mat_khau TEXT, ho_ten TEXT, sdt TEXT, dia_chi TEXT, vai_tro TEXT DEFAULT "khach")')
    conn.execute('''CREATE TABLE IF NOT EXISTS don_hang (
        id INTEGER PRIMARY KEY AUTOINCREMENT, khach_hang_id INTEGER, ten_khach TEXT, 
        sdt TEXT, dia_chi TEXT, tong_tien REAL, tien_da_tra REAL DEFAULT 0, 
        ngay_dat DATETIME DEFAULT CURRENT_TIMESTAMP, trang_thai TEXT DEFAULT "Chờ xử lý")''')
    conn.execute('CREATE TABLE IF NOT EXISTS chi_tiet_don (id INTEGER PRIMARY KEY AUTOINCREMENT, don_hang_id INTEGER, san_pham_id INTEGER, so_luong INTEGER, gia REAL)')
    conn.execute('CREATE TABLE IF NOT EXISTS anh_san_pham (id INTEGER PRIMARY KEY AUTOINCREMENT, san_pham_id INTEGER, du_ong_dan TEXT)')
    
    # --- BẢNG MỚI: QUẢN LÝ MEGA MENU ---
    conn.execute('CREATE TABLE IF NOT EXISTS menu_item (id INTEGER PRIMARY KEY AUTOINCREMENT, cot INTEGER, nhom TEXT, icon_nhom TEXT, ten_link TEXT, url TEXT, badge_html TEXT)')
    if conn.execute("SELECT COUNT(*) FROM menu_item").fetchone()[0] == 0:
        defaults = [
            (1, 'BANDAI SPIRITS', 'fas fa-robot', 'S.H.Figuarts', '/san-pham?hang_sx=Bandai', ''),
            (1, 'BANDAI SPIRITS', 'fas fa-robot', 'Mô hình khớp cử động', '/san-pham?danh_muc=Action Figure', ''),
            (2, 'THƯƠNG HIỆU KHÁC', 'fas fa-chess-knight', 'Good Smile Company', '/san-pham?hang_sx=Good Smile', ''),
            (2, 'THƯƠNG HIỆU KHÁC', 'fas fa-chess-knight', 'Nendoroid & Figma', '/san-pham?hang_sx=Figma', ''),
            (3, 'HOT TREND', 'fas fa-fire', 'Hàng có sẵn', '/san-pham?kieu_hang=Co san', '<span class="badge bg-success rounded-circle p-1 me-1" style="font-size:0.4rem;"> </span>'),
            (3, 'HOT TREND', 'fas fa-fire', 'Hàng Pre-order', '/san-pham?kieu_hang=Pre-order', '<span class="badge bg-warning text-dark p-1 me-1" style="font-size:0.5rem;"><i class="fas fa-hourglass-half"></i></span>')
        ]
        conn.executemany('INSERT INTO menu_item (cot, nhom, icon_nhom, ten_link, url, badge_html) VALUES (?,?,?,?,?,?)', defaults)

    try:
        conn.execute("ALTER TABLE san_pham ADD COLUMN so_luong_nhap INTEGER DEFAULT 0")
        conn.execute("UPDATE san_pham SET so_luong_nhap = so_luong WHERE so_luong_nhap = 0")
    except:
        pass
    try:
        conn.execute("ALTER TABLE san_pham ADD COLUMN gia_goc REAL DEFAULT 0")
    except: pass
    
    if conn.execute("SELECT COUNT(*) FROM khach_hang WHERE vai_tro = 'admin'").fetchone()[0] == 0:
        hashed_pw = generate_password_hash('123')
        conn.execute("INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, vai_tro) VALUES ('admin', ?, 'Quản trị viên', 'admin')", (hashed_pw,))
        
    conn.execute('CREATE TABLE IF NOT EXISTS lich_su_tra_nguon (id INTEGER PRIMARY KEY AUTOINCREMENT, san_pham_id INTEGER, so_tien REAL, ngay_tra DATETIME DEFAULT CURRENT_TIMESTAMP)')
    conn.commit()
    conn.close()

def cap_nhat_db_phan_loai():
    conn = ket_noi_db()
    for col in ['gia_san_new', 'gia_san_likenew', 'gia_order_new', 'gia_order_likenew']:
        try: 
            conn.execute(f"ALTER TABLE san_pham ADD COLUMN {col} REAL DEFAULT 0")
        except: 
            pass
    try: 
        conn.execute("UPDATE san_pham SET gia_san_new = gia_ban WHERE gia_san_new = 0 AND gia_san_likenew = 0 AND gia_order_new = 0 AND gia_order_likenew = 0 AND gia_ban > 0")
    except: 
        pass
    conn.commit()
    conn.close()

def cap_nhat_db_crm():
    conn = ket_noi_db()
    try: conn.execute("ALTER TABLE khach_hang ADD COLUMN nhom_khach TEXT DEFAULT 'Thường'")
    except: pass
    try: conn.execute("ALTER TABLE khach_hang ADD COLUMN ghi_chu TEXT DEFAULT ''")
    except: pass
    conn.commit()
    conn.close()

tao_bang()
cap_nhat_db_phan_loai()
cap_nhat_db_crm()

@app.route('/')
def index():
    conn = ket_noi_db()
    san_phams = conn.execute('SELECT * FROM san_pham ORDER BY id DESC LIMIT 8').fetchall()
    hang_sxs_raw = conn.execute('SELECT DISTINCT hang_sx FROM san_pham WHERE hang_sx IS NOT NULL AND hang_sx != "" LIMIT 8').fetchall()
    danh_sach_hang = [h['hang_sx'] for h in hang_sxs_raw]
    hang_co_san = conn.execute("SELECT * FROM san_pham WHERE kieu_hang = 'Co san' ORDER BY id DESC LIMIT 12").fetchall()
    hang_order = conn.execute("SELECT * FROM san_pham WHERE kieu_hang = 'Pre-order' ORDER BY id DESC LIMIT 12").fetchall()
    conn.close()
    return render_template('index.html', san_phams=san_phams, hang_sxs=danh_sach_hang, hang_co_san=hang_co_san, hang_order=hang_order)

@app.route('/thong-tin/<slug>')
def trang_thong_tin(slug):
    settings = get_settings()
    danh_sach_trang = {
        'chinh-sach-cua-hang': {'title': 'Chính sách cửa hàng', 'json_key': 'cs_cua_hang'},
        'chinh-sach-doi-tra': {'title': 'Chính sách đổi trả', 'json_key': 'cs_doi_tra'},
        'chinh-sach-van-chuyen': {'title': 'Chính sách vận chuyển', 'json_key': 'cs_van_chuyen'},
        'huong-dan-mua-hang': {'title': 'Hướng dẫn mua hàng', 'json_key': 'hd_mua_hang'}
    }
    if slug not in danh_sach_trang:
        return "Không tìm thấy trang", 404
    thong_tin_trang = danh_sach_trang[slug]
    noi_dung = settings.get(thong_tin_trang['json_key'], '')
    if not noi_dung:
        noi_dung = "Nội dung đang được cập nhật."
    return render_template('trang_thong_tin.html', tieu_de=thong_tin_trang['title'], noi_dung=noi_dung, settings=settings)

@app.route('/san-pham/<string:hash_id>')
def chi_tiet_sp(hash_id):
    decoded = hashids.decode(hash_id)
    if not decoded:
        return "Đường dẫn không hợp lệ sếp ơi!", 404
    id = decoded[0]
    
    conn = ket_noi_db()
    sp = conn.execute('SELECT * FROM san_pham WHERE id = ?', (id,)).fetchone()
    if not sp: 
        conn.close()
        return "Không tìm thấy sản phẩm", 404
    
    anh_phu = conn.execute('SELECT * FROM hinh_anh_sp WHERE san_pham_id = ?', (id,)).fetchall()
    san_pham_lien_quan = conn.execute('SELECT * FROM san_pham WHERE hang_sx = ? AND id != ? LIMIT 4', (sp['hang_sx'], id)).fetchall()
    tieu_de_goi_y = "SẢN PHẨM CÙNG HÃNG"
    
    if not san_pham_lien_quan:
        san_pham_lien_quan = conn.execute('SELECT * FROM san_pham WHERE id != ? ORDER BY id DESC LIMIT 4', (id,)).fetchall()
        tieu_de_goi_y = "GỢI Ý SẢN PHẨM KHÁC"
        
    da_xem_ids = session.get('da_xem', [])
    san_pham_da_xem = []
    
    if da_xem_ids:
        ids_to_fetch = [idx for idx in da_xem_ids if idx != id]
        if ids_to_fetch:
            placeholders = ','.join(['?'] * len(ids_to_fetch))
            query_dx = f'SELECT * FROM san_pham WHERE id IN ({placeholders})'
            sp_da_xem_db = conn.execute(query_dx, ids_to_fetch).fetchall()
            san_pham_da_xem = sorted(sp_da_xem_db, key=lambda x: ids_to_fetch.index(x['id']))

    if id in da_xem_ids:
        da_xem_ids.remove(id)
    da_xem_ids.insert(0, id)
    if len(da_xem_ids) > 11:   
        da_xem_ids.pop()
        
    session['da_xem'] = da_xem_ids
    session.modified = True
    conn.close()
    
    return render_template('chi_tiet.html', sp=sp, anh_phu=anh_phu, san_pham_lien_quan=san_pham_lien_quan, tieu_de_goi_y=tieu_de_goi_y, san_pham_da_xem=san_pham_da_xem)

@app.route('/dang-nhap', methods=['GET', 'POST'])
@limiter.limit("30 per minute")
def dang_nhap():
    if request.method == 'POST':
        conn = ket_noi_db()
        tai_khoan_nhap_vao = request.form['tai_khoan']
        u = conn.execute('SELECT * FROM khach_hang WHERE sdt=? OR tai_khoan=?', (tai_khoan_nhap_vao, tai_khoan_nhap_vao)).fetchone()
        
        if u:
            mat_khau_db = u['mat_khau']
            mat_khau_nhap = request.form['mat_khau']
            if mat_khau_db.startswith('scrypt:') or mat_khau_db.startswith('pbkdf2:'):
                hop_le = check_password_hash(mat_khau_db, mat_khau_nhap)
            else:
                hop_le = (mat_khau_db == mat_khau_nhap)
            
            if hop_le:
                session.clear()
                if u['vai_tro'] == 'admin': session['admin_id'] = u['id']
                else: session['khach_id'] = u['id']
                session['khach_ten'] = u['ho_ten']
                conn.close()
                return redirect(url_for('index'))
                
        conn.close()
        flash('Sai tài khoản, số điện thoại hoặc mật khẩu rồi sếp ơi!', 'danger')
        return redirect(url_for('dang_nhap'))
    return render_template('dang_nhap_chung.html')

@app.route('/dang-ky', methods=['GET', 'POST'])
def dang_ky():
    if request.method == 'POST':
        conn = ket_noi_db()
        hashed_pw = generate_password_hash(request.form['mat_khau'])
        try:
            conn.execute('INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, sdt, dia_chi) VALUES (?,?,?,?,?)', 
                         (request.form['tai_khoan'], hashed_pw, request.form['ho_ten'], request.form['sdt'], request.form['dia_chi']))
            conn.commit()
            return redirect(url_for('dang_nhap'))
        except: 
            return "Lỗi: Tài khoản đã tồn tại!"
        finally: 
            conn.close()
    return render_template('dang_ky_khach.html')

@app.route('/dang-xuat')
def dang_xuat():
    session.clear()
    return redirect(url_for('index'))

@app.route('/them-vao-gio/<string:hash_id>')
def them_vao_gio(hash_id):
    decoded = hashids.decode(hash_id)
    if not decoded:
        return redirect(url_for('index'))
    id = decoded[0]

    conn = ket_noi_db()
    sp = conn.execute('SELECT * FROM san_pham WHERE id=?', (id,)).fetchone()
    conn.close()
    if not sp: return redirect(url_for('index'))

    hinh_thuc = request.args.get('hinh_thuc', 'san')
    loai = request.args.get('loai', 'new')
    
    key_gia = f"gia_{hinh_thuc}_{loai}"
    gia_chon = sp[key_gia] if key_gia in sp.keys() else sp['gia_ban']
        
    if gia_chon <= 0:
        return redirect(url_for('chi_tiet_sp', hash_id=hash_id))

    if hinh_thuc == 'san' and sp['so_luong'] <= 0:
        flash('Mặt hàng này hiện đã hết hàng sẵn trong kho!', 'danger')
        return redirect(url_for('chi_tiet_sp', hash_id=hash_id))

    ten_variant = f"{sp['ten']} ({'Có sẵn' if hinh_thuc=='san' else 'Order'} - {'New Seal' if loai=='new' else 'Like New'})"
    cart_item_id = f"{id}_{hinh_thuc}_{loai}"

    gio = session.get('gio_hang', [])
    if isinstance(gio, dict): gio = []

    for item in gio: item.pop('error', None)

    found = False
    for item in gio:
        if item.get('cart_id', str(item['id'])) == cart_item_id:
            if hinh_thuc == 'san':
                if item['so_luong'] < sp['so_luong']: item['so_luong'] += 1
                else: item['error'] = f"Kho chỉ còn tối đa {sp['so_luong']} hộp!"
            else:
                item['so_luong'] += 1 
            found = True; break
    
    if not found:
        gio.append({'cart_id': cart_item_id, 'id': id, 'ten': ten_variant, 'gia': gia_chon, 'hinh_anh': sp['hinh_anh'], 'so_luong': 1})

    session['gio_hang'] = gio
    session.modified = True
    return redirect(url_for('xem_gio_hang'))

@app.route('/gio-hang')
def xem_gio_hang():
    gio = session.get('gio_hang', [])
    if isinstance(gio, dict) or (isinstance(gio, list) and len(gio) > 0 and not isinstance(gio[0], dict)): 
        gio = []
        session['gio_hang'] = gio
        session.modified = True
    tong_tien = sum(item['gia'] * item['so_luong'] for item in gio)
    return render_template('gio_hang.html', gio_hang=gio, tong_tien=tong_tien)

@app.route('/cap-nhat-gio/<cart_id>/<hanh_dong>')
def cap_nhat_gio(cart_id, hanh_dong):
    gio = session.get('gio_hang', [])
    real_id = int(str(cart_id).split('_')[0]) if '_' in str(cart_id) else int(cart_id)
    conn = ket_noi_db()
    sp = conn.execute('SELECT so_luong FROM san_pham WHERE id=?', (real_id,)).fetchone()
    conn.close()
    
    for item in gio:
        if item.get('cart_id', str(item['id'])) == cart_id:
            item.pop('error', None)
            if hanh_dong == 'tang':
                if sp and item['so_luong'] < sp['so_luong']: item['so_luong'] += 1
                else: item['error'] = "Tối đa rồi sếp ơi!"
            elif hanh_dong == 'giam' and item['so_luong'] > 1: item['so_luong'] -= 1
            break
    session['gio_hang'] = gio
    session.modified = True
    return redirect(url_for('xem_gio_hang'))

@app.route('/xoa-khoi-gio/<cart_id>')
def xoa_khoi_gio(cart_id):
    gio = session.get('gio_hang', [])
    gio = [item for item in gio if item.get('cart_id', str(item['id'])) != cart_id]
    session['gio_hang'] = gio; session.modified = True
    return redirect(url_for('xem_gio_hang'))

@app.route('/admin')
def admin():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    tu_khoa = request.args.get('tu_khoa', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    query_count = "SELECT COUNT(*) FROM san_pham"
    query = "SELECT * FROM san_pham"
    params = []
    if tu_khoa:
        where_clause = " WHERE ten LIKE ? OR id LIKE ?"
        query_count += where_clause
        query += where_clause
        params = [f'%{tu_khoa}%', f'%{tu_khoa}%']
    
    tong_sp = conn.execute(query_count, params).fetchone()[0]
    tong_trang = (tong_sp + per_page - 1) // per_page
    query += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    sps = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('admin.html', san_phams=sps, tu_khoa=tu_khoa, page=page, tong_trang=tong_trang)

@app.route('/them', methods=['GET', 'POST'])
def them_san_pham():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    if request.method == 'POST':
        f = request.files['hinh_anh']
        img = ''
        if f and f.filename != '':
            filename = secure_filename(f.filename)
            base_name = os.path.splitext(filename)[0]
            webp_name = base_name + ".webp"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], webp_name)
            img_raw = Image.open(f)
            img_raw.convert("RGB").save(save_path, "WEBP", quality=80) 
            img = '/static/uploads/' + webp_name

        cur = conn.cursor()
        gia_san_new = float(request.form.get('gia_san_new', 0) or 0)
        gia_san_likenew = float(request.form.get('gia_san_likenew', 0) or 0)
        gia_order_new = float(request.form.get('gia_order_new', 0) or 0)
        gia_order_likenew = float(request.form.get('gia_order_likenew', 0) or 0)
        gia_ban = float(request.form.get('gia_ban', gia_san_new)) 
        gia_goc = float(request.form.get('gia_goc', 0) or 0)
        
        cur.execute('''INSERT INTO san_pham (ten, the_loai, hang_sx, gia_nhap, gia_goc, gia_ban, so_luong, so_luong_nhap, hinh_anh, mo_ta, kieu_hang, tien_coc, ngay_phat_hanh, nguon_nhap_id, tien_da_tra_nguon, trang_thai_nhap, ngay_du_kien_ve, gia_san_new, gia_san_likenew, gia_order_new, gia_order_likenew) 
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                    (request.form['ten'], request.form['the_loai'], request.form['hang_sx'], 
                     float(request.form.get('gia_nhap', 0) or 0), gia_goc, gia_ban, 
                     int(request.form.get('so_luong', 0) or 0), int(request.form.get('so_luong', 0) or 0), 
                     img, request.form['mo_ta'], request.form['kieu_hang'], 
                     float(request.form.get('tien_coc', 0) or 0), request.form.get('ngay_phat_hanh', ''), 
                     request.form.get('nguon_nhap_id'), float(request.form.get('tien_da_tra_nguon', 0) or 0), 
                     request.form.get('trang_thai_nhap', 'Còn nợ'), request.form.get('ngay_ve', ''),
                     gia_san_new, gia_san_likenew, gia_order_new, gia_order_likenew))
        sid = cur.lastrowid

        tien_da_tra_nguon = float(request.form.get('tien_da_tra_nguon', 0) or 0)
        if tien_da_tra_nguon > 0:
            conn.execute('INSERT INTO lich_su_tra_nguon (san_pham_id, so_tien) VALUES (?, ?)', (sid, tien_da_tra_nguon))
        
        for pf in request.files.getlist('hinh_anh_phu'):
            if pf and pf.filename != '':
                filename_phu = secure_filename(pf.filename)
                base_name_phu = os.path.splitext(filename_phu)[0]
                webp_name_phu = base_name_phu + "_" + str(sid) + ".webp"
                save_path_phu = os.path.join(app.config['UPLOAD_FOLDER'], webp_name_phu)
                img_phu_raw = Image.open(pf)
                img_phu_raw.convert("RGB").save(save_path_phu, "WEBP", quality=80)
                conn.execute('INSERT INTO hinh_anh_sp (san_pham_id, du_ong_dan) VALUES (?,?)', (sid, '/static/uploads/' + webp_name_phu))
        conn.commit(); conn.close(); return redirect(url_for('admin'))
    
    dms = conn.execute('SELECT * FROM danh_muc').fetchall()
    hgs = conn.execute('SELECT * FROM hang_sx_list').fetchall()
    ngs = conn.execute('SELECT * FROM nguon_nhap').fetchall()
    conn.close()
    return render_template('them.html', danh_mucs=dms, hangs=hgs, nguons=ngs)

@app.route('/sua/<int:id>', methods=['GET', 'POST'])
def sua_san_pham(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    if request.method == 'POST':
        gia_san_new = float(request.form.get('gia_san_new', 0) or 0)
        gia_san_likenew = float(request.form.get('gia_san_likenew', 0) or 0)
        gia_order_new = float(request.form.get('gia_order_new', 0) or 0)
        gia_order_likenew = float(request.form.get('gia_order_likenew', 0) or 0)
        gia_ban = float(request.form.get('gia_ban', gia_san_new)) 
        gia_goc = float(request.form.get('gia_goc', 0) or 0)
        
        # BẢO MẬT TUYỆT ĐỐI CHỐNG LỖI KEYERROR
        ten_sp = request.form.get('ten', 'Chưa có tên')
        the_loai = request.form.get('the_loai', '')
        hang_sx = request.form.get('hang_sx', '')
        mo_ta = request.form.get('mo_ta', '')
        kieu_hang = request.form.get('kieu_hang', 'Co san')
        so_luong = int(request.form.get('so_luong', 0) or 0)
        
        f = request.files.get('hinh_anh')
        img_sql = ""
        tham_so = [
            ten_sp, the_loai, hang_sx,
            float(request.form.get('gia_nhap', 0) or 0), gia_goc, gia_ban, so_luong,
            mo_ta, kieu_hang, float(request.form.get('tien_coc', 0) or 0),
            request.form.get('ngay_phat_hanh', ''), request.form.get('nguon_nhap_id'),
            float(request.form.get('tien_da_tra_nguon', 0) or 0), request.form.get('trang_thai_nhap', 'Còn nợ'),
            request.form.get('ngay_ve', ''), gia_san_new, gia_san_likenew, gia_order_new, gia_order_likenew
        ]
        
        if f and f.filename != '':
            sp = conn.execute('SELECT hinh_anh FROM san_pham WHERE id=?', (id,)).fetchone()
            if sp and sp['hinh_anh']:
                try: os.remove(os.path.join(app.root_path, sp['hinh_anh'].lstrip('/')))
                except: pass
            filename = secure_filename(f.filename)
            base_name = os.path.splitext(filename)[0]
            import time
            webp_name = f"{base_name}_{id}_{int(time.time())}_main.webp"
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], webp_name)
            img_raw = Image.open(f)
            img_raw.convert("RGB").save(save_path, "WEBP", quality=80)
            img_sql = ", hinh_anh = ?"
            tham_so.append('/static/uploads/' + webp_name)
        
        tham_so.append(id)

        conn.execute(f'''UPDATE san_pham SET 
            ten=?, the_loai=?, hang_sx=?, gia_nhap=?, gia_goc=?, gia_ban=?, so_luong=?, mo_ta=?, 
            kieu_hang=?, tien_coc=?, ngay_phat_hanh=?, nguon_nhap_id=?, tien_da_tra_nguon=?, 
            trang_thai_nhap=?, ngay_du_kien_ve=?, gia_san_new=?, gia_san_likenew=?, gia_order_new=?, gia_order_likenew=? {img_sql} 
            WHERE id=?''', tuple(tham_so))
        
        # --- BẮT ĐẦU: XỬ LÝ ẢNH PHỤ (THAY THẾ ẢNH CŨ NẾU CÓ UPLOAD MỚI) ---
        files_phu = request.files.getlist('hinh_anh_phu')
        # Kiểm tra xem Sếp có chọn file ảnh phụ nào không
        if files_phu and files_phu[0].filename != '':
            # 1. Lấy danh sách ảnh phụ cũ và xóa khỏi ổ cứng cho nhẹ máy
            old_anh_phu = conn.execute('SELECT du_ong_dan FROM hinh_anh_sp WHERE san_pham_id=?', (id,)).fetchall()
            for old in old_anh_phu:
                try: os.remove(os.path.join(app.root_path, old['du_ong_dan'].lstrip('/')))
                except: pass
            
            # 2. Xóa ảnh phụ cũ khỏi Database
            conn.execute('DELETE FROM hinh_anh_sp WHERE san_pham_id=?', (id,))
            
            # 3. Lưu bộ ảnh phụ mới Sếp vừa chọn vào
            for pf in files_phu:
                if pf and pf.filename != '':
                    filename_phu = secure_filename(pf.filename)
                    base_name_phu = os.path.splitext(filename_phu)[0]
                    import time
                    webp_name_phu = f"{base_name_phu}_{id}_{int(time.time())}.webp"
                    save_path_phu = os.path.join(app.config['UPLOAD_FOLDER'], webp_name_phu)
                    img_phu_raw = Image.open(pf)
                    img_phu_raw.convert("RGB").save(save_path_phu, "WEBP", quality=80)
                    conn.execute('INSERT INTO hinh_anh_sp (san_pham_id, du_ong_dan) VALUES (?,?)', (id, '/static/uploads/' + webp_name_phu))
        # --- KẾT THÚC: XỬ LÝ ẢNH PHỤ ---
        
        conn.commit(); conn.close()
        return redirect(url_for('admin')) 

    sp = conn.execute('SELECT * FROM san_pham WHERE id = ?', (id,)).fetchone()
    anh_phu = conn.execute('SELECT * FROM hinh_anh_sp WHERE san_pham_id = ?', (id,)).fetchall() # NẠP ẢNH PHỤ
    dms = conn.execute('SELECT * FROM danh_muc').fetchall()
    hgs = conn.execute('SELECT * FROM hang_sx_list').fetchall()
    ngs = conn.execute('SELECT * FROM nguon_nhap').fetchall()
    conn.close()
    return render_template('sua.html', sp=sp, anh_phu=anh_phu, danh_mucs=dms, hangs=hgs, nguons=ngs)

@app.route('/xoa/<int:id>', methods=['POST'])
def xoa_san_pham(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    don_hang_dang_chua = conn.execute('''SELECT d.id, d.trang_thai FROM chi_tiet_don c
        JOIN don_hang d ON c.don_hang_id = d.id WHERE c.san_pham_id = ? AND d.trang_thai NOT IN ('Hoàn thành', 'Đã hủy')''', (id,)).fetchone()
    if don_hang_dang_chua:
        conn.close()
        return f"<script>alert('SẾP KHOAN XÓA! Sản phẩm này đang nằm trong Đơn hàng #{don_hang_dang_chua['id']}. Vui lòng Hủy đơn hoặc Hoàn thành đơn trước khi xóa.'); window.location.href='/admin';</script>"

    sp = conn.execute('SELECT hinh_anh FROM san_pham WHERE id=?', (id,)).fetchone()
    if sp and sp['hinh_anh']:
        try: os.remove(os.path.join(app.root_path, sp['hinh_anh'].lstrip('/')))
        except: pass
    anh_phus = conn.execute('SELECT du_ong_dan FROM hinh_anh_sp WHERE san_pham_id=?', (id,)).fetchall()
    for anh in anh_phus:
        try: os.remove(os.path.join(app.root_path, anh['du_ong_dan'].lstrip('/')))
        except: pass

    conn.execute('DELETE FROM san_pham WHERE id=?', (id,))
    conn.execute('DELETE FROM hinh_anh_sp WHERE san_pham_id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/cong-no-nguon')
def cong_no_nguon():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    nguons = conn.execute('SELECT * FROM nguon_nhap').fetchall()
    tu_khoa = request.args.get('tu_khoa', '') # Thêm biến từ khóa
    nguon_id = request.args.get('nguon_id', '')
    kieu_hang = request.args.get('kieu_hang', '')
    trang_thai_loc = request.args.get('trang_thai_loc', '')
    sap_xep = request.args.get('sap_xep', 'uu_tien_no')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    
    query = "SELECT sp.*, n.ten_nguon FROM san_pham sp LEFT JOIN nguon_nhap n ON sp.nguon_nhap_id = n.id WHERE 1=1"
    params = []
    
    if tu_khoa:
        query += " AND sp.ten LIKE ?"; params.append(f'%{tu_khoa}%')
    if nguon_id:
        query += " AND sp.nguon_nhap_id = ?"; params.append(nguon_id)
    if kieu_hang:
        query += " AND sp.kieu_hang = ?"; params.append(kieu_hang)
    if trang_thai_loc:
        query += " AND sp.trang_thai_nhap = ?"; params.append(trang_thai_loc)
        
    total_items = conn.execute("SELECT COUNT(*) FROM (" + query + ")", params).fetchone()[0]
    total_pages = (total_items + per_page - 1) // per_page
    
    if sap_xep == 'moi_nhat':
        query += " ORDER BY sp.id DESC LIMIT ? OFFSET ?"
    elif sap_xep == 'cu_nhat':
        query += " ORDER BY sp.id ASC LIMIT ? OFFSET ?"
    else: 
        query += " ORDER BY CASE WHEN sp.trang_thai_nhap = 'Còn nợ' THEN 1 ELSE 2 END, sp.id DESC LIMIT ? OFFSET ?"
        
    params.extend([per_page, offset])
    items = conn.execute(query, params).fetchall()
    
    # Tính tổng nợ khớp với bộ lọc
    tong_no_query = "SELECT SUM(sp.gia_nhap * sp.so_luong_nhap - sp.tien_da_tra_nguon) FROM san_pham sp WHERE sp.trang_thai_nhap = 'Còn nợ'"
    tong_no_params = []
    if tu_khoa:
        tong_no_query += " AND sp.ten LIKE ?"; tong_no_params.append(f'%{tu_khoa}%')
    if nguon_id:
        tong_no_query += " AND sp.nguon_nhap_id = ?"; tong_no_params.append(nguon_id)
    if kieu_hang:
        tong_no_query += " AND sp.kieu_hang = ?"; tong_no_params.append(kieu_hang)
        
    tong_no_result = conn.execute(tong_no_query, tong_no_params).fetchone()[0]
    tong_no = tong_no_result if tong_no_result else 0
    conn.close()
    return render_template('cong_no_nguon.html', items=items, nguons=nguons, tong_no=tong_no, page=page, tong_trang=total_pages, nguon_chon=nguon_id, kieu_chon=kieu_hang, trang_thai_loc=trang_thai_loc, sap_xep_chon=sap_xep, tu_khoa=tu_khoa)

@app.route('/admin/xuat-excel-nguon/<int:nguon_id>')
def xuat_excel_nguon(nguon_id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    logs = conn.execute('''
        SELECT l.so_tien, l.ngay_tra, s.ten as ten_sp 
        FROM lich_su_tra_nguon l 
        JOIN san_pham s ON l.san_pham_id = s.id 
        WHERE s.nguon_nhap_id = ? ORDER BY l.id DESC
    ''', (nguon_id,)).fetchall()
    ten_nguon = conn.execute("SELECT ten_nguon FROM nguon_nhap WHERE id = ?", (nguon_id,)).fetchone()
    conn.close()
    
    if not ten_nguon: return "Không tìm thấy nguồn", 404

    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(['Ngày Chuyển Khoản', 'Sản Phẩm', 'Số Tiền Đã Chuyển (VNĐ)'])
    
    for l in logs:
        writer.writerow([l['ngay_tra'], l['ten_sp'], l['so_tien']])
        
    safe_name = secure_filename(ten_nguon['ten_nguon'])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=LichSu_ChuyenTien_{safe_name}.csv"})

@app.route('/admin/cap-nhat-tra-tien/<int:id>', methods=['POST'])
def cap_nhat_tra_tien(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    sp = conn.execute('SELECT gia_nhap, so_luong_nhap, tien_da_tra_nguon FROM san_pham WHERE id=?', (id,)).fetchone()
    so_tien_nhap_vao = float(request.form.get('so_tien', 0))
    hanh_dong = request.form.get('hanh_dong')
    
    # Tính toán lại logic để đảm bảo không lọt bất kỳ 1 đồng nào
    if hanh_dong == 'cong':
        tien_moi = sp['tien_da_tra_nguon'] + so_tien_nhap_vao
        tien_ghi_log = so_tien_nhap_vao
    else: # hanh_dong == 'sua'
        tien_moi = so_tien_nhap_vao
        tien_ghi_log = tien_moi - sp['tien_da_tra_nguon'] # Trừ hao để lấy số tiền vừa đưa thêm
        
    # GHI LOG LỊCH SỬ CHUYỂN TIỀN VÀO DATABASE
    if tien_ghi_log > 0:
        conn.execute('INSERT INTO lich_su_tra_nguon (san_pham_id, so_tien) VALUES (?, ?)', (id, tien_ghi_log))
        
    tong_nhap = sp['gia_nhap'] * sp['so_luong_nhap']
    trang_thai = request.form.get('trang_thai', 'Còn nợ')
    if tien_moi >= tong_nhap:
        trang_thai = 'Đã thanh toán'
        
    conn.execute('UPDATE san_pham SET tien_da_tra_nguon=?, trang_thai_nhap=?, ngay_du_kien_ve=? WHERE id=?', (tien_moi, trang_thai, request.form.get('ngay_ve', ''), id))
    conn.commit(); conn.close()
    return redirect(url_for('cong_no_nguon'))

@app.route('/api/lich-su-tra-nguon/<int:sp_id>')
def api_lich_su_tra_nguon(sp_id):
    if 'admin_id' not in session: return jsonify([])
    conn = ket_noi_db()
    logs = conn.execute('SELECT so_tien, ngay_tra FROM lich_su_tra_nguon WHERE san_pham_id = ? ORDER BY id DESC', (sp_id,)).fetchall()
    conn.close()
    return jsonify([{'so_tien': "{:,.0f}".format(l['so_tien']), 'ngay_tra': l['ngay_tra']} for l in logs])

@app.route('/api/lich-su-nguon/<int:nguon_id>')
def api_lich_su_nguon(nguon_id):
    if 'admin_id' not in session: return jsonify([])
    conn = ket_noi_db()
    logs = conn.execute('''
        SELECT l.so_tien, l.ngay_tra, s.ten as ten_sp 
        FROM lich_su_tra_nguon l 
        JOIN san_pham s ON l.san_pham_id = s.id 
        WHERE s.nguon_nhap_id = ? ORDER BY l.id DESC
    ''', (nguon_id,)).fetchall()
    conn.close()
    return jsonify([{'so_tien': "{:,.0f}".format(l['so_tien']), 'ngay_tra': l['ngay_tra'], 'ten_sp': l['ten_sp']} for l in logs])

@app.route('/admin/nguon-nhap', methods=['GET', 'POST'])
def quan_ly_nguon_nhap():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    if request.method == 'POST':
        conn.execute('INSERT INTO nguon_nhap (ten_nguon) VALUES (?)', (request.form['ten_nguon'],)); conn.commit()
    ngs = conn.execute('SELECT * FROM nguon_nhap').fetchall(); conn.close()
    return render_template('quan_ly_nguon.html', nguons=ngs)

@app.route('/admin/hang-sx', methods=['GET', 'POST'])
def quan_ly_hang_sx():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    if request.method == 'POST':
        conn.execute('INSERT INTO hang_sx_list (ten_hang) VALUES (?)', (request.form['ten_hang'],)); conn.commit()
    hgs = conn.execute('SELECT * FROM hang_sx_list').fetchall(); conn.close()
    return render_template('quan_ly_hang.html', hangs=hgs)

@app.route('/danh-muc', methods=['GET', 'POST'])
def quan_ly_danh_muc():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    if request.method == 'POST':
        conn.execute('INSERT INTO danh_muc (ten_danh_muc) VALUES (?)', (request.form['ten_danh_muc'],)); conn.commit()
    dms = conn.execute('SELECT * FROM danh_muc').fetchall(); conn.close()
    return render_template('danh_muc.html', danh_mucs=dms)

@app.route('/admin/xuat-excel-don-hang')
def xuat_excel_don_hang():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    dhs = conn.execute("SELECT id, ten_khach, sdt, dia_chi, tong_tien, tien_da_tra, ngay_dat, trang_thai FROM don_hang ORDER BY id DESC").fetchall()
    conn.close()
    
    output = io.StringIO()
    output.write('\ufeff') # Khắc phục lỗi font tiếng Việt trong Excel
    writer = csv.writer(output)
    writer.writerow(['Mã Đơn', 'Tên Khách', 'Số Điện Thoại', 'Địa Chỉ', 'Tổng Bill (VNĐ)', 'Đã Thu (VNĐ)', 'Khách Còn Nợ (VNĐ)', 'Ngày Đặt', 'Trạng Thái'])
    
    for dh in dhs:
        con_no = dh['tong_tien'] - dh['tien_da_tra']
        writer.writerow([dh['id'], dh['ten_khach'], dh['sdt'], dh['dia_chi'], dh['tong_tien'], dh['tien_da_tra'], con_no, dh['ngay_dat'], dh['trang_thai']])
    
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=Bao_Cao_Don_Hang.csv"})

@app.route('/admin/don-hang', methods=['GET', 'POST'])
def quan_ly_don_hang():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    if request.method == 'POST':
        don_id = request.form['don_id']
        trang_thai = request.form['trang_thai']
        tien_da_tra = request.form.get('tien_da_tra', 0)
        conn.execute('UPDATE don_hang SET trang_thai = ?, tien_da_tra = ? WHERE id = ?', (trang_thai, tien_da_tra, don_id))
        conn.commit(); return redirect(url_for('quan_ly_don_hang'))

    tu_khoa = request.args.get('tu_khoa', '')
    trang_thai_loc = request.args.get('trang_thai', '')
    sap_xep = request.args.get('sap_xep', 'moi_nhat')
    page = request.args.get('page', 1, type=int)
    per_page = 10 
    
    cau_lenh_base = ' FROM don_hang WHERE 1=1'
    dk = []
    if tu_khoa:
        cau_lenh_base += ''' AND (
            ten_khach LIKE ? 
            OR sdt LIKE ? 
            OR id LIKE ? 
            OR id IN (
                SELECT don_hang_id FROM chi_tiet_don c 
                JOIN san_pham s ON c.san_pham_id = s.id 
                WHERE s.ten LIKE ?
            )
        )'''
        dk.extend([f'%{tu_khoa}%', f'%{tu_khoa}%', f'%{tu_khoa}%', f'%{tu_khoa}%'])
    if trang_thai_loc:
        cau_lenh_base += ' AND trang_thai = ?'; dk.append(trang_thai_loc)

    total_rev = conn.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai = 'Hoàn thành'").fetchone()[0] or 0
    total_debt = conn.execute("SELECT SUM(tong_tien - tien_da_tra) FROM don_hang WHERE trang_thai != 'Đã hủy'").fetchone()[0] or 0
    pending_count = conn.execute("SELECT COUNT(id) FROM don_hang WHERE trang_thai = 'Chờ xử lý'").fetchone()[0] or 0

    tong_don = conn.execute('SELECT COUNT(id)' + cau_lenh_base, dk).fetchone()[0]
    tong_trang = (tong_don + per_page - 1) // per_page

    cau_lenh = 'SELECT *' + cau_lenh_base
    if sap_xep == 'moi_nhat': cau_lenh += ' ORDER BY id DESC'
    elif sap_xep == 'cu_nhat': cau_lenh += ' ORDER BY id ASC'
    elif sap_xep == 'tien_cao': cau_lenh += ' ORDER BY tong_tien DESC'
    
    cau_lenh += ' LIMIT ? OFFSET ?'
    dk.extend([per_page, (page - 1) * per_page])
    don_hangs = conn.execute(cau_lenh, dk).fetchall()
    
    don_hangs_full = []
    for dh in don_hangs:
        dh_dict = dict(dh)
        cac_mon = conn.execute('''SELECT c.*, s.ten, s.hinh_anh, s.kieu_hang, s.ngay_phat_hanh FROM chi_tiet_don c 
            JOIN san_pham s ON c.san_pham_id = s.id WHERE c.don_hang_id = ?''', (dh['id'],)).fetchall()
        dh_dict['ds_mat_hang'] = cac_mon 
        don_hangs_full.append(dh_dict)
    conn.close()

    return render_template('quan_ly_don.html', don_hangs=don_hangs_full, trang_thai_chon=trang_thai_loc, sap_xep_chon=sap_xep, tu_khoa=tu_khoa, page=page, tong_trang=tong_trang, total_rev=total_rev, total_debt=total_debt, pending_count=pending_count)

@app.route('/admin/khach-hang', methods=['GET', 'POST'])
def quan_ly_khach_hang():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    if request.method == 'POST':
        kh_id = request.form.get('kh_id')
        mat_khau_nhap = request.form['mat_khau']
        nhom_khach = request.form.get('nhom_khach', 'Thường')
        ghi_chu = request.form.get('ghi_chu', '')
        if not mat_khau_nhap.startswith('scrypt:'):
            mat_khau_nhap = generate_password_hash(mat_khau_nhap)
        if kh_id: 
            conn.execute('UPDATE khach_hang SET ho_ten=?, tai_khoan=?, sdt=?, dia_chi=?, mat_khau=?, nhom_khach=?, ghi_chu=? WHERE id=?', (request.form['ho_ten'], request.form['tai_khoan'], request.form['sdt'], request.form['dia_chi'], mat_khau_nhap, nhom_khach, ghi_chu, kh_id))
        else: 
            try: conn.execute('INSERT INTO khach_hang (ho_ten, tai_khoan, mat_khau, sdt, dia_chi, nhom_khach, ghi_chu) VALUES (?,?,?,?,?,?,?)', (request.form['ho_ten'], request.form['tai_khoan'], mat_khau_nhap, request.form['sdt'], request.form['dia_chi'], nhom_khach, ghi_chu))
            except: pass
        conn.commit(); return redirect(url_for('quan_ly_khach_hang'))

    tu_khoa = request.args.get('tu_khoa', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    query_count = "SELECT COUNT(*) FROM khach_hang k"
    query = '''SELECT k.*, COUNT(DISTINCT d.id) as so_don, 
               IFNULL(SUM(CASE WHEN d.trang_thai != 'Đã hủy' THEN d.tong_tien ELSE 0 END), 0) as tong_mua, 
               IFNULL(SUM(CASE WHEN d.trang_thai != 'Đã hủy' THEN d.tien_da_tra ELSE 0 END), 0) as da_tra
        FROM khach_hang k LEFT JOIN don_hang d ON k.id = d.khach_hang_id'''
    params = []
    if tu_khoa:
        where_clause = " WHERE k.ho_ten LIKE ? OR k.tai_khoan LIKE ? OR k.sdt LIKE ?"
        query_count += where_clause; query += where_clause
        params = [f'%{tu_khoa}%', f'%{tu_khoa}%', f'%{tu_khoa}%']
        
    tong_khach = conn.execute(query_count, params).fetchone()[0]
    tong_trang = (tong_khach + per_page - 1) // per_page
    query += " GROUP BY k.id ORDER BY k.id DESC LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    khachs = conn.execute(query, params).fetchall()
    
    # BỔ SUNG: TÍNH TOÁN SỐ LIỆU TỔNG HỢP TOÀN TIỆM (LOẠI TRỪ ĐƠN HỦY)
    thong_ke_tong = conn.execute('''
        SELECT 
            COUNT(DISTINCT k.id) as total_khach,
            IFNULL(SUM(CASE WHEN d.trang_thai != 'Đã hủy' THEN d.tong_tien ELSE 0 END), 0) as total_bill,
            IFNULL(SUM(CASE WHEN d.trang_thai != 'Đã hủy' THEN d.tien_da_tra ELSE 0 END), 0) as total_paid
        FROM khach_hang k
        LEFT JOIN don_hang d ON k.id = d.khach_hang_id
    ''').fetchone()
    
    conn.close()
    return render_template('quan_ly_khach.html', khachs=khachs, tu_khoa=tu_khoa, page=page, tong_trang=tong_trang, thong_ke_tong=thong_ke_tong)

@app.route('/admin/xoa-khach-hang/<int:id>')
def xoa_khach_hang(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    kh = conn.execute('SELECT vai_tro FROM khach_hang WHERE id = ?', (id,)).fetchone()
    if kh and kh['vai_tro'] == 'admin':
        conn.close()
        return "<script>alert('Sếp không thể xóa tài khoản Admin ở đây!'); window.location.href='/admin/khach-hang';</script>"
    conn.execute('DELETE FROM khach_hang WHERE id = ?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('quan_ly_khach_hang'))

@app.route('/admin/khach-hang/<int:id>')
def chi_tiet_khach(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    khach = conn.execute('SELECT * FROM khach_hang WHERE id = ?', (id,)).fetchone()
    
    thong_ke = conn.execute('''
        SELECT COUNT(id) as so_don, 
               IFNULL(SUM(CASE WHEN trang_thai != 'Đã hủy' THEN tong_tien ELSE 0 END), 0) as tong_mua, 
               IFNULL(SUM(CASE WHEN trang_thai != 'Đã hủy' THEN tien_da_tra ELSE 0 END), 0) as tong_tra 
        FROM don_hang WHERE khach_hang_id = ?
    ''', (id,)).fetchone()
    
    don_hangs = conn.execute('SELECT * FROM don_hang WHERE khach_hang_id = ? ORDER BY id DESC', (id,)).fetchall()
    conn.close()
    return render_template('chi_tiet_khach.html', khach=khach, thong_ke=thong_ke, don_hangs=don_hangs)

@app.route('/admin/cap-nhat-don/<int:id>', methods=['POST'])
def cap_nhat_don(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    dh = conn.execute('SELECT tong_tien, tien_da_tra FROM don_hang WHERE id=?', (id,)).fetchone()
    so_tien_nhap = float(request.form.get('so_tien', 0))
    hanh_dong = request.form.get('hanh_dong', 'cong')
    trang_thai = request.form.get('trang_thai')
    tien_moi = dh['tien_da_tra'] + so_tien_nhap if hanh_dong == 'cong' else so_tien_nhap
    
    if tien_moi >= dh['tong_tien']: trang_thai = 'Hoàn thành'
    conn.execute('UPDATE don_hang SET trang_thai=?, tien_da_tra=? WHERE id=?', (trang_thai, tien_moi, id))
    conn.commit(); conn.close()
    return redirect(url_for('quan_ly_don_hang'))

@app.route('/admin/huy-don/<int:id>')
def huy_don(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    dh = conn.execute('SELECT trang_thai FROM don_hang WHERE id = ?', (id,)).fetchone()
    if dh and dh['trang_thai'] != 'Đã hủy':
        items = conn.execute('SELECT san_pham_id, so_luong FROM chi_tiet_don WHERE don_hang_id = ?', (id,)).fetchall()
        for item in items:
            conn.execute('UPDATE san_pham SET so_luong = so_luong + ? WHERE id = ?', (item['so_luong'], item['san_pham_id']))
        conn.execute('UPDATE don_hang SET trang_thai = "Đã hủy" WHERE id = ?', (id,))
        conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('quan_ly_don_hang'))

@app.route('/admin/thong-ke')
def thong_ke():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    dt = conn.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai='Hoàn thành'").fetchone()[0] or 0
    sd = conn.execute("SELECT COUNT(*) FROM don_hang WHERE trang_thai='Chờ xử lý'").fetchone()[0] or 0
    
    # TỐI ƯU THẦN THÁNH: Tự động tạo mốc 7 ngày gần nhất để biểu đồ không bao giờ bị rỗng dữ liệu
    import datetime
    chart_labels = []
    chart_data = []
    for i in range(6, -1, -1):
        ngay_str = (datetime.date.today() - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
        chart_labels.append(ngay_str)
        
        # Lấy doanh thu thực tế của ngày này, nếu không có tự động trả về 0đ
        row = conn.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai='Hoàn thành' AND DATE(ngay_dat) = ?", (ngay_str,)).fetchone()
        chart_data.append(row[0] or 0)

    top_products = conn.execute('''SELECT s.ten, SUM(c.so_luong) as total_qty FROM chi_tiet_don c
        JOIN san_pham s ON c.san_pham_id = s.id JOIN don_hang d ON c.don_hang_id = d.id
        WHERE d.trang_thai = 'Hoàn thành' GROUP BY s.id ORDER BY total_qty DESC LIMIT 5''').fetchall()
    conn.close()
    return render_template('thong_ke.html', doanh_thu=dt, so_don_moi=sd, thue_vat=dt*0.03, labels=json.dumps(chart_labels), values=json.dumps(chart_data), top_sps=top_products)

@app.route('/xoa-danh-muc/<int:id>', methods=['POST'])
def xoa_danh_muc(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    conn.execute('DELETE FROM danh_muc WHERE id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('quan_ly_danh_muc'))

@app.route('/xoa-hang/<int:id>', methods=['POST'])
def xoa_hang(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    conn.execute('DELETE FROM hang_sx_list WHERE id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('quan_ly_hang_sx'))

@app.route('/xoa-nguon/<int:id>', methods=['POST'])
def xoa_nguon(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    conn.execute('DELETE FROM nguon_nhap WHERE id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('quan_ly_nguon_nhap'))

@app.route('/admin/don-hang/<int:id>', methods=['GET', 'POST'])
def xem_sua_don_hang(id):
    khach_id = session.get('khach_id')
    admin_id = session.get('admin_id')
    if not admin_id and not khach_id: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    dh = conn.execute('SELECT * FROM don_hang WHERE id = ?', (id,)).fetchone()
    if not dh: 
        conn.close(); return "Không tìm thấy đơn hàng!", 404
    if not admin_id and dh['khach_hang_id'] != khach_id:
        conn.close(); return "<script>alert('Sếp không có quyền xem đơn của người khác!'); window.history.back();</script>"

    if request.method == 'POST' and admin_id:
        tong_tien_moi = float(request.form.get('tong_tien', 0))
        tien_da_tra_moi = float(request.form.get('tien_da_tra', 0))
        trang_thai_moi = request.form['trang_thai']
        
        # Tự động kích hoạt trạng thái "Hoàn thành" nếu sếp đã thu đủ tiền
        if tien_da_tra_moi >= tong_tien_moi and trang_thai_moi in ['Chờ xử lý', 'Đang giao hàng']:
            trang_thai_moi = 'Hoàn thành'
            
        # Cập nhật cả trạng thái, tiền đã trả và TỔNG TIỀN MỚI vào đơn hàng
        conn.execute('UPDATE don_hang SET trang_thai = ?, tien_da_tra = ?, tong_tien = ? WHERE id = ?', 
                     (trang_thai_moi, tien_da_tra_moi, tong_tien_moi, id))
        conn.commit()
        conn.close()
        flash(f'Đã cập nhật tài chính đơn hàng #{id} thành công!', 'success')
        return redirect(url_for('quan_ly_don_hang'))

    items = conn.execute('''SELECT c.*, s.ten, s.hinh_anh, s.hang_sx FROM chi_tiet_don c 
        JOIN san_pham s ON c.san_pham_id = s.id WHERE c.don_hang_id = ?''', (id,)).fetchall()
    
    khach_info = conn.execute('SELECT nhom_khach, ghi_chu FROM khach_hang WHERE id = ?', (dh['khach_hang_id'],)).fetchone()
    conn.close()
    return render_template('chi_tiet_don.html', dh=dh, items=items, khach_info=khach_info)

@app.route('/admin/in-hoa-don/<int:id>')
def in_hoa_don(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    dh = conn.execute('SELECT * FROM don_hang WHERE id = ?', (id,)).fetchone()
    items = conn.execute('SELECT c.*, s.ten FROM chi_tiet_don c JOIN san_pham s ON c.san_pham_id = s.id WHERE c.don_hang_id = ?', (id,)).fetchall()
    conn.close()
    return render_template('in_hoa_don.html', dh=dh, items=items)

@app.route('/ho-so')
def ho_so_khach():
    khach_id = session.get('khach_id')
    if not khach_id:
        if session.get('admin_id'): return redirect(url_for('quan_ly_khach_hang')) 
        return redirect(url_for('dang_nhap'))
        
    page = request.args.get('page', 1, type=int)
    per_page = 8 
    conn = ket_noi_db()
    khach = conn.execute('SELECT * FROM khach_hang WHERE id = ?', (khach_id,)).fetchone()
    tong_don = conn.execute('SELECT COUNT(id) FROM don_hang WHERE khach_hang_id = ?', (khach_id,)).fetchone()[0]
    tong_trang = (tong_don + per_page - 1) // per_page
    don_hangs = conn.execute('SELECT * FROM don_hang WHERE khach_hang_id = ? ORDER BY id DESC LIMIT ? OFFSET ?', (khach_id, per_page, (page - 1) * per_page)).fetchall()
    
    don_hangs_full = []
    for dh in don_hangs:
        dh_dict = dict(dh)
        items = conn.execute('SELECT c.*, s.ten, s.hinh_anh FROM chi_tiet_don c JOIN san_pham s ON c.san_pham_id = s.id WHERE c.don_hang_id = ?', (dh['id'],)).fetchall()
        dh_dict['items'] = items
        don_hangs_full.append(dh_dict)
    conn.close()
    return render_template('ho_so.html', khach=khach, don_hangs=don_hangs_full, page=page, tong_trang=tong_trang)

@app.route('/admin/cai-dat', methods=['GET', 'POST'])
def cai_dat_giao_dien():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    settings = get_settings()
    conn = ket_noi_db()
    
    if request.method == 'POST':
        hanh_dong = request.form.get('hanh_dong')
        
        # 1. XỬ LÝ LƯU CẤU HÌNH CHUNG
        if hanh_dong == 'luu_cai_dat_chung':
            def xu_ly_anh(ten_input, file_cu):
                if request.form.get(f'is_delete_{ten_input}') == 'true': return "" 
                file = request.files.get(ten_input)
                if file and file.filename != '':
                    filepath = os.path.join('static/uploads', secure_filename(file.filename))
                    file.save(filepath); return '/' + filepath
                return file_cu

            settings['ten_web'] = request.form.get('ten_web', settings.get('ten_web'))
            settings['mau_chu_dao'] = request.form.get('mau_chu_dao', settings.get('mau_chu_dao'))
            settings['dia_chi'] = request.form.get('dia_chi', '')
            settings['dien_thoai'] = request.form.get('dien_thoai', '')
            settings['email'] = request.form.get('email', '')
            settings['ma_so_thue'] = request.form.get('ma_so_thue', '')
            settings['link_fb'] = request.form.get('link_fb', '#')
            settings['link_ig'] = request.form.get('link_ig', '#')
            settings['link_yt'] = request.form.get('link_yt', '#')
            settings['logo_url'] = xu_ly_anh('logo_file', settings.get('logo_url'))
            
            # --- VÒNG LẶP LƯU 5 BANNER ---
            for i in range(1, 6):
                settings[f'banner_{i}'] = xu_ly_anh(f'banner_{i}_file', settings.get(f'banner_{i}'))
            
            # --- VÒNG LẶP LƯU 3 VIDEO YOUTUBE ---
            for i in range(1, 4):
                settings[f'video_{i}'] = request.form.get(f'video_{i}', '')
            # Tương thích với data cũ (nếu sếp đã có video_trang_chu)
            if not settings.get('video_1') and settings.get('video_trang_chu'):
                settings['video_1'] = settings.get('video_trang_chu')

            save_settings(settings)
            flash('Đã lưu Cấu Hình Chung thành công!', 'success')

        # 2. XỬ LÝ LƯU NỘI DUNG CHÍNH SÁCH
        elif hanh_dong == 'luu_chinh_sach':
            settings['cs_cua_hang'] = request.form.get('cs_cua_hang', '')
            settings['cs_doi_tra'] = request.form.get('cs_doi_tra', '')
            settings['cs_van_chuyen'] = request.form.get('cs_van_chuyen', '')
            settings['hd_mua_hang'] = request.form.get('hd_mua_hang', '')
            save_settings(settings)
            flash('Đã lưu Nội dung Chính Sách!', 'success')

        elif hanh_dong == 'luu_topics':
            def xu_ly_anh_topic(ten_input, file_cu):
                file = request.files.get(ten_input)
                if file and file.filename != '':
                    filepath = os.path.join('static/uploads', secure_filename(file.filename))
                    file.save(filepath); return '/' + filepath
                return file_cu

            for i in range(1, 4):
                settings[f'topic_{i}_title'] = request.form.get(f'topic_{i}_title', '')
                settings[f'topic_{i}_date'] = request.form.get(f'topic_{i}_date', '')
                settings[f'topic_{i}_link'] = request.form.get(f'topic_{i}_link', '/san-pham')
                settings[f'topic_{i}_img'] = xu_ly_anh_topic(f'topic_{i}_img', settings.get(f'topic_{i}_img'))
            
            save_settings(settings)
            flash('Đã lưu các Banner Topics Hàng Về!', 'success')
            
        # 3. XỬ LÝ THÊM LINK MENU
        elif hanh_dong == 'them_menu':
            conn.execute('INSERT INTO menu_item (cot, nhom, icon_nhom, ten_link, url, badge_html) VALUES (?,?,?,?,?,?)',
                         (request.form['cot'], request.form['nhom'], request.form['icon_nhom'], request.form['ten_link'], request.form['url'], request.form.get('badge_html','')))
            conn.commit()
            flash('Đã thêm link vào Menu!', 'success')
            
        # 4. XỬ LÝ XÓA LINK MENU
        elif hanh_dong == 'xoa_menu':
            conn.execute('DELETE FROM menu_item WHERE id=?', (request.form['id'],))
            conn.commit()
            flash('Đã xóa link khỏi Menu!', 'success')
            
        conn.close()
        return redirect(url_for('cai_dat_giao_dien'))
        
    try: items = conn.execute('SELECT * FROM menu_item ORDER BY cot ASC, id ASC').fetchall()
    except: items = []
    conn.close()
    return render_template('cai_dat.html', settings=settings, items=items)

@app.route('/san-pham')
def tat_ca_san_pham():
    conn = ket_noi_db()
    tu_khoa = request.args.get('tu_khoa', '')
    danh_muc_loc = request.args.get('danh_muc', '')
    hang_loc = request.args.get('hang_sx', '')
    kieu_loc = request.args.get('kieu_hang', '')
    ton_kho = request.args.get('ton_kho', '') 
    sap_xep = request.args.get('sap_xep', 'moi_nhat')
    page = request.args.get('page', 1, type=int)
    per_page = 12 
    
    cau_lenh_base = ' FROM san_pham WHERE 1=1'
    dk = []
    if tu_khoa:
        cau_lenh_base += ' AND ten LIKE ?'; dk.append(f'%{tu_khoa}%')
    if danh_muc_loc:
        cau_lenh_base += ' AND the_loai = ?'; dk.append(danh_muc_loc)
    if hang_loc:
        cau_lenh_base += ' AND hang_sx = ?'; dk.append(hang_loc)
    if kieu_loc:
        cau_lenh_base += ' AND kieu_hang = ?'; dk.append(kieu_loc)
    if ton_kho == 'con_hang': cau_lenh_base += ' AND so_luong > 0'
    elif ton_kho == 'het_hang': cau_lenh_base += ' AND so_luong <= 0'
        
    tong_sp = conn.execute('SELECT COUNT(id)' + cau_lenh_base, dk).fetchone()[0]
    tong_trang = (tong_sp + per_page - 1) // per_page
    
    order_by = ' ORDER BY id DESC'
    if sap_xep == 'cu_nhat': order_by = ' ORDER BY id ASC'
    if sap_xep == 'gia_tang': order_by = ' ORDER BY gia_ban ASC'
    elif sap_xep == 'gia_giam': order_by = ' ORDER BY gia_ban DESC'
    
    cau_lenh = 'SELECT *' + cau_lenh_base + order_by + ' LIMIT ? OFFSET ?'
    dk.extend([per_page, (page - 1) * per_page])
    san_phams = conn.execute(cau_lenh, dk).fetchall()
    danh_mucs = conn.execute('SELECT DISTINCT the_loai as ten_danh_muc FROM san_pham').fetchall()
    hangs = conn.execute('SELECT DISTINCT hang_sx as ten_hang FROM san_pham').fetchall()
    conn.close()

    if request.args.get('ajax') == '1':
        return render_template('partials_san_pham.html', san_phams=san_phams, page=page, tong_trang=tong_trang, dm_chon=danh_muc_loc, hang_chon=hang_loc, kieu_chon=kieu_loc, tu_khoa=tu_khoa, ton_kho_chon=ton_kho, sap_xep_chon=sap_xep)
    
    return render_template('tat_ca_san_pham.html', san_phams=san_phams, danh_mucs=danh_mucs, hangs=hangs, page=page, tong_trang=tong_trang, dm_chon=danh_muc_loc, hang_chon=hang_loc, kieu_chon=kieu_loc, tu_khoa=tu_khoa, ton_kho_chon=ton_kho, sap_xep_chon=sap_xep)

@app.route('/thanh-toan', methods=['GET', 'POST'])
def thanh_toan():
    gio_hang = session.get('gio_hang', [])
    if not gio_hang: return redirect(url_for('xem_gio_hang'))
    tong_tien = sum(item['gia'] * item['so_luong'] for item in gio_hang)
    conn = ket_noi_db()
    danh_sach_khach = conn.execute('SELECT id, ho_ten, sdt FROM khach_hang ORDER BY ho_ten ASC').fetchall()
    
    if request.method == 'POST':
        ten_khach = request.form['ten']
        sdt = request.form['sdt']
        dia_chi = request.form['dia_chi']
        
        # BỔ SUNG: Bắt số tiền khách đã trả (Chỉ khi Admin lên đơn)
        tien_da_tra = 0
        if session.get('admin_id'):
            try: tien_da_tra = float(request.form.get('tien_da_tra', 0))
            except: tien_da_tra = 0
            
        khach_id = session.get('khach_id')
        if session.get('admin_id'):
            kh_chon = request.form.get('khach_id_duoc_chon')
            if kh_chon: khach_id = kh_chon
            
        cur = conn.cursor()
        if not khach_id:
            kh_db = cur.execute('SELECT id FROM khach_hang WHERE sdt = ?', (sdt,)).fetchone()
            if kh_db: khach_id = kh_db['id']
            else: khach_id = 0

        # TỰ ĐỘNG CHUYỂN TRẠNG THÁI NẾU CÓ ĐÓNG TIỀN
        trang_thai = 'Hoàn thành' if tien_da_tra >= tong_tien and tong_tien > 0 else 'Chờ xử lý'
        if tien_da_tra > 0 and trang_thai != 'Hoàn thành':
            trang_thai = 'Đã cọc'

        # Chèn thêm tien_da_tra vào Database
        cur.execute('INSERT INTO don_hang (khach_hang_id, ten_khach, sdt, dia_chi, tong_tien, tien_da_tra, trang_thai) VALUES (?, ?, ?, ?, ?, ?, ?)', (khach_id, ten_khach, sdt, dia_chi, tong_tien, tien_da_tra, trang_thai))
        don_id = cur.lastrowid
        
        for item in gio_hang:
            cur.execute('INSERT INTO chi_tiet_don (don_hang_id, san_pham_id, so_luong, gia) VALUES (?, ?, ?, ?)', (don_id, item['id'], item['so_luong'], item['gia']))
            cur.execute('UPDATE san_pham SET so_luong = so_luong - ? WHERE id = ?', (item['so_luong'], item['id']))
            
        conn.commit(); conn.close()
        session['gio_hang'] = []; session.modified = True
        
        if session.get('admin_id'):
            flash(f'Đã lên đơn & Ghi nhận thanh toán thành công! Mã đơn: #{don_id}', 'success')
            return redirect(url_for('quan_ly_don_hang'))
        else:
            flash(f'Tuyệt vời! Bạn đã đặt hàng thành công. Mã đơn: #{don_id}', 'success')
            return redirect(url_for('ho_so_khach'))

    conn.close()
    return render_template('thanh_toan.html', gio_hang=gio_hang, tong_tien=tong_tien, khachs=danh_sach_khach)

@app.route('/api/get-khach-info/<int:id>')
def get_khach_info(id):
    conn = ket_noi_db()
    kh = conn.execute('SELECT ho_ten, sdt, dia_chi FROM khach_hang WHERE id = ?', (id,)).fetchone()
    conn.close()
    if kh: return {"ho_ten": kh['ho_ten'], "sdt": kh['sdt'], "dia_chi": kh['dia_chi']}
    return {"error": "Không tìm thấy"}, 404

@app.route('/api/search-products')
def search_products_api():
    tu_khoa = request.args.get('tu_khoa', '').strip()
    if len(tu_khoa) < 1: return jsonify([])
    conn = ket_noi_db()
    sps = conn.execute("SELECT id, ten, hinh_anh, gia_ban, kieu_hang FROM san_pham WHERE ten LIKE ? LIMIT 5", (f'%{tu_khoa}%',)).fetchall()
    conn.close()
    
    ket_qua = []
    for sp in sps:
        ket_qua.append({"id": sp['id'], "ten": sp['ten'], "hinh_anh": sp['hinh_anh'], "gia": "{:,.0f}".format(sp['gia_ban']), "status": sp['kieu_hang']})
    return jsonify(ket_qua)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    Timer(1.5, lambda: webbrowser.open_new('http://127.0.0.1:5000/')).start()
    app.run(debug=True)