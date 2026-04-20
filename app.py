import os, webbrowser, sqlite3
from threading import Timer
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'wolves_master_system_ultimate_v7'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
        conn.execute("INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, vai_tro) VALUES ('admin', '123', 'Quản trị viên', 'admin')")
    conn.commit(); conn.close()

tao_bang()

# --- HÀM ĐẾM SỐ LƯỢNG GIỎ HÀNG TRÊN THANH MENU ---
@app.context_processor
def inject_data():
    gio_hang = session.get('gio_hang', [])
    so_luong = 0
    
    # Tính tổng số lượng từ danh sách giỏ hàng mới
    if isinstance(gio_hang, list):
        for item in gio_hang:
            if isinstance(item, dict) and 'so_luong' in item:
                so_luong += item['so_luong']

    return dict(
        so_luong_gio_hang=so_luong, 
        is_admin='admin_id' in session, 
        is_khach='khach_id' in session, 
        khach_ten=session.get('khach_ten', '')
    )

# ==================== TRANG CHỦ & ĐĂNG NHẬP ====================

@app.route('/')
def trang_chu():
    conn = ket_noi_db()
    dms = conn.execute('SELECT * FROM danh_muc').fetchall()
    tk, tl, kh = request.args.get('tim_kiem',''), request.args.get('the_loai',''), request.args.get('kieu_hang','')
    q = "SELECT * FROM san_pham WHERE 1=1"
    p = []
    if tk: q += " AND ten LIKE ?"; p.append(f"%{tk}%")
    if tl: q += " AND the_loai = ?"; p.append(tl)
    if kh: q += " AND kieu_hang = ?"; p.append(kh)
    sps = conn.execute(q + " ORDER BY id DESC", p).fetchall()
    conn.close()
    return render_template('index.html', san_phams=sps, danh_mucs=dms, tu_khoa=tk, the_loai_chon=tl, kieu_hang_chon=kh)

@app.route('/san-pham/<int:id>')
def chi_tiet(id):
    conn = ket_noi_db()
    sp = conn.execute('SELECT * FROM san_pham WHERE id=?', (id,)).fetchone()
    if not sp:
        conn.close(); return "Sản phẩm không tồn tại!", 404
        
    anh_phu = conn.execute('SELECT du_ong_dan FROM hinh_anh_sp WHERE san_pham_id=?', (id,)).fetchall()
    
    # Lấy Sản phẩm liên quan (Cùng hãng sản xuất, loại trừ sản phẩm hiện tại, lấy tối đa 4 cái)
    sp_lien_quan = conn.execute('SELECT * FROM san_pham WHERE hang_sx=? AND id!=? LIMIT 4', (sp['hang_sx'], id)).fetchall()
    
    conn.close()
    return render_template('chi_tiet.html', sp=sp, anh_phu=anh_phu, sp_lien_quan=sp_lien_quan)

@app.route('/dang-nhap', methods=['GET', 'POST'])
def dang_nhap():
    if request.method == 'POST':
        conn = ket_noi_db()
        u = conn.execute('SELECT * FROM khach_hang WHERE tai_khoan=? AND mat_khau=?', (request.form['tai_khoan'], request.form['mat_khau'])).fetchone()
        conn.close()
        if u:
            session.clear()
            if u['vai_tro'] == 'admin': session['admin_id'] = u['id']
            else: session['khach_id'] = u['id']
            session['khach_ten'] = u['ho_ten']
            return redirect(url_for('trang_chu'))
        return "Sai tài khoản hoặc mật khẩu!"
    return render_template('dang_nhap_chung.html')

@app.route('/dang-ky', methods=['GET', 'POST'])
def dang_ky():
    if request.method == 'POST':
        conn = ket_noi_db()
        try:
            conn.execute('INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, sdt, dia_chi) VALUES (?,?,?,?,?)', 
                         (request.form['tai_khoan'], request.form['mat_khau'], request.form['ho_ten'], request.form['sdt'], request.form['dia_chi']))
            conn.commit()
            return redirect(url_for('dang_nhap'))
        except: return "Lỗi: Tài khoản đã tồn tại!"
        finally: conn.close()
    return render_template('dang_ky_khach.html')

