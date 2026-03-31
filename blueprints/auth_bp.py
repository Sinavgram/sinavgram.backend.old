# blueprints/auth_bp.py
import html
from flask import Blueprint, request, jsonify, url_for, current_app, render_template, flash, session, redirect
from datetime import datetime, timedelta, timezone
import jwt # PyJWT
from werkzeug.security import generate_password_hash

from models import db, User
from utils import send_verification_email, send_password_reset_email, generate_verification_code, send_admin_login_code_email, send_new_login_notification_email
from decorators import admin_required # For admin_logout

auth_bp = Blueprint('auth_bp', __name__, url_prefix='/api/auth')
admin_auth_bp = Blueprint('admin_auth_bp', __name__, url_prefix='/admin') # For admin login/logout html routes

@auth_bp.route('/register', methods=['POST'])
def register_user_api():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('email') or not data.get('password'):
        return jsonify({'message': 'Kullanıcı adı, e-posta ve şifre gereklidir.'}), 400
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Bu kullanıcı adı zaten alınmış.'}), 409
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Bu e-posta adresi zaten kayıtlı.'}), 409
    if len(data['password']) < 6:
        return jsonify({'message': 'Şifre en az 6 karakter olmalıdır.'}), 400

    user = User(username=data['username'], email=data['email'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    try:
        token = user.get_email_verification_token()
        # Ensure 'main_bp.verify_email_route_html' is the correct endpoint name after blueprinting
        verify_url = url_for('main_bp.verify_email_route_html', token=token, _external=True)
        send_verification_email(user.email, user.username, verify_url)
    except Exception as e:
        current_app.logger.error(f"Doğrulama e-postası gönderilemedi {user.email}: {e}")
    return jsonify({'message': 'Kullanıcı başarıyla kaydedildi. Lütfen e-postanızı doğrulayın. E-postayı görmüyorsanız, spam klasörünüzü kontrol edin.'}), 201

@auth_bp.route('/login', methods=['POST'])
def login_user_api():
    data = request.get_json()
    identifier = data.get('identifier') or data.get('email')
    password = data.get('password')
    
    if not data or not identifier or not password:
        return jsonify({'message': 'E-posta/Kullanıcı adı ve şifre gereklidir.'}), 400
    
    user = User.query.filter((User.email == identifier) | (User.username == identifier)).first()
    
    if not user or not user.check_password(password):
        return jsonify({'message': 'Geçersiz e-posta/kullanıcı adı veya şifre.'}), 401
    
    if not user.is_active:
        return jsonify({'message': 'Hesabınız devre dışı bırakılmış.'}), 403

    if not user.email_verified and not user.is_admin:
        return jsonify({'message': 'Hesap doğrulanmamış. Lütfen e-postanızı kontrol edin.','email_not_verified': True, 'email': user.email }), 403

    if user.is_premium and user.premium_expiration_date:
        exp_date_aware = user.premium_expiration_date
        if exp_date_aware.tzinfo is None or exp_date_aware.tzinfo.utcoffset(exp_date_aware) is None:
            exp_date_aware = exp_date_aware.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp_date_aware:
            user.is_premium = False
            
    # --- YENİ EKLENEN IP KONTROL MANTIĞI ---
    ip_address = request.remote_addr
    
    # known_ips alanı boşsa (ilk giriş), listeyi başlat ve IP'yi ekle
    if user.known_ips is None:
        user.known_ips = [ip_address]
    
    # Eğer IP adresi bilinenler arasında yoksa
    elif ip_address not in user.known_ips:
        # Yeni IP'yi listeye ekle
        user.known_ips.append(ip_address)
        
        # Kullanıcıya bildirim gönder
        invalidation_token = user.generate_invalidation_token()
        invalidation_url = url_for('auth_bp.invalidate_sessions', token=invalidation_token, _external=True)
        send_new_login_notification_email(user, ip_address, invalidation_url)

    # JWT Token'ı oluştururken versiyon bilgisini de ekle
    token = jwt.encode({
        'user_id': user.id, 
        'is_admin': user.is_admin,
        'ver': user.token_version, # <<< TOKEN VERSİYONU EKLENDİ
        'exp': datetime.now(timezone.utc) + timedelta(days=180)
    }, current_app.config['SECRET_KEY'], algorithm="HS256")
    
    db.session.commit() # IP adresi veya token değişikliklerini kaydet
    
    return jsonify({
        'message': 'Giriş başarılı.', 
        'token': token, 
        'user': {
            'id': user.id, 'username': user.username, 'email': user.email, 'is_admin': user.is_admin,
            'email_verified': user.email_verified, 'score': user.score, 'is_premium': user.is_premium,
            'has_active_premium': user.has_active_premium, 'is_active': user.is_active,
            'premium_expiration_date': user.premium_expiration_date.isoformat() if user.premium_expiration_date else None
        }
    }), 200

@auth_bp.route('/invalidate-sessions/<token>', methods=['GET'])
def invalidate_sessions(token):
    """
    E-postadaki linke tıklandığında tüm oturumları geçersiz kılar ve
    kullanıcıyı şifre sıfırlamaya yönlendirir.
    """
    # Güvenlik token'ına göre kullanıcıyı bul
    user = User.query.filter_by(security_token=token).first()

    # Token geçerli mi ve süresi dolmamış mı kontrol et
    if not user or user.security_token_expiration < datetime.now(timezone.utc):
        flash("Bu güvenlik bağlantısı geçersiz veya süresi dolmuş. Lütfen yeni bir şifre sıfırlama isteğinde bulunun.", "warning")
        return redirect(url_for('main_bp.index_page')) # Ana sayfaya yönlendir

    # Token versiyonunu artırarak tüm eski oturumları geçersiz kıl
    user.token_version += 1
    # Güvenlik token'ını tek kullanımlık yapmak için sıfırla
    user.security_token = None
    user.security_token_expiration = None
    
    db.session.commit()

    # Yeni bir şifre sıfırlama token'ı oluştur ve kullanıcıyı yönlendir
    reset_token = user.get_password_reset_token()
    reset_url = url_for('main_bp.web_set_new_password_form', token=reset_token, _external=True)
    
    flash("Hesap güvenliğiniz için tüm aktif girişler sonlandırıldı. Lütfen şimdi şifrenizi yenileyin.", "success")
    return redirect(reset_url)

@auth_bp.route('/password-reset/request', methods=['POST'])
def request_password_reset_api():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'message': 'E-posta adresi gereklidir.'}), 400

    user = User.query.filter_by(email=email).first()
    if user:
        if not user.is_active:
            current_app.logger.info(f"Aktif olmayan kullanıcı ({email}) için şifre sıfırlama isteği alındı.")
        try:
            reset_token = user.get_password_reset_token()
            # Ensure 'main_bp.web_set_new_password_form' is correct
            reset_url_for_email = url_for('main_bp.web_set_new_password_form', token=reset_token, _external=True)
            send_password_reset_email(user.email, user.username, reset_url_for_email)
            return jsonify({'message': 'Şifre sıfırlama talimatları e-posta adresinize gönderildi.'}), 200
        except Exception as e:
            current_app.logger.error(f"Şifre sıfırlama e-postası gönderilemedi {user.email}: {e}")
            return jsonify({'message': 'Şifre sıfırlama e-postası gönderilirken bir hata oluştu.'}), 500
    else:
        return jsonify({'message': 'Bu e-posta adresi ile kayıtlı kullanıcı bulunamadı.'}), 404

