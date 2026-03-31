# blueprints/admin_panel_bp.py
import os
import html
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
from sqlalchemy import or_
from models import db, User, Question, Subtopic, Course, QuestionReport, UserAnswer, MailingList
from decorators import admin_required # Uses the custom admin_required decorator
from utils import allowed_file # For image uploads
from models import MailingList
from utils import send_newsletter_broadcast

admin_panel_bp = Blueprint('admin_panel_bp', __name__, url_prefix='/admin', template_folder='../templates') # Specify template_folder

@admin_panel_bp.route('/') # Redirect /admin to /admin/dashboard
@admin_panel_bp.route('/dashboard')
@admin_required
def admin_dashboard(current_admin_user): # current_admin_user is passed by @admin_required
    pending_questions_count = Question.query.filter_by(status='pending').count()
    # Count new reports for questions that are not already rejected
    reported_questions_count = QuestionReport.query.join(Question, QuestionReport.question_id == Question.id)\
        .filter(QuestionReport.status == 'new', Question.status != 'rejected').count()

    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    now_utc = datetime.now(timezone.utc)
    active_premium_users = User.query.filter(
        User.is_premium == True, User.is_active == True, # Only active premium users
        User.premium_expiration_date != None, User.premium_expiration_date > now_utc
    ).count()
    total_questions = Question.query.count()
    approved_questions = Question.query.filter_by(status='approved').count()
    total_premium_questions = Question.query.filter_by(is_premium_only=True, status='approved').count()

    top_5_users = User.query.filter(User.is_admin == False, User.is_active == True).order_by(User.score.desc()).limit(5).all()
    top_5_users_data = [{'username': html.escape(u.username), 'score': u.score, 'is_premium': u.has_active_premium} for u in top_5_users]

    live_stats_summary = {
        'total_users': total_users, 'active_users': active_users,
        'active_premium_users': active_premium_users, 'total_questions': total_questions,
        'approved_questions': approved_questions, 'total_premium_questions': total_premium_questions,
        'top_5_users': top_5_users_data
    }
    # admin_user is already passed by context_processor or can be passed explicitly
    return render_template('admin/admin_dashboard.html', # Path will be admin/admin_dashboard.html
                           title="Admin Paneli", # admin_user=current_admin_user, (already in context)
                           pending_count=pending_questions_count,
                           reported_count=reported_questions_count,
                           live_stats=live_stats_summary)

@admin_panel_bp.route('/manage_users', methods=['GET'])
@admin_required
def admin_manage_users(current_admin_user):
    # Sadece ana adminin bu sayfaya erişebilmesi için yetki kontrolü
    if current_admin_user.username != 'mehmetalper04':
        flash('Bu sayfaya erişim yetkiniz yok.', 'danger')
        return redirect(url_for('admin_panel_bp.admin_dashboard'))

    try:
        # URL'den arama sorgusunu ve sayfa numarasını al
        search_query = request.args.get('q', '', type=str)
        page = request.args.get('page', 1, type=int)
        per_page = 15  # Sayfa başına gösterilecek kullanıcı sayısı

        # Temel sorgu objesini oluştur
        query = User.query

        # Eğer bir arama sorgusu varsa, kullanıcı adı veya e-posta sütununda filtrele
        if search_query:
            search_term = f"%{search_query}%"
            query = query.filter(or_(
                User.username.ilike(search_term),
                User.email.ilike(search_term)
            ))

        # Sorguyu sırala ve Flask-SQLAlchemy'nin paginate fonksiyonu ile sayfalara ayır
        pagination = query.order_by(
            User.is_admin.desc(), User.created_at.desc()
        ).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        users_list = pagination.items

    except Exception as e:
        current_app.logger.error(f"Kullanıcı yönetimi sayfası hatası: {e}")
        flash("Kullanıcılar listelenirken bir hata oluştu.", "danger")
        users_list = []
        pagination = None
        search_query = ''

    return render_template('admin/manage_users.html',
                           title="Kullanıcı Yönetimi",
                           users_list=users_list,
                           pagination=pagination,
                           search_query=search_query)

