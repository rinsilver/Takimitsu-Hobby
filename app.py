import os, webbrowser, sqlite3
from threading import Timer
# Sửa lại dòng import từ flask để có đầy đủ các hàm sếp đang dùng
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from werkzeug.security import generate_password_hash, check_password_hash # Thêm dòng này để mã hóa bảo mật
import json
from flask_wtf.csrf import CSRFProtect
import os
from PIL import Image # Đảm bảo đã có dòng này ở đầu file app.py
from werkzeug.utils import secure_filename # Để xử lý tên file an toàn
from flask_mail import Mail, Message 

app = Flask(__name__)
app.secret_key = 'wolves_master_system_ultimate_v7'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = True # Bật cái này khi web có HTTPS
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 # 1 ngày tự động đăng xuất

# CẤU HÌNH EMAIL (Sếp thay thông tin của sếp vào đây)
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'duymx25092000@gmail.com' # Email sếp dùng gửi
app.config['MAIL_PASSWORD'] = 'voxr henm kuap hgpu'      # 16 ký tự App Password vừa tạo
app.config['MAIL_DEFAULT_SENDER'] = ('TAKIMITSU HOBBY', 'duymx25092000@gmail.com')

mail = Mail(app)
csrf = CSRFProtect(app)

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# --- BẢO MẬT SESSION (Chống Hacker ăn cắp Cookie) ---
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400 # Tự động đăng xuất sau 1 ngày

# --- KHIÊN CHỐNG BRUTE-FORCE (Spam đăng nhập) ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# --- HỆ THỐNG QUẢN LÝ CÀI ĐẶT GIAO DIỆN (JSON) ---
SETTINGS_FILE = 'settings.json'

def gui_email_thong_bao(don_id, ten_khach, email_khach, tong_tien, gio_hang):
    try:
        # 1. Gửi cho Khách hàng (Xác nhận đơn)
        msg_khach = Message(f"Xác nhận đơn hàng #{don_id} từ Takimitsu Hobby",
                           recipients=[email_khach])
        
        # Tạo nội dung HTML cho chuyên nghiệp
        html_content = f"<h3>Chào {ten_khach}, cảm ơn sếp đã ủng hộ shop!</h3>"
        html_content += f"<p>Đơn hàng <b>#{don_id}</b> của sếp đã được tiếp nhận.</p>"
        html_content += "<ul>"
        for item in gio_hang:
            html_content += f"<li>{item['ten']} x {item['so_luong']} - {item['gia']:,.0f}đ</li>"
        html_content += "</ul>"
        html_content += f"<h4>Tổng cộng: {tong_tien:,.0f} VNĐ</h4>"
        html_content += "<p>Shop sẽ sớm liên hệ để giao hàng cho sếp!</p>"
        
        msg_khach.html = html_content
        mail.send(msg_khach)

        # 2. Gửi cho Sếp (Báo có đơn mới)
        msg_admin = Message(f"SẾP ƠI! CÓ ĐƠN HÀNG MỚI #{don_id}",
                           recipients=['email_cua_sep@gmail.com']) # Nhận tại mail chính của sếp
        msg_admin.body = f"Khách {ten_khach} vừa đặt đơn #{don_id}. Tổng tiền: {tong_tien:,.0f}đ. Vào Admin check ngay sếp ơi!"
        mail.send(msg_admin)
        
        return True
    except Exception as e:
        print(f"Lỗi gửi mail: {e}")
        return False
    
def get_settings():
    if not os.path.exists(SETTINGS_FILE):
        default_settings = {
            "ten_web": "WOLVES STORE", "logo_url": "", "mau_chu_dao": "#e60012",
            "banner_1": "", "banner_2": "", 
            "thong_tin_footer": "Shop online chuyên sản phẩm mô hình chính hãng",
            "dia_chi": "TP. Hồ Chí Minh", "dien_thoai": "091.416.5278", "email": "0914165278",
            "link_fb": "#", "link_ig": "#", "link_yt": "#",
            # THÊM 4 DÒNG NÀY ĐỂ TẠO CHỖ CHỨA CHÍNH SÁCH
            "cs_cua_hang": "", "cs_doi_tra": "", "cs_van_chuyen": "", "hd_mua_hang": "",
            "video_trang_chu": "HGCsAcFzaFw" # <-- THÊM DÒNG NÀY
        }
        save_settings(default_settings)
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f: return json.load(f)

def save_settings(settings_data):
    # Giả sử sếp lưu vào file json
    import json
    with open('settings.json', 'w', encoding='utf-8') as f:
        json.dump(settings_data, f, ensure_ascii=False, indent=4)

# Bơm settings vào TOÀN BỘ trang web
@app.context_processor
def inject_data():
    gio_hang = session.get('gio_hang', [])
    so_luong = 0
    if isinstance(gio_hang, list):
        for item in gio_hang:
            if isinstance(item, dict) and 'so_luong' in item:
                so_luong += item['so_luong']

    # Trả về ĐẦY ĐỦ các biến cần thiết cho toàn web
    return dict(
        so_luong_gio_hang=so_luong, 
        is_admin='admin_id' in session, 
        is_khach='khach_id' in session, 
        khach_ten=session.get('khach_ten', ''),
        settings=get_settings() # ĐẢM BẢO DÒNG NÀY LUÔN TỒN TẠI
    )
# --- CƠ SỞ DỮ LIỆU ---
def ket_noi_db():
    conn = sqlite3.connect('database_v5.db')
    conn.row_factory = sqlite3.Row
    return conn

def tao_bang():
    conn = ket_noi_db()
    # Các lệnh CREATE TABLE cũ... (Sếp cứ giữ nguyên đoạn CREATE TABLE cũ)
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
    
    # THÊM CỘT: tien_da_tra (Tiền khách đã cọc/trả)
    conn.execute('''CREATE TABLE IF NOT EXISTS don_hang (
        id INTEGER PRIMARY KEY AUTOINCREMENT, khach_hang_id INTEGER, ten_khach TEXT, 
        sdt TEXT, dia_chi TEXT, tong_tien REAL, tien_da_tra REAL DEFAULT 0, 
        ngay_dat DATETIME DEFAULT CURRENT_TIMESTAMP, trang_thai TEXT DEFAULT "Chờ xử lý")''')
        
    conn.execute('CREATE TABLE IF NOT EXISTS chi_tiet_don (id INTEGER PRIMARY KEY AUTOINCREMENT, don_hang_id INTEGER, san_pham_id INTEGER, so_luong INTEGER, gia REAL)')

    # 🔥 LỆNH THẦN THÁNH: Tự động cấy thêm cột "Số lượng nhập" mà không làm mất dữ liệu
    try:
        conn.execute("ALTER TABLE san_pham ADD COLUMN so_luong_nhap INTEGER DEFAULT 0")
        conn.execute("UPDATE san_pham SET so_luong_nhap = so_luong WHERE so_luong_nhap = 0")
    except:
        pass # Nếu cột đã tồn tại thì bỏ qua
    
    if conn.execute("SELECT COUNT(*) FROM khach_hang WHERE vai_tro = 'admin'").fetchone()[0] == 0:
        hashed_pw = generate_password_hash('123') # Biến '123' thành chuỗi bảo mật
        conn.execute("INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, vai_tro) VALUES ('admin', ?, 'Quản trị viên', 'admin')", (hashed_pw,))
    conn.commit(); conn.close()

def cap_nhat_db_phan_loai():
    conn = ket_noi_db()
    for col in ['gia_san_new', 'gia_san_likenew', 'gia_order_new', 'gia_order_likenew']:
        try: conn.execute(f"ALTER TABLE san_pham ADD COLUMN {col} REAL DEFAULT 0")
        except: pass
    # Lấy giá bán cũ làm mặc định cho "Có sẵn - New" để web không bị lỗi
    try: conn.execute("UPDATE san_pham SET gia_san_new = gia_ban WHERE gia_san_new = 0 AND gia_san_likenew = 0 AND gia_order_new = 0 AND gia_order_likenew = 0 AND gia_ban > 0")
    except: pass
    conn.commit()
    conn.close()

