import os, webbrowser, sqlite3
from threading import Timer
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'wolves_clone_final_v5'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def ket_noi_db():
    conn = sqlite3.connect('database_v5.db')
    conn.row_factory = sqlite3.Row
    return conn

def tao_bang():
    conn = ket_noi_db()
    # Bảng sản phẩm full tính năng Pre-order
    conn.execute('''CREATE TABLE IF NOT EXISTS san_pham (
        id INTEGER PRIMARY KEY AUTOINCREMENT, ten TEXT, the_loai TEXT, hang_sx TEXT, 
        gia_nhap REAL, gia_ban REAL, so_luong INTEGER, hinh_anh TEXT, mo_ta TEXT, 
        kieu_hang TEXT DEFAULT 'Co san', tien_coc REAL DEFAULT 0, ngay_phat_hanh TEXT)''')
    conn.execute('CREATE TABLE IF NOT EXISTS danh_muc (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_danh_muc TEXT)')
    conn.execute('CREATE TABLE IF NOT EXISTS hinh_anh_sp (id INTEGER PRIMARY KEY AUTOINCREMENT, san_pham_id INTEGER, du_ong_dan TEXT)')
    conn.execute('''CREATE TABLE IF NOT EXISTS khach_hang (
        id INTEGER PRIMARY KEY AUTOINCREMENT, tai_khoan TEXT UNIQUE, mat_khau TEXT, 
        ho_ten TEXT, sdt TEXT, dia_chi TEXT, vai_tro TEXT DEFAULT 'khach')''')
    conn.execute('''CREATE TABLE IF NOT EXISTS don_hang (
        id INTEGER PRIMARY KEY AUTOINCREMENT, khach_hang_id INTEGER, ten_khach TEXT, 
        sdt TEXT, dia_chi TEXT, tong_tien REAL, ngay_dat DATETIME DEFAULT CURRENT_TIMESTAMP, 
        trang_thai TEXT DEFAULT "Chờ xử lý")''')
    conn.execute('CREATE TABLE IF NOT EXISTS chi_tiet_don (id INTEGER PRIMARY KEY AUTOINCREMENT, don_hang_id INTEGER, san_pham_id INTEGER, so_luong INTEGER, gia REAL)')
    
    if conn.execute("SELECT COUNT(*) FROM khach_hang WHERE vai_tro = 'admin'").fetchone()[0] == 0:
        conn.execute("INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, vai_tro) VALUES ('admin', '123456', 'Quản trị viên', 'admin')")
    conn.commit(); conn.close()

tao_bang()

@app.context_processor
def inject_data():
    return dict(so_luong_gio_hang=sum(session.get('gio_hang', {}).values()), 
                is_admin='admin_id' in session, is_khach='khach_id' in session, 
                khach_ten=session.get('khach_ten', ''))

# --- USER ROUTES ---
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
def chi_tiet_san_pham(id):
    conn = ket_noi_db()
    sp = conn.execute('SELECT * FROM san_pham WHERE id = ?', (id,)).fetchone()
    anh_phu = conn.execute('SELECT * FROM hinh_anh_sp WHERE san_pham_id = ?', (id,)).fetchall()
    conn.close()
    return render_template('chi_tiet.html', sp=sp, anh_phu=anh_phu)

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
        return "Sai thông tin!"
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
        except:
            return "Lỗi đăng ký!"
        finally:
            conn.close()
    return render_template('dang_ky_khach.html')

@app.route('/dang-xuat')
def dang_xuat():
    session.clear(); return redirect(url_for('trang_chu'))

# --- GIỎ HÀNG & LỊCH SỬ ---
@app.route('/gio-hang')
def xem_gio_hang():
    conn = ket_noi_db(); items, tong = [], 0
    for sid, sl in session.get('gio_hang', {}).items():
        sp = conn.execute('SELECT * FROM san_pham WHERE id=?', (sid,)).fetchone()
        if sp:
            tong += sp['gia_ban'] * sl
            items.append({'id':sid, 'ten':sp['ten'], 'gia_ban':sp['gia_ban'], 'so_luong':sl, 'hinh_anh':sp['hinh_anh'], 'thanh_tien': sp['gia_ban']*sl})
    uid = session.get('khach_id') or session.get('admin_id')
    u = conn.execute('SELECT * FROM khach_hang WHERE id=?', (uid,)).fetchone() if uid else None
    conn.close()
    return render_template('gio_hang.html', gio_hang=items, tong_tien=tong, user=u)

@app.route('/them-vao-gio/<int:id>')
def them_vao_gio(id):
    if 'gio_hang' not in session: session['gio_hang'] = {}
    session['gio_hang'][str(id)] = session['gio_hang'].get(str(id), 0) + 1
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

# --- QUẢN TRỊ (ADMIN) ---
@app.route('/admin')
def admin():
    if 'admin_id' not in session: return redirect(url_for('dang_nhap'))
    conn = ket_noi_db(); sps = conn.execute('SELECT * FROM san_pham').fetchall(); conn.close()
    return render_template('admin.html', san_phams=sps)