@app.route('/dang-xuat')
def dang_xuat():
    session.clear()
    return redirect(url_for('trang_chu'))

# ==================== GIỎ HÀNG & ĐẶT HÀNG ====================

# 1. THÊM VÀO GIỎ HÀNG
@app.route('/them-vao-gio/<int:id>')
def them_vao_gio(id):
    conn = ket_noi_db()
    sp = conn.execute('SELECT id, ten, gia_ban, hinh_anh, so_luong, kieu_hang FROM san_pham WHERE id=?', (id,)).fetchone()
    conn.close()
    
    if not sp: return redirect(url_for('index'))

    gio = session.get('gio_hang', [])
    if isinstance(gio, dict): gio = []
    elif isinstance(gio, list) and len(gio) > 0 and not isinstance(gio[0], dict): gio = []

    # Xóa các báo lỗi cũ (nếu có) để làm mới
    for item in gio:
        item.pop('error', None)

    found = False
    for item in gio:
        if item['id'] == id:
            if item['so_luong'] < sp['so_luong']:
                item['so_luong'] += 1
            else:
                item['error'] = f"Chỉ còn {sp['so_luong']} cái!" # Gắn lỗi vào đúng SP này
            found = True
            break
    
    if not found:
        if sp['kieu_hang'] != 'Pre-order' and sp['so_luong'] <= 0:
            # Hết hàng từ đầu thì cho vào giỏ với thông báo đỏ
            gio.append({'id': sp['id'], 'ten': sp['ten'], 'gia': sp['gia_ban'], 'hinh_anh': sp['hinh_anh'], 'so_luong': 1, 'error': 'Đã hết hàng!'})
        else:
            gio.append({'id': sp['id'], 'ten': sp['ten'], 'gia': sp['gia_ban'], 'hinh_anh': sp['hinh_anh'], 'so_luong': 1})

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
@app.route('/cap-nhat-gio/<int:id>/<hanh_dong>')
def cap_nhat_gio(id, hanh_dong):
    gio = session.get('gio_hang', [])
    conn = ket_noi_db()
    sp = conn.execute('SELECT so_luong, kieu_hang FROM san_pham WHERE id=?', (id,)).fetchone()
    conn.close()
    
    for item in gio:
        if item['id'] == id:
            item.pop('error', None) # Xóa dòng chữ đỏ cũ đi khi thao tác lại
            
            if hanh_dong == 'tang':
                if sp and item['so_luong'] < sp['so_luong']:
                    item['so_luong'] += 1
                else:
                    item['error'] = f"Tối đa {sp['so_luong']} món!" # Báo lỗi nếu bấm quá
            elif hanh_dong == 'giam' and item['so_luong'] > 1:
                item['so_luong'] -= 1
            break
            
    session['gio_hang'] = gio
    session.modified = True
    return redirect(url_for('xem_gio_hang'))

# 4. XÓA KHỎI GIỎ
@app.route('/xoa-khoi-gio/<int:id>')
def xoa_khoi_gio(id):
    gio = session.get('gio_hang', [])
    # Dùng list comprehension để giữ lại những SP có ID khác với ID muốn xóa
    gio = [item for item in gio if item['id'] != id]
    
    session['gio_hang'] = gio
    session.modified = True
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
    conn = ket_noi_db(); sps = conn.execute('SELECT * FROM san_pham').fetchall(); conn.close()
    return render_template('admin.html', san_phams=sps)