tao_bang()
cap_nhat_db_phan_loai()

# ================= TRANG CHỦ (STYLE TAMASHII) =================
@app.route('/')
def index():
    conn = ket_noi_db()
    # 1. Giữ nguyên dữ liệu cũ của sếp
    san_phams = conn.execute('SELECT * FROM san_pham ORDER BY id DESC LIMIT 8').fetchall()
    hang_sxs_raw = conn.execute('SELECT DISTINCT hang_sx FROM san_pham WHERE hang_sx IS NOT NULL AND hang_sx != "" LIMIT 8').fetchall()
    danh_sach_hang = [h['hang_sx'] for h in hang_sxs_raw]
    
    # 2. Lấy thêm dữ liệu cho 2 khối Tamashii mới
    hang_co_san = conn.execute("SELECT * FROM san_pham WHERE kieu_hang = 'Co san' ORDER BY id DESC LIMIT 12").fetchall()
    hang_order = conn.execute("SELECT * FROM san_pham WHERE kieu_hang = 'Pre-order' ORDER BY id DESC LIMIT 12").fetchall()
    
    conn.close()
    return render_template('index.html', san_phams=san_phams, hang_sxs=danh_sach_hang, 
                           hang_co_san=hang_co_san, hang_order=hang_order)

@app.route('/thong-tin/<slug>')
def trang_thong_tin(slug):
    settings = get_settings() # Lấy từ JSON cực nhanh

    # Ánh xạ đường dẫn URL với Key trong file JSON
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

