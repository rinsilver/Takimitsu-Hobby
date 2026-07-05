from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import ket_noi_db

# Khởi tạo Blueprint có tên là 'auth'
auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/dang-nhap', methods=['GET', 'POST'])
def dang_nhap():
    if request.method == 'POST':
        conn = ket_noi_db()
        tai_khoan_nhap_vao = request.form['tai_khoan']
        u = conn.execute('SELECT * FROM khach_hang WHERE sdt=? OR tai_khoan=?', (tai_khoan_nhap_vao, tai_khoan_nhap_vao)).fetchone()
        
        if u:
            mat_khau_db = u['mat_khau']
            mat_khau_nhap = request.form['mat_khau']
            
            # Xử lý tương thích ngược với mật khẩu mã hóa hoặc chưa mã hóa
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
                return redirect(url_for('client.index')) # Trỏ về blueprint client
                
        conn.close()
        flash('Sai tài khoản, số điện thoại hoặc mật khẩu rồi bẹn ơi!', 'danger')
        return redirect(url_for('auth.dang_nhap'))
    return render_template('dang_nhap_chung.html')

@auth_bp.route('/dang-ky', methods=['GET', 'POST'])
def dang_ky():
    if request.method == 'POST':
        conn = ket_noi_db()
        hashed_pw = generate_password_hash(request.form['mat_khau'])
        try:
            conn.execute('INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, sdt, dia_chi) VALUES (?,?,?,?,?)', 
                         (request.form['tai_khoan'], hashed_pw, request.form['ho_ten'], request.form['sdt'], request.form['dia_chi']))
            conn.commit()
            return redirect(url_for('auth.dang_nhap'))
        except: 
            return "Lỗi: Tài khoản đã tồn tại!"
        finally: 
            conn.close()
    return render_template('dang_ky_khach.html')

@auth_bp.route('/dang-xuat')
def dang_xuat():
    session.clear()
    return redirect(url_for('client.index'))