@admin_panel_bp.route('/manage_users/add_admin', methods=['GET', 'POST'])
@admin_required
def admin_add_new_admin_user(current_admin_user):
    if current_admin_user.username != 'mehmetalper04':
        flash('Sadece ana admin yeni admin kullanıcıları ekleyebilir.', 'danger')
        return redirect(url_for('admin_panel_bp.admin_dashboard'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not email or not password: flash('Kullanıcı adı, e-posta ve şifre alanları zorunludur.', 'danger')
        elif len(password) < 6: flash('Şifre en az 6 karakter olmalıdır.', 'danger')
        elif User.query.filter_by(username=username).first(): flash(f"'{username}' kullanıcı adı zaten mevcut.", 'danger')
        elif User.query.filter_by(email=email).first(): flash(f"'{email}' e-posta adresi zaten kullanılıyor.", 'danger')
        else:
            try:
                new_admin = User(username=username, email=email, is_admin=True, email_verified=True, is_active=True)
                new_admin.set_password(password)
                db.session.add(new_admin)
                db.session.commit()
                flash(f"'{username}' isimli yeni admin kullanıcısı başarıyla oluşturuldu.", 'success')
                return redirect(url_for('admin_panel_bp.admin_manage_users'))
            except Exception as e:
                db.session.rollback()
                flash(f"Yeni admin oluşturulurken bir veritabanı hatası oluştu: {str(e)}", 'danger')
                current_app.logger.error(f"Error creating new admin user via web: {e}")

    return render_template('admin/add_admin_user.html', title="Yeni Admin Ekle")


@admin_panel_bp.route('/toggle_user_status/<int:user_to_toggle_id>', methods=['POST'])
@admin_required
def admin_toggle_user_status(current_admin_user, user_to_toggle_id):
    if current_admin_user.username != 'mehmetalper04':
        flash('Kullanıcı durumunu sadece ana admin değiştirebilir.', 'danger')
        return redirect(url_for('admin_panel_bp.admin_manage_users'))
    if current_admin_user.id == user_to_toggle_id:
        flash("Kendi aktiflik durumunuzu bu arayüzden değiştiremezsiniz!", 'danger')
        return redirect(url_for('admin_panel_bp.admin_manage_users'))

    user_to_toggle = User.query.get_or_404(user_to_toggle_id)
    if user_to_toggle.username == 'mehmetalper04': # Cannot change primary admin status
        flash(f"Ana admin kullanıcısının ('{user_to_toggle.username}') durumu değiştirilemez!", 'warning')
        return redirect(url_for('admin_panel_bp.admin_manage_users'))

    try:
        user_to_toggle.is_active = not user_to_toggle.is_active
        action_taken = "aktifleştirildi" if user_to_toggle.is_active else "devre dışı bırakıldı"
        db.session.commit()
        flash(f"'{user_to_toggle.username}' kullanıcısı başarıyla {action_taken}.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f"Kullanıcı durumu değiştirilirken bir hata oluştu: {str(e)}", 'danger')
    return redirect(url_for('admin_panel_bp.admin_manage_users'))

@admin_panel_bp.route('/questions/pending')
@admin_required
def admin_pending_questions(current_admin_user):
    try:
        search_query = request.args.get('q', '', type=str)
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Sayfa başına gösterilecek soru sayısı

        # Temel sorguyu başlat
        query = Question.query.filter_by(status='pending')

        # Arama sorgusu varsa, soru metni veya gönderen kullanıcı adına göre filtrele
        if search_query:
            search_term = f"%{search_query}%"
            # User tablosu ile join yaparak kullanıcı adına göre de arama yap
            query = query.join(User, User.id == Question.submitted_by_user_id).filter(
                or_(
                    Question.text.ilike(search_term),
                    User.username.ilike(search_term)
                )
            )
        
        # Sonuçları sırala ve sayfalara ayır
        pagination = query.order_by(Question.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        questions = pagination.items

    except Exception as e:
        current_app.logger.error(f"Onay bekleyen sorular listelenirken hata: {e}")
        flash("Sorular listelenirken bir hata oluştu.", "danger")
        questions = []
        pagination = None
        search_query = ''
    return render_template('admin/admin_pending_questions.html', 
                           title="Onay Bekleyen Sorular", 
                           questions_pagination=pagination,
                           search_query=search_query)

@admin_panel_bp.route('/questions/reported')
@admin_required
def admin_reported_questions(current_admin_user):
    """
    Raporlanan soruları arama ve sayfalama işlevselliği ile listeler.
    """
    try:
        search_query = request.args.get('q', '', type=str)
        page = request.args.get('page', 1, type=int)
        per_page = 10

        # Temel sorgu: Yeni ve işlenmemiş raporları getir.
        query = QuestionReport.query.join(
            Question, QuestionReport.question_id == Question.id
        ).filter(
            QuestionReport.status == 'new', Question.status != 'rejected'
        )

        # Arama sorgusu varsa filtrele
        if search_query:
            search_term = f"%{search_query}%"
            # Raporu gönderen kullanıcıyı da sorguya dahil et
            query = query.join(User, QuestionReport.reported_by_user_id == User.id).filter(
                or_(
                    Question.text.ilike(search_term),
                    QuestionReport.reason.ilike(search_term),
                    User.username.ilike(search_term)
                )
            )
        
        # Sonuçları sırala ve sayfalara ayır
        pagination = query.order_by(QuestionReport.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

    except Exception as e:
        current_app.logger.error(f"Raporlanan sorular listelenirken hata: {e}")
        flash("Raporlanan sorular listelenirken bir hata oluştu.", "danger")
        pagination = None
        search_query = ''

    return render_template('admin/admin_reported_questions.html', 
                           title="Raporlanan Sorular", 
                           reports_pagination=pagination,
                           search_query=search_query)

@admin_panel_bp.route('/question/<int:question_id>/edit', methods=['GET', 'POST'])
@admin_required
def admin_edit_question(current_admin_user, question_id):
    """
    Belirli bir soruyu düzenlemek için sayfa sunar ve güncellemeleri işler.
    """
    question = Question.query.get_or_404(question_id)
    # Formdaki dropdown'ları doldurmak için tüm dersleri çek
    courses = Course.query.order_by(Course.name).all()

    if request.method == 'POST':
        try:
            # Formdan gelen verileri al ve soru nesnesini güncelle
            question.text = request.form.get('text', question.text)
            question.subtopic_id = request.form.get('subtopic_id', question.subtopic_id, type=int)
            question.option_a = request.form.get('option_a', question.option_a)
            question.option_b = request.form.get('option_b', question.option_b)
            question.option_c = request.form.get('option_c', question.option_c)
            question.option_d = request.form.get('option_d', question.option_d)
            question.option_e = request.form.get('option_e', question.option_e)
            question.correct_option = request.form.get('correct_option', question.correct_option).upper()
            
            new_status = request.form.get('status', question.status)
            if new_status in ['pending', 'approved', 'rejected', 'reported']:
                question.status = new_status
            
            question.is_premium_only = 'is_premium_only' in request.form

            # Resmi kaldırma seçeneğini işle
            if 'remove_image' in request.form and question.image_filename:
                old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image_filename)
                if os.path.exists(old_image_path):
                    os.remove(old_image_path)
                question.image_filename = None

            # Yeni resim yükleme işlemini yap
            if 'image' in request.files:
                file = request.files['image']
                if file and file.filename and allowed_file(file.filename):
                    # Varsa eski resmi sil
                    if question.image_filename:
                        old_image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image_filename)
                        if os.path.exists(old_image_path):
                            os.remove(old_image_path)
                    
                    # Yeni resmi kaydet
                    filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
                    file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
                    question.image_filename = filename
                elif file and file.filename:
                    # İzin verilmeyen dosya türü
                    flash('İzin verilmeyen resim formatı. Sadece .png, .jpg, .jpeg, .gif yüklenebilir.', 'warning')

            # Eğer soru onaylandıysa, ilişkili raporların durumunu güncelle
            if question.status == 'approved':
                QuestionReport.query.filter_by(question_id=question.id, status='new').update({'status': 'resolved'})

            db.session.commit()
            flash(f'Soru (ID: {question.id}) başarıyla güncellendi.', 'success')
            
            # Kaynağa göre yönlendirme yap
            source = request.args.get('source', 'dashboard')
            if source == 'pending':
                return redirect(url_for('.admin_pending_questions'))
            elif source == 'reported':
                return redirect(url_for('.admin_reported_questions'))
            
            return redirect(url_for('.admin_edit_question', question_id=question.id, source=source))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Soru güncellenirken hata oluştu: {e}", exc_info=True)
            flash(f'Soru güncellenirken beklenmedik bir hata oluştu: {e}', 'danger')

    # GET isteği için şablonu render et
    return render_template('admin/admin_edit_question.html',
                           title=f"Soru Düzenle: ID {question.id}",
                           question=question,
                           courses=courses)


@admin_panel_bp.route('/question/<int:question_id>/approve', methods=['POST'])
@admin_required
def admin_approve_question(current_admin_user, question_id):
    question = Question.query.get_or_404(question_id)
    redirect_source = request.form.get('source')
    if question.status in ['pending', 'reported']:
        question.status = 'approved'
        question.updated_at = datetime.utcnow()
        QuestionReport.query.filter_by(question_id=question.id, status='new').update({'status': 'resolved'})
        db.session.commit()
        flash(f'Soru ID {question.id} onaylandı ve ilişkili raporlar çözüldü.', 'success')
    else: flash(f'Soru ID {question.id} zaten onaylanmış veya farklı bir durumda.', 'warning')
    
    if redirect_source == 'pending': return redirect(url_for('.admin_pending_questions'))
    if redirect_source == 'reported': return redirect(url_for('.admin_reported_questions'))
    if redirect_source == 'edit': return redirect(url_for('.admin_edit_question', question_id=question_id, source=redirect_source))
    return redirect(request.referrer or url_for('.admin_dashboard'))


@admin_panel_bp.route('/question/<int:question_id>/reject', methods=['POST'])
@admin_required
def admin_reject_question(current_admin_user, question_id):
    question = Question.query.get_or_404(question_id)
    redirect_source = request.form.get('source')
    if question.status in ['pending', 'reported']:
        question.status = 'rejected'
        question.updated_at = datetime.utcnow()
        QuestionReport.query.filter_by(question_id=question.id, status='new').update({'status': 'dismissed'})
        db.session.commit()
        flash(f'Soru ID {question.id} reddedildi ve ilişkili raporlar kapatıldı.', 'info')
    else: flash(f'Soru ID {question.id} zaten işlenmiş veya farklı bir durumda.', 'warning')

    if redirect_source == 'pending': return redirect(url_for('.admin_pending_questions'))
    if redirect_source == 'reported': return redirect(url_for('.admin_reported_questions'))
    return redirect(request.referrer or url_for('.admin_dashboard'))


@admin_panel_bp.route('/report/<int:report_id>/dismiss', methods=['POST'])
@admin_required
def admin_dismiss_report(current_admin_user, report_id):
    report = QuestionReport.query.get_or_404(report_id)
    if report.status in ['new', 'reviewed']:
        report.status = 'dismissed'
        question = report.question # Assuming report.question relationship exists
        if question:
            other_new_reports = QuestionReport.query.filter(
                QuestionReport.question_id == report.question_id,
                QuestionReport.status == 'new',
                QuestionReport.id != report.id ).count()
            if other_new_reports == 0 and question.status == 'reported':
                question.status = 'approved' # Auto-approve if no other reports
                question.updated_at = datetime.utcnow()
                flash(f'Rapor ID {report.id} kapatıldı. Soru ID {question.id} onaylandı.', 'success')
            else: flash(f'Rapor ID {report.id} kapatıldı.', 'success')
        else: flash(f'Rapor ID {report.id} kapatıldı, ilişkili soru bulunamadı.', 'warning')
        db.session.commit()
    else: flash(f'Rapor ID {report.id} zaten işlenmiş.', 'warning')
    return redirect(url_for('.admin_reported_questions'))


@admin_panel_bp.route('/question/<int:question_id>/delete', methods=['POST'])
@admin_required
def admin_delete_question(current_admin_user, question_id):
    question = Question.query.get_or_404(question_id)
    # Delete related data first (or set to nullify if foreign keys allow)
    QuestionReport.query.filter_by(question_id=question.id).delete(synchronize_session=False)
    UserAnswer.query.filter_by(question_id=question.id).delete(synchronize_session=False)
    
    if question.image_filename:
        image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image_filename)
        if os.path.exists(image_path):
            try: os.remove(image_path)
            except OSError as e: flash(f"Soru silindi ancak resim ({question.image_filename}) silinirken hata.", "warning")

    db.session.delete(question)
    db.session.commit()
    flash(f'Soru ID {question.id} ve ilişkili veriler silindi.', 'success')

    prev_page = request.referrer
    if prev_page:
        if 'pending' in prev_page: return redirect(url_for('.admin_pending_questions'))
        if 'reported' in prev_page: return redirect(url_for('.admin_reported_questions'))
        if f'/question/{question_id}/edit' in prev_page: return redirect(url_for('.admin_dashboard'))
    return redirect(url_for('.admin_dashboard'))

@admin_panel_bp.route('/questions/all')
@admin_required
def admin_all_questions(current_admin_user):
    """
    Tüm soruları arama ve sayfalama işlevselliği ile listeler.
    Artık Soru ID ve Link ID üzerinden de arama yapılabilir.
    """
    try:
        search_query = request.args.get('q', '', type=str)
        page = request.args.get('page', 1, type=int)
        per_page = 20  # Sayfa başına gösterilecek soru sayısı

        # Temel sorgu objesini oluştur
        query = Question.query

        # Eğer bir arama sorgusu varsa, ilgili alanlarda filtrele
        if search_query:
            search_term = f"%{search_query}%"
            
            # Arama yapılacak alanların listesi
            search_filters = [
                Question.text.ilike(search_term),
                Question.link_id.ilike(search_term), # Link ID ile arama
                Subtopic.name.ilike(search_term),
                Course.name.ilike(search_term),
                User.username.ilike(search_term)
            ]

            # Eğer arama terimi bir sayı ise, Soru ID'si ile de arama yap
            if search_query.isdigit():
                question_id = int(search_query)
                search_filters.append(Question.id == question_id)

            # Arama yaparken ilişkili tabloları (Subtopic, Course, User) sorguya dahil et
            query = query.join(Subtopic, Question.subtopic_id == Subtopic.id)\
                         .join(Course, Subtopic.course_id == Course.id)\
                         .outerjoin(User, Question.submitted_by_user_id == User.id)\
                         .filter(or_(*search_filters))
    
        # Sonuçları en yeniden eskiye doğru sırala ve sayfalara ayır
        pagination = query.order_by(Question.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
    
    except Exception as e:
        current_app.logger.error(f"Tüm sorular listelenirken hata: {e}", exc_info=True)
        flash("Sorular listelenirken bir hata oluştu.", "danger")
        pagination = None
        search_query = ''
        
    return render_template('admin/admin_all_questions.html', 
                           title="Tüm Sorular (Soru Bankası)", 
                           questions_pagination=pagination,
                           search_query=search_query)

@admin_panel_bp.route('/mailing-list')
@admin_required
def admin_view_mailing_list(current_admin_user):
    try:
        # URL'den arama sorgusunu ve sayfa numarasını al
        search_query = request.args.get('q', '', type=str)
        page = request.args.get('page', 1, type=int)
        per_page = 20  # Sayfa başına gösterilecek kayıt sayısı

        # Temel sorgu objesini oluştur
        query = MailingList.query

        if search_query:
            query = query.filter(MailingList.email.ilike(f'%{search_query}%'))

        pagination = query.order_by(MailingList.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        # Mevcut sayfadaki kayıtları al
        emails = pagination.items

    except Exception as e:
        current_app.logger.error(f"E-posta listesi çekilirken hata oluştu: {e}")
        flash("E-posta listesi alınırken bir veritabanı hatası oluştu.", "danger")
        emails = []
        pagination = None
        search_query = ''

    return render_template('admin/view_mailing_list.html',
                           title="E-posta Bülteni Listesi",
                           emails=emails,
                           pagination=pagination,
                           search_query=search_query)

@admin_panel_bp.route('/send-newsletter', methods=['GET', 'POST'])
@admin_required
def send_newsletter(current_admin_user):
    if request.method == 'POST':
        subject = request.form.get('subject')
        body = request.form.get('body')

        if not subject or not body:
            flash("Konu ve içerik alanları zorunludur.", "danger")
            return redirect(url_for('.send_newsletter'))

        try:
            subscribers = MailingList.query.all()
            recipient_emails = [s.email for s in subscribers]

            if not recipient_emails:
                flash("Bülten gönderilecek kayıtlı e-posta adresi bulunmuyor.", "warning")
                return redirect(url_for('.send_newsletter'))

            # E-posta gövdesini şablondan render et
            email_html = render_template('emails/email_newsletter.html',
                                         subject=subject,
                                         body=body)

            # Asenkron gönderme fonksiyonunu çağır
            send_newsletter_broadcast(subject=subject,
                                      html_body=email_html,
                                      recipients=recipient_emails)

            flash(f"{len(recipient_emails)} aboneye bülten gönderme işlemi başlatıldı.", "success")
        
        except Exception as e:
            current_app.logger.error(f"Bülten gönderme hatası: {e}", exc_info=True)
            flash("Bülten gönderilirken beklenmedik bir hata oluştu.", "danger")

        return redirect(url_for('.send_newsletter'))

    # GET isteği için formu göster
    return render_template('admin/send_newsletter.html', title="Bülten Postası Gönder")

@admin_panel_bp.route('/send-newsletter2', methods=['GET', 'POST'])
@admin_required
def send_newsletter2(current_admin_user):
    if request.method == 'POST':
        subject = request.form.get('subject')
        body = request.form.get('body')

        if not subject or not body:
            flash("Konu ve içerik alanları zorunludur.", "danger")
            return redirect(url_for('.send_newsletter2'))

        try:
            subscribers = User.query.all()
            recipient_emails = [s.email for s in subscribers]

            if not recipient_emails:
                flash("Bülten gönderilecek kayıtlı e-posta adresi bulunmuyor.", "warning")
                return redirect(url_for('.send_newsletter2'))

            # E-posta gövdesini şablondan render et
            email_html = render_template('emails/email_newsletter.html',
                                         subject=subject,
                                         body=body)

            # Asenkron gönderme fonksiyonunu çağır
            send_newsletter_broadcast(subject=subject,
                                      html_body=email_html,
                                      recipients=recipient_emails)

            flash(f"{len(recipient_emails)} aboneye bülten gönderme işlemi başlatıldı.", "success")
        
        except Exception as e:
            current_app.logger.error(f"Bülten gönderme hatası: {e}", exc_info=True)
            flash("Bülten gönderilirken beklenmedik bir hata oluştu.", "danger")

        return redirect(url_for('.send_newsletter2'))

    # GET isteği için formu göster
    return render_template('admin/send_newsletter2.html', title="Bülten Postası Gönder")