# ================= TRANG CHI TIẾT SẢN PHẨM =================
@app.route('/san-pham/<int:id>')
def chi_tiet_sp(id):
    # Kiểm tra admin nếu cần (tùy sếp)
    # if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    
    conn = ket_noi_db()
    
    # 1. TỰ ĐỘNG TẠO BẢNG ẢNH PHỤ (Giữ nguyên của sếp)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS anh_san_pham (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            san_pham_id INTEGER,
            du_ong_dan TEXT
        )
    ''')
    conn.commit()

    sp = conn.execute('SELECT * FROM san_pham WHERE id = ?', (id,)).fetchone()
    if not sp: 
        conn.close()
        return "Không tìm thấy sản phẩm", 404
    
    # Kéo danh sách ảnh phụ (Giữ nguyên của sếp)
    anh_phu = conn.execute('SELECT * FROM hinh_anh_sp WHERE san_pham_id = ?', (id,)).fetchall()
    
    # 2. LOGIC SẢN PHẨM LIÊN QUAN (Nâng cấp từ code của sếp)
    san_pham_lien_quan = conn.execute('SELECT * FROM san_pham WHERE hang_sx = ? AND id != ? LIMIT 4', (sp['hang_sx'], id)).fetchall()
    tieu_de_goi_y = "SẢN PHẨM CÙNG HÃNG"
    
    if not san_pham_lien_quan:
        san_pham_lien_quan = conn.execute('SELECT * FROM san_pham WHERE id != ? ORDER BY id DESC LIMIT 4', (id,)).fetchall()
        tieu_de_goi_y = "GỢI Ý SẢN PHẨM KHÁC"
        
    # 3. LOGIC "SẢN PHẨM VỪA XEM" (Phần marketing tôi thêm cho sếp)
    da_xem_ids = session.get('da_xem', [])
    san_pham_da_xem = []
    
    # Lấy danh sách các sản phẩm đã xem từ DB (trừ cái đang xem hiện tại)
    if da_xem_ids:
        # Lọc bỏ ID hiện tại ra khỏi danh sách hiển thị "đã xem"
        ids_to_fetch = [idx for idx in da_xem_ids if idx != id]
        if ids_to_fetch:
            # Tạo chuỗi ?,?,? cho SQL
            placeholders = ','.join(['?'] * len(ids_to_fetch))
            query_dx = f'SELECT * FROM san_pham WHERE id IN ({placeholders})'
            sp_da_xem_db = conn.execute(query_dx, ids_to_fetch).fetchall()
            # Sắp xếp đúng thứ tự khách đã xem (gần nhất hiện lên trước)
            san_pham_da_xem = sorted(sp_da_xem_db, key=lambda x: ids_to_fetch.index(x['id']))

    # Cập nhật ID sản phẩm hiện tại vào lịch sử session
    if id in da_xem_ids:
        da_xem_ids.remove(id) # Xóa vị trí cũ nếu có
    da_xem_ids.insert(0, id)  # Đưa lên đầu danh sách
    
    if len(da_xem_ids) > 11:   
        da_xem_ids.pop()
        
    session['da_xem'] = da_xem_ids
    session.modified = True # Ép Flask phải lưu session ngay

    conn.close()
    
    # TRẢ VỀ ĐẦY ĐỦ BIẾN CHO CHI_TIET.HTML
    return render_template('chi_tiet.html', 
                           sp=sp, 
                           anh_phu=anh_phu, 
                           san_pham_lien_quan=san_pham_lien_quan, 
                           tieu_de_goi_y=tieu_de_goi_y,
                           san_pham_da_xem=san_pham_da_xem)

@app.route('/dang-nhap', methods=['GET', 'POST'])
@limiter.limit("30 per minute") # Nhớ giữ lại cái khiên chống hack này sếp nhé
def dang_nhap():
    if request.method == 'POST':
        conn = ket_noi_db()
        tai_khoan_nhap_vao = request.form['tai_khoan']
        
        # 1. Tìm bằng Số điện thoại hoặc Tên tài khoản
        u = conn.execute('SELECT * FROM khach_hang WHERE sdt=? OR tai_khoan=?', 
                         (tai_khoan_nhap_vao, tai_khoan_nhap_vao)).fetchone()
        
        if u:
            # 2. XỬ LÝ MẬT KHẨU "THÔNG MINH"
            mat_khau_db = u['mat_khau']
            mat_khau_nhap = request.form['mat_khau']
            hop_le = False
            
            # Nếu pass trong DB đã mã hóa (có chữ scrypt) -> Dùng check_password_hash
            if mat_khau_db.startswith('scrypt:') or mat_khau_db.startswith('pbkdf2:'):
                hop_le = check_password_hash(mat_khau_db, mat_khau_nhap)
            # Nếu pass trong DB là chữ thường (như "123" sếp vừa lưu) -> So sánh trực tiếp
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
        # MÃ HÓA mật khẩu khách nhập vào
        hashed_pw = generate_password_hash(request.form['mat_khau'])
        try:
            conn.execute('INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, sdt, dia_chi) VALUES (?,?,?,?,?)', 
                         (request.form['tai_khoan'], hashed_pw, request.form['ho_ten'], request.form['sdt'], request.form['dia_chi']))
            conn.commit()
            return redirect(url_for('dang_nhap'))
        except: return "Lỗi: Tài khoản đã tồn tại!"
        finally: conn.close()
    return render_template('dang_ky_khach.html')

# ================= ĐĂNG XUẤT =================
@app.route('/dang-xuat')
def dang_xuat():
    session.clear()
    return redirect(url_for('index'))  # <-- Đổi 'trang_chu' thành 'index' ở đây

# ==================== GIỎ HÀNG & ĐẶT HÀNG ====================

# 1. THÊM VÀO GIỎ HÀNG
@app.route('/them-vao-gio/<int:id>')
def them_vao_gio(id):
    conn = ket_noi_db()
    sp = conn.execute('SELECT * FROM san_pham WHERE id=?', (id,)).fetchone()
    conn.close()
    if not sp: return redirect(url_for('index'))

    hinh_thuc = request.args.get('hinh_thuc', 'san')
    loai = request.args.get('loai', 'new')
    
    key_gia = f"gia_{hinh_thuc}_{loai}"
    gia_chon = sp[key_gia] if key_gia in sp.keys() else sp['gia_ban']
        
    if gia_chon <= 0:
        return redirect(url_for('chi_tiet_sp', id=id))

    # Đánh dấu Variant bằng ID chuỗi (vd: 1_san_new) để giỏ hàng không bị trùng
    ten_variant = f"{sp['ten']} ({'Có sẵn' if hinh_thuc=='san' else 'Order'} - {'New Seal' if loai=='new' else 'Like New'})"
    cart_item_id = f"{id}_{hinh_thuc}_{loai}"

    gio = session.get('gio_hang', [])
    if isinstance(gio, dict): gio = []

    for item in gio: item.pop('error', None)

    found = False
    for item in gio:
        if item.get('cart_id', str(item['id'])) == cart_item_id:
            if item['so_luong'] < sp['so_luong']: item['so_luong'] += 1
            else: item['error'] = f"Chỉ còn {sp['so_luong']} cái!"
            found = True; break
    
    if not found:
        gio.append({'cart_id': cart_item_id, 'id': id, 'ten': ten_variant, 'gia': gia_chon, 'hinh_anh': sp['hinh_anh'], 'so_luong': 1})

    session['gio_hang'] = gio
    session.modified = True
    return redirect(url_for('xem_gio_hang'))


# 2. XEM GIỎ HÀNG
@app.route('/gio-hang')
def xem_gio_hang():
    gio = session.get('gio_hang', [])
    
    # 🔥 Áp dụng luôn cơ chế Tự chữa lành cho lúc xem giỏ
    if isinstance(gio, dict) or (isinstance(gio, list) and len(gio) > 0 and not isinstance(gio[0], dict)): 
        gio = []
        session['gio_hang'] = gio
        session.modified = True
        
    tong_tien = sum(item['gia'] * item['so_luong'] for item in gio)
    
    return render_template('gio_hang.html', gio_hang=gio, tong_tien=tong_tien)

# 3. TĂNG / GIẢM SỐ LƯỢNG
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

@app.route('/dat-hang', methods=['POST'])
def dat_hang():
    uid = session.get('khach_id') or session.get('admin_id')
    if not uid: return "<script>alert('Vui lòng đăng nhập!'); window.location.href='/dang-nhap';</script>"
    conn = ket_noi_db(); cur = conn.cursor()
    tong = 0; cart = session.get('gio_hang', {})
    for sid, sl in cart.items():
        p = cur.execute('SELECT gia_ban FROM san_pham WHERE id=?', (sid,)).fetchone()
        if p: tong += p['gia_ban'] * sl
    cur.execute('INSERT INTO don_hang (khach_hang_id, ten_khach, sdt, dia_chi, tong_tien) VALUES (?,?,?,?,?)', 
                (uid, request.form['ten_khach'], request.form['sdt'], request.form['dia_chi'], tong))
    did = cur.lastrowid
    for sid, sl in cart.items():
        p = cur.execute('SELECT gia_ban FROM san_pham WHERE id=?', (sid,)).fetchone()
        if p:
            cur.execute('INSERT INTO chi_tiet_don (don_hang_id, san_pham_id, so_luong, gia) VALUES (?,?,?,?)', (did, sid, sl, p['gia_ban']))
            cur.execute('UPDATE san_pham SET so_luong = so_luong - ? WHERE id = ?', (sl, sid))
    conn.commit(); conn.close(); session.pop('gio_hang', None)
    return redirect(url_for('lich_su_don_hang'))

@app.route('/lich-su-don-hang')
def lich_su_don_hang():
    uid = session.get('khach_id') or session.get('admin_id')
    if not uid: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    ds = conn.execute('SELECT * FROM don_hang WHERE khach_hang_id=? ORDER BY id DESC', (uid,)).fetchall()
    conn.close()
    return render_template('lich_su_don_hang.html', ds_don_hang=ds)

# ==================== HỆ THỐNG QUẢN TRỊ (ADMIN) ====================

@app.route('/admin')
def admin():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    tu_khoa = request.args.get('tu_khoa', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10 # 10 sản phẩm 1 trang
    
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
        # --- XỬ LÝ ẢNH CHÍNH SANG WEBP ---
        f = request.files['hinh_anh']
        img = ''
        if f and f.filename != '':
            filename = secure_filename(f.filename)
            base_name = os.path.splitext(filename)[0]
            webp_name = base_name + ".webp" # Đổi đuôi file
            save_path = os.path.join(app.config['UPLOAD_FOLDER'], webp_name)
            
            # Mở ảnh và nén sang WebP
            img_raw = Image.open(f)
            img_raw.convert("RGB").save(save_path, "WEBP", quality=80) 
            img = '/static/uploads/' + webp_name

        cur = conn.cursor()
        
        # Lấy giá và số lượng từ form
        gia_san_new = float(request.form.get('gia_san_new', 0) or 0)
        gia_san_likenew = float(request.form.get('gia_san_likenew', 0) or 0)
        gia_order_new = float(request.form.get('gia_order_new', 0) or 0)
        gia_order_likenew = float(request.form.get('gia_order_likenew', 0) or 0)
        gia_ban = float(request.form.get('gia_ban', gia_san_new)) 
        
        # Lưu vào Database
        cur.execute('''INSERT INTO san_pham (ten, the_loai, hang_sx, gia_nhap, gia_ban, so_luong, so_luong_nhap, hinh_anh, mo_ta, kieu_hang, tien_coc, ngay_phat_hanh, nguon_nhap_id, tien_da_tra_nguon, trang_thai_nhap, ngay_du_kien_ve, gia_san_new, gia_san_likenew, gia_order_new, gia_order_likenew) 
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                    (request.form['ten'], request.form['the_loai'], request.form['hang_sx'], 
                     float(request.form.get('gia_nhap', 0) or 0), gia_ban, 
                     int(request.form.get('so_luong', 0) or 0), int(request.form.get('so_luong', 0) or 0), 
                     img, request.form['mo_ta'], request.form['kieu_hang'], 
                     float(request.form.get('tien_coc', 0) or 0), request.form.get('ngay_phat_hanh', ''), 
                     request.form.get('nguon_nhap_id'), float(request.form.get('tien_da_tra_nguon', 0) or 0), 
                     request.form.get('trang_thai_nhap', 'Còn nợ'), request.form.get('ngay_ve', ''),
                     gia_san_new, gia_san_likenew, gia_order_new, gia_order_likenew))
        
        sid = cur.lastrowid
        
        # --- XỬ LÝ ẢNH PHỤ SANG WEBP ---
        for pf in request.files.getlist('hinh_anh_phu'):
            if pf and pf.filename != '':
                filename_phu = secure_filename(pf.filename)
                base_name_phu = os.path.splitext(filename_phu)[0]
                webp_name_phu = base_name_phu + "_" + str(sid) + ".webp" # Thêm ID để tránh trùng
                save_path_phu = os.path.join(app.config['UPLOAD_FOLDER'], webp_name_phu)
                
                img_phu_raw = Image.open(pf)
                img_phu_raw.convert("RGB").save(save_path_phu, "WEBP", quality=80)
                conn.execute('INSERT INTO hinh_anh_sp (san_pham_id, du_ong_dan) VALUES (?,?)', 
                             (sid, '/static/uploads/' + webp_name_phu))
        
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
        # 1. Lấy 4 giá phân loại từ form (Nếu không điền thì mặc định là 0)
        gia_san_new = float(request.form.get('gia_san_new', 0) or 0)
        gia_san_likenew = float(request.form.get('gia_san_likenew', 0) or 0)
        gia_order_new = float(request.form.get('gia_order_new', 0) or 0)
        gia_order_likenew = float(request.form.get('gia_order_likenew', 0) or 0)
        
        # Lấy giá bán gốc làm mặc định
        gia_ban = float(request.form.get('gia_ban', gia_san_new)) 

        f = request.files.get('hinh_anh')
        img_sql = ""
        
        # 2. Xây dựng danh sách tham số (Cộng thêm 4 trường giá phân loại)
        tham_so = [
            request.form['ten'], request.form['the_loai'], request.form['hang_sx'],
            float(request.form.get('gia_nhap', 0) or 0), gia_ban, int(request.form.get('so_luong', 0) or 0),
            request.form['mo_ta'], request.form['kieu_hang'], float(request.form.get('tien_coc', 0) or 0),
            request.form.get('ngay_phat_hanh', ''), request.form.get('nguon_nhap_id'),
            float(request.form.get('tien_da_tra_nguon', 0) or 0), request.form.get('trang_thai_nhap', 'Còn nợ'),
            request.form.get('ngay_ve', ''),
            gia_san_new, gia_san_likenew, gia_order_new, gia_order_likenew # <-- 4 CỘT MỚI Ở ĐÂY
        ]

        if f and f.filename != '':
            ten_file = secure_filename(f.filename)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], ten_file))
            img_sql = ", hinh_anh = ?"
            tham_so.append('/static/uploads/' + ten_file)
            
        tham_so.append(id) # ID cho mệnh đề WHERE

        # 3. Thực thi cập nhật database
        conn.execute(f'''
            UPDATE san_pham SET 
            ten=?, the_loai=?, hang_sx=?, gia_nhap=?, gia_ban=?, so_luong=?, mo_ta=?, 
            kieu_hang=?, tien_coc=?, ngay_phat_hanh=?, nguon_nhap_id=?, tien_da_tra_nguon=?, 
            trang_thai_nhap=?, ngay_du_kien_ve=?,
            gia_san_new=?, gia_san_likenew=?, gia_order_new=?, gia_order_likenew=? {img_sql} 
            WHERE id=?
        ''', tuple(tham_so))
        
        # 4. Lưu thêm ảnh phụ mới (nếu sếp có up thêm)
        for pf in request.files.getlist('hinh_anh_phu'):
            if pf and pf.filename != '':
                ten_file = secure_filename(pf.filename)
                pf.save(os.path.join(app.config['UPLOAD_FOLDER'], ten_file))
                conn.execute('INSERT INTO hinh_anh_sp (san_pham_id, du_ong_dan) VALUES (?,?)', (id, '/static/uploads/'+ten_file))
                
        conn.commit(); conn.close()
        return redirect(url_for('admin')) 

    # LẤY DATA CHO GET METHOD HIỂN THỊ LÊN FORM
    sp = conn.execute('SELECT * FROM san_pham WHERE id = ?', (id,)).fetchone()
    dms = conn.execute('SELECT * FROM danh_muc').fetchall()
    hgs = conn.execute('SELECT * FROM hang_sx_list').fetchall()
    ngs = conn.execute('SELECT * FROM nguon_nhap').fetchall()
    conn.close()
    
    return render_template('sua.html', sp=sp, danh_mucs=dms, hangs=hgs, nguons=ngs)