@app.route('/them', methods=['GET', 'POST'])
def them_san_pham():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    if request.method == 'POST':
        f = request.files['hinh_anh']
        img = '/static/uploads/' + secure_filename(f.filename) if f and f.filename != '' else ''
        if img: f.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename)))
        cur = conn.cursor()
        
        # ĐÃ SỬA: Thêm cột so_luong_nhap, thêm một dấu ? vào VALUES, và lưu request.form['so_luong'] 2 lần
        cur.execute('''INSERT INTO san_pham (ten, the_loai, hang_sx, gia_nhap, gia_ban, so_luong, so_luong_nhap, hinh_anh, mo_ta, kieu_hang, tien_coc, ngay_phat_hanh, nguon_nhap_id, tien_da_tra_nguon, trang_thai_nhap, ngay_du_kien_ve) 
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                    (request.form['ten'], request.form['the_loai'], request.form['hang_sx'], 
                     float(request.form['gia_nhap']), float(request.form['gia_ban']), 
                     int(request.form['so_luong']), int(request.form['so_luong']), # <-- Bí quyết nhân đôi nằm ở đây
                     img, request.form['mo_ta'], request.form['kieu_hang'], 
                     float(request.form.get('tien_coc', 0)), request.form.get('ngay_phat_hanh', ''), 
                     request.form.get('nguon_nhap_id'), float(request.form.get('tien_da_tra_nguon', 0)), 
                     request.form.get('trang_thai_nhap', 'Còn nợ'), request.form.get('ngay_ve', '')))
        
        sid = cur.lastrowid
        
        # Lưu ảnh phụ
        for pf in request.files.getlist('hinh_anh_phu'):
            if pf and pf.filename != '':
                ten_file = secure_filename(pf.filename)
                pf.save(os.path.join(app.config['UPLOAD_FOLDER'], ten_file))
                conn.execute('INSERT INTO hinh_anh_sp (san_pham_id, du_ong_dan) VALUES (?,?)', (sid, '/static/uploads/'+ten_file))
        
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
        conn.execute('''UPDATE san_pham SET ten=?, the_loai=?, hang_sx=?, gia_nhap=?, gia_ban=?, so_luong=?, mo_ta=?, kieu_hang=?, tien_coc=?, ngay_phat_hanh=?, ngay_du_kien_ve=? WHERE id=?''', 
            (request.form['ten'], request.form['the_loai'], request.form['hang_sx'], float(request.form['gia_nhap']), float(request.form['gia_ban']), int(request.form['so_luong']), request.form['mo_ta'], request.form['kieu_hang'], float(request.form.get('tien_coc', 0)), request.form.get('ngay_phat_hanh', ''), request.form.get('ngay_ve', ''), id))
        conn.commit(); conn.close(); return redirect(url_for('admin'))
    sp = conn.execute('SELECT * FROM san_pham WHERE id=?', (id,)).fetchone()
    dms = conn.execute('SELECT * FROM danh_muc').fetchall()
    hgs = conn.execute('SELECT * FROM hang_sx_list').fetchall()
    conn.close()
    return render_template('sua.html', sp=sp, danh_mucs=dms, hangs=hgs)

@app.route('/xoa/<int:id>', methods=['POST'])
def xoa_san_pham(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    # KIỂM TRA KHÓA AN TOÀN: Xem sản phẩm này có đang nằm trong đơn hàng nào không
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

    # Nếu an toàn (Không ai đặt, hoặc đơn đã xong/hủy), tiến hành xóa
    conn.execute('DELETE FROM san_pham WHERE id=?', (id,))
    # Xóa luôn ảnh phụ cho nhẹ server
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
    nguon_id = request.args.get('nguon_id', '')
    kieu_hang = request.args.get('kieu_hang', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    
    query = "SELECT sp.*, n.ten_nguon FROM san_pham sp LEFT JOIN nguon_nhap n ON sp.nguon_nhap_id = n.id WHERE 1=1"
    params = []
    
    if nguon_id:
        query += " AND sp.nguon_nhap_id = ?"; params.append(nguon_id)
    if kieu_hang:
        query += " AND sp.kieu_hang = ?"; params.append(kieu_hang)
        
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
    return render_template('cong_no_nguon.html', items=items, nguons=nguons, tong_no=tong_no, 
                           current_page=page, total_pages=total_pages, nguon_chon=nguon_id, kieu_chon=kieu_hang)

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
@app.route('/admin/don-hang')
def quan_ly_don_hang():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    
    trang_thai_loc = request.args.get('trang_thai', '')
    sap_xep = request.args.get('sap_xep', 'moi_nhat')
    page = request.args.get('page', 1, type=int)
    per_page = 10 # 10 đơn 1 trang
    offset = (page - 1) * per_page
    
    query = "SELECT * FROM don_hang WHERE 1=1"
    params = []
    
    # --- ĐOẠN LOGIC MỚI BỔ SUNG ---
    if trang_thai_loc:
        query += " AND trang_thai = ?"; params.append(trang_thai_loc)
    else:
        # Nếu sếp không lọc gì cụ thể, mặc định ẨN hết các đơn Đã hủy cho sạch trang
        query += " AND trang_thai != 'Đã hủy'"
    # -----------------------------
        
    # Sắp xếp theo tên khách và ngày tháng
    if sap_xep == 'moi_nhat': query += " ORDER BY id DESC"
    elif sap_xep == 'cu_nhat': query += " ORDER BY id ASC"
    elif sap_xep == 'tien_cao': query += " ORDER BY tong_tien DESC"
    elif sap_xep == 'ten_az': query += " ORDER BY ten_khach ASC"
    elif sap_xep == 'ten_za': query += " ORDER BY ten_khach DESC"
        
    # Phân trang
    total_items = conn.execute("SELECT COUNT(*) FROM (" + query + ")", params).fetchone()[0]
    total_pages = (total_items + per_page - 1) // per_page
    
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    dhs = conn.execute(query, params).fetchall()
    
    # Kéo thêm Ngày về và Ngày phát hành từ bảng sản phẩm
    don_hangs_full = []
    for dh in dhs:
        dh_dict = dict(dh)
        chi_tiet = conn.execute('''
            SELECT c.*, s.ten, s.ngay_phat_hanh, s.ngay_du_kien_ve, s.kieu_hang, s.hinh_anh 
            FROM chi_tiet_don c 
            JOIN san_pham s ON c.san_pham_id = s.id 
            WHERE c.don_hang_id = ?
        ''', (dh['id'],)).fetchall()
        dh_dict['chi_tiet'] = chi_tiet
        don_hangs_full.append(dh_dict)
        
    conn.close()
    return render_template('quan_ly_don.html', don_hangs=don_hangs_full, 
                           trang_thai_chon=trang_thai_loc, sap_xep_chon=sap_xep,
                           current_page=page, total_pages=total_pages)

# ==================== 2. HỒ SƠ KHÁCH HÀNG (THỐNG KÊ CHI TIẾT) ====================
# ================= QUẢN LÝ DANH SÁCH KHÁCH HÀNG (TRANG TỔNG) =================
@app.route('/admin/khach-hang', methods=['GET', 'POST'])
def quan_ly_khach_hang():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    # XỬ LÝ KHI BẤM NÚT TẠO KHÁCH HÀNG MỚI
    if request.method == 'POST':
        ho_ten = request.form['ho_ten']
        tai_khoan = request.form['tai_khoan']
        mat_khau = request.form['mat_khau']
        sdt = request.form['sdt']
        dia_chi = request.form['dia_chi']
        
        try:
            conn.execute('INSERT INTO khach_hang (ho_ten, tai_khoan, mat_khau, sdt, dia_chi) VALUES (?,?,?,?,?)',
                        (ho_ten, tai_khoan, mat_khau, sdt, dia_chi))
            conn.commit()
        except:
            pass # Tránh lỗi nếu trùng tài khoản
            
    # LẤY DANH SÁCH HIỂN THỊ
    khachs = conn.execute('''
        SELECT k.id, k.ho_ten, k.sdt, k.tai_khoan, 
               COUNT(d.id) as so_don, 
               IFNULL(SUM(d.tong_tien), 0) as tong_mua, 
               IFNULL(SUM(d.tien_da_tra), 0) as da_tra
        FROM khach_hang k
        LEFT JOIN don_hang d ON k.id = d.khach_hang_id
        GROUP BY k.id
        ORDER BY k.id DESC
    ''').fetchall()
    
    conn.close()
    return render_template('quan_ly_khach.html', khachs=khachs)


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

# --- TÍNH NĂNG HỦY ĐƠN VÀ HOÀN TRẢ TỒN KHO ---
@app.route('/admin/huy-don/<int:id>', methods=['POST'])
def huy_don_hang(id):
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    
    # 1. Kiểm tra xem đơn này đã hủy chưa (tránh lỗi bấm 2 lần bị cộng dồn kho)
    dh = conn.execute('SELECT trang_thai FROM don_hang WHERE id=?', (id,)).fetchone()
    
    if dh and dh['trang_thai'] != 'Đã hủy':
        # 2. Cập nhật trạng thái thành Đã hủy
        conn.execute("UPDATE don_hang SET trang_thai = 'Đã hủy' WHERE id = ?", (id,))
        
        # 3. Hoàn trả lại Tồn kho cho từng sản phẩm trong đơn
        chi_tiet = conn.execute('SELECT san_pham_id, so_luong FROM chi_tiet_don WHERE don_hang_id=?', (id,)).fetchall()
        for ct in chi_tiet:
            # Cộng lại số lượng vào bảng san_pham
            conn.execute('UPDATE san_pham SET so_luong = so_luong + ? WHERE id = ?', (ct['so_luong'], ct['san_pham_id']))
            
        conn.commit()
        
    conn.close()
    return redirect(url_for('quan_ly_don_hang'))

@app.route('/admin/thong-ke')
def thong_ke():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db()
    dt = conn.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai='Hoàn thành'").fetchone()[0] or 0
    sd = conn.execute("SELECT COUNT(*) FROM don_hang WHERE trang_thai='Chờ xử lý'").fetchone()[0]
    conn.close()
    return render_template('thong_ke.html', doanh_thu=dt, so_don_moi=sd, tien_loi=dt*0.3, thue_vat=dt*0.1)
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

# ================= XỬ LÝ THANH TOÁN & ĐẶT HÀNG =================
@app.route('/thanh-toan', methods=['GET', 'POST'])
def thanh_toan():
    gio_hang = session.get('gio_hang', [])
    if not gio_hang:
        return redirect(url_for('xem_gio_hang')) # Giỏ trống thì đuổi về
        
    tong_tien = sum(item['gia'] * item['so_luong'] for item in gio_hang)
    
    # Nếu khách bấm Nút ĐẶT HÀNG
    if request.method == 'POST':
        ten_khach = request.form['ten']
        sdt = request.form['sdt']
        dia_chi = request.form['dia_chi']
        khach_id = session.get('khach_id', 0) # Bằng 0 nếu là khách vãng lai
        
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
            
        conn.commit()
        conn.close()
        
        # 3. Xóa sạch giỏ hàng
        session['gio_hang'] = []
        session.modified = True
        
        # Trả về trang thông báo thành công
        return f"<script>alert('Tuyệt vời! Sếp đã đặt hàng thành công. Mã đơn: #{don_id}'); window.location.href='/';</script>"

    # Nếu truy cập bình thường thì mở giao diện Thanh toán
    return render_template('thanh_toan.html', gio_hang=gio_hang, tong_tien=tong_tien)

if __name__ == '__main__':
    Timer(1.5, lambda: webbrowser.open_new('http://127.0.0.1:5000/')).start()
    app.run(debug=True)