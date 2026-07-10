import os
import csv
import io
import json
import datetime
from PIL import Image
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash
from flask import Blueprint, abort, render_template, request, redirect, session, jsonify, flash, Response, current_app

from database.db import ket_noi_db, get_settings, save_settings

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
def admin_dashboard():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    
    tu_khoa = request.args.get('tu_khoa', '')
    danh_muc = request.args.get('danh_muc', '')
    hang_sx = request.args.get('hang_sx', '')
    kieu_hang = request.args.get('kieu_hang', '')
    sap_xep = request.args.get('sap_xep', 'moi_nhat')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    query_count = "SELECT COUNT(*) FROM san_pham s WHERE 1=1"
    query = """
        SELECT s.*, 
        IFNULL((SELECT gia_nhap FROM lo_hang_nhap WHERE san_pham_id = s.id ORDER BY id DESC LIMIT 1), s.gia_nhap) as gia_nhap_thuc_te,
        IFNULL((SELECT SUM(c.so_luong) FROM chi_tiet_don c JOIN don_hang d ON c.don_hang_id = d.id WHERE c.san_pham_id = s.id AND d.trang_thai = 'Hoàn thành'), 0) as luong_giao_thanh_cong,
        IFNULL((SELECT SUM(c.so_luong) FROM chi_tiet_don c JOIN don_hang d ON c.don_hang_id = d.id WHERE c.san_pham_id = s.id AND d.trang_thai NOT IN ('Hoàn thành', 'Đã hủy')), 0) as luong_dang_giao
        FROM san_pham s WHERE 1=1
    """
    params = []
    
    if tu_khoa:
        clause = " AND (s.ten LIKE ? OR s.id LIKE ?)"
        query_count += clause; query += clause
        params.extend([f'%{tu_khoa}%', f'%{tu_khoa}%'])
    if danh_muc:
        clause = " AND s.the_loai = ?"
        query_count += clause; query += clause; params.append(danh_muc)
    if hang_sx:
        clause = " AND s.hang_sx = ?"
        query_count += clause; query += clause; params.append(hang_sx)
    if kieu_hang:
        clause = " AND s.kieu_hang = ?"
        query_count += clause; query += clause; params.append(kieu_hang)
    
    tong_sp = conn.execute(query_count, params).fetchone()[0]
    tong_trang = (tong_sp + per_page - 1) // per_page
    
    if sap_xep == 'moi_nhat': query += " ORDER BY s.id DESC"
    elif sap_xep == 'cu_nhat': query += " ORDER BY s.id ASC"
    elif sap_xep == 'ton_nhieu': query += " ORDER BY s.so_luong DESC"
    elif sap_xep == 'ton_it': query += " ORDER BY s.so_luong ASC"
    else: query += " ORDER BY s.id DESC"
    
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    sps = conn.execute(query, params).fetchall()
    
    dms = conn.execute('SELECT * FROM danh_muc').fetchall()
    hgs = conn.execute('SELECT * FROM hang_sx_list').fetchall()
    
    # --- THUẬT TOÁN TÍNH THỐNG KÊ ĐỘNG CHO 4 THẺ DASHBOARD ---
    try:
        # 1. Dòng hàng bán chạy nhất (Dựa trên số lượng đã bán trong đơn hoàn thành)
        dong_bc_row = conn.execute('''
            SELECT s.the_loai, SUM(c.so_luong) as sl 
            FROM chi_tiet_don c JOIN san_pham s ON c.san_pham_id = s.id 
            JOIN don_hang d ON c.don_hang_id = d.id
            WHERE d.trang_thai = 'Hoàn thành' AND s.the_loai != '' 
            GROUP BY s.the_loai ORDER BY sl DESC LIMIT 1
        ''').fetchone()
        dong_ban_chay = dong_bc_row['the_loai'] if dong_bc_row and dong_bc_row['the_loai'] else "Chưa có data"

        # 2. Giá nhập trung bình của toàn bộ các Lô hàng
        gia_tb_row = conn.execute('SELECT AVG(gia_nhap) FROM lo_hang_nhap WHERE gia_nhap > 0').fetchone()
        gia_nhap_tb = gia_tb_row[0] if gia_tb_row and gia_tb_row[0] else 0

        # 3. Hãng phổ biến nhất trong kho
        hang_top_row = conn.execute('''
            SELECT hang_sx, COUNT(id) as sl 
            FROM san_pham WHERE hang_sx != '' AND hang_sx IS NOT NULL
            GROUP BY hang_sx ORDER BY sl DESC LIMIT 1
        ''').fetchone()
        hang_nhieu_nhat = hang_top_row['hang_sx'] if hang_top_row and hang_top_row['hang_sx'] else "Chưa có data"
    except:
        dong_ban_chay = "N/A"
        gia_nhap_tb = 0
        hang_nhieu_nhat = "N/A"
        
    conn.close()
    
    # Bơm thêm 4 biến thống kê ra ngoài HTML
    return render_template('admin.html', san_phams=sps, tu_khoa=tu_khoa, 
                           danh_muc=danh_muc, hang_sx=hang_sx, kieu_hang=kieu_hang, sap_xep=sap_xep,
                           danh_mucs=dms, hangs=hgs, page=page, tong_trang=tong_trang,
                           tong_sp=tong_sp, dong_ban_chay=dong_ban_chay, gia_nhap_tb=gia_nhap_tb, hang_nhieu_nhat=hang_nhieu_nhat)

