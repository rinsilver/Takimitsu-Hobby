from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, abort, Response
from database.db import ket_noi_db, get_settings, hashids,tao_slug

client_bp = Blueprint('client', __name__)

@client_bp.route('/')
def index():
    conn = ket_noi_db()
    san_phams = conn.execute('SELECT * FROM san_pham ORDER BY id DESC LIMIT 8').fetchall()
    hang_sxs_raw = conn.execute('SELECT DISTINCT hang_sx FROM san_pham WHERE hang_sx IS NOT NULL AND hang_sx != "" LIMIT 8').fetchall()
    danh_sach_hang = [h['hang_sx'] for h in hang_sxs_raw]
    hang_co_san = conn.execute("SELECT * FROM san_pham WHERE kieu_hang = 'Co san' ORDER BY id DESC LIMIT 12").fetchall()
    hang_order = conn.execute("SELECT * FROM san_pham WHERE kieu_hang = 'Pre-order' ORDER BY id DESC LIMIT 12").fetchall()
    
    return render_template('index.html', san_phams=san_phams, hang_sxs=danh_sach_hang, hang_co_san=hang_co_san, hang_order=hang_order)

@client_bp.route('/thong-tin/<slug>')
def trang_thong_tin(slug):
    settings = get_settings()
    danh_sach_trang = {
        'chinh-sach-cua-hang': {'title': 'Chính sách cửa hàng', 'json_key': 'cs_cua_hang'},
        'chinh-sach-doi-tra': {'title': 'Chính sách đổi trả', 'json_key': 'cs_doi_tra'},
        'chinh-sach-van-chuyen': {'title': 'Chính sách vận chuyển', 'json_key': 'cs_van_chuyen'},
        'huong-dan-mua-hang': {'title': 'Hướng dẫn mua hàng', 'json_key': 'hd_mua_hang'}
    }
    if slug not in danh_sach_trang: return "Không tìm thấy trang", 404
    thong_tin_trang = danh_sach_trang[slug]
    noi_dung = settings.get(thong_tin_trang['json_key'], '')
    if not noi_dung: noi_dung = "Nội dung đang được cập nhật."
    return render_template('trang_thong_tin.html', tieu_de=thong_tin_trang['title'], noi_dung=noi_dung, settings=settings)

@client_bp.route('/san-pham/<string:slug_id>')
def chi_tiet_sp(slug_id):
    # Trích xuất mã ID ở cuối URL (VD: mo-hinh-luffy-8L -> lấy 8L)
    hash_id = slug_id.split('-')[-1]
    
    decoded = hashids.decode(hash_id)
    if not decoded: abort(404)
    id = decoded[0]
    
    conn = ket_noi_db()
    sp = conn.execute('SELECT * FROM san_pham WHERE id = ?', (id,)).fetchone()
    if not sp: 
        abort(404)
    # Lấy số lượng đã bán thực tế (Loại trừ đơn Đã hủy)
    da_ban = conn.execute("SELECT SUM(c.so_luong) FROM chi_tiet_don c JOIN don_hang d ON c.don_hang_id = d.id WHERE c.san_pham_id = ? AND d.trang_thai != 'Đã hủy'", (id,)).fetchone()[0] or 0
    
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

    if id in da_xem_ids: da_xem_ids.remove(id)
    da_xem_ids.insert(0, id)
    if len(da_xem_ids) > 11: da_xem_ids.pop()
        
    session['da_xem'] = da_xem_ids; session.modified = True
    
    
    return render_template('chi_tiet.html', sp=sp, anh_phu=anh_phu, san_pham_lien_quan=san_pham_lien_quan, tieu_de_goi_y=tieu_de_goi_y, san_pham_da_xem=san_pham_da_xem, da_ban=da_ban)