@auth_bp.route('/password-reset/set-new', methods=['POST'])
def set_new_password_api():
    data = request.get_json()
    token = data.get('token')
    new_password = data.get('new_password')

    if not token or not new_password:
        return jsonify({'message': 'Token ve yeni şifre gereklidir.'}), 400
    if len(new_password) < 6:
        return jsonify({'message': 'Yeni şifre en az 6 karakter olmalıdır.'}), 400

    user = User.verify_password_reset_token(token)

    if not isinstance(user, User):
        if user == 'expired':
            return jsonify({'message': 'Şifre sıfırlama token süresi dolmuş. Lütfen işlemi tekrar başlatın.'}), 401
        return jsonify({'message': 'Geçersiz veya süresi dolmuş token. Şifre sıfırlama işlemi yapılamadı.'}), 400

    try:
        user.set_password(new_password)
        if not user.email_verified:
             user.email_verified = True
        db.session.commit()
        return jsonify({'message': 'Şifreniz başarıyla güncellendi. Şimdi yeni şifrenizle giriş yapabilirsiniz.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Yeni şifre ayarlanırken hata oluştu (Kullanıcı ID: {user.id}): {e}")
        return jsonify({'message': 'Şifre güncellenirken bir sunucu hatası oluştu.'}), 500

@auth_bp.route('/resend-verification-email', methods=['POST'])
def resend_verification_email_api():
    data = request.get_json()
    user_for_email = None
    current_user_obj_from_token = None

    auth_header = request.headers.get('Authorization')
    if auth_header:
        try:
            token = auth_header.split(" ")[1]
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"], options={"verify_exp": False})
            user_from_token = User.query.get(payload.get('user_id'))
            if user_from_token:
                current_user_obj_from_token = user_from_token
        except Exception:
            pass

    if current_user_obj_from_token:
        if current_user_obj_from_token.email_verified:
            return jsonify({'message': 'E-posta adresiniz zaten doğrulanmış.'}), 400
        user_for_email = current_user_obj_from_token
    elif data and data.get('email'):
        email_to_verify = data.get('email')
        user_for_email = User.query.filter_by(email=email_to_verify).first()
        if not user_for_email:
            return jsonify({'message': 'Bu e-posta adresi ile kayıtlı kullanıcı bulunamadı.'}), 404
        if user_for_email.email_verified:
            return jsonify({'message': 'Bu e-posta adresi zaten doğrulanmış.'}), 400
    else:
        return jsonify({'message': 'E-posta adresi veya geçerli bir kullanıcı token\'ı gereklidir.'}), 400

    try:
        verification_jwt_token = user_for_email.get_email_verification_token()
        # Ensure 'main_bp.verify_email_route_html' is correct
        verify_url = url_for('main_bp.verify_email_route_html', token=verification_jwt_token, _external=True)
        send_verification_email(user_for_email.email, user_for_email.username, verify_url)
        return jsonify({'message': f'{user_for_email.email} adresine yeni doğrulama e-postası gönderildi.'}), 200
    except Exception as e:
        current_app.logger.error(f"Doğrulama e-postası tekrar gönderilemedi {user_for_email.email}: {e}")
        return jsonify({'message': 'Doğrulama e-postası gönderilirken bir hata oluştu.'}), 500


# Admin login, verify code, logout (HTML routes)
@auth_bp.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if 'admin_id' in session:
        admin_user_session = User.query.get(session['admin_id'])
        if admin_user_session and admin_user_session.is_admin and admin_user_session.is_active:
            return redirect(url_for('admin_panel_bp.admin_dashboard')) # Updated blueprint name

    if request.method == 'GET' and 'admin_id_pending_verification' in session:
        session.pop('admin_id_pending_verification', None)
        session.pop('admin_verification_code', None)
        session.pop('admin_code_expiration_utc', None)
        session.pop('admin_email_for_code', None)
        flash('Doğrulama işlemi iptal edildi.', 'info')

    if request.method == 'POST':
        identifier = request.form.get('identifier')
        password = request.form.get('password')

        if not identifier or not password:
            flash('E-posta/Kullanıcı adı ve şifre gereklidir.', 'danger')
        else:
            user = User.query.filter(User.is_admin == True).filter(
                (User.email == identifier) | (User.username == identifier)
            ).first()

            if user and user.check_password(password):
                if not user.email_verified:
                    flash('Admin e-postanız doğrulanmamış. Lütfen sistem yöneticinizle iletişime geçin.', 'danger')
                    return render_template('admin/admin_login.html', title="Admin Girişi")

                if not user.is_active:
                    flash('Hesabınız devre dışı bırakılmış. Bu hesapla giriş yapamazsınız.', 'danger')
                    current_app.logger.warning(f"Devre dışı bırakılmış admin hesabı ({user.username}) için giriş denemesi.")
                    return render_template('admin/admin_login.html', title="Admin Girişi")

                verification_code = generate_verification_code()
                expiration_minutes = current_app.config['ADMIN_2FA_CODE_EXPIRATION_MINUTES']

                session['admin_id_pending_verification'] = user.id
                session['admin_verification_code'] = verification_code
                session['admin_code_expiration_utc'] = (datetime.now(timezone.utc) + timedelta(minutes=expiration_minutes)).isoformat()
                session['admin_email_for_code'] = user.email

                try:
                    send_admin_login_code_email(user.email, user.username, verification_code)
                    flash(f'{html.escape(user.email)} adresine bir doğrulama kodu gönderildi. Lütfen kodu giriniz.', 'info')
                    return redirect(url_for('auth_bp.admin_verify_code')) # Corrected to auth_bp
                except Exception as e:
                    current_app.logger.error(f"Admin giriş (2FA) kodu e-postası gönderilemedi {user.email}: {e}")
                    flash('Doğrulama kodu gönderilirken bir hata oluştu. Lütfen tekrar deneyin veya yönetici ile iletişime geçin.', 'danger')
            else:
                flash('Geçersiz yönetici kimlik bilgileri veya yetki yok.', 'danger')
    return render_template('admin/admin_login.html', title="Admin Girişi")

@auth_bp.route('/admin_verify_code', methods=['GET', 'POST']) # Changed to admin_auth_bp
def admin_verify_code():
    if 'admin_id' in session:
        return redirect(url_for('admin_panel_bp.admin_dashboard')) # Updated blueprint name

    if 'admin_id_pending_verification' not in session or \
       'admin_verification_code' not in session or \
       'admin_code_expiration_utc' not in session:
        flash('Doğrulama işlemi başlatılmamış veya oturum süresi dolmuş. Lütfen tekrar giriş yapın.', 'warning')
        return redirect(url_for('auth_bp.admin_login')) # Corrected

    admin_email_for_display = session.get('admin_email_for_code', 'kayıtlı e-posta adresinize')

    if request.method == 'POST':
        submitted_code = request.form.get('verification_code', '').strip()

        if not submitted_code:
            flash('Lütfen doğrulama kodunu giriniz.', 'danger')
            return render_template('admin/admin_verify_code.html', title="Admin Kod Doğrulama", email=admin_email_for_display)

        stored_code = session.get('admin_verification_code')
        expiration_str = session.get('admin_code_expiration_utc')
        expiration_utc = datetime.fromisoformat(expiration_str)

        if datetime.now(timezone.utc) > expiration_utc:
            session.pop('admin_id_pending_verification', None)
            session.pop('admin_verification_code', None)
            session.pop('admin_code_expiration_utc', None)
            session.pop('admin_email_for_code', None)
            flash('Doğrulama kodunun süresi dolmuş. Lütfen tekrar giriş yapın.', 'danger')
            return redirect(url_for('auth_bp.admin_login')) # Corrected

        if submitted_code == stored_code:
            admin_id_to_login = session['admin_id_pending_verification']
            user_to_login = User.query.get(admin_id_to_login)
            if not user_to_login or not user_to_login.is_admin or not user_to_login.is_active:
                flash('Hesabınızla ilgili bir sorun oluştu veya hesap aktif değil.', 'danger')
                # Clear session keys
                session.pop('admin_id_pending_verification', None)
                session.pop('admin_verification_code', None)
                session.pop('admin_code_expiration_utc', None)
                session.pop('admin_email_for_code', None)
                return redirect(url_for('auth_bp.admin_login'))


            session.pop('admin_id_pending_verification', None)
            session.pop('admin_verification_code', None)
            session.pop('admin_code_expiration_utc', None)
            session.pop('admin_email_for_code', None)

            session['admin_id'] = admin_id_to_login
            session.permanent = True # Already set in main app.py
            # app.permanent_session_lifetime = timedelta(days=7) # This is set in main app.py

            flash('Başarıyla doğrulandı ve giriş yaptınız!', 'success')
            return redirect(url_for('admin_panel_bp.admin_dashboard')) # Updated blueprint name
        else:
            flash('Geçersiz doğrulama kodu. Lütfen tekrar deneyin.', 'danger')

    return render_template('admin/admin_verify_code.html', title="Admin Kod Doğrulama", email=admin_email_for_display)

@auth_bp.route('/admin_logout') # Changed to admin_auth_bp
@admin_required # Ensure admin_required decorator uses the correct redirect
def admin_logout(current_admin_user): # current_admin_user is passed by @admin_required
    session.pop('admin_id_pending_verification', None)
    session.pop('admin_verification_code', None)
    session.pop('admin_code_expiration_utc', None)
    session.pop('admin_email_for_code', None)
    session.pop('admin_id', None)
    flash('Başarıyla çıkış yaptınız.', 'info')
    return redirect(url_for('auth_bp.admin_login')) # Corrected
    