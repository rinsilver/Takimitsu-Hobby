import sqlite3
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash

# Kết nối database giống hệt app.py
DB_NAME = 'database_v5.db'

def create_seed_data():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    print("🚀 Đang khởi tạo dữ liệu giả (Seed Data) cho Takimitsu Hobby...")

    # 1. TẠO DANH MỤC, HÃNG SẢN XUẤT, NGUỒN NHẬP
    danh_mucs = ['Action Figure', 'Statue', 'Model Kit', 'Nendoroid', 'Figma']
    hang_sxs = ['Bandai', 'Good Smile', 'Kotobukiya', 'Hot Toys', 'Banpresto', 'MegaHouse']
    nguon_nhaps = ['AmiAmi', 'HobbySearch', 'Amazon Japan', 'Mandarake']

    for dm in danh_mucs:
        cur.execute("INSERT INTO danh_muc (ten_danh_muc) VALUES (?)", (dm,))
    for h in hang_sxs:
        cur.execute("INSERT INTO hang_sx_list (ten_hang) VALUES (?)", (h,))
    for n in nguon_nhaps:
        cur.execute("INSERT INTO nguon_nhap (ten_nguon) VALUES (?)", (n,))
    
    print("✅ Đã tạo Danh mục, Hãng SX, Nguồn nhập.")

    # 2. TẠO KHÁCH HÀNG ẢO
    khach_hangs = [
        ('khach1', '123', 'Nguyễn Văn A', '0901111222', '123 Đường A, Quận 1, TP.HCM', 'khach'),
        ('khach2', '123', 'Trần Thị B', '0903333444', '456 Đường B, Quận 2, TP.HCM', 'khach'),
        ('khach3', '123', 'Lê Văn C', '0905555666', '789 Đường C, Quận 3, TP.HCM', 'khach'),
        ('khach4', '123', 'Phạm Thị D', '0907777888', '101 Đường D, Quận 4, TP.HCM', 'khach'),
        ('khach5', '123', 'Vũ Văn E', '0909999000', '202 Đường E, Quận 5, TP.HCM', 'khach')
    ]
    
    khach_ids = []
    for kh in khach_hangs:
        try:
            hashed_pw = generate_password_hash(kh[1])
            cur.execute('''INSERT INTO khach_hang (tai_khoan, mat_khau, ho_ten, sdt, dia_chi, vai_tro) 
                           VALUES (?,?,?,?,?,?)''', (kh[0], hashed_pw, kh[2], kh[3], kh[4], kh[5]))
            khach_ids.append(cur.lastrowid)
        except:
            pass # Bỏ qua nếu tài khoản bị trùng
            
    print(f"✅ Đã tạo {len(khach_ids)} khách hàng ảo.")

    # 3. TẠO SẢN PHẨM ẢO (Đa dạng trạng thái)
    ten_mo_hinhs = [
        "Son Goku Super Saiyan", "Monkey D. Luffy Gear 5", "Uzumaki Naruto Sage Mode", 
        "Roronoa Zoro Ashura", "Gojou Satoru Jujutsu Kaisen", "Hatsune Miku Symphony", 
        "Iron Man Mark 85", "Batman The Dark Knight", "Gundam Barbatos Lupus Rex", 
        "Nezuko Sakura Miku", "Eren Yeager Demon Form", "Levi Ackerman Final Season"
    ]
    
    san_pham_ids = []
    for i in range(25): # Tạo 25 sản phẩm
        ten = random.choice(ten_mo_hinhs) + f" Ver {random.randint(1, 100)}"
        the_loai = random.choice(danh_mucs)
        hang_sx = random.choice(hang_sxs)
        nguon_id = random.randint(1, len(nguon_nhaps))
        
        gia_nhap = random.randint(500, 3000) * 1000
        gia_ban = gia_nhap + random.randint(200, 1000) * 1000
        
        so_luong_nhap = random.randint(5, 50)
        so_luong_ton = random.randint(0, so_luong_nhap)
        
        kieu_hang = random.choice(['Co san', 'Pre-order'])
        trang_thai_nhap = random.choice(['Còn nợ', 'Đã thanh toán'])
        
        tien_da_tra_nguon = (gia_nhap * so_luong_nhap) if trang_thai_nhap == 'Đã thanh toán' else random.randint(0, gia_nhap * so_luong_nhap)
        
        hinh_anh = f"/static/uploads/Logo.jpg" # Dùng tạm Logo.jpg làm ảnh mặc định
        mo_ta = "Sản phẩm mô hình chính hãng cực xịn xò. Seed data tự động tạo."
        
        cur.execute('''INSERT INTO san_pham 
            (ten, the_loai, hang_sx, gia_nhap, gia_ban, so_luong, so_luong_nhap, 
            hinh_anh, mo_ta, kieu_hang, nguon_nhap_id, tien_da_tra_nguon, trang_thai_nhap, 
            gia_san_new, gia_san_likenew, gia_order_new, gia_order_likenew) 
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''', 
            (ten, the_loai, hang_sx, gia_nhap, gia_ban, so_luong_ton, so_luong_nhap, 
             hinh_anh, mo_ta, kieu_hang, nguon_id, tien_da_tra_nguon, trang_thai_nhap, 
             gia_ban, gia_ban - 200000, gia_ban - 100000, gia_ban - 300000))
        
        san_pham_ids.append(cur.lastrowid)

    print("✅ Đã tạo 25 sản phẩm mô hình (Có tồn kho, Hết hàng, Pre-order).")

    # 4. TẠO ĐƠN HÀNG ẢO CHO BÁO CÁO THỐNG KÊ (Rải rác trong 7 ngày qua)
    trang_thais = ['Chờ xử lý', 'Đã cọc', 'Đang giao hàng', 'Hoàn thành', 'Đã hủy']
    
    for _ in range(30): # Tạo 30 đơn hàng
        khach = random.choice(khach_hangs)
        kh_id = random.choice(khach_ids) if khach_ids else 1
        
        # Ngày tạo đơn: Random từ 7 ngày trước đến hôm nay để test biểu đồ
        ngay_dat = datetime.now() - timedelta(days=random.randint(0, 7))
        ngay_dat_str = ngay_dat.strftime("%Y-%m-%d %H:%M:%S")
        
        trang_thai = random.choice(trang_thais)
        
        cur.execute('''INSERT INTO don_hang (khach_hang_id, ten_khach, sdt, dia_chi, tong_tien, tien_da_tra, ngay_dat, trang_thai, email) 
                       VALUES (?,?,?,?,?,?,?,?,?)''', 
                    (kh_id, khach[2], khach[3], khach[4], 0, 0, ngay_dat_str, trang_thai, 'khachhang@gmail.com'))
        
        don_id = cur.lastrowid
        
        # Chọn ngẫu nhiên 1 đến 3 sản phẩm cho đơn này
        sp_trong_don = random.sample(san_pham_ids, random.randint(1, 3))
        tong_tien = 0
        
        for sp_id in sp_trong_don:
            sp = cur.execute('SELECT gia_ban FROM san_pham WHERE id=?', (sp_id,)).fetchone()
            so_luong_mua = random.randint(1, 3)
            gia = sp[0]
            tong_tien += (gia * so_luong_mua)
            
            cur.execute('INSERT INTO chi_tiet_don (don_hang_id, san_pham_id, so_luong, gia) VALUES (?,?,?,?)', 
                        (don_id, sp_id, so_luong_mua, gia))
        
        # Cập nhật lại tổng tiền đơn hàng và tiền đã trả
        tien_da_tra = tong_tien if trang_thai == 'Hoàn thành' else random.choice([0, tong_tien * 0.3])
        cur.execute('UPDATE don_hang SET tong_tien = ?, tien_da_tra = ? WHERE id = ?', (tong_tien, tien_da_tra, don_id))

    print("✅ Đã tạo 30 đơn hàng lịch sử rải rác trong 7 ngày để test Biểu đồ.")
    
    conn.commit()
    conn.close()
    print("🎉 HOÀN TẤT SEED DATA! Sếp hãy khởi động lại app.py và tận hưởng thành quả.")

if __name__ == '__main__':
    # Cảnh báo an toàn
    confirm = input("CẢNH BÁO: Thao tác này sẽ thêm rất nhiều dữ liệu rác vào Database của sếp. Sếp có chắc chắn muốn tiếp tục? (Y/N): ")
    if confirm.lower() == 'y':
        create_seed_data()
    else:
        print("Đã hủy thao tác.")