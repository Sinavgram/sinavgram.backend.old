# decorators.py
from functools import wraps
import jwt # PyJWT
from flask import request, jsonify, current_app, session, flash, redirect, url_for
from models import User # Import User model


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'message': 'Bearer token hatalı biçimlendirilmiş.'}), 401

        if not token:
            return jsonify({'message': 'Token eksik!'}), 401

        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            current_user_obj = User.query.get(data['user_id'])
            
            if not current_user_obj:
                raise Exception("Kullanıcı bulunamadı")
            if not current_user_obj.is_active:
                 return jsonify({'message': 'Hesabınız aktif değil.'}), 403

            # --- TOKEN VERSİYON KONTROLÜ ---
            # Token içindeki versiyon ile veritabanındaki versiyonu karşılaştır.
            token_version_from_payload = data.get('ver', -1)
            if current_user_obj.token_version != token_version_from_payload:
                return jsonify({
                    'message': 'Oturum zaman aşımına uğradı veya sonlandırıldı. Lütfen tekrar giriş yapın.', 
                    'code': 'SESSION_INVALIDATED'
                }), 401
            # --- KONTROL SONU ---

        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token süresi dolmuş!'}), 401
        except Exception as e:
            current_app.logger.error(f"Token doğrulama hatası: {e}")
            return jsonify({'message': 'Token geçersiz!'}), 401

        return f(current_user_obj, *args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            flash('Bu sayfaya erişmek için admin girişi yapmanız gerekmektedir.', 'warning')
            return redirect(url_for('auth_bp.admin_login')) # Updated blueprint name

        admin_user_from_session = User.query.get(session['admin_id'])

        if not admin_user_from_session or not admin_user_from_session.is_admin:
            flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
            session.pop('admin_id', None)
            return redirect(url_for('auth_bp.admin_login')) # Updated blueprint name

        if not admin_user_from_session.is_active:
            flash('Hesabınız aktif değil. Bu sayfaya erişim yetkiniz yok.', 'danger')
            session.pop('admin_id', None)
            current_app.logger.warning(f"Devre dışı bırakılmış admin ({admin_user_from_session.username}) yetkili bir sayfaya erişmeye çalıştı.")
            return redirect(url_for('auth_bp.admin_login')) # Updated blueprint name

        return f(admin_user_from_session, *args, **kwargs)
    return decorated