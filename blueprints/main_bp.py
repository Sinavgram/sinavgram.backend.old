# blueprints/main_bp.py
import os
import html
from flask import Blueprint, Response, render_template, redirect, session, url_for, current_app, jsonify, request, send_from_directory, make_response
from datetime import datetime, timezone
from models import db, User, Question, Subtopic, Course # Add Course if needed by templates
from werkzeug.utils import secure_filename # For uploaded_file if it handles more generic uploads

main_bp = Blueprint('main_bp', __name__)

# --- Public Web Page Routes (HTML Sayfaları) ---
@main_bp.route('/')
def index_page(): return render_template('index.html')

@main_bp.route('/login')
def login_page(): return render_template('login.html')

@main_bp.route('/register')
def register_page(): return render_template('register.html')

@main_bp.route('/app-ads.txt')
def app_ads():
    content = render_template('app-ads.txt')
    return Response(content, mimetype='text/plain')

@main_bp.route('/web/password-reset-form/<token>', methods=['GET'])
def web_set_new_password_form(token):
    user_or_status = User.verify_password_reset_token(token)
    status_message = "Şifre sıfırlama bağlantısı geçersiz veya süresi dolmuş." # Default
    status_title = "Geçersiz Bağlantı" # Default

    if not isinstance(user_or_status, User):
        if user_or_status == 'expired':
            status_title = "Bağlantı Süresi Dolmuş"
            status_message = "Şifre sıfırlama bağlantısının süresi dolmuş. Lütfen şifre sıfırlama isteğini yeniden yapın."
        elif user_or_status == 'user_not_found_or_inactive':
            status_title = "Kullanıcı Hatası"
            status_message = "Bu bağlantıyla ilişkili kullanıcı bulunamadı veya hesap aktif değil."
        # Render an error page or pass error to template
        return render_template('set_new_password_web_form.html', # Or a dedicated error page
                               title=status_title,
                               error_message=status_message,
                               reset_token=None, # No valid token
                               api_base_url=current_app.config['API_BASE_URL'])

    return render_template('set_new_password_web_form.html',
                           title="Yeni Şifre Belirle",
                           reset_token=token,
                           api_base_url=current_app.config['API_BASE_URL'])


@main_bp.route('/verify-email/<token>')
def verify_email_route_html(token):
    user_or_status = User.verify_email_verification_token(token)
    status_message = ""
    status_icon = ""
    status_title = ""
    is_success = False
    user_username_escaped = "Kullanıcı" # Default

    if user_or_status == 'expired':
        status_title = "Bağlantı Süresi Dolmuş!"
        status_message = "Doğrulama bağlantısının süresi dolmuş."
        status_icon = "&#9200;"
    elif user_or_status == 'invalid' or user_or_status is None:
        status_title = "Doğrulama Başarısız!"
        status_message = "Geçersiz doğrulama bağlantısı."
        status_icon = "&#10060;"
    else: # User object
        user = user_or_status
        user_username_escaped = html.escape(user.username)
        is_success = True
        status_icon = "&#10004;"
        if user.email_verified:
            status_title = "E-posta Zaten Doğrulanmış!"
            status_message = f"Merhaba {user_username_escaped}, e-posta adresiniz zaten doğrulanmış."
        else:
            user.email_verified = True
            user.is_active = True
            db.session.commit()
            status_title = "E-posta Başarıyla Doğrulandı!"
            status_message = f"Merhaba {user_username_escaped}, e-posta adresiniz başarıyla doğrulandı ve hesabınız aktifleştirildi!"

    return render_template('email_verified_page.html',
                           status_title=status_title,
                           status_message=status_message,
                           status_icon=status_icon,
                           is_success=is_success,
                           app_deep_link=f"sinavgram://login")


@main_bp.route('/questions/share/<link_id>', methods=['GET'])
def get_shared_question_api_or_html(link_id):
    question = Question.query.filter_by(link_id=link_id, status='approved').first()
    if not question:
        if 'text/html' in request.accept_mimetypes:
            return render_template('shared_question_page.html', question=None, error_message="Soru bulunamadı veya onaylanmamış."), 404
        return jsonify({'message': 'Soru bulunamadı veya onaylanmamış.'}), 404

    subtopic_name = question.subtopic.name if question.subtopic else "Bilinmeyen Alt Konu"
    course_name = question.subtopic.course.name if question.subtopic and question.subtopic.course else "Bilinmeyen Ders"

    question_data = {
        'id': question.id,
        'text': question.text,
        'options': question.get_options_dict(),
        'image_url': question.get_image_url(), # Relies on uploaded_file_route being defined
        'link_id': question.link_id,
        'subtopic_name': subtopic_name,
        'course_name': course_name,
        'subtopic_id': question.subtopic_id
    }
    if 'text/html' in request.accept_mimetypes:
        return render_template('shared_question_page.html', question=question_data, app_deep_link=f"sinavgram://question/{question.link_id}")
    return jsonify(question_data), 200


@main_bp.route('/live')
def live_stats_page():
    total_users = User.query.count()
    now_utc = datetime.now(timezone.utc)
    active_premium_users = User.query.filter(
        User.is_premium == True,
        User.premium_expiration_date != None,
        User.premium_expiration_date > now_utc
    ).count()
    total_questions = Question.query.count()
    approved_questions_count = Question.query.filter_by(status='approved').count()
    total_premium_questions = Question.query.filter_by(is_premium_only=True, status='approved').count()

    top_10_users = User.query.filter(User.is_admin == False).order_by(User.score.desc()).limit(10).all()
    top_10_users_with_premium_status = []
    for user_stat in top_10_users:
        top_10_users_with_premium_status.append({
            'username': html.escape(user_stat.username),
            'score': user_stat.score,
            'is_premium': user_stat.has_active_premium
        })

    stats_data = {
        'total_users': total_users,
        'active_premium_users': active_premium_users,
        'total_questions': total_questions,
        'approved_questions_count': approved_questions_count,
        'total_premium_questions': total_premium_questions,
        'top_10_users': top_10_users_with_premium_status
    }

    admin_link_visible = False
    if 'admin_id' in session: # from flask import session
        admin_user_session = User.query.get(session['admin_id'])
        if admin_user_session and admin_user_session.is_admin and admin_user_session.is_active:
            admin_link_visible = True

    return render_template('live_stats.html', stats=stats_data, admin_user_link_visible=admin_link_visible)


# Static file serving for question images (and potentially avatars if stored similarly)
@main_bp.route('/static/uploads/question_images/<filename>')
def uploaded_file_route(filename): # Renamed to avoid conflict if 'uploaded_file' is used elsewhere
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

# Add a route for avatar images if they are in a different folder or need specific handling
@main_bp.route('/static/uploads/avatars/<filename>')
def avatar_file_route(filename):
    AVATAR_UPLOAD_FOLDER = os.path.join(current_app.config['UPLOAD_FOLDER_AVATARS'])
    if not os.path.exists(AVATAR_UPLOAD_FOLDER): os.makedirs(AVATAR_UPLOAD_FOLDER)
    return send_from_directory(AVATAR_UPLOAD_FOLDER, filename)