@admin_bp.route('/them', methods=['GET', 'POST'])
def them_san_pham():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    if request.method == 'POST':
        f = request.files['hinh_anh']
        img = ''
        if f and f.filename != '':
            filename = secure_filename(f.filename)
            base_name = os.path.splitext(filename)[0]
            webp_name = base_name + ".webp"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], webp_name)
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
        
        cur.execute('''INSERT INTO san_pham (ten, the_loai, hang_sx, gia_goc, gia_ban, so_luong, hinh_anh, mo_ta, kieu_hang, tien_coc, ngay_phat_hanh, gia_san_new, gia_san_likenew, gia_order_new, gia_order_likenew) 
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
                    (request.form['ten'], request.form['the_loai'], request.form['hang_sx'], 
                     gia_goc, gia_ban, int(request.form.get('so_luong', 0) or 0), 
                     img, request.form['mo_ta'], request.form['kieu_hang'], 
                     float(request.form.get('tien_coc', 0) or 0), request.form.get('ngay_phat_hanh', ''), 
                     gia_san_new, gia_san_likenew, gia_order_new, gia_order_likenew))
        sid = cur.lastrowid

        # TỰ ĐỘNG TẠO LÔ HÀNG ĐẦU TIÊN
        gia_nhap = float(request.form.get('gia_nhap', 0) or 0)
        sl_nhap = int(request.form.get('so_luong', 0) or 0)
        nguon_id = request.form.get('nguon_nhap_id')
        tien_tra = float(request.form.get('tien_da_tra_nguon', 0) or 0)
        tt_nhap = request.form.get('trang_thai_nhap', 'Còn nợ')
        ngay_ve = request.form.get('ngay_ve', '')

        if nguon_id or gia_nhap > 0 or sl_nhap > 0:
            cur.execute('''INSERT INTO lo_hang_nhap (san_pham_id, nguon_nhap_id, so_luong_nhap, gia_nhap, tien_da_tra_nguon, trang_thai_nhap, ngay_du_kien_ve) VALUES (?,?,?,?,?,?,?)''', (sid, nguon_id, sl_nhap, gia_nhap, tien_tra, tt_nhap, ngay_ve))
            lo_id = cur.lastrowid
            if tien_tra > 0: conn.execute('INSERT INTO lich_su_tra_nguon (san_pham_id, lo_hang_id, so_tien) VALUES (?, ?, ?)', (sid, lo_id, tien_tra))
        
        for pf in request.files.getlist('hinh_anh_phu'):
            if pf and pf.filename != '':
                filename_phu = secure_filename(pf.filename)
                base_name_phu = os.path.splitext(filename_phu)[0]
                import time
                webp_name_phu = f"{base_name_phu}_{sid}_{int(time.time())}.webp"
                save_path_phu = os.path.join(current_app.config['UPLOAD_FOLDER'], webp_name_phu)
                img_phu_raw = Image.open(pf)
                img_phu_raw.convert("RGB").save(save_path_phu, "WEBP", quality=80)
                conn.execute('INSERT INTO hinh_anh_sp (san_pham_id, du_ong_dan) VALUES (?,?)', (sid, '/static/uploads/' + webp_name_phu))
        conn.commit(); conn.close(); return redirect('/admin')
    
    dms = conn.execute('SELECT * FROM danh_muc').fetchall()
    hgs = conn.execute('SELECT * FROM hang_sx_list').fetchall()
    ngs = conn.execute('SELECT * FROM nguon_nhap').fetchall()
    conn.close()
    return render_template('them.html', danh_mucs=dms, hangs=hgs, nguons=ngs)

@admin_bp.route('/sua/<int:id>', methods=['GET', 'POST'])
def sua_san_pham(id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    if request.method == 'POST':
        gia_san_new = float(request.form.get('gia_san_new', 0) or 0)
        gia_san_likenew = float(request.form.get('gia_san_likenew', 0) or 0)
        gia_order_new = float(request.form.get('gia_order_new', 0) or 0)
        gia_order_likenew = float(request.form.get('gia_order_likenew', 0) or 0)
        gia_ban = float(request.form.get('gia_ban', gia_san_new)) 
        gia_goc = float(request.form.get('gia_goc', 0) or 0)
        
        ten_sp = request.form.get('ten', 'Chưa có tên')
        the_loai = request.form.get('the_loai', '')
        hang_sx = request.form.get('hang_sx', '')
        mo_ta = request.form.get('mo_ta', '')
        kieu_hang = request.form.get('kieu_hang', 'Co san')
        so_luong = int(request.form.get('so_luong', 0) or 0)
        
        f = request.files.get('hinh_anh')
        img_sql = ""
        tham_so = [
            ten_sp, the_loai, hang_sx, gia_goc, gia_ban, so_luong, mo_ta, 
            kieu_hang, float(request.form.get('tien_coc', 0) or 0), 
            request.form.get('ngay_phat_hanh', ''), 
            gia_san_new, gia_san_likenew, gia_order_new, gia_order_likenew
        ]
        
        if f and f.filename != '':
            sp = conn.execute('SELECT hinh_anh FROM san_pham WHERE id=?', (id,)).fetchone()
            if sp and sp['hinh_anh']:
                try: os.remove(os.path.join(current_app.root_path, sp['hinh_anh'].lstrip('/')))
                except: pass
            filename = secure_filename(f.filename)
            base_name = os.path.splitext(filename)[0]
            import time
            webp_name = f"{base_name}_{id}_{int(time.time())}_main.webp"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], webp_name)
            img_raw = Image.open(f)
            img_raw.convert("RGB").save(save_path, "WEBP", quality=80)
            img_sql = ", hinh_anh = ?"
            tham_so.append('/static/uploads/' + webp_name)
        
        tham_so.append(id)

        conn.execute(f'''UPDATE san_pham SET 
            ten=?, the_loai=?, hang_sx=?, gia_goc=?, gia_ban=?, so_luong=?, mo_ta=?, 
            kieu_hang=?, tien_coc=?, ngay_phat_hanh=?, gia_san_new=?, gia_san_likenew=?, gia_order_new=?, gia_order_likenew=? {img_sql} 
            WHERE id=?''', tuple(tham_so))
        
        files_phu = request.files.getlist('hinh_anh_phu')
        if files_phu and files_phu[0].filename != '':
            old_anh_phu = conn.execute('SELECT du_ong_dan FROM hinh_anh_sp WHERE san_pham_id=?', (id,)).fetchall()
            for old in old_anh_phu:
                try: os.remove(os.path.join(current_app.root_path, old['du_ong_dan'].lstrip('/')))
                except: pass
            conn.execute('DELETE FROM hinh_anh_sp WHERE san_pham_id=?', (id,))
            for pf in files_phu:
                if pf and pf.filename != '':
                    filename_phu = secure_filename(pf.filename)
                    base_name_phu = os.path.splitext(filename_phu)[0]
                    import time
                    webp_name_phu = f"{base_name_phu}_{id}_{int(time.time())}.webp"
                    save_path_phu = os.path.join(current_app.config['UPLOAD_FOLDER'], webp_name_phu)
                    img_phu_raw = Image.open(pf)
                    img_phu_raw.convert("RGB").save(save_path_phu, "WEBP", quality=80)
                    conn.execute('INSERT INTO hinh_anh_sp (san_pham_id, du_ong_dan) VALUES (?,?)', (id, '/static/uploads/' + webp_name_phu))
        
        conn.commit(); conn.close()
        flash('Đã lưu thông tin Sản phẩm thành công!', 'success')
        return redirect('/admin') 

    sp = conn.execute('SELECT * FROM san_pham WHERE id = ?', (id,)).fetchone()
    if not sp: conn.close(); abort(404)
    lo_hangs = conn.execute('SELECT l.*, n.ten_nguon FROM lo_hang_nhap l LEFT JOIN nguon_nhap n ON l.nguon_nhap_id = n.id WHERE l.san_pham_id = ? ORDER BY l.id DESC', (id,)).fetchall()
    anh_phu = conn.execute('SELECT * FROM hinh_anh_sp WHERE san_pham_id = ?', (id,)).fetchall()
    dms = conn.execute('SELECT * FROM danh_muc').fetchall()
    hgs = conn.execute('SELECT * FROM hang_sx_list').fetchall()
    ngs = conn.execute('SELECT * FROM nguon_nhap').fetchall()
    
    # --- ĐOẠN CODE LẤY DANH SÁCH KHÁCH CHỜ PRE-ORDER ---
    khach_cho = conn.execute('''
        SELECT d.id as don_id, d.ten_khach, d.sdt, d.ngay_dat, d.tien_da_tra, d.tong_tien, c.so_luong 
        FROM chi_tiet_don c 
        JOIN don_hang d ON c.don_hang_id = d.id 
        WHERE c.san_pham_id = ? AND d.trang_thai IN ('Đã cọc', 'Chờ xử lý', 'Hàng về - Chờ TT') 
        ORDER BY d.ngay_dat ASC
    ''', (id,)).fetchall()
    
    conn.close()
    return render_template('sua.html', sp=sp, lo_hangs=lo_hangs, anh_phu=anh_phu, danh_mucs=dms, hangs=hgs, nguons=ngs, khach_cho=khach_cho)

@admin_bp.route('/admin/them-lo-hang', methods=['POST'])
def them_lo_hang():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    sp_id = request.form['san_pham_id']
    nguon_id = request.form.get('nguon_nhap_id')
    sl = int(request.form.get('so_luong_nhap', 0) or 0)
    gia = float(request.form.get('gia_nhap', 0) or 0)
    tra = float(request.form.get('tien_da_tra_nguon', 0) or 0)
    ngay_ve = request.form.get('ngay_ve', '')
    tt = 'Hoàn thành' if tra >= (sl * gia) else 'Còn nợ'
    
    cur = conn.cursor()
    cur.execute('''INSERT INTO lo_hang_nhap (san_pham_id, nguon_nhap_id, so_luong_nhap, gia_nhap, tien_da_tra_nguon, trang_thai_nhap, ngay_du_kien_ve) 
                   VALUES (?,?,?,?,?,?,?)''', (sp_id, nguon_id, sl, gia, tra, tt, ngay_ve))
    lo_id = cur.lastrowid
    
    conn.execute('UPDATE san_pham SET so_luong = so_luong + ? WHERE id = ?', (sl, sp_id))
    if tra > 0: conn.execute('INSERT INTO lich_su_tra_nguon (san_pham_id, lo_hang_id, so_tien) VALUES (?, ?, ?)', (sp_id, lo_id, tra))
        
    conn.commit(); conn.close()
    flash('Đã nhập lô hàng mới thành công!', 'success')
    return redirect(f'/sua/{sp_id}')

@admin_bp.route('/admin/xoa-lo-hang/<int:lo_id>', methods=['POST'])
def xoa_lo_hang(lo_id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    lo = conn.execute('SELECT san_pham_id, so_luong_nhap FROM lo_hang_nhap WHERE id = ?', (lo_id,)).fetchone()
    if lo:
        conn.execute('UPDATE san_pham SET so_luong = so_luong - ? WHERE id = ?', (lo['so_luong_nhap'], lo['san_pham_id']))
        conn.execute('DELETE FROM lo_hang_nhap WHERE id = ?', (lo_id,))
        conn.execute('DELETE FROM lich_su_tra_nguon WHERE lo_hang_id = ?', (lo_id,))
        conn.commit()
    conn.close()
    flash('Đã xóa lô hàng!', 'success')
    return redirect(request.referrer or '/admin')

@admin_bp.route('/xoa/<int:id>', methods=['POST'])
def xoa_san_pham(id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    don_hang_dang_chua = conn.execute('''SELECT d.id, d.trang_thai FROM chi_tiet_don c JOIN don_hang d ON c.don_hang_id = d.id WHERE c.san_pham_id = ? AND d.trang_thai NOT IN ('Hoàn thành', 'Đã hủy')''', (id,)).fetchone()
    if don_hang_dang_chua:
        conn.close()
        return f"<script>alert('SẾP KHOAN XÓA! Sản phẩm này đang nằm trong Đơn hàng #{don_hang_dang_chua['id']}. Vui lòng Hủy đơn hoặc Hoàn thành đơn trước khi xóa.'); window.location.href='/admin';</script>"

    sp = conn.execute('SELECT hinh_anh FROM san_pham WHERE id=?', (id,)).fetchone()
    if sp and sp['hinh_anh']:
        try: os.remove(os.path.join(current_app.root_path, sp['hinh_anh'].lstrip('/')))
        except: pass
    anh_phus = conn.execute('SELECT du_ong_dan FROM hinh_anh_sp WHERE san_pham_id=?', (id,)).fetchall()
    for anh in anh_phus:
        try: os.remove(os.path.join(current_app.root_path, anh['du_ong_dan'].lstrip('/')))
        except: pass

    conn.execute('DELETE FROM san_pham WHERE id=?', (id,))
    conn.execute('DELETE FROM hinh_anh_sp WHERE san_pham_id=?', (id,))
    conn.execute('DELETE FROM lo_hang_nhap WHERE san_pham_id=?', (id,))
    conn.commit(); conn.close()
    return redirect('/admin')

@admin_bp.route('/admin/cong-no-nguon')
def cong_no_nguon():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    nguons = conn.execute('SELECT * FROM nguon_nhap').fetchall()
    tu_khoa = request.args.get('tu_khoa', '')
    nguon_id = request.args.get('nguon_id', '')
    kieu_hang = request.args.get('kieu_hang', '')
    trang_thai_loc = request.args.get('trang_thai_loc', '')
    sap_xep = request.args.get('sap_xep', 'uu_tien_no')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    
    query = """
        SELECT l.id, l.san_pham_id, l.nguon_nhap_id, l.so_luong_nhap, l.gia_nhap, l.tien_da_tra_nguon, l.trang_thai_nhap, l.ngay_du_kien_ve, l.ngay_tao,
               s.ten, s.hinh_anh, s.kieu_hang, n.ten_nguon 
        FROM lo_hang_nhap l 
        JOIN san_pham s ON l.san_pham_id = s.id 
        LEFT JOIN nguon_nhap n ON l.nguon_nhap_id = n.id 
        WHERE 1=1
    """
    params = []
    
    if tu_khoa: query += " AND s.ten LIKE ?"; params.append(f'%{tu_khoa}%')
    if nguon_id: query += " AND l.nguon_nhap_id = ?"; params.append(nguon_id)
    if kieu_hang: query += " AND s.kieu_hang = ?"; params.append(kieu_hang)
    if trang_thai_loc: query += " AND l.trang_thai_nhap = ?"; params.append(trang_thai_loc)
        
    total_items = conn.execute("SELECT COUNT(*) FROM (" + query + ")", params).fetchone()[0]
    total_pages = (total_items + per_page - 1) // per_page
    
    if sap_xep == 'moi_nhat': query += " ORDER BY l.id DESC LIMIT ? OFFSET ?"
    elif sap_xep == 'cu_nhat': query += " ORDER BY l.id ASC LIMIT ? OFFSET ?"
    else: query += " ORDER BY CASE WHEN l.trang_thai_nhap = 'Còn nợ' THEN 1 ELSE 2 END, l.id DESC LIMIT ? OFFSET ?"
        
    params.extend([per_page, offset])
    items = conn.execute(query, params).fetchall()
    
    tong_no_query = """
        SELECT SUM(l.gia_nhap * l.so_luong_nhap - l.tien_da_tra_nguon) 
        FROM lo_hang_nhap l JOIN san_pham s ON l.san_pham_id = s.id WHERE l.trang_thai_nhap = 'Còn nợ'
    """
    tong_no_params = []
    if tu_khoa: tong_no_query += " AND s.ten LIKE ?"; tong_no_params.append(f'%{tu_khoa}%')
    if nguon_id: tong_no_query += " AND l.nguon_nhap_id = ?"; tong_no_params.append(nguon_id)
    if kieu_hang: tong_no_query += " AND s.kieu_hang = ?"; tong_no_params.append(kieu_hang)
        
    tong_no_result = conn.execute(tong_no_query, tong_no_params).fetchone()[0]
    tong_no = tong_no_result if tong_no_result else 0
    conn.close()
    return render_template('cong_no_nguon.html', items=items, nguons=nguons, tong_no=tong_no, page=page, tong_trang=total_pages, nguon_chon=nguon_id, kieu_chon=kieu_hang, trang_thai_loc=trang_thai_loc, sap_xep_chon=sap_xep, tu_khoa=tu_khoa)

@admin_bp.route('/admin/xuat-excel-nguon/<int:nguon_id>')
def xuat_excel_nguon(nguon_id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    logs = conn.execute('''
        SELECT l.so_tien, l.ngay_tra, s.ten as ten_sp 
        FROM lich_su_tra_nguon l 
        JOIN lo_hang_nhap lo ON l.lo_hang_id = lo.id 
        JOIN san_pham s ON lo.san_pham_id = s.id 
        WHERE lo.nguon_nhap_id = ? ORDER BY l.id DESC
    ''', (nguon_id,)).fetchall()
    ten_nguon = conn.execute("SELECT ten_nguon FROM nguon_nhap WHERE id = ?", (nguon_id,)).fetchone()
    conn.close()
    if not ten_nguon: return "Không tìm thấy nguồn", 404
    output = io.StringIO(); output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(['Ngày Chuyển Khoản', 'Sản Phẩm', 'Số Tiền Đã Chuyển (VNĐ)'])
    for l in logs: writer.writerow([l['ngay_tra'], l['ten_sp'], l['so_tien']])
    safe_name = secure_filename(ten_nguon['ten_nguon'])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=LichSu_ChuyenTien_{safe_name}.csv"})

@admin_bp.route('/admin/cap-nhat-tra-tien/<int:lo_id>', methods=['POST'])
def cap_nhat_tra_tien(lo_id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    lo = conn.execute('SELECT gia_nhap, so_luong_nhap, tien_da_tra_nguon, san_pham_id FROM lo_hang_nhap WHERE id=?', (lo_id,)).fetchone()
    so_tien_nhap_vao = float(request.form.get('so_tien', 0))
    hanh_dong = request.form.get('hanh_dong')
    
    if hanh_dong == 'cong':
        tien_moi = lo['tien_da_tra_nguon'] + so_tien_nhap_vao
        tien_ghi_log = so_tien_nhap_vao
    else:
        tien_moi = so_tien_nhap_vao
        tien_ghi_log = tien_moi - lo['tien_da_tra_nguon']
        
    if tien_ghi_log > 0:
        conn.execute('INSERT INTO lich_su_tra_nguon (san_pham_id, lo_hang_id, so_tien) VALUES (?, ?, ?)', (lo['san_pham_id'], lo_id, tien_ghi_log))
        
    tong_nhap = lo['gia_nhap'] * lo['so_luong_nhap']
    trang_thai = request.form.get('trang_thai', 'Còn nợ')
    if tien_moi >= tong_nhap: trang_thai = 'Đã thanh toán'
        
    conn.execute('UPDATE lo_hang_nhap SET tien_da_tra_nguon=?, trang_thai_nhap=?, ngay_du_kien_ve=? WHERE id=?', (tien_moi, trang_thai, request.form.get('ngay_ve', ''), lo_id))
    conn.commit(); conn.close()
    return redirect(request.referrer or '/admin/cong-no-nguon')

@admin_bp.route('/api/lich-su-tra-nguon/<int:lo_id>')
def api_lich_su_tra_nguon(lo_id):
    if 'admin_id' not in session: return jsonify([])
    conn = ket_noi_db()
    logs = conn.execute('SELECT so_tien, ngay_tra FROM lich_su_tra_nguon WHERE lo_hang_id = ? ORDER BY id DESC', (lo_id,)).fetchall()
    conn.close()
    return jsonify([{'so_tien': "{:,.0f}".format(l['so_tien']), 'ngay_tra': l['ngay_tra']} for l in logs])

@admin_bp.route('/api/lich-su-nguon/<int:nguon_id>')
def api_lich_su_nguon(nguon_id):
    if 'admin_id' not in session: return jsonify([])
    conn = ket_noi_db()
    logs = conn.execute('''
        SELECT l.so_tien, l.ngay_tra, s.ten as ten_sp 
        FROM lich_su_tra_nguon l JOIN lo_hang_nhap lo ON l.lo_hang_id = lo.id 
        JOIN san_pham s ON lo.san_pham_id = s.id 
        WHERE lo.nguon_nhap_id = ? ORDER BY l.id DESC
    ''', (nguon_id,)).fetchall()
    conn.close()
    return jsonify([{'so_tien': "{:,.0f}".format(l['so_tien']), 'ngay_tra': l['ngay_tra'], 'ten_sp': l['ten_sp']} for l in logs])

@admin_bp.route('/admin/nguon-nhap', methods=['GET', 'POST'])
def quan_ly_nguon_nhap():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    if request.method == 'POST':
        conn.execute('INSERT INTO nguon_nhap (ten_nguon) VALUES (?)', (request.form['ten_nguon'],)); conn.commit()
    ngs = conn.execute('SELECT * FROM nguon_nhap').fetchall(); conn.close()
    return render_template('quan_ly_nguon.html', nguons=ngs)

@admin_bp.route('/admin/hang-sx', methods=['GET', 'POST'])
def quan_ly_hang_sx():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    if request.method == 'POST':
        conn.execute('INSERT INTO hang_sx_list (ten_hang) VALUES (?)', (request.form['ten_hang'],)); conn.commit()
    hgs = conn.execute('SELECT * FROM hang_sx_list').fetchall(); conn.close()
    return render_template('quan_ly_hang.html', hangs=hgs)

@admin_bp.route('/danh-muc', methods=['GET', 'POST'])
def quan_ly_danh_muc():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    if request.method == 'POST':
        conn.execute('INSERT INTO danh_muc (ten_danh_muc) VALUES (?)', (request.form['ten_danh_muc'],)); conn.commit()
    dms = conn.execute('SELECT * FROM danh_muc').fetchall(); conn.close()
    return render_template('danh_muc.html', danh_mucs=dms)

@admin_bp.route('/xoa-danh-muc/<int:id>', methods=['POST'])
def xoa_danh_muc(id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db(); conn.execute('DELETE FROM danh_muc WHERE id=?', (id,)); conn.commit(); conn.close()
    return redirect('/danh-muc')

@admin_bp.route('/xoa-hang/<int:id>', methods=['POST'])
def xoa_hang(id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db(); conn.execute('DELETE FROM hang_sx_list WHERE id=?', (id,)); conn.commit(); conn.close()
    return redirect('/admin/hang-sx')

@admin_bp.route('/xoa-nguon/<int:id>', methods=['POST'])
def xoa_nguon(id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db(); conn.execute('DELETE FROM nguon_nhap WHERE id=?', (id,)); conn.commit(); conn.close()
    return redirect('/admin/nguon-nhap')

@admin_bp.route('/admin/xuat-excel-don-hang')
def xuat_excel_don_hang():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    dhs = conn.execute("SELECT id, ten_khach, sdt, dia_chi, tong_tien, tien_da_tra, ngay_dat, trang_thai FROM don_hang ORDER BY id DESC").fetchall()
    conn.close()
    output = io.StringIO(); output.write('\ufeff')
    writer = csv.writer(output)
    writer.writerow(['Mã Đơn', 'Tên Khách', 'Số Điện Thoại', 'Địa Chỉ', 'Tổng Bill (VNĐ)', 'Đã Thu (VNĐ)', 'Khách Còn Nợ (VNĐ)', 'Ngày Đặt', 'Trạng Thái'])
    for dh in dhs: writer.writerow([dh['id'], dh['ten_khach'], dh['sdt'], dh['dia_chi'], dh['tong_tien'], dh['tien_da_tra'], dh['tong_tien'] - dh['tien_da_tra'], dh['ngay_dat'], dh['trang_thai']])
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": "attachment;filename=Bao_Cao_Don_Hang.csv"})

@admin_bp.route('/admin/don-hang', methods=['GET', 'POST'])
def quan_ly_don_hang():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    if request.method == 'POST':
        conn.execute('UPDATE don_hang SET trang_thai = ?, tien_da_tra = ? WHERE id = ?', (request.form['trang_thai'], request.form.get('tien_da_tra', 0), request.form['don_id']))
        conn.commit(); return redirect('/admin/don-hang')

    tu_khoa = request.args.get('tu_khoa', '')
    trang_thai_loc = request.args.get('trang_thai', '')
    sap_xep = request.args.get('sap_xep', 'moi_nhat')
    page = request.args.get('page', 1, type=int)
    per_page = 10 
    
    cau_lenh_base = ' FROM don_hang WHERE 1=1'
    dk = []
    if tu_khoa:
        cau_lenh_base += ' AND (ten_khach LIKE ? OR sdt LIKE ? OR id LIKE ? OR id IN (SELECT don_hang_id FROM chi_tiet_don c JOIN san_pham s ON c.san_pham_id = s.id WHERE s.ten LIKE ?))'
        dk.extend([f'%{tu_khoa}%', f'%{tu_khoa}%', f'%{tu_khoa}%', f'%{tu_khoa}%'])
    if trang_thai_loc: cau_lenh_base += ' AND trang_thai = ?'; dk.append(trang_thai_loc)

    total_rev = conn.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai = 'Hoàn thành'").fetchone()[0] or 0
    total_debt = conn.execute("SELECT SUM(tong_tien - tien_da_tra) FROM don_hang WHERE trang_thai != 'Đã hủy'").fetchone()[0] or 0
    pending_count = conn.execute("SELECT COUNT(id) FROM don_hang WHERE trang_thai = 'Chờ xử lý'").fetchone()[0] or 0

    tong_don = conn.execute('SELECT COUNT(id)' + cau_lenh_base, dk).fetchone()[0]
    tong_trang = (tong_don + per_page - 1) // per_page

    cau_lenh = 'SELECT *' + cau_lenh_base
    if sap_xep == 'moi_nhat': cau_lenh += ' ORDER BY id DESC'
    elif sap_xep == 'cu_nhat': cau_lenh += ' ORDER BY id ASC'
    elif sap_xep == 'tien_cao': cau_lenh += ' ORDER BY tong_tien DESC'
    
    cau_lenh += ' LIMIT ? OFFSET ?'; dk.extend([per_page, (page - 1) * per_page])
    don_hangs = conn.execute(cau_lenh, dk).fetchall()
    
    don_hangs_full = []
    for dh in don_hangs:
        dh_dict = dict(dh)
        dh_dict['ds_mat_hang'] = conn.execute('SELECT c.*, s.ten, s.hinh_anh, s.kieu_hang, s.ngay_phat_hanh FROM chi_tiet_don c JOIN san_pham s ON c.san_pham_id = s.id WHERE c.don_hang_id = ?', (dh['id'],)).fetchall()
        don_hangs_full.append(dh_dict)
    conn.close()
    return render_template('quan_ly_don.html', don_hangs=don_hangs_full, trang_thai_chon=trang_thai_loc, sap_xep_chon=sap_xep, tu_khoa=tu_khoa, page=page, tong_trang=tong_trang, total_rev=total_rev, total_debt=total_debt, pending_count=pending_count)

@admin_bp.route('/admin/khach-hang', methods=['GET', 'POST'])
def quan_ly_khach_hang():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    if request.method == 'POST':
        kh_id = request.form.get('kh_id')
        mat_khau_nhap = request.form['mat_khau']
        nhom_khach = request.form.get('nhom_khach', 'Thường')
        ghi_chu = request.form.get('ghi_chu', '')
        if not mat_khau_nhap.startswith('scrypt:'): mat_khau_nhap = generate_password_hash(mat_khau_nhap)
        if kh_id: conn.execute('UPDATE khach_hang SET ho_ten=?, tai_khoan=?, sdt=?, dia_chi=?, mat_khau=?, nhom_khach=?, ghi_chu=? WHERE id=?', (request.form['ho_ten'], request.form['tai_khoan'], request.form['sdt'], request.form['dia_chi'], mat_khau_nhap, nhom_khach, ghi_chu, kh_id))
        else: 
            try: conn.execute('INSERT INTO khach_hang (ho_ten, tai_khoan, mat_khau, sdt, dia_chi, nhom_khach, ghi_chu) VALUES (?,?,?,?,?,?,?)', (request.form['ho_ten'], request.form['tai_khoan'], mat_khau_nhap, request.form['sdt'], request.form['dia_chi'], nhom_khach, ghi_chu))
            except: pass
        conn.commit(); return redirect('/admin/khach-hang')

    tu_khoa = request.args.get('tu_khoa', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    query_count = "SELECT COUNT(*) FROM khach_hang k"
    query = "SELECT k.*, COUNT(DISTINCT d.id) as so_don, IFNULL(SUM(CASE WHEN d.trang_thai != 'Đã hủy' THEN d.tong_tien ELSE 0 END), 0) as tong_mua, IFNULL(SUM(CASE WHEN d.trang_thai != 'Đã hủy' THEN d.tien_da_tra ELSE 0 END), 0) as da_tra FROM khach_hang k LEFT JOIN don_hang d ON k.id = d.khach_hang_id"
    params = []
    if tu_khoa:
        where_clause = " WHERE k.ho_ten LIKE ? OR k.tai_khoan LIKE ? OR k.sdt LIKE ?"
        query_count += where_clause; query += where_clause; params = [f'%{tu_khoa}%', f'%{tu_khoa}%', f'%{tu_khoa}%']
        
    tong_khach = conn.execute(query_count, params).fetchone()[0]
    tong_trang = (tong_khach + per_page - 1) // per_page
    query += " GROUP BY k.id ORDER BY k.id DESC LIMIT ? OFFSET ?"; params.extend([per_page, (page - 1) * per_page])
    khachs = conn.execute(query, params).fetchall()
    
    thong_ke_tong = conn.execute("SELECT COUNT(DISTINCT k.id) as total_khach, IFNULL(SUM(CASE WHEN d.trang_thai != 'Đã hủy' THEN d.tong_tien ELSE 0 END), 0) as total_bill, IFNULL(SUM(CASE WHEN d.trang_thai != 'Đã hủy' THEN d.tien_da_tra ELSE 0 END), 0) as total_paid FROM khach_hang k LEFT JOIN don_hang d ON k.id = d.khach_hang_id").fetchone()
    conn.close()
    return render_template('quan_ly_khach.html', khachs=khachs, tu_khoa=tu_khoa, page=page, tong_trang=tong_trang, thong_ke_tong=thong_ke_tong)

@admin_bp.route('/admin/xoa-khach-hang/<int:id>')
def xoa_khach_hang(id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    kh = conn.execute('SELECT vai_tro FROM khach_hang WHERE id = ?', (id,)).fetchone()
    if kh and kh['vai_tro'] == 'admin':
        conn.close(); return "<script>alert('Sếp không thể xóa tài khoản Admin ở đây!'); window.location.href='/admin/khach-hang';</script>"
    conn.execute('DELETE FROM khach_hang WHERE id = ?', (id,)); conn.commit(); conn.close()
    return redirect('/admin/khach-hang')

@admin_bp.route('/admin/khach-hang/<int:id>')
def chi_tiet_khach(id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    khach = conn.execute('SELECT * FROM khach_hang WHERE id = ?', (id,)).fetchone()
    if not khach: conn.close(); abort(404)
    thong_ke = conn.execute("SELECT COUNT(id) as so_don, IFNULL(SUM(CASE WHEN trang_thai != 'Đã hủy' THEN tong_tien ELSE 0 END), 0) as tong_mua, IFNULL(SUM(CASE WHEN trang_thai != 'Đã hủy' THEN tien_da_tra ELSE 0 END), 0) as tong_tra FROM don_hang WHERE khach_hang_id = ?", (id,)).fetchone()
    don_hangs = conn.execute('SELECT * FROM don_hang WHERE khach_hang_id = ? ORDER BY id DESC', (id,)).fetchall()
    conn.close()
    return render_template('chi_tiet_khach.html', khach=khach, thong_ke=thong_ke, don_hangs=don_hangs)

@admin_bp.route('/admin/cap-nhat-don/<int:id>', methods=['POST'])
def cap_nhat_don(id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    dh = conn.execute('SELECT tong_tien, tien_da_tra FROM don_hang WHERE id=?', (id,)).fetchone()
    so_tien_nhap = float(request.form.get('so_tien', 0))
    tien_moi = dh['tien_da_tra'] + so_tien_nhap if request.form.get('hanh_dong', 'cong') == 'cong' else so_tien_nhap
    trang_thai = 'Hoàn thành' if tien_moi >= dh['tong_tien'] else request.form.get('trang_thai')
    conn.execute('UPDATE don_hang SET trang_thai=?, tien_da_tra=? WHERE id=?', (trang_thai, tien_moi, id))
    conn.commit(); conn.close()
    return redirect('/admin/don-hang')

@admin_bp.route('/admin/huy-don/<int:id>')
def huy_don(id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    dh = conn.execute('SELECT trang_thai FROM don_hang WHERE id = ?', (id,)).fetchone()
    if dh and dh['trang_thai'] != 'Đã hủy':
        items = conn.execute('SELECT san_pham_id, so_luong FROM chi_tiet_don WHERE don_hang_id = ?', (id,)).fetchall()
        for item in items: conn.execute('UPDATE san_pham SET so_luong = so_luong + ? WHERE id = ?', (item['so_luong'], item['san_pham_id']))
        conn.execute('UPDATE don_hang SET trang_thai = "Đã hủy" WHERE id = ?', (id,)); conn.commit()
    conn.close()
    return redirect(request.referrer or '/admin/don-hang')

@admin_bp.route('/admin/don-hang/<int:id>', methods=['GET', 'POST'])
@admin_bp.route('/admin/don-hang/<int:id>', methods=['GET', 'POST'])
def xem_sua_don_hang(id):
    khach_id = session.get('khach_id'); admin_id = session.get('admin_id')
    if not admin_id and not khach_id: return redirect('/dang-nhap')
    conn = ket_noi_db()
    dh = conn.execute('SELECT * FROM don_hang WHERE id = ?', (id,)).fetchone()
    if not dh: conn.close(); abort(404)
    if not admin_id and dh['khach_hang_id'] != khach_id: conn.close(); return "<script>alert('Sếp không có quyền xem đơn của người khác!'); window.history.back();</script>"

    if request.method == 'POST' and admin_id:
        # --- LOGIC SANG TÊN ĐỔI CHỦ ---
        if request.form.get('hanh_dong') == 'sang_ten':
            khach_id_moi = request.form.get('khach_id_moi')
            khach_moi = conn.execute('SELECT ho_ten, sdt, dia_chi FROM khach_hang WHERE id = ?', (khach_id_moi,)).fetchone()
            if khach_moi:
                conn.execute('UPDATE don_hang SET khach_hang_id = ?, ten_khach = ?, sdt = ?, dia_chi = ? WHERE id = ?', 
                             (khach_id_moi, khach_moi['ho_ten'], khach_moi['sdt'], khach_moi['dia_chi'], id))
                conn.commit()
                flash(f'Đã sang tên đơn hàng #{id} thành công cho khách {khach_moi["ho_ten"]}!', 'success')
            conn.close()
            return redirect(f'/admin/don-hang/{id}')
            
        # --- LOGIC CẬP NHẬT TIỀN VÀ KHO NHƯ CŨ ---
        tong_tien_moi = float(request.form.get('tong_tien', 0))
        tien_da_tra_moi = float(request.form.get('tien_da_tra', 0))
        trang_thai_moi = request.form['trang_thai']
        ghi_chu_moi = request.form.get('ghi_chu', '')
        
        if tien_da_tra_moi >= tong_tien_moi and trang_thai_moi in ['Chờ xử lý', 'Đã cọc', 'Hàng về - Chờ TT', 'Đang giao hàng']:
            trang_thai_moi = 'Hoàn thành'
            
        dh_old = conn.execute('SELECT trang_thai FROM don_hang WHERE id = ?', (id,)).fetchone()
        
        if dh_old['trang_thai'] not in ['Đã hủy', 'Hủy - Thu cọc'] and trang_thai_moi in ['Đã hủy', 'Hủy - Thu cọc']:
            items = conn.execute('SELECT san_pham_id, so_luong FROM chi_tiet_don WHERE don_hang_id = ?', (id,)).fetchall()
            for item in items: conn.execute('UPDATE san_pham SET so_luong = so_luong + ? WHERE id = ?', (item['so_luong'], item['san_pham_id']))
            
        elif dh_old['trang_thai'] in ['Đã hủy', 'Hủy - Thu cọc'] and trang_thai_moi not in ['Đã hủy', 'Hủy - Thu cọc']:
            items = conn.execute('SELECT san_pham_id, so_luong FROM chi_tiet_don WHERE don_hang_id = ?', (id,)).fetchall()
            for item in items: conn.execute('UPDATE san_pham SET so_luong = so_luong - ? WHERE id = ?', (item['so_luong'], item['san_pham_id']))

        conn.execute('UPDATE don_hang SET trang_thai = ?, tien_da_tra = ?, tong_tien = ?, ghi_chu = ? WHERE id = ?', (trang_thai_moi, tien_da_tra_moi, tong_tien_moi, ghi_chu_moi, id))
        conn.commit(); conn.close()
        flash(f'Đã cập nhật tài chính đơn hàng #{id} thành công!', 'success')
        return redirect('/admin/don-hang')

    items = conn.execute('SELECT c.*, s.ten, s.hinh_anh, s.hang_sx FROM chi_tiet_don c JOIN san_pham s ON c.san_pham_id = s.id WHERE c.don_hang_id = ?', (id,)).fetchall()
    khach_info = conn.execute('SELECT nhom_khach, ghi_chu FROM khach_hang WHERE id = ?', (dh['khach_hang_id'],)).fetchone()
    
    # Truyền thêm danh sách toàn bộ khách hàng để làm Menu chọn lúc Sang Tên
    khachs_all = conn.execute('SELECT id, ho_ten, sdt FROM khach_hang ORDER BY ho_ten ASC').fetchall()
    conn.close()
    
    return render_template('chi_tiet_don.html', dh=dh, items=items, khach_info=khach_info, khachs_all=khachs_all)

@admin_bp.route('/admin/in-hoa-don/<int:id>')
def in_hoa_don(id):
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    dh = conn.execute('SELECT * FROM don_hang WHERE id = ?', (id,)).fetchone()
    if not dh: conn.close(); abort(404)
    items = conn.execute('SELECT c.*, s.ten FROM chi_tiet_don c JOIN san_pham s ON c.san_pham_id = s.id WHERE c.don_hang_id = ?', (id,)).fetchall()
    conn.close()
    return render_template('in_hoa_don.html', dh=dh, items=items)

@admin_bp.route('/admin/thong-ke')
def thong_ke():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    
    # Nhận bộ lọc từ giao diện
    nam = request.args.get('nam', '')
    thang = request.args.get('thang', '')
    try: thue_pct = float(request.args.get('thue_pct', 2))
    except: thue_pct = 2.0
    
    where_clause = " WHERE d.trang_thai = 'Hoàn thành'"
    params = []
    if nam:
        where_clause += " AND strftime('%Y', d.ngay_dat) = ?"
        params.append(nam)
    if thang:
        where_clause += " AND strftime('%m', d.ngay_dat) = ?"
        params.append(thang)
        
    # 1. Tính tổng doanh thu thực tế
    dt_row = conn.execute(f"SELECT SUM(d.tong_tien) FROM don_hang d {where_clause}", params).fetchone()
    doanh_thu = dt_row[0] if dt_row and dt_row[0] else 0
    
    # 2. Tính giá vốn hàng bán dựa trên Lô Nhập thực tế
    cogs_query = f"""
        SELECT SUM(c.so_luong * IFNULL((SELECT gia_nhap FROM lo_hang_nhap WHERE san_pham_id = c.san_pham_id ORDER BY id DESC LIMIT 1), s.gia_nhap))
        FROM chi_tiet_don c
        JOIN san_pham s ON c.san_pham_id = s.id
        JOIN don_hang d ON c.don_hang_id = d.id
        {where_clause}
    """
    cogs_row = conn.execute(cogs_query, params).fetchone()
    gia_von = cogs_row[0] if cogs_row and cogs_row[0] else 0
    
    loi_nhuan_gop = doanh_thu - gia_von
    thue_phai_tra = doanh_thu * (thue_pct / 100)
    loi_nhuan_rong = loi_nhuan_gop - thue_phai_tra
    
    # Số đơn chờ xử lý toàn tiệm
    sd = conn.execute("SELECT COUNT(*) FROM don_hang WHERE trang_thai='Chờ xử lý'").fetchone()[0] or 0
    
    # 3. Xử lý dữ liệu Biểu đồ thích ứng động
    chart_labels = []
    chart_data = []
    
    if nam and thang:
        days_in_month = 31
        if thang in ['04', '06', '09', '11']: days_in_month = 30
        elif thang == '02':
            y_int = int(nam)
            days_in_month = 29 if (y_int % 4 == 0 and (y_int % 100 != 0 or y_int % 400 == 0)) else 28
            
        for day in range(1, days_in_month + 1):
            day_str = f"{day:02d}"
            full_date = f"{nam}-{thang}-{day_str}"
            chart_labels.append(f"Ngày {day_str}")
            r = conn.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai='Hoàn thành' AND DATE(ngay_dat) = ?", (full_date,)).fetchone()
            chart_data.append(r[0] or 0)
            
    elif nam and not thang:
        for m in range(1, 13):
            m_str = f"{m:02d}"
            chart_labels.append(f"Tháng {m_str}")
            r = conn.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai='Hoàn thành' AND strftime('%Y-%m', ngay_dat) = ?", (f"{nam}-{m_str}",)).fetchone()
            chart_data.append(r[0] or 0)
            
    else:
        import datetime
        for i in range(6, -1, -1):
            ngay_str = (datetime.date.today() - datetime.timedelta(days=i)).strftime('%Y-%m-%d')
            chart_labels.append(ngay_str)
            row = conn.execute("SELECT SUM(tong_tien) FROM don_hang WHERE trang_thai='Hoàn thành' AND DATE(ngay_dat) = ?", (ngay_str,)).fetchone()
            chart_data.append(row[0] or 0)
            
    # Top sản phẩm bán chạy trong kỳ lọc
    top_query = f"""
        SELECT s.ten, SUM(c.so_luong) as total_qty 
        FROM chi_tiet_don c 
        JOIN san_pham s ON c.san_pham_id = s.id 
        JOIN don_hang d ON c.don_hang_id = d.id 
        {where_clause}
        GROUP BY s.id ORDER BY total_qty DESC LIMIT 5
    """
    top_products = conn.execute(top_query, params).fetchall()
    years_list = conn.execute("SELECT DISTINCT strftime('%Y', ngay_dat) as y FROM don_hang WHERE ngay_dat IS NOT NULL ORDER BY y DESC").fetchall()
    
    conn.close()
    return render_template('thong_ke.html', 
                           doanh_thu=doanh_thu, gia_von=gia_von, loi_nhuan_gop=loi_nhuan_gop,
                           thue_vat=thue_phai_tra, loi_nhuan_rong=loi_nhuan_rong, so_don_moi=sd,
                           labels=json.dumps(chart_labels), values=json.dumps(chart_data), 
                           top_sps=top_products, years_list=years_list,
                           nam_chon=nam, thang_chon=thang, thue_pct=thue_pct)

@admin_bp.route('/admin/xuat-excel-thong-ke')
def xuat_excel_thong_ke():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    conn = ket_noi_db()
    
    nam = request.args.get('nam', '')
    thang = request.args.get('thang', '')
    try: thue_pct = float(request.args.get('thue_pct', 3))
    except: thue_pct = 3.0
    
    where_clause = " WHERE d.trang_thai = 'Hoàn thành'"
    params = []
    filename_part = "Toan_Thoi_Gian"
    if nam:
        where_clause += " AND strftime('%Y', d.ngay_dat) = ?"
        params.append(nam); filename_part = f"Nam_{nam}"
    if thang:
        where_clause += " AND strftime('%m', d.ngay_dat) = ?"
        params.append(thang); filename_part += f"_Thang_{thang}"
        
    query = f"""
        SELECT d.id as don_id, d.ngay_dat, d.ten_khach, d.tong_tien,
        (SELECT SUM(c.so_luong * IFNULL((SELECT gia_nhap FROM lo_hang_nhap WHERE san_pham_id = c.san_pham_id ORDER BY id DESC LIMIT 1), s.gia_nhap)) 
         FROM chi_tiet_don c JOIN san_pham s ON c.san_pham_id = s.id WHERE c.don_hang_id = d.id) as don_gia_von
        FROM don_hang d
        {where_clause}
        ORDER BY d.id DESC
    """
    orders = conn.execute(query, params).fetchall()
    conn.close()
    
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output)
    
    writer.writerow(['BÁO CÁO DOANH SỐ VÀ TÀI CHÍNH CHI TIẾT - TAKIMITSU HOBBY'])
    writer.writerow([f'Kỳ báo cáo: {filename_part.replace("_", " ")}'])
    writer.writerow([f'Tỷ lệ thuế: {thue_pct}%'])
    writer.writerow([])
    writer.writerow(['Mã Đơn', 'Ngày Đặt', 'Tên Khách Hàng', 'Doanh Thu (VNĐ)', 'Giá Vốn Kho (VNĐ)', 'Lợi Nhuận Gộp (VNĐ)', 'Thuế Phải Nộp (VNĐ)', 'Lợi Nhuận Ròng (VNĐ)'])
    
    tong_dt, tong_von, tong_gop, tong_thue, tong_rong = 0, 0, 0, 0, 0
    for o in orders:
        dt = o['tong_tien'] or 0
        von = o['don_gia_von'] or 0
        gop = dt - von
        thue = dt * (thue_pct / 100)
        rong = gop - thue
        
        tong_dt += dt; tong_von += von; tong_gop += gop; tong_thue += thue; tong_rong += rong
        writer.writerow([f"#{o['don_id']}", o['ngay_dat'], o['ten_khach'], dt, von, gop, thue, rong])
        
    writer.writerow([])
    writer.writerow(['TỔNG KẾT KỲ LỌC', '', '', tong_dt, tong_von, tong_gop, tong_thue, tong_rong])
    
    return Response(output.getvalue(), mimetype="text/csv", headers={"Content-Disposition": f"attachment;filename=BaoCao_TaiChinh_{filename_part}.csv"})

@admin_bp.route('/admin/cai-dat', methods=['GET', 'POST'])
def cai_dat_giao_dien():
    if 'admin_id' not in session: return redirect('/dang-nhap')
    settings = get_settings()
    conn = ket_noi_db()
    
    if request.method == 'POST':
        hanh_dong = request.form.get('hanh_dong')
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
            
            for i in range(1, 6): settings[f'banner_{i}'] = xu_ly_anh(f'banner_{i}_file', settings.get(f'banner_{i}'))
            for i in range(1, 4): settings[f'video_{i}'] = request.form.get(f'video_{i}', '')
            if not settings.get('video_1') and settings.get('video_trang_chu'): settings['video_1'] = settings.get('video_trang_chu')

            save_settings(settings); flash('Đã lưu Cấu Hình Chung thành công!', 'success')

        elif hanh_dong == 'luu_chinh_sach':
            settings['cs_cua_hang'] = request.form.get('cs_cua_hang', '')
            settings['cs_doi_tra'] = request.form.get('cs_doi_tra', '')
            settings['cs_van_chuyen'] = request.form.get('cs_van_chuyen', '')
            settings['hd_mua_hang'] = request.form.get('hd_mua_hang', '')
            save_settings(settings); flash('Đã lưu Nội dung Chính Sách!', 'success')

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
            
            save_settings(settings); flash('Đã lưu các Banner Topics Hàng Về!', 'success')
            
        elif hanh_dong == 'them_menu':
            conn.execute('INSERT INTO menu_item (cot, nhom, icon_nhom, ten_link, url, badge_html) VALUES (?,?,?,?,?,?)', (request.form['cot'], request.form['nhom'], request.form['icon_nhom'], request.form['ten_link'], request.form['url'], request.form.get('badge_html','')))
            conn.commit(); flash('Đã thêm link vào Menu!', 'success')
            
        elif hanh_dong == 'xoa_menu':
            conn.execute('DELETE FROM menu_item WHERE id=?', (request.form['id'],))
            conn.commit(); flash('Đã xóa link khỏi Menu!', 'success')
            
        conn.close()
        return redirect('/admin/cai-dat')
        
    try: items = conn.execute('SELECT * FROM menu_item ORDER BY cot ASC, id ASC').fetchall()
    except: items = []
    conn.close()
    return render_template('cai_dat.html', settings=settings, items=items)