@client_bp.route('/them-vao-gio/<string:hash_id>')
def them_vao_gio(hash_id):
    decoded = hashids.decode(hash_id)
    if not decoded: return redirect(url_for('client.index'))
    id = decoded[0]

    conn = ket_noi_db()
    sp = conn.execute('SELECT * FROM san_pham WHERE id=?', (id,)).fetchone()
    
    if not sp: return redirect(url_for('client.index'))

    hinh_thuc = request.args.get('hinh_thuc', 'san')
    loai = request.args.get('loai', 'new')
    
    key_gia = f"gia_{hinh_thuc}_{loai}"
    gia_chon = sp[key_gia] if key_gia in sp.keys() else sp['gia_ban']
        
    if gia_chon <= 0: return redirect(url_for('client.chi_tiet_sp', hash_id=hash_id))
    if hinh_thuc == 'san' and sp['so_luong'] <= 0:
        flash('Mặt hàng này hiện đã hết hàng sẵn trong kho!', 'danger')
        return redirect(url_for('client.chi_tiet_sp', hash_id=hash_id))

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
    
    if not found: gio.append({'cart_id': cart_item_id, 'id': id, 'ten': ten_variant, 'gia': gia_chon, 'hinh_anh': sp['hinh_anh'], 'so_luong': 1})

    session['gio_hang'] = gio; session.modified = True
    return redirect(url_for('client.xem_gio_hang'))

@client_bp.route('/gio-hang')
def xem_gio_hang():
    gio = session.get('gio_hang', [])
    if isinstance(gio, dict) or (isinstance(gio, list) and len(gio) > 0 and not isinstance(gio[0], dict)): 
        gio = []
        session['gio_hang'] = gio; session.modified = True
    tong_tien = sum(item['gia'] * item['so_luong'] for item in gio)
    return render_template('gio_hang.html', gio_hang=gio, tong_tien=tong_tien)

@client_bp.route('/cap-nhat-gio/<cart_id>/<hanh_dong>')
def cap_nhat_gio(cart_id, hanh_dong):
    gio = session.get('gio_hang', [])
    real_id = int(str(cart_id).split('_')[0]) if '_' in str(cart_id) else int(cart_id)
    conn = ket_noi_db()
    sp = conn.execute('SELECT so_luong FROM san_pham WHERE id=?', (real_id,)).fetchone()
    
    
    for item in gio:
        if item.get('cart_id', str(item['id'])) == cart_id:
            item.pop('error', None)
            if hanh_dong == 'tang':
                if sp and item['so_luong'] < sp['so_luong']: item['so_luong'] += 1
                else: item['error'] = "Tối đa rồi sếp ơi!"
            elif hanh_dong == 'giam' and item['so_luong'] > 1: item['so_luong'] -= 1
            break
    session['gio_hang'] = gio; session.modified = True
    return redirect(url_for('client.xem_gio_hang'))

@client_bp.route('/xoa-khoi-gio/<cart_id>')
def xoa_khoi_gio(cart_id):
    gio = session.get('gio_hang', [])
    gio = [item for item in gio if item.get('cart_id', str(item['id'])) != cart_id]
    session['gio_hang'] = gio; session.modified = True
    return redirect(url_for('client.xem_gio_hang'))

@client_bp.route('/san-pham')
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
    if tu_khoa: cau_lenh_base += ' AND ten LIKE ?'; dk.append(f'%{tu_khoa}%')
    if danh_muc_loc: cau_lenh_base += ' AND the_loai = ?'; dk.append(danh_muc_loc)
    if hang_loc: cau_lenh_base += ' AND hang_sx = ?'; dk.append(hang_loc)
    if kieu_loc: cau_lenh_base += ' AND kieu_hang = ?'; dk.append(kieu_loc)
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
    

    if request.args.get('ajax') == '1':
        return render_template('partials_san_pham.html', san_phams=san_phams, page=page, tong_trang=tong_trang, dm_chon=danh_muc_loc, hang_chon=hang_loc, kieu_chon=kieu_loc, tu_khoa=tu_khoa, ton_kho_chon=ton_kho, sap_xep_chon=sap_xep)
    
    return render_template('tat_ca_san_pham.html', san_phams=san_phams, danh_mucs=danh_mucs, hangs=hangs, page=page, tong_trang=tong_trang, dm_chon=danh_muc_loc, hang_chon=hang_loc, kieu_chon=kieu_loc, tu_khoa=tu_khoa, ton_kho_chon=ton_kho, sap_xep_chon=sap_xep)

