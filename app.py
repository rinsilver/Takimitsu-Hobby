import os
import webbrowser
from threading import Timer
from flask import Flask, session, render_template
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from database.db import tao_bang_va_cap_nhat, get_settings, get_mega_menu, hashids, tao_slug
from routes.auth import auth_bp
from routes.client import client_bp
from routes.admin import admin_bp

app = Flask(__name__)
# Tự động sinh một key mã hóa siêu mạnh mỗi khi web khởi động
app.secret_key = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 2592000  # Trình duyệt khách tự động lưu Cache ảnh 30 ngày (Siêu nhẹ Server)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- BẢO MẬT COOKIE & SESSION ---
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 1 ngày tự động đăng xuất

csrf = CSRFProtect(app)

# --- KHIÊN CHỐNG BRUTE-FORCE (Spam đăng nhập) ---
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# Tự động khởi tạo và cập nhật CSDL
tao_bang_va_cap_nhat()

# ĐĂNG KÝ CÁC BLUEPRINTS
app.register_blueprint(auth_bp)
app.register_blueprint(client_bp)
app.register_blueprint(admin_bp)

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
        mega_menu=get_mega_menu(),
        encode_id=lambda id: hashids.encode(id),
        tao_slug=tao_slug
    )

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    Timer(1.5, lambda: webbrowser.open_new('http://127.0.0.1:5000/')).start()
    app.run(debug=True)