@app.route('/them', methods=['GET', 'POST'])
def them_san_pham():
    conn = ket_noi_db()
    if request.method == 'POST':
        f = request.files['hinh_anh']
        img = '/static/uploads/' + secure_filename(f.filename) if f else ''
        if f: f.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(f.filename)))
        cur = conn.cursor()
        cur.execute('INSERT INTO san_pham (ten, the_loai, hang_sx, gia_nhap, gia_ban, so_luong, hinh_anh, mo_ta, kieu_hang, tien_coc, ngay_phat_hanh) VALUES (?,?,?,?,?,?,?,?,?,?,?)', 
                    (request.form['ten'], request.form['the_loai'], request.form['hang_sx'], float(request.form['gia_nhap']), float(request.form['gia_ban']), int(request.form['so_luong']), img, request.form['mo_ta'], request.form['kieu_hang'], float(request.form.get('tien_coc',0) or 0), request.form.get('ngay_phat_hanh','')))
        sid = cur.lastrowid
        for pf in request.files.getlist('hinh_anh_phu'):
            if pf:
                pf.save(os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(pf.filename)))
                conn.execute('INSERT INTO hinh_anh_sp (san_pham_id, du_ong_dan) VALUES (?,?)', (sid, '/static/uploads/'+secure_filename(pf.filename)))
        conn.commit(); conn.close(); return redirect(url_for('admin'))
    dms = conn.execute('SELECT * FROM danh_muc').fetchall(); conn.close()
    return render_template('them.html', danh_mucs=dms)

@app.route('/sua/<int:id>', methods=['GET', 'POST'])
def sua_san_pham(id):
    conn = ket_noi_db()
    if request.method == 'POST':
        conn.execute('UPDATE san_pham SET ten=?, the_loai=?, hang_sx=?, gia_nhap=?, gia_ban=?, so_luong=?, mo_ta=?, kieu_hang=?, tien_coc=?, ngay_phat_hanh=? WHERE id=?', 
                     (request.form['ten'], request.form['the_loai'], request.form['hang_sx'], float(request.form['gia_nhap']), float(request.form['gia_ban']), int(request.form['so_luong']), request.form['mo_ta'], request.form['kieu_hang'], float(request.form.get('tien_coc',0) or 0), request.form.get('ngay_phat_hanh',''), id))
        conn.commit(); conn.close(); return redirect(url_for('admin'))
    sp = conn.execute('SELECT * FROM san_pham WHERE id=?', (id,)).fetchone()
    dms = conn.execute('SELECT * FROM danh_muc').fetchall(); conn.close()
    return render_template('sua.html', sp=sp, danh_mucs=dms)

@app.route('/xoa/<int:id>', methods=['POST'])
def xoa_san_pham(id):
    conn = ket_noi_db(); conn.execute('DELETE FROM san_pham WHERE id=?', (id,)); conn.commit(); conn.close()
    return redirect(url_for('admin'))

@app.route('/admin/don-hang')
def quan_ly_don_hang():
    conn = ket_noi_db(); dhs = conn.execute('SELECT * FROM don_hang ORDER BY id DESC').fetchall(); conn.close()
    return render_template('quan_ly_don.html', don_hangs=dhs)

@app.route('/admin/cap-nhat-don/<int:id>', methods=['POST'])
def cap_nhat_don(id):
    conn = ket_noi_db(); conn.execute('UPDATE don_hang SET trang_thai=? WHERE id=?', (request.form['trang_thai'], id)); conn.commit(); conn.close()
    return redirect(url_for('quan_ly_don_hang'))

@app.route('/admin/thong-ke')
def thong_ke():
    conn = ket_noi_db()
    dt = conn.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai='Hoàn thành'").fetchone()[0] or 0
    sd = conn.execute("SELECT COUNT(*) FROM don_hang WHERE trang_thai='Chờ xử lý'").fetchone()[0]
    conn.close()
    return render_template('thong_ke.html', doanh_thu=dt, so_don_moi=sd, tien_loi=dt*0.3, thue_vat=dt*0.1)

@app.route('/danh-muc', methods=['GET', 'POST'])
def quan_ly_danh_muc():
    conn = ket_noi_db()
    if request.method == 'POST':
        conn.execute('INSERT INTO danh_muc (ten_danh_muc) VALUES (?)', (request.form['ten_danh_muc'],)); conn.commit()
    dms = conn.execute('SELECT * FROM danh_muc').fetchall(); conn.close()
    return render_template('danh_muc.html', danh_mucs=dms)

@app.route('/admin/khach-hang')
def quan_ly_khach_hang():
    conn = ket_noi_db(); ks = conn.execute('SELECT * FROM khach_hang WHERE vai_tro="khach"').fetchall(); conn.close()
    return render_template('quan_ly_khach.html', khach_hangs=ks)

if __name__ == '__main__':
    Timer(1.5, lambda: webbrowser.open_new('http://127.0.0.1:5000/')).start()
    app.run(debug=True)