@client_bp.route('/thanh-toan', methods=['GET', 'POST'])
def thanh_toan():
    gio_hang = session.get('gio_hang', [])
    if not gio_hang: return redirect(url_for('client.xem_gio_hang'))
    tong_tien = sum(item['gia'] * item['so_luong'] for item in gio_hang)
    conn = ket_noi_db()
    danh_sach_khach = conn.execute('SELECT id, ho_ten, sdt FROM khach_hang ORDER BY ho_ten ASC').fetchall()
    
    if request.method == 'POST':
        ten_khach = request.form['ten']
        sdt = request.form['sdt']
        dia_chi = request.form['dia_chi']
        
        tien_da_tra = 0
        if session.get('admin_id'):
            try: tien_da_tra = float(request.form.get('tien_da_tra', 0))
            except: tien_da_tra = 0
            
        khach_id = session.get('khach_id')
        if session.get('admin_id'):
            kh_chon = request.form.get('khach_id_duoc_chon')
            if kh_chon: khach_id = kh_chon
            
        cur = conn.cursor()
        # --- THÊM CHỐT CHẶN KIỂM TRA LẠI KHO TRƯỚC KHI LÊN ĐƠN ---
        for item in gio_hang:
            if '_san_' in item.get('cart_id', ''):
                # Ép DB trừ kho ngay lập tức VÀ phải đảm bảo kho >= số lượng mua
                cur.execute('UPDATE san_pham SET so_luong = so_luong - ? WHERE id = ? AND so_luong >= ?', (item['so_luong'], item['id'], item['so_luong']))
                
                # Nếu lệnh Update thất bại (Rowcount = 0) nghĩa là kho không đủ!
                if cur.rowcount == 0:
                    conn.rollback() # Hủy bỏ toàn bộ giao dịch, không tạo đơn
                    flash(f"Mặt hàng {item['ten']} vừa bị khách khác chốt mất tích tắc! Kho không đủ số lượng. Vui lòng kiểm tra lại giỏ hàng.", "danger")
                    return redirect(url_for('client.xem_gio_hang'))
                
        # Nếu vượt qua hết vòng lặp trên thì kho đủ, bắt đầu tạo hóa đơn
        if not khach_id:
            kh_db = cur.execute('SELECT id FROM khach_hang WHERE sdt = ?', (sdt,)).fetchone()
            if kh_db: khach_id = kh_db['id']
            else: khach_id = 0

        trang_thai = 'Hoàn thành' if tien_da_tra >= tong_tien and tong_tien > 0 else 'Chờ xử lý'
        if tien_da_tra > 0 and trang_thai != 'Hoàn thành':
            trang_thai = 'Đã cọc'

        ghi_chu = request.form.get('ghi_chu', '')
        
        cur.execute('INSERT INTO don_hang (khach_hang_id, ten_khach, sdt, dia_chi, tong_tien, tien_da_tra, trang_thai, ghi_chu) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', (khach_id, ten_khach, sdt, dia_chi, tong_tien, tien_da_tra, trang_thai, ghi_chu))
        don_id = cur.lastrowid
        
        for item in gio_hang:
            cur.execute('INSERT INTO chi_tiet_don (don_hang_id, san_pham_id, ten_sp, hinh_anh_sp, so_luong, gia) VALUES (?, ?, ?, ?, ?, ?)', (don_id, item['id'], item['ten'], item['hinh_anh'], item['so_luong'], item['gia']))
            cur.execute('UPDATE san_pham SET so_luong = so_luong - ? WHERE id = ?', (item['so_luong'], item['id']))
            
        conn.commit(); 
        session['gio_hang'] = []; session.modified = True
        
        if session.get('admin_id'):
            flash(f'Đã lên đơn & Ghi nhận thanh toán thành công! Mã đơn: #{don_id}', 'success')
            return redirect('/admin/don-hang') # Fixed redirect for temporary bypass
        else:
            flash(f'Tuyệt vời! Bạn đã đặt hàng thành công. Mã đơn: #{don_id}', 'success')
            return redirect(url_for('client.ho_so_khach'))

    
    return render_template('thanh_toan.html', gio_hang=gio_hang, tong_tien=tong_tien, khachs=danh_sach_khach)

@client_bp.route('/ho-so')
def ho_so_khach():
    khach_id = session.get('khach_id')
    if not khach_id:
        if session.get('admin_id'): return redirect('/admin/khach-hang') 
        return redirect(url_for('auth.dang_nhap'))
        
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
    
    return render_template('ho_so.html', khach=khach, don_hangs=don_hangs_full, page=page, tong_trang=tong_trang)

@client_bp.route('/api/get-khach-info/<int:id>')
def get_khach_info(id):
    if 'admin_id' not in session: 
        return {"error": "Không có quyền truy cập!"}, 403
    
    conn = ket_noi_db()
    kh = conn.execute('SELECT ho_ten, sdt, dia_chi FROM khach_hang WHERE id = ?', (id,)).fetchone()
    
    if kh: return {"ho_ten": kh['ho_ten'], "sdt": kh['sdt'], "dia_chi": kh['dia_chi']}
    return {"error": "Không tìm thấy"}, 404