@app.route('/xoa/<int:id>', methods=['POST'])
def xoa_san_pham(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    # 1. KIỂM TRA KHÓA AN TOÀN: Xem sản phẩm này có đang nằm trong đơn hàng nào không
    don_hang_dang_chua = conn.execute('''
        SELECT d.id, d.trang_thai 
        FROM chi_tiet_don c
        JOIN don_hang d ON c.don_hang_id = d.id
        WHERE c.san_pham_id = ? AND d.trang_thai NOT IN ('Hoàn thành', 'Đã hủy')
    ''', (id,)).fetchone()

    if don_hang_dang_chua:
        # Nếu có khách đang đặt, trả về thông báo lỗi (bằng JavaScript alert)
        conn.close()
        return f"<script>alert('SẾP KHOAN XÓA! Sản phẩm này đang nằm trong Đơn hàng #{don_hang_dang_chua['id']} (Trạng thái: {don_hang_dang_chua['trang_thai']}). Vui lòng Hủy đơn hoặc Hoàn thành đơn trước khi xóa sản phẩm khỏi kho.'); window.location.href='/admin';</script>"

    # 2. XÓA FILE ẢNH VẬT LÝ ĐỂ NHẸ Ổ CỨNG
    sp = conn.execute('SELECT hinh_anh FROM san_pham WHERE id=?', (id,)).fetchone()
    if sp and sp['hinh_anh']:
        try: os.remove(os.path.join(app.root_path, sp['hinh_anh'].lstrip('/')))
        except: pass
    
    anh_phus = conn.execute('SELECT du_ong_dan FROM hinh_anh_sp WHERE san_pham_id=?', (id,)).fetchall()
    for anh in anh_phus:
        try: os.remove(os.path.join(app.root_path, anh['du_ong_dan'].lstrip('/')))
        except: pass

    # 3. XÓA DỮ LIỆU TRONG DATABASE
    conn.execute('DELETE FROM san_pham WHERE id=?', (id,))
    conn.execute('DELETE FROM hinh_anh_sp WHERE san_pham_id=?', (id,))
    
    conn.commit()
    conn.close()
    return redirect(url_for('admin'))

# ==================== QUẢN LÝ CÔNG NỢ & NGUỒN ====================
@app.route('/admin/cong-no-nguon')
def cong_no_nguon():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    nguons = conn.execute('SELECT * FROM nguon_nhap').fetchall()
    
    # 1. NHẬN CÁC BIẾN TỪ BỘ LỌC
    nguon_id = request.args.get('nguon_id', '')
    kieu_hang = request.args.get('kieu_hang', '')
    trang_thai_loc = request.args.get('trang_thai_loc', '') # Thêm dòng này để bắt Trạng thái
    
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    
    query = "SELECT sp.*, n.ten_nguon FROM san_pham sp LEFT JOIN nguon_nhap n ON sp.nguon_nhap_id = n.id WHERE 1=1"
    params = []
    
    # 2. GẮN ĐIỀU KIỆN LỌC VÀO TRUY VẤN
    if nguon_id:
        query += " AND sp.nguon_nhap_id = ?"; params.append(nguon_id)
    if kieu_hang:
        query += " AND sp.kieu_hang = ?"; params.append(kieu_hang)
    if trang_thai_loc: # Thêm khối này để lọc Database
        query += " AND sp.trang_thai_nhap = ?"; params.append(trang_thai_loc)
        
    total_items = conn.execute("SELECT COUNT(*) FROM (" + query + ")", params).fetchone()[0]
    total_pages = (total_items + per_page - 1) // per_page
    
    query += " ORDER BY CASE WHEN sp.trang_thai_nhap = 'Còn nợ' THEN 1 ELSE 2 END, sp.ngay_du_kien_ve ASC LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    items = conn.execute(query, params).fetchall()
    
    # Đã sửa lại: Tính tổng nợ dựa trên "so_luong_nhap" thay vì "so_luong"
    tong_no_query = "SELECT SUM(sp.gia_nhap * sp.so_luong_nhap - sp.tien_da_tra_nguon) FROM san_pham sp WHERE sp.trang_thai_nhap = 'Còn nợ'"
    tong_no_params = []
    if nguon_id:
        tong_no_query += " AND sp.nguon_nhap_id = ?"; tong_no_params.append(nguon_id)
    if kieu_hang:
        tong_no_query += " AND sp.kieu_hang = ?"; tong_no_params.append(kieu_hang)
        
    tong_no_result = conn.execute(tong_no_query, tong_no_params).fetchone()[0]
    tong_no = tong_no_result if tong_no_result else 0
    
    conn.close()
    
    # 3. TRUYỀN ĐÚNG TÊN BIẾN RA HTML (page, tong_trang, trang_thai_loc)
    return render_template('cong_no_nguon.html', items=items, nguons=nguons, tong_no=tong_no, 
                           page=page, tong_trang=total_pages, # Đã đổi tên biến để khớp với giao diện
                           nguon_chon=nguon_id, kieu_chon=kieu_hang, trang_thai_loc=trang_thai_loc)

@app.route('/admin/cap-nhat-tra-tien/<int:id>', methods=['POST'])
def cap_nhat_tra_tien(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    sp = conn.execute('SELECT gia_nhap, so_luong, tien_da_tra_nguon FROM san_pham WHERE id=?', (id,)).fetchone()
    
    so_tien_nhap_vao = float(request.form.get('so_tien', 0))
    hanh_dong = request.form.get('hanh_dong') # Lấy hành động (Cộng thêm hoặc Ghi đè)
    
    # 1. Tính toán tiền mới
    if hanh_dong == 'cong':
        tien_moi = sp['tien_da_tra_nguon'] + so_tien_nhap_vao
    else:
        tien_moi = so_tien_nhap_vao # Sếp chọn sửa trực tiếp
        
    tong_nhap = sp['gia_nhap'] * sp['so_luong']
    trang_thai = request.form.get('trang_thai', 'Còn nợ')
    
    # 2. Tự động Auto-chuyển trạng thái nếu trả đủ tiền
    if tien_moi >= tong_nhap:
        trang_thai = 'Đã thanh toán'
        
    conn.execute('UPDATE san_pham SET tien_da_tra_nguon=?, trang_thai_nhap=?, ngay_du_kien_ve=? WHERE id=?', 
                 (tien_moi, trang_thai, request.form.get('ngay_ve', ''), id))
    conn.commit(); conn.close()
    return redirect(url_for('cong_no_nguon'))

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

# ==================== ĐƠN HÀNG & THỐNG KÊ ====================

# ==================== 1. QUẢN LÝ ĐƠN HÀNG (CÓ PHÂN TRANG & SẮP XẾP) ====================
# ================= QUẢN LÝ TẤT CẢ ĐƠN HÀNG (CÓ PHÂN TRANG) =================
@app.route('/admin/don-hang', methods=['GET', 'POST'])
def quan_ly_don_hang():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    # 1. XỬ LÝ LƯU CẬP NHẬT NHANH (Mã đơn và Tiền trả)
    if request.method == 'POST':
        don_id = request.form['don_id']
        trang_thai = request.form['trang_thai']
        tien_da_tra = request.form.get('tien_da_tra', 0)
        
        conn.execute('UPDATE don_hang SET trang_thai = ?, tien_da_tra = ? WHERE id = ?', 
                     (trang_thai, tien_da_tra, don_id))
        conn.commit()
        return redirect(url_for('quan_ly_don_hang'))

    # 2. LẤY THAM SỐ LỌC & TÌM KIẾM
    tu_khoa = request.args.get('tu_khoa', '') # Thêm ô tìm kiếm
    trang_thai_loc = request.args.get('trang_thai', '')
    sap_xep = request.args.get('sap_xep', 'moi_nhat')
    page = request.args.get('page', 1, type=int)
    per_page = 10 
    
    # Xây dựng câu lệnh điều kiện (Dùng WHERE 1=1 để dễ nối chuỗi)
    cau_lenh_base = ' FROM don_hang WHERE 1=1'
    dk = []
    
    if tu_khoa:
        cau_lenh_base += ' AND (ten_khach LIKE ? OR sdt LIKE ? OR id LIKE ?)'
        dk.extend([f'%{tu_khoa}%', f'%{tu_khoa}%', f'%{tu_khoa}%'])
        
    if trang_thai_loc:
        cau_lenh_base += ' AND trang_thai = ?'
        dk.append(trang_thai_loc)

    # --- 3. TÍNH TOÁN THỐNG KÊ (GIẢI QUYẾT LỖI GẠCH ĐỎ) ---
    # Tính Tổng doanh thu từ các đơn đã Hoàn thành
    total_rev = conn.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai = 'Hoàn thành'").fetchone()[0] or 0
    # Tính Tổng tiền nợ khách (Các đơn chưa hủy)
    total_debt = conn.execute("SELECT SUM(tong_tien - tien_da_tra) FROM don_hang WHERE trang_thai != 'Đã hủy'").fetchone()[0] or 0
    # Đếm số đơn chờ xử lý
    pending_count = conn.execute("SELECT COUNT(id) FROM don_hang WHERE trang_thai = 'Chờ xử lý'").fetchone()[0] or 0

    # Tính toán số trang cho phân trang
    tong_don = conn.execute('SELECT COUNT(id)' + cau_lenh_base, dk).fetchone()[0]
    tong_trang = (tong_don + per_page - 1) // per_page

    # 4. LẤY DỮ LIỆU PHÂN TRANG
    cau_lenh = 'SELECT *' + cau_lenh_base
    if sap_xep == 'moi_nhat': cau_lenh += ' ORDER BY id DESC'
    elif sap_xep == 'cu_nhat': cau_lenh += ' ORDER BY id ASC'
    elif sap_xep == 'tien_cao': cau_lenh += ' ORDER BY tong_tien DESC'
    
    cau_lenh += ' LIMIT ? OFFSET ?'
    dk.extend([per_page, (page - 1) * per_page])
    
    don_hangs = conn.execute(cau_lenh, dk).fetchall()
        # Kéo thêm chi tiết từng món đồ
    don_hangs_full = []
    for dh in don_hangs:
        dh_dict = dict(dh)
        # Truy vấn lấy các món trong đơn
        cac_mon = conn.execute('''
            SELECT c.*, s.ten, s.hinh_anh, s.kieu_hang, s.ngay_phat_hanh 
            FROM chi_tiet_don c 
            JOIN san_pham s ON c.san_pham_id = s.id 
            WHERE c.don_hang_id = ?
        ''', (dh['id'],)).fetchall()
        
        # ĐỔI TÊN Ở ĐÂY: Thay 'items' thành 'ds_mat_hang' để tránh trùng hàm hệ thống
        dh_dict['ds_mat_hang'] = cac_mon 
        don_hangs_full.append(dh_dict)

    conn.close()

    # 5. TRẢ VỀ TOÀN BỘ BIẾN CẦN THIẾT
    return render_template('quan_ly_don.html', 
                           don_hangs=don_hangs_full, 
                           trang_thai_chon=trang_thai_loc, 
                           sap_xep_chon=sap_xep,
                           tu_khoa=tu_khoa,
                           page=page, 
                           tong_trang=tong_trang,
                           total_rev=total_rev, 
                           total_debt=total_debt, 
                           pending_count=pending_count)

# ==================== 2. HỒ SƠ KHÁCH HÀNG (THỐNG KÊ CHI TIẾT) ====================
@app.route('/admin/khach-hang', methods=['GET', 'POST'])
def quan_ly_khach_hang():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    # ... (Giữ nguyên đoạn If request.method == 'POST' của sếp ở đây) ...
    if request.method == 'POST':
        kh_id = request.form.get('kh_id')
        mat_khau_nhap = request.form['mat_khau']
        if not mat_khau_nhap.startswith('scrypt:'):
            mat_khau_nhap = generate_password_hash(mat_khau_nhap)
        if kh_id: 
            conn.execute('UPDATE khach_hang SET ho_ten=?, tai_khoan=?, sdt=?, dia_chi=?, mat_khau=? WHERE id=?',
                        (request.form['ho_ten'], request.form['tai_khoan'], request.form['sdt'], request.form['dia_chi'], mat_khau_nhap, kh_id))
        else: 
            try:
                conn.execute('INSERT INTO khach_hang (ho_ten, tai_khoan, mat_khau, sdt, dia_chi) VALUES (?,?,?,?,?)',
                            (request.form['ho_ten'], request.form['tai_khoan'], mat_khau_nhap, request.form['sdt'], request.form['dia_chi']))
            except: pass
        conn.commit()
        return redirect(url_for('quan_ly_khach_hang'))

    tu_khoa = request.args.get('tu_khoa', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    query_count = "SELECT COUNT(*) FROM khach_hang k"
    query = '''
        SELECT k.*, COUNT(d.id) as so_don, IFNULL(SUM(d.tong_tien), 0) as tong_mua, IFNULL(SUM(d.tien_da_tra), 0) as da_tra
        FROM khach_hang k LEFT JOIN don_hang d ON k.id = d.khach_hang_id
    '''
    params = []; count_params = []
    
    if tu_khoa:
        where_clause = " WHERE k.ho_ten LIKE ? OR k.tai_khoan LIKE ? OR k.sdt LIKE ?"
        query_count += where_clause
        query += where_clause
        params = [f'%{tu_khoa}%', f'%{tu_khoa}%', f'%{tu_khoa}%']
        count_params = params.copy()
        
    tong_khach = conn.execute(query_count, count_params).fetchone()[0]
    tong_trang = (tong_khach + per_page - 1) // per_page
    
    query += " GROUP BY k.id ORDER BY k.id DESC LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    khachs = conn.execute(query, params).fetchall()
    conn.close()
    
    return render_template('quan_ly_khach.html', khachs=khachs, tu_khoa=tu_khoa, page=page, tong_trang=tong_trang)

    # ... (Giữ nguyên đoạn code SELECT danh sách khách hàng bên dưới) ...
    tu_khoa = request.args.get('tu_khoa', '')
    query = '''
        SELECT k.*, 
               COUNT(d.id) as so_don, 
               IFNULL(SUM(d.tong_tien), 0) as tong_mua, 
               IFNULL(SUM(d.tien_da_tra), 0) as da_tra
        FROM khach_hang k
        LEFT JOIN don_hang d ON k.id = d.khach_hang_id
    '''
    params = []
    if tu_khoa:
        query += " WHERE k.ho_ten LIKE ? OR k.tai_khoan LIKE ? OR k.sdt LIKE ?"
        params = [f'%{tu_khoa}%', f'%{tu_khoa}%', f'%{tu_khoa}%']
        
    query += " GROUP BY k.id ORDER BY k.id DESC"
    khachs = conn.execute(query, params).fetchall()
    conn.close()
    return render_template('quan_ly_khach.html', khachs=khachs, tu_khoa=tu_khoa)

@app.route('/admin/xoa-khach-hang/<int:id>')
def xoa_khach_hang(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    # Không cho phép tự xóa tài khoản admin đang đăng nhập hoặc chính admin gốc
    kh = conn.execute('SELECT vai_tro FROM khach_hang WHERE id = ?', (id,)).fetchone()
    if kh and kh['vai_tro'] == 'admin':
        conn.close()
        return "<script>alert('Sếp không thể xóa tài khoản Admin ở đây!'); window.location.href='/admin/khach-hang';</script>"
    
    conn.execute('DELETE FROM khach_hang WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('quan_ly_khach_hang'))

# ================= XEM HỒ SƠ CHI TIẾT 1 KHÁCH HÀNG =================
@app.route('/admin/khach-hang/<int:id>')
def chi_tiet_khach(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    # 1. Lấy thông tin cá nhân
    khach = conn.execute('SELECT * FROM khach_hang WHERE id = ?', (id,)).fetchone()
    
    # 2. Thống kê tài chính
    thong_ke = conn.execute('''
        SELECT COUNT(id) as so_don, SUM(tong_tien) as tong_mua, SUM(tien_da_tra) as tong_tra 
        FROM don_hang WHERE khach_hang_id = ?
    ''', (id,)).fetchone()
    
    # 3. Lịch sử mua hàng
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
    
    # Tính tiền khách trả mới
    tien_moi = dh['tien_da_tra'] + so_tien_nhap if hanh_dong == 'cong' else so_tien_nhap
    
    # Tự động gạt sang "Hoàn thành" nếu khách đã trả đủ
    if tien_moi >= dh['tong_tien']:
        trang_thai = 'Hoàn thành'
        
    conn.execute('UPDATE don_hang SET trang_thai=?, tien_da_tra=? WHERE id=?', 
                 (trang_thai, tien_moi, id))
    conn.commit(); conn.close()
    return redirect(url_for('quan_ly_don_hang'))

# ================= XÓA / HỦY ĐƠN HÀNG =================
# ================= HỦY ĐƠN HÀNG (GIỮ LẠI LỊCH SỬ) =================
@app.route('/admin/huy-don/<int:id>')
def huy_don(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    # Kiểm tra xem đơn đã hủy chưa (tránh cộng dồn kho nhiều lần)
    dh = conn.execute('SELECT trang_thai FROM don_hang WHERE id = ?', (id,)).fetchone()
    
    if dh and dh['trang_thai'] != 'Đã hủy':
        # 1. Lấy thông tin đồ trong đơn để HOÀN LẠI VÀO KHO
        items = conn.execute('SELECT san_pham_id, so_luong FROM chi_tiet_don WHERE don_hang_id = ?', (id,)).fetchall()
        for item in items:
            conn.execute('UPDATE san_pham SET so_luong = so_luong + ? WHERE id = ?', 
                         (item['so_luong'], item['san_pham_id']))
            
        # 2. CẬP NHẬT trạng thái thay vì xóa
        conn.execute('UPDATE don_hang SET trang_thai = "Đã hủy" WHERE id = ?', (id,))
        conn.commit()
        
    conn.close()
    return redirect(request.referrer or url_for('quan_ly_don_hang'))

# BÁO CÁO THỐNG KÊ CHUYÊN SÂU
@app.route('/admin/thong-ke')
def thong_ke():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    # 1. Thống kê tổng quan
    dt = conn.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai='Hoàn thành'").fetchone()[0] or 0
    sd = conn.execute("SELECT COUNT(*) FROM don_hang WHERE trang_thai='Chờ xử lý'").fetchone()[0] or 0
    
    # 2. Lấy dữ liệu 7 ngày gần nhất để vẽ biểu đồ
    ds_ngay = conn.execute('''
        SELECT DATE(ngay_dat) as ngay, SUM(tong_tien) as doanh_thu 
        FROM don_hang 
        WHERE trang_thai='Hoàn thành' 
        GROUP BY ngay 
        ORDER BY ngay DESC LIMIT 7
    ''').fetchall()
    
    # Sắp xếp lại dữ liệu theo đúng chiều thời gian để biểu đồ không bị ngược
    chart_labels = [row['ngay'] for row in reversed(ds_ngay)]
    chart_data = [row['doanh_thu'] for row in reversed(ds_ngay)]

    # 3. Lấy Top 5 mô hình bán chạy nhất
    top_products = conn.execute('''
        SELECT s.ten, SUM(c.so_luong) as total_qty
        FROM chi_tiet_don c
        JOIN san_pham s ON c.san_pham_id = s.id
        JOIN don_hang d ON c.don_hang_id = d.id
        WHERE d.trang_thai = 'Hoàn thành'
        GROUP BY s.id 
        ORDER BY total_qty DESC LIMIT 5
    ''').fetchall()

    conn.close()
    
    # TRUYỀN ĐỦ BIẾN RA HTML - Nếu thiếu một trong các biến này là lỗi ngay sếp nhé
    return render_template('thong_ke.html', 
                           doanh_thu=dt, 
                           so_don_moi=sd, 
                           tien_loi=dt*0.05, 
                           thue_vat=dt*0.03,
                           labels=json.dumps(chart_labels), # Biến cho biểu đồ
                           values=json.dumps(chart_data),   # Biến cho biểu đồ
                           top_sps=top_products)           # Biến cho danh sách Top 5

# Xóa Danh mục
@app.route('/xoa-danh-muc/<int:id>', methods=['POST'])
def xoa_danh_muc(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    conn.execute('DELETE FROM danh_muc WHERE id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('quan_ly_danh_muc'))

# Xóa Hãng
@app.route('/xoa-hang/<int:id>', methods=['POST'])
def xoa_hang(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    conn.execute('DELETE FROM hang_sx_list WHERE id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('quan_ly_hang_sx'))

# Xóa Nguồn (Bí mật)
@app.route('/xoa-nguon/<int:id>', methods=['POST'])
def xoa_nguon(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    conn.execute('DELETE FROM nguon_nhap WHERE id=?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('quan_ly_nguon_nhap'))

@app.route('/admin/chi-tiet-don/<int:id>')
def chi_tiet_don_json(id):
    if 'admin_id' not in session: 
        return jsonify({"error": "Unauthorized"}), 401
    
    conn = ket_noi_db()
    # Ép kiểu dữ liệu trả về để tránh lỗi 500
    conn.row_factory = sqlite3.Row 
    
    row = conn.execute('SELECT * FROM don_hang WHERE id = ?', (id,)).fetchone()
    
    if not row:
        conn.close()
        return jsonify({"error": "Không tìm thấy đơn"}), 404
        
    dh = dict(row) # Chuyển dòng dữ liệu thành từ điển
    
    items = conn.execute('''
        SELECT c.*, s.ten, s.hinh_anh 
        FROM chi_tiet_don c 
        JOIN san_pham s ON c.san_pham_id = s.id 
        WHERE c.don_hang_id = ?
    ''', (id,)).fetchall()
    
    conn.close()
    
    # Sử dụng đúng tên biến ds_mat_hang đã thống nhất ở Frontend
    return jsonify({
        "id": dh['id'],
        "ten_khach": dh['ten_khach'],
        "sdt": dh['sdt'],
        "dia_chi": dh['dia_chi'],
        "trang_thai": dh['trang_thai'],
        "tong_tien": dh['tong_tien'],
        "tien_da_tra": dh['tien_da_tra'],
        "ds_mat_hang": [{"ten": i['ten'], "so_luong": i['so_luong'], "gia": i['gia'], "hinh_anh": i['hinh_anh']} for i in items]
    })

# ================= XEM VÀ CHỈNH SỬA ĐƠN HÀNG =================
@app.route('/admin/don-hang/<int:id>', methods=['GET', 'POST'])
def xem_sua_don_hang(id):
    # Cho phép cả Admin và Khách đã đăng nhập
    khach_id = session.get('khach_id')
    admin_id = session.get('admin_id')
    if not admin_id and not khach_id: return redirect(url_for('dang_nhap'))

    conn = ket_noi_db()
    dh = conn.execute('SELECT * FROM don_hang WHERE id = ?', (id,)).fetchone()
    if not dh: 
        conn.close(); return "Không tìm thấy đơn hàng!", 404

    # BẢO MẬT: Nếu là khách thì CHỈ ĐƯỢC XEM đơn của chính mình
    if not admin_id and dh['khach_hang_id'] != khach_id:
        conn.close(); return "<script>alert('Sếp không có quyền xem đơn của người khác!'); window.history.back();</script>"

    # NẾU LÀ ADMIN BẤM NÚT LƯU CẬP NHẬT
    if request.method == 'POST' and admin_id:
        trang_thai = request.form['trang_thai']
        tien_da_tra = request.form.get('tien_da_tra', 0)
        conn.execute('UPDATE don_hang SET trang_thai = ?, tien_da_tra = ? WHERE id = ?', 
                     (trang_thai, tien_da_tra, id))
        conn.commit()
        conn.close()
        return redirect(url_for('xem_sua_don_hang', id=id))

    # Kéo dữ liệu món hàng
    items = conn.execute('''
        SELECT c.*, s.ten, s.hinh_anh, s.hang_sx 
        FROM chi_tiet_don c 
        JOIN san_pham s ON c.san_pham_id = s.id 
        WHERE c.don_hang_id = ?
    ''', (id,)).fetchall()
    conn.close()

    return render_template('chi_tiet_don.html', dh=dh, items=items)

# ================= IN HÓA ĐƠN =================
@app.route('/admin/in-hoa-don/<int:id>')
def in_hoa_don(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    dh = conn.execute('SELECT * FROM don_hang WHERE id = ?', (id,)).fetchone()
    items = conn.execute('''
        SELECT c.*, s.ten 
        FROM chi_tiet_don c 
        JOIN san_pham s ON c.san_pham_id = s.id 
        WHERE c.don_hang_id = ?
    ''', (id,)).fetchall()
    conn.close()
    
    return render_template('in_hoa_don.html', dh=dh, items=items)

# ================= HỒ SƠ KHÁCH HÀNG & LỊCH SỬ ĐƠN (CÁ NHÂN) =================
@app.route('/ho-so')
def ho_so_khach():
    # Kiểm tra xem có khách đăng nhập chưa
    khach_id = session.get('khach_id')
    if not khach_id:
        # Nếu là Admin đang soi web thì đẩy thẳng về trang Quản lý khách của Admin
        if session.get('admin_id'):
            return redirect(url_for('quan_ly_khach_hang')) 
        return redirect(url_for('dang_nhap'))
        
    conn = ket_noi_db()
    
    # 1. Lấy thông tin cá nhân của khách đó
    khach = conn.execute('SELECT * FROM khach_hang WHERE id = ?', (khach_id,)).fetchone()
    
    # 2. Lấy danh sách lịch sử đơn hàng của họ
    don_hangs = conn.execute('SELECT * FROM don_hang WHERE khach_hang_id = ? ORDER BY id DESC', (khach_id,)).fetchall()
    
    # 3. Lấy thêm hình ảnh, chi tiết đồ trong từng đơn để khách xem cho trực quan
    don_hangs_full = []
    for dh in don_hangs:
        dh_dict = dict(dh)
        items = conn.execute('''
            SELECT c.*, s.ten, s.hinh_anh 
            FROM chi_tiet_don c 
            JOIN san_pham s ON c.san_pham_id = s.id 
            WHERE c.don_hang_id = ?
        ''', (dh['id'],)).fetchall()
        dh_dict['items'] = items
        don_hangs_full.append(dh_dict)
        
    conn.close()
    return render_template('ho_so.html', khach=khach, don_hangs=don_hangs_full)
# ================= TRANG ADMIN: CÀI ĐẶT GIAO DIỆN =================

@app.route('/admin/cai-dat', methods=['GET', 'POST'])
def cai_dat_giao_dien():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    settings = get_settings()
    
    if request.method == 'POST':
        def xu_ly_anh(ten_input, file_cu):
            # Nếu sếp bấm nút xóa, JavaScript sẽ gửi giá trị rỗng lên đây
            is_delete = request.form.get(f'is_delete_{ten_input}') == 'true'
            if is_delete: return "" 
            
            file = request.files.get(ten_input)
            if file and file.filename != '':
                filename = secure_filename(file.filename)
                filepath = os.path.join('static/uploads', filename)
                file.save(filepath)
                return '/' + filepath
            return file_cu

        # ... (đoạn trên giữ nguyên)
        new_settings = {
            "ten_web": request.form.get('ten_web', settings.get('ten_web')),
            "mau_chu_dao": request.form.get('mau_chu_dao', settings.get('mau_chu_dao')),
            "thong_tin_footer": request.form.get('thong_tin_footer', ''),
            "dia_chi": request.form.get('dia_chi', ''),
            "dien_thoai": request.form.get('dien_thoai', ''),
            "email": request.form.get('email', ''),
            "link_fb": request.form.get('link_fb', '#'),
            "link_ig": request.form.get('link_ig', '#'),
            "link_yt": request.form.get('link_yt', '#'),
            "logo_url": xu_ly_anh('logo_file', settings.get('logo_url')),
            "banner_1": xu_ly_anh('banner_1_file', settings.get('banner_1')),
            "banner_2": xu_ly_anh('banner_2_file', settings.get('banner_2')),
            
            # CHỈ CẦN THÊM 4 DÒNG NÀY ĐỂ LƯU LẠI KHI BẤM NÚT "LƯU CÀI ĐẶT"
            "cs_cua_hang": request.form.get('cs_cua_hang', settings.get('cs_cua_hang', '')),
            "cs_doi_tra": request.form.get('cs_doi_tra', settings.get('cs_doi_tra', '')),
            "cs_van_chuyen": request.form.get('cs_van_chuyen', settings.get('cs_van_chuyen', '')),
            "hd_mua_hang": request.form.get('hd_mua_hang', settings.get('hd_mua_hang', '')),
            "video_trang_chu": request.form.get('video_trang_chu', settings.get('video_trang_chu', 'HGCsAcFzaFw'))
        }
        save_settings(new_settings)
        return redirect(url_for('cai_dat_giao_dien'))
    return render_template('cai_dat.html', settings=settings)

# ================= TRANG KHÁCH: TẤT CẢ SẢN PHẨM =================
# ================= TRANG KHÁCH: TẤT CẢ SẢN PHẨM (CÓ TÌM THEO TÊN) =================
# ================= TRANG KHÁCH: TẤT CẢ SẢN PHẨM (CẬP NHẬT BỘ LỌC TỒN KHO) =================
# Thay thế toàn bộ hàm này trong app.py
@app.route('/san-pham')
def tat_ca_san_pham():
    conn = ket_noi_db()
    
    tu_khoa = request.args.get('tu_khoa', '')
    danh_muc_loc = request.args.get('danh_muc', '')
    hang_loc = request.args.get('hang_sx', '')
    kieu_loc = request.args.get('kieu_hang', '')
    ton_kho = request.args.get('ton_kho', '') 
    sap_xep = request.args.get('sap_xep', 'moi_nhat') # <-- BIẾN MỚI
    
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
    if ton_kho == 'con_hang':
        cau_lenh_base += ' AND so_luong > 0'
    elif ton_kho == 'het_hang':
        cau_lenh_base += ' AND so_luong <= 0'
        
    tong_sp = conn.execute('SELECT COUNT(id)' + cau_lenh_base, dk).fetchone()[0]
    tong_trang = (tong_sp + per_page - 1) // per_page
    
    # LOGIC SẮP XẾP MỚI
    order_by = ' ORDER BY id DESC'
    if sap_xep == 'gia_tang': order_by = ' ORDER BY gia_ban ASC'
    elif sap_xep == 'gia_giam': order_by = ' ORDER BY gia_ban DESC'
    
    cau_lenh = 'SELECT *' + cau_lenh_base + order_by + ' LIMIT ? OFFSET ?'
    dk.extend([per_page, (page - 1) * per_page])
    
    san_phams = conn.execute(cau_lenh, dk).fetchall()
    danh_mucs = conn.execute('SELECT DISTINCT the_loai as ten_danh_muc FROM san_pham').fetchall()
    hangs = conn.execute('SELECT DISTINCT hang_sx as ten_hang FROM san_pham').fetchall()
    conn.close()
    
    return render_template('tat_ca_san_pham.html', san_phams=san_phams, danh_mucs=danh_mucs, hangs=hangs, 
                           page=page, tong_trang=tong_trang, 
                           dm_chon=danh_muc_loc, hang_chon=hang_loc, kieu_chon=kieu_loc, 
                           tu_khoa=tu_khoa, ton_kho_chon=ton_kho, sap_xep_chon=sap_xep)

# ================= XỬ LÝ THANH TOÁN & ĐẶT HÀNG =================
@app.route('/thanh-toan', methods=['GET', 'POST'])
def thanh_toan():
    gio_hang = session.get('gio_hang', [])
    if not gio_hang:
        return redirect(url_for('xem_gio_hang')) # Giỏ trống thì đuổi về
        
    tong_tien = sum(item['gia'] * item['so_luong'] for item in gio_hang)
    conn = ket_noi_db()
    # Lấy danh sách khách hàng để hiện vào ô chọn
    danh_sach_khach = conn.execute('SELECT id, ho_ten, sdt FROM khach_hang ORDER BY ho_ten ASC').fetchall()
    conn.close()
    # Nếu khách bấm Nút ĐẶT HÀNG
    if request.method == 'POST':
        ten_khach = request.form['ten']
        sdt = request.form['sdt']
        dia_chi = request.form['dia_chi']
        khach_id = session.get('khach_id', 0) # Bằng 0 nếu là khách vãng lai
        email_khach = request.form.get('email', '')
        
        conn = ket_noi_db()
        cur = conn.cursor()
        
        # 1. Tạo Đơn hàng chính
        cur.execute('INSERT INTO don_hang (khach_hang_id, ten_khach, sdt, dia_chi, tong_tien, trang_thai) VALUES (?, ?, ?, ?, ?, ?)', 
                    (khach_id, ten_khach, sdt, dia_chi, tong_tien, 'Chờ xử lý'))
        don_id = cur.lastrowid
        
        # 2. Tạo Chi tiết đơn & Trừ tồn kho
        for item in gio_hang:
            cur.execute('INSERT INTO chi_tiet_don (don_hang_id, san_pham_id, so_luong, gia) VALUES (?, ?, ?, ?)', 
                        (don_id, item['id'], item['so_luong'], item['gia']))
            # Trừ Tồn kho (so_luong) đi, giữ nguyên (so_luong_nhap)
            cur.execute('UPDATE san_pham SET so_luong = so_luong - ? WHERE id = ?', (item['so_luong'], item['id']))
            
        # GỌI HÀM GỬI MAIL
        gui_email_thong_bao(don_id, ten_khach, email_khach, tong_tien, gio_hang)

        conn.commit()
        conn.close()
        
        # 3. Xóa sạch giỏ hàng
        session['gio_hang'] = []
        session.modified = True
        
        flash(f'Tuyệt vời! Sếp đã đặt hàng thành công. Mã đơn: #{don_id}', 'success')
        return redirect(url_for('index'))

    # Nếu truy cập bình thường thì mở giao diện Thanh toán
    return render_template('thanh_toan.html', 
                       gio_hang=gio_hang, 
                       tong_tien=tong_tien, 
                       khachs=danh_sach_khach) # Thêm khachs vào đây sếp nhé

# 2. THÊM ROUTE MỚI ĐỂ LẤY THÔNG TIN KHÁCH KHI CHỌN
@app.route('/api/get-khach-info/<int:id>')
def get_khach_info(id):
    conn = ket_noi_db()
    kh = conn.execute('SELECT ho_ten, sdt, dia_chi FROM khach_hang WHERE id = ?', (id,)).fetchone()
    conn.close()
    if kh:
        return {
            "ho_ten": kh['ho_ten'],
            "sdt": kh['sdt'],
            "dia_chi": kh['dia_chi']
        }
    return {"error": "Không tìm thấy"}, 404

# API TÌM KIẾM SẢN PHẨM NHANH (BẢN NÂNG CẤP)
@app.route('/api/search-products')
def search_products_api():
    tu_khoa = request.args.get('tu_khoa', '').strip()
    if len(tu_khoa) < 1: return jsonify([])
        
    conn = ket_noi_db()
    # Kéo thêm trường kieu_hang để hiện Badge
    query = "SELECT id, ten, hinh_anh, gia_ban, kieu_hang FROM san_pham WHERE ten LIKE ? LIMIT 5"
    sps = conn.execute(query, (f'%{tu_khoa}%',)).fetchall()
    conn.close()
    
    ket_qua = []
    for sp in sps:
        ket_qua.append({
            "id": sp['id'],
            "ten": sp['ten'],
            "hinh_anh": sp['hinh_anh'],
            "gia": "{:,.0f}".format(sp['gia_ban']),
            "status": sp['kieu_hang'] # 'Co san' hoặc 'Pre-order'
        })
    return jsonify(ket_qua)

if __name__ == '__main__':
    Timer(1.5, lambda: webbrowser.open_new('http://127.0.0.1:5000/')).start()
    app.run(debug=True)