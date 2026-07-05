import sqlite3
import json
import os
from werkzeug.security import generate_password_hash
from hashids import Hashids

SETTINGS_FILE = 'settings.json'
hashids = Hashids(salt="takimitsu_hobby_sieu_bao_mat", min_length=8)

def ket_noi_db():
    conn = sqlite3.connect('database_v5.db')
    conn.row_factory = sqlite3.Row
    return conn

def save_settings(settings_data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings_data, f, ensure_ascii=False, indent=4)

def get_settings():
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            "ten_web": "TAKIMITSU HOBBY", "logo_url": "", "mau_chu_dao": "#e60012",
            "banner_1": "", "banner_2": "", 
            "thong_tin_footer": "Nơi cho những con nghiện nhựa",
            "dia_chi": "TP. Hồ Chí Minh", "dien_thoai": "091.416.5278", "email": "012345678",
            "ma_so_thue": "",
            "link_fb": "#", "link_ig": "#", "link_yt": "#",
            "cs_cua_hang": "", "cs_doi_tra": "", "cs_van_chuyen": "", "hd_mua_hang": "",
            "video_trang_chu": "HGCsAcFzaFw"
        }
        save_settings(default_settings)
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: 
        return json.load(f)

def get_mega_menu():
    conn = ket_noi_db()
    try:
        items = conn.execute('SELECT * FROM menu_item ORDER BY cot ASC, id ASC').fetchall()
    except:
        conn.execute('CREATE TABLE IF NOT EXISTS menu_item (id INTEGER PRIMARY KEY AUTOINCREMENT, cot INTEGER, nhom TEXT, icon_nhom TEXT, ten_link TEXT, url TEXT, badge_html TEXT)')
        defaults = [
            (1, 'BANDAI SPIRITS', 'fas fa-robot', 'S.H.Figuarts', '/san-pham?hang_sx=Bandai', ''),
            (1, 'BANDAI SPIRITS', 'fas fa-robot', 'Mô hình khớp cử động', '/san-pham?danh_muc=Action Figure', '')
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

def tao_bang_va_cap_nhat():
    conn = ket_noi_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS san_pham (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ten TEXT, the_loai TEXT, hang_sx TEXT, 
        gia_nhap REAL, gia_ban REAL, so_luong INTEGER, hinh_anh TEXT, mo_ta TEXT, 
        kieu_hang TEXT DEFAULT 'Co san', tien_coc REAL DEFAULT 0, ngay_phat_hanh TEXT,
        nguon_nhap_id INTEGER, tien_da_tra_nguon REAL DEFAULT 0, 
        trang_thai_nhap TEXT DEFAULT 'Còn nợ', ngay_du_kien_ve TEXT,
        so_luong_nhap INTEGER DEFAULT 0, gia_san_new REAL DEFAULT 0, 
        gia_san_likenew REAL DEFAULT 0, gia_order_new REAL DEFAULT 0, 
        gia_order_likenew REAL DEFAULT 0, gia_goc REAL DEFAULT 0)''')
    
    conn.execute('CREATE TABLE IF NOT EXISTS danh_muc (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_danh_muc TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS nguon_nhap (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_nguon TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS hang_sx_list (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_hang TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS hinh_anh_sp (id INTEGER PRIMARY KEY AUTOINCREMENT, san_pham_id INTEGER, du_ong_dan TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS khach_hang (id INTEGER PRIMARY KEY AUTOINCREMENT, tai_khoan TEXT UNIQUE, mat_khau TEXT, ho_ten TEXT, sdt TEXT, dia_chi TEXT, vai_tro TEXT DEFAULT "khach", nhom_khach TEXT DEFAULT "Thường", ghi_chu TEXT DEFAULT "")')
    conn.execute('''CREATE TABLE IF NOT EXISTS don_hang (
        id INTEGER PRIMARY KEY AUTOINCREMENT, khach_hang_id INTEGER, ten_khach TEXT, 
        sdt TEXT, dia_chi TEXT, tong_tien REAL, tien_da_tra REAL DEFAULT 0, 
        ngay_dat DATETIME DEFAULT CURRENT_TIMESTAMP, trang_thai TEXT DEFAULT "Chờ xử lý")''')
    conn.execute('CREATE TABLE IF NOT EXISTS chi_tiet_don (id INTEGER PRIMARY KEY AUTOINCREMENT, don_hang_id INTEGER, san_pham_id INTEGER, so_luong INTEGER, gia REAL)')
    conn.execute('CREATE TABLE IF NOT EXISTS menu_item (id INTEGER PRIMARY KEY AUTOINCREMENT, cot INTEGER, nhom TEXT, icon_nhom TEXT, ten_link TEXT, url TEXT, badge_html TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS lich_su_tra_nguon (id INTEGER PRIMARY KEY AUTOINCREMENT, san_pham_id INTEGER, so_tien REAL, ngay_tra DATETIME DEFAULT CURRENT_TIMESTAMP)')
    
    if conn.execute("SELECT COUNT(*) FROM khach_hang WHERE vai_tro = 'admin'").fetchone()[0] == 0:
        hashed_pw = generate_password_hash('123')
        conn.execute("INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, vai_tro) VALUES ('admin', ?, 'Quản trị viên', 'admin')", (hashed_pw,))
        
    # --- BẢN CẬP NHẬT MỚI V7: TÁCH BẢNG LÔ HÀNG ---
    conn.execute('''CREATE TABLE IF NOT EXISTS lo_hang_nhap (
        id INTEGER PRIMARY KEY AUTOINCREMENT, san_pham_id INTEGER, nguon_nhap_id INTEGER, 
        so_luong_nhap INTEGER, gia_nhap REAL, tien_da_tra_nguon REAL DEFAULT 0, 
        trang_thai_nhap TEXT DEFAULT 'Còn nợ', ngay_du_kien_ve TEXT, ngay_tao DATETIME DEFAULT CURRENT_TIMESTAMP)''')

    try: conn.execute("ALTER TABLE lich_su_tra_nguon ADD COLUMN lo_hang_id INTEGER")
    except: pass 

    # AUTO MIGRATION: Dời dữ liệu nguồn cũ sang bảng lô hàng
    if conn.execute("SELECT COUNT(*) FROM lo_hang_nhap").fetchone()[0] == 0:
        sps = conn.execute("SELECT id, nguon_nhap_id, so_luong_nhap, gia_nhap, tien_da_tra_nguon, trang_thai_nhap, ngay_du_kien_ve FROM san_pham WHERE so_luong_nhap > 0 OR gia_nhap > 0").fetchall()
        for sp in sps:
            cur = conn.cursor()
            cur.execute('''INSERT INTO lo_hang_nhap (san_pham_id, nguon_nhap_id, so_luong_nhap, gia_nhap, tien_da_tra_nguon, trang_thai_nhap, ngay_du_kien_ve) VALUES (?, ?, ?, ?, ?, ?, ?)''', (sp['id'], sp['nguon_nhap_id'], sp['so_luong_nhap'], sp['gia_nhap'], sp['tien_da_tra_nguon'], sp['trang_thai_nhap'], sp['ngay_du_kien_ve']))
            new_lo_id = cur.lastrowid
            conn.execute("UPDATE lich_su_tra_nguon SET lo_hang_id = ? WHERE san_pham_id = ?", (new_lo_id, sp['id']))
            
    conn.commit(); conn.close()