@client_bp.route('/api/search-products')
def search_products_api():
    tu_khoa = request.args.get('tu_khoa', '').strip()
    if len(tu_khoa) < 1: return jsonify({"keywords": [], "products": []})
    
    conn = ket_noi_db()
    # 1. Tìm các từ khóa gợi ý (Lấy tên gốc của sản phẩm)
    kw_rows = conn.execute("SELECT DISTINCT ten FROM san_pham WHERE ten LIKE ? LIMIT 3", (f'%{tu_khoa}%',)).fetchall()
    keywords = [row['ten'] for row in kw_rows]

    # 2. Tìm danh sách sản phẩm hiển thị
    sps = conn.execute("SELECT id, ten, hinh_anh, gia_ban, kieu_hang FROM san_pham WHERE ten LIKE ? LIMIT 5", (f'%{tu_khoa}%',)).fetchall()
    
    
    ket_qua = []
    for sp in sps:
        ket_qua.append({
            "id": hashids.encode(sp['id']), 
            "ten": sp['ten'], 
            "hinh_anh": sp['hinh_anh'], 
            "gia": "{:,.0f}".format(sp['gia_ban']), 
            "status": sp['kieu_hang'],
            "slug": tao_slug(sp['ten'])
        })
    return jsonify({"keywords": keywords, "products": ket_qua})

# --- VŨ KHÍ SEO: TỰ ĐỘNG TẠO SITEMAP.XML CHO GOOGLE BOT ---
@client_bp.route('/sitemap.xml')
def sitemap():
    conn = ket_noi_db()
    sps = conn.execute("SELECT id, ten FROM san_pham ORDER BY id DESC").fetchall()
    
    
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    
    base_url = request.url_root.rstrip('/')
    
    # Khai báo các trang tĩnh quan trọng
    pages = ['/', '/san-pham', '/thong-tin/chinh-sach-cua-hang', '/thong-tin/chinh-sach-doi-tra', '/thong-tin/chinh-sach-van-chuyen', '/thong-tin/huong-dan-mua-hang']
    for p in pages:
        xml += f'  <url>\n    <loc>{base_url}{p}</loc>\n    <changefreq>daily</changefreq>\n    <priority>0.9</priority>\n  </url>\n'
        
    # Khai báo toàn bộ link Sản phẩm
    for sp in sps:
        slug = tao_slug(sp['ten'])
        hash_id = hashids.encode(sp['id'])
        xml += f'  <url>\n    <loc>{base_url}/san-pham/{slug}-{hash_id}</loc>\n    <changefreq>weekly</changefreq>\n    <priority>0.8</priority>\n  </url>\n'
        
    xml += '</urlset>'
    return Response(xml, mimetype='application/xml')

@client_bp.route('/tra-cuu', methods=['GET', 'POST'])
def tra_cuu():
    if request.method == 'POST':
        sdt = request.form.get('sdt', '').strip()
        ma_don = request.form.get('ma_don', '').strip()
        conn = ket_noi_db()
        dh = conn.execute('SELECT * FROM don_hang WHERE id = ? AND sdt = ?', (ma_don, sdt)).fetchone()
        if not dh:
            
            flash('Không tìm thấy đơn hàng! Vui lòng kiểm tra lại Mã đơn và SĐT.', 'danger')
            return redirect('/tra-cuu')
        
        items = conn.execute('SELECT c.*, s.ten, s.hinh_anh, s.hang_sx FROM chi_tiet_don c JOIN san_pham s ON c.san_pham_id = s.id WHERE c.don_hang_id = ?', (ma_don,)).fetchall()
        
        return render_template('tra_cuu.html', dh=dh, items=items)
        
    return render_template('tra_cuu.html')

# --- CHỈ ĐƯỜNG CHO GOOGLE BOT (ROBOTS.TXT) ---
@client_bp.route('/robots.txt')
def robots():
    base_url = request.url_root.rstrip('/')
    # Chặn Bot mò vào các trang Admin bảo mật, chỉ đường đến file Sitemap
    txt = f"User-agent: *\nDisallow: /admin/\nDisallow: /thanh-toan\nDisallow: /dang-nhap\n\nSitemap: {base_url}/sitemap.xml"
    return Response(txt, mimetype='text/plain')
    