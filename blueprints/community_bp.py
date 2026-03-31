# blueprints/community_bp.py

import uuid
import os
import jwt
from functools import wraps
from flask import Blueprint, request, current_app, render_template, jsonify, url_for, flash, redirect
from werkzeug.utils import secure_filename

from models import db, User, Question, Subtopic, Course, MailingList
from utils import allowed_file

# --- Opsiyonel Token Kontrolü için Özel Dekoratör ---
def token_optional(f):
    """
    Bu özel dekoratör, Authorization başlığında geçerli bir token varsa kullanıcıyı
    bulur ve view fonksiyonuna bir argüman olarak geçer. Token yoksa veya geçersizse
    argüman olarak None geçer, böylece sayfa halka açık kalmaya devam eder.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
            try:
                data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
                user_id = data.get('user_id')
                if user_id:
                    found_user = User.query.get(user_id)
                    # Sadece aktif kullanıcıları geçerli say
                    if found_user and found_user.is_active:
                         user = found_user
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                # Geçersiz veya süresi dolmuş token'ı görmezden gel, kullanıcı None olarak kalır
                pass
        # Bulunan kullanıcıyı (veya None'ı) view fonksiyonuna ilk argüman olarak gönder
        return f(user, *args, **kwargs)
    return decorated_function


community_bp = Blueprint('community_bp', __name__,
                         url_prefix='/community',
                         template_folder='../templates')

@community_bp.route('/add-question', methods=['GET'])
@token_optional # Yeni dekoratörü uygula
def add_question_form(user): # 'user' nesnesi artık dekoratörden argüman olarak geliyor
    """
    Kullanıcıların soru ekleyebileceği HTML formunu gösterir.
    """
    try:
        courses = Course.query.order_by(Course.name).all()
        subtopics_by_course = {}
        all_subtopics = Subtopic.query.order_by(Subtopic.name).all()
        for st in all_subtopics:
            if st.course_id not in subtopics_by_course:
                subtopics_by_course[st.course_id] = []
            subtopics_by_course[st.course_id].append({'id': st.id, 'name': st.name})
    except Exception as e:
        current_app.logger.error(f"Soru ekleme formu için veri çekme hatası: {e}")
        courses = []
        subtopics_by_course = {}

    return render_template('add_question.html',
                           title="Topluluğa Soru Ekle",
                           courses=courses,
                           subtopics_by_course=subtopics_by_course,
                           user=user)


@community_bp.route('/submit-question', methods=['POST'])
@token_optional # Yeni dekoratörü uygula
def submit_question_handler(user): # 'user' nesnesi artık dekoratörden argüman olarak geliyor
    """
    Topluluk soru ekleme formundan gelen veriyi işler.
    """
    submitter = user  # Dekorator'den gelen kullanıcıyı al

    if not submitter:
        submitter = User.query.filter_by(username='mehmetalper04').first()

    if not submitter:
        return jsonify({'message': "Soru göndermek için varsayılan kullanıcı ('mehmetalper04') bulunamadı."}), 500

    required_fields = ['subtopic_id', 'text', 'option_a', 'option_b', 'option_c', 'option_d', 'option_e', 'correct_option']
    if not all(field in request.form for field in required_fields):
        missing = ", ".join(f for f in required_fields if f not in request.form)
        return jsonify({'message': f'Lütfen tüm zorunlu alanları doldurun. Eksik alan: {missing}'}), 400

    correct_option = request.form.get('correct_option', '').upper()
    if correct_option not in ['A', 'B', 'C', 'D', 'E']:
        return jsonify({'message': 'Geçersiz doğru seçenek. A, B, C, D veya E olmalıdır.'}), 400

    subtopic = Subtopic.query.get(request.form.get('subtopic_id'))
    if not subtopic:
        return jsonify({'message': 'Lütfen geçerli bir ders ve alt konu seçin.'}), 400

    filename = None
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename and allowed_file(file.filename):
            filename = secure_filename(f"{uuid.uuid4()}{os.path.splitext(file.filename)[1]}")
            try:
                file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
            except Exception as e:
                return jsonify({'message': 'Resim dosyası kaydedilirken bir hata oluştu.'}), 500
        elif file and file.filename:
            return jsonify({'message': 'İzin verilmeyen dosya türü. Lütfen .png, .jpg, .jpeg veya .gif formatında bir resim yükleyin.'}), 400

    is_premium_only = 'is_premium_only' in request.form

    try:
        new_question = Question(
            subtopic_id=subtopic.id, text=request.form['text'], option_a=request.form['option_a'],
            option_b=request.form['option_b'], option_c=request.form['option_c'],
            option_d=request.form['option_d'], option_e=request.form['option_e'],
            correct_option=correct_option, image_filename=filename, status='pending',
            submitted_by_user_id=submitter.id, user_id=submitter.id, is_premium_only=is_premium_only
        )
        db.session.add(new_question)
        db.session.commit()
        
        message = f"Sorunuz başarıyla onaya gönderildi! Katkınız için teşekkürler, {submitter.username}."
        return jsonify({'message': message}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Topluluk gönderimi - Soru ekleme hatası: {e}", exc_info=True)
        return jsonify({'message': 'Soru gönderilirken beklenmedik bir veritabanı hatası oluştu.'}), 500

@community_bp.route('/subscribe', methods=['GET'])
def subscribe_page():
    """
    Kullanıcıların e-posta bültenine abone olabileceği HTML sayfasını sunar.
    """
    return render_template('mailing_list_signup.html', title="Bültenimize Abone Olun")

@community_bp.route('/add-email', methods=['POST'])
def add_email_to_list():
    data = request.get_json()
    if not data or not data.get('email'):
        return jsonify({'message': 'E-posta adresi gereklidir.'}), 400
    email = data.get('email')
    if MailingList.query.filter_by(email=email).first():
        return jsonify({'message': f"Bu e-posta adresi zaten bültenimize kayıtlı."}), 409
    try:
        new_entry = MailingList(email=email)
        db.session.add(new_entry)
        db.session.commit()
        return jsonify({'message': "Bültenimize başarıyla abone oldunuz! Teşekkürler."}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'message': 'E-posta kaydedilirken bir sunucu hatası oluştu.'}), 500
    

@community_bp.route('/unsubscribe', methods=['GET', 'POST'])
def unsubscribe_page():
    if request.method == 'POST':
        email_to_unsubscribe = request.form.get('email')
        if not email_to_unsubscribe:
            flash("Lütfen geçerli bir e-posta adresi girin.", "warning")
            return redirect(url_for('.unsubscribe_page'))

        try:
            mailing_entry = MailingList.query.filter_by(email=email_to_unsubscribe).first()
            if mailing_entry:
                db.session.delete(mailing_entry)
                db.session.commit()
                flash(f"'{email_to_unsubscribe}' adresi bülten listesinden başarıyla kaldırıldı.", "success")
                current_app.logger.info(f"Kullanıcı bültenden ayrıldı: {email_to_unsubscribe}")
            else:
                flash("Girdiğiniz e-posta adresi bülten listemizde bulunamadı.", "info")
            
            return redirect(url_for('.unsubscribe_page'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Abonelikten ayrılma hatası: {e}", exc_info=True)
            flash("İşlem sırasında beklenmedik bir hata oluştu. Lütfen daha sonra tekrar deneyin.", "danger")
            return redirect(url_for('.unsubscribe_page'))

    return render_template('unsubscribe.html', title="Bültenden Ayrıl")