import os
import webbrowser
from threading import Timer
from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'he_thong_ban_hang_doc_quyen' 
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# 1. ĐỔI SANG DATABASE V4
def ket_noi_db():
    conn = sqlite3.connect('database_v4.db')
    conn.row_factory = sqlite3.Row
    return conn

def tao_bang_moi():
    conn = ket_noi_db()
    conn.execute('''CREATE TABLE IF NOT EXISTS san_pham (id INTEGER PRIMARY KEY AUTOINCREMENT, ten TEXT, the_loai TEXT, hang_sx TEXT, gia_nhap REAL, gia_ban REAL, so_luong INTEGER, hinh_anh TEXT, mo_ta TEXT, kieu_hang TEXT DEFAULT 'Co san', tien_coc REAL DEFAULT 0, ngay_phat_hanh TEXT)''')
    conn.execute('CREATE TABLE IF NOT EXISTS danh_muc (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_danh_muc TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS hinh_anh_sp (id INTEGER PRIMARY KEY AUTOINCREMENT, san_pham_id INTEGER, du_ong_dan TEXT)')
    
    # 2. BẢNG KHÁCH HÀNG ĐÃ THÊM CỘT "VAI TRÒ"
    conn.execute('''CREATE TABLE IF NOT EXISTS khach_hang (
        id INTEGER PRIMARY KEY AUTOINCREMENT, tai_khoan TEXT UNIQUE, mat_khau TEXT, ho_ten TEXT, sdt TEXT, dia_chi TEXT, vai_tro TEXT DEFAULT 'khach'
    )''')
    
    conn.execute('CREATE TABLE IF NOT EXISTS don_hang (id INTEGER PRIMARY KEY AUTOINCREMENT, khach_hang_id INTEGER, ten_khach TEXT, sdt TEXT, dia_chi TEXT, tong_tien REAL, ngay_dat DATETIME DEFAULT CURRENT_TIMESTAMP, trang_thai TEXT DEFAULT "Chờ xử lý")')
    conn.execute('CREATE TABLE IF NOT EXISTS chi_tiet_don (id INTEGER PRIMARY KEY AUTOINCREMENT, don_hang_id INTEGER, san_pham_id INTEGER, so_luong INTEGER, gia REAL)')
    
    # Tự động tạo 1 tài khoản Admin mặc định nếu chưa có
    if conn.execute("SELECT COUNT(*) FROM khach_hang WHERE vai_tro = 'admin'").fetchone()[0] == 0:
        conn.execute("INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, vai_tro) VALUES ('admin', '123456', 'Quản trị viên', 'admin')")
        
    if conn.execute('SELECT COUNT(*) FROM danh_muc').fetchone()[0] == 0:
        conn.execute("INSERT INTO danh_muc (ten_danh_muc) VALUES ('Áo thun'), ('Quần Jeans'), ('Giày Sneaker')")
    conn.commit()
    conn.close()

tao_bang_moi()

@app.context_processor
def inject_data():
    # Kiểm tra xem ai đang đăng nhập
    is_admin = 'admin_id' in session
    is_khach = 'khach_id' in session
    ten_hien_thi = session.get('khach_ten', '')
    
    return dict(
        so_luong_gio_hang=sum(session.get('gio_hang', {}).values()),
        is_admin=is_admin,
        is_khach=is_khach,
        khach_ten=ten_hien_thi
    )

# ==================== ĐĂNG NHẬP THÔNG MINH 1 CỬA ====================
@app.route('/dang-nhap', methods=['GET', 'POST'])
def dang_nhap():
    if request.method == 'POST':
        tk, mk = request.form['tai_khoan'], request.form['mat_khau']
        conn = ket_noi_db()
        user = conn.execute('SELECT * FROM khach_hang WHERE tai_khoan=? AND mat_khau=?', (tk, mk)).fetchone()
        conn.close()
        
        if user:
            # Nếu là Admin -> Cho vào trang quản trị
            if user['vai_tro'] == 'admin':
                session['admin_id'] = user['id']
                session['khach_ten'] = 'Admin' # Để hiện tên trên menu
                return redirect(url_for('admin'))
            # Nếu là Khách -> Cho vào trang chủ mua sắm
            else:
                session['khach_id'] = user['id']
                session['khach_ten'] = user['ho_ten']
                return redirect(url_for('trang_chu'))
                
        return "<h3 style='text-align:center; padding:50px; color:red;'>Sai tài khoản hoặc mật khẩu! <a href='/dang-nhap'>Thử lại</a></h3>"
    
    return render_template('dang_nhap_chung.html')

@app.route('/dang-xuat')
def dang_xuat():
    session.clear() # Xóa toàn bộ bộ nhớ (Giỏ hàng, phiên đăng nhập)
    return redirect(url_for('trang_chu'))

# Đăng ký khách hàng (Tự đăng ký ở trang chủ)
@app.route('/dang-ky', methods=['GET', 'POST'])
def dang_ky():
    if request.method == 'POST':
        try:
            conn = ket_noi_db()
            conn.execute('INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, sdt, dia_chi, vai_tro) VALUES (?, ?, ?, ?, ?, "khach")', 
                         (request.form['tai_khoan'], request.form['mat_khau'], request.form['ho_ten'], request.form['sdt'], request.form['dia_chi']))
            conn.commit()
            return redirect(url_for('dang_nhap'))
        except: return "Tài khoản đã tồn tại!"
        finally: conn.close()
    return render_template('dang_ky_khach.html')

# ==================== ADMIN: QUẢN LÝ KHÁCH HÀNG ====================
@app.route('/admin/khach-hang', methods=['GET', 'POST'])
def quan_ly_khach_hang():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    
    conn = ket_noi_db()
    if request.method == 'POST':
        # Admin chủ động thêm tài khoản cho khách
        try:
            conn.execute('INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, sdt, dia_chi, vai_tro) VALUES (?, ?, ?, ?, ?, "khach")', 
                         (request.form['tai_khoan'], request.form['mat_khau'], request.form['ho_ten'], request.form['sdt'], request.form['dia_chi']))
            conn.commit()
        except: pass # Bỏ qua nếu trùng tên đăng nhập
        return redirect(url_for('quan_ly_khach_hang'))
        
    khach_hangs = conn.execute('SELECT * FROM khach_hang WHERE vai_tro = "khach" ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('quan_ly_khach.html', khach_hangs=khach_hangs)

@app.route('/admin/xoa-khach/<int:id>', methods=['POST'])
def xoa_khach(id):
    conn = ket_noi_db()
    conn.execute('DELETE FROM khach_hang WHERE id = ?', (id,))
    conn.commit(); conn.close()
    return redirect(url_for('quan_ly_khach_hang'))

# ==================== CÁC HÀM CÒN LẠI (GIỮ NGUYÊN) ====================
@app.route('/')
def trang_chu():
    conn = ket_noi_db()
    danh_mucs = conn.execute('SELECT * FROM danh_muc').fetchall()
    tu_khoa, the_loai_chon, kieu_hang_chon = request.args.get('tim_kiem', '').strip(), request.args.get('the_loai', ''), request.args.get('kieu_hang', '')
    query = 'SELECT * FROM san_pham WHERE 1=1'
    tham_so = []
    if tu_khoa: query += ' AND ten LIKE ?'; tham_so.append(f'%{tu_khoa}%')
    if the_loai_chon: query += ' AND the_loai = ?'; tham_so.append(the_loai_chon)
    if kieu_hang_chon: query += ' AND kieu_hang = ?'; tham_so.append(kieu_hang_chon)
    query += ' ORDER BY id DESC'
    san_phams = conn.execute(query, tham_so).fetchall()
    conn.close()
    return render_template('index.html', san_phams=san_phams, danh_mucs=danh_mucs, tu_khoa=tu_khoa, the_loai_chon=the_loai_chon, kieu_hang_chon=kieu_hang_chon)

@app.route('/san-pham/<int:id>')
def chi_tiet_san_pham(id):
    conn = ket_noi_db()
    sp = conn.execute('SELECT * FROM san_pham WHERE id = ?', (id,)).fetchone()
    anh_phu = conn.execute('SELECT * FROM hinh_anh_sp WHERE san_pham_id = ?', (id,)).fetchall()
    conn.close()
    return render_template('chi_tiet.html', sp=sp, anh_phu=anh_phu) if sp else ("Lỗi 404", 404)

@app.route('/them-vao-gio/<int:id>')
def them_vao_gio(id):
    if 'gio_hang' not in session: session['gio_hang'] = {}
    session['gio_hang'][str(id)] = session['gio_hang'].get(str(id), 0) + 1
    session.modified = True
    return redirect(url_for('xem_gio_hang'))

@app.route('/gio-hang')
def xem_gio_hang():
    conn = ket_noi_db()
    san_phams_trong_gio, tong_tien = [], 0
    for sp_id, so_luong in session.get('gio_hang', {}).items():
        sp = conn.execute('SELECT * FROM san_pham WHERE id = ?', (sp_id,)).fetchone()
        if sp:
            tong_tien += sp['gia_ban'] * so_luong
            san_phams_trong_gio.append({'id': sp['id'], 'ten': sp['ten'], 'hinh_anh': sp['hinh_anh'], 'gia_ban': sp['gia_ban'], 'so_luong': so_luong, 'thanh_tien': sp['gia_ban'] * so_luong})
    user_info = conn.execute('SELECT * FROM khach_hang WHERE id = ?', (session['khach_id'],)).fetchone() if 'khach_id' in session else None
    conn.close()
    return render_template('gio_hang.html', gio_hang=san_phams_trong_gio, tong_tien=tong_tien, user=user_info)

@app.route('/xoa-khoi-gio/<int:id>')
def xoa_khoi_gio(id):
    if 'gio_hang' in session and str(id) in session['gio_hang']:
        del session['gio_hang'][str(id)]
        session.modified = True
    return redirect(url_for('xem_gio_hang'))

@app.route('/dat-hang', methods=['POST'])
def dat_hang():
    # 1. KIỂM TRA ĐĂNG NHẬP: Nếu chưa đăng nhập khách hoặc admin thì không cho đặt
    if 'khach_id' not in session and 'admin_id' not in session:
        return "<script>alert('Vui lòng đăng nhập để tiến hành đặt hàng!'); window.location.href='/dang-nhap';</script>"

    if not session.get('gio_hang'): 
        return redirect(url_for('trang_chu'))
        
    conn = ket_noi_db()
    cursor = conn.cursor()
    
    # Lấy ID người mua (Ưu tiên khach_id, nếu sếp mua thì lấy admin_id)
    nguoi_mua_id = session.get('khach_id') or session.get('admin_id')
    
    # ... (Các đoạn code tính tiền và lưu đơn hàng bên dưới giữ nguyên) ...
    # Chú ý: Đảm bảo cột khach_hang_id trong lệnh INSERT sử dụng biến nguoi_mua_id
    cursor.execute('INSERT INTO don_hang (khach_hang_id, ten_khach, sdt, dia_chi, tong_tien) VALUES (?, ?, ?, ?, ?)', 
                   (nguoi_mua_id, request.form['ten_khach'], request.form['sdt'], request.form['dia_chi'], tong_tien))
    
    # ... (Code trừ kho và xóa giỏ hàng giữ nguyên) ...
    conn.commit()
    conn.close()
    session.pop('gio_hang', None)
    return "<h2 style='text-align:center; padding:50px;'>🎉 Đặt hàng thành công! <br><a href='/'>Quay lại trang chủ</a></h2>"

@app.route('/admin')
def admin():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db(); san_phams = conn.execute('SELECT * FROM san_pham').fetchall(); conn.close()
    return render_template('admin.html', san_phams=san_phams)

@app.route('/them', methods=['GET', 'POST'])
def them_san_pham():
    conn = ket_noi_db()
    if request.method == 'POST':
        file_chinh = request.files['hinh_anh']
        du_ong_dan_chinh = '/static/uploads/' + secure_filename(file_chinh.filename) if file_chinh and file_chinh.filename else ''
        if du_ong_dan_chinh: file_chinh.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file_chinh.filename)))
        cursor = conn.cursor()
        cursor.execute('''INSERT INTO san_pham (ten, the_loai, hang_sx, gia_nhap, gia_ban, so_luong, hinh_anh, mo_ta, kieu_hang, tien_coc, ngay_phat_hanh) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
            (request.form['ten'], request.form['the_loai'], request.form['hang_sx'], float(request.form['gia_nhap']), float(request.form['gia_ban']), int(request.form['so_luong']), du_ong_dan_chinh, request.form['mo_ta'], request.form.get('kieu_hang', 'Co san'), float(request.form.get('tien_coc', 0) or 0), request.form.get('ngay_phat_hanh', '')))
        sp_id = cursor.lastrowid
        for file in request.files.getlist('hinh_anh_phu'):
            if file and file.filename:
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename)))
                conn.execute('INSERT INTO hinh_anh_sp (san_pham_id, du_ong_dan) VALUES (?, ?)', (sp_id, '/static/uploads/' + secure_filename(file.filename)))
        conn.commit(); conn.close()
        return redirect(url_for('admin'))
    danh_mucs = conn.execute('SELECT * FROM danh_muc').fetchall(); conn.close()
    return render_template('them.html', danh_mucs=danh_mucs)

@app.route('/sua/<int:id>', methods=['GET', 'POST'])
def sua_san_pham(id):
    conn = ket_noi_db()
    if request.method == 'POST':
        conn.execute('''UPDATE san_pham SET ten=?, the_loai=?, hang_sx=?, gia_nhap=?, gia_ban=?, so_luong=?, mo_ta=?, kieu_hang=?, tien_coc=?, ngay_phat_hanh=? WHERE id=?''', 
            (request.form['ten'], request.form['the_loai'], request.form['hang_sx'], float(request.form['gia_nhap']), float(request.form['gia_ban']), int(request.form['so_luong']), request.form['mo_ta'], request.form['kieu_hang'], float(request.form.get('tien_coc', 0) or 0), request.form.get('ngay_phat_hanh', ''), id))
        conn.commit(); conn.close()
        return redirect(url_for('admin'))
    sp = conn.execute('SELECT * FROM san_pham WHERE id=?', (id,)).fetchone()
    danh_mucs = conn.execute('SELECT * FROM danh_muc').fetchall(); conn.close()
    return render_template('sua.html', sp=sp, danh_mucs=danh_mucs)

@app.route('/xoa/<int:id>', methods=['POST'])
def xoa_san_pham(id):
    conn = ket_noi_db(); conn.execute('DELETE FROM san_pham WHERE id = ?', (id,)); conn.execute('DELETE FROM hinh_anh_sp WHERE san_pham_id = ?', (id,)); conn.commit(); conn.close()
    return redirect(url_for('admin'))

@app.route('/danh-muc', methods=['GET', 'POST'])
def quan_ly_danh_muc():
    conn = ket_noi_db()
    if request.method == 'POST': conn.execute('INSERT INTO danh_muc (ten_danh_muc) VALUES (?)', (request.form['ten_danh_muc'],)); conn.commit(); return redirect(url_for('quan_ly_danh_muc'))
    danh_mucs = conn.execute('SELECT * FROM danh_muc').fetchall(); conn.close()
    return render_template('danh_muc.html', danh_mucs=danh_mucs)

@app.route('/xoa-danh-muc/<int:id>', methods=['POST'])
def xoa_danh_muc(id):
    conn = ket_noi_db(); conn.execute('DELETE FROM danh_muc WHERE id = ?', (id,)); conn.commit(); conn.close()
    return redirect(url_for('quan_ly_danh_muc'))

@app.route('/admin/don-hang')
def quan_ly_don_hang():
    conn = ket_noi_db(); don_hangs = conn.execute('SELECT * FROM don_hang ORDER BY id DESC').fetchall(); conn.close()
    return render_template('quan_ly_don.html', don_hangs=don_hangs)

@app.route('/admin/cap-nhat-don/<int:id>', methods=['POST'])
def cap_nhat_don(id):
    conn = ket_noi_db(); conn.execute('UPDATE don_hang SET trang_thai = ? WHERE id = ?', (request.form['trang_thai'], id)); conn.commit(); conn.close()
    return redirect(url_for('quan_ly_don_hang'))

@app.route('/admin/thong-ke')
def thong_ke():
    conn = ket_noi_db()
    doanh_thu = conn.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai = 'Hoàn thành'").fetchone()[0] or 0
    chi_tiets = conn.execute("SELECT c.so_luong, s.gia_nhap FROM chi_tiet_don c JOIN don_hang d ON c.don_hang_id = d.id JOIN san_pham s ON c.san_pham_id = s.id WHERE d.trang_thai = 'Hoàn thành'").fetchall()
    tien_loi = doanh_thu - sum(r['so_luong'] * r['gia_nhap'] for r in chi_tiets)
    thue_vat = doanh_thu * 0.1
    so_don_moi = conn.execute("SELECT COUNT(*) FROM don_hang WHERE trang_thai = 'Chờ xử lý'").fetchone()[0]
    conn.close()
    return render_template('thong_ke.html', doanh_thu=doanh_thu, tien_loi=tien_loi, thue_vat=thue_vat, so_don_moi=so_don_moi)

if __name__ == '__main__':
    Timer(1.5, lambda: webbrowser.open_new('http://127.0.0.1:5000/')).start()
    app.run(debug=False)