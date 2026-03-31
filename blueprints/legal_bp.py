# blueprints/legal_bp.py
import json
from datetime import datetime, timezone
from flask import Blueprint, render_template, jsonify, request, Response, current_app

# Gerekli modelleri ve token dekoratörünü import ettiğinizden emin olun
from models import db, User, Question, UserAnswer, QuestionReport, Payment, MailingList, question_likes, question_saves
from decorators import token_required

legal_bp = Blueprint('legal_bp', __name__,
                     url_prefix='/legal', # Sayfalara /legal/privacy-policy gibi erişilecek
                     template_folder='../templates') # Ana templates klasörünü kullan

@legal_bp.route('/privacy-policy')
def privacy_policy_page():
    """
    Gizlilik Sözleşmesi sayfasını sunar.
    """
    return render_template('legal/privacy_policy.html', title="Gizlilik Sözleşmesi")

@legal_bp.route('/terms-of-service')
def terms_of_service_page():
    """
    Kullanım Şartları sayfasını sunar.
    """
    return render_template('legal/terms_of_service.html', title="Kullanım Şartları")

# --- YENİ EKLENEN ROTOLAR ---

@legal_bp.route('/about')
def about_page():
    """
    Hakkımızda sayfasını sunar.
    """
    return render_template('legal/about.html', title="Hakkımızda")

@legal_bp.route('/contact')
def contact_page():
    """
    İletişim sayfasını sunar.
    """
    return render_template('legal/contact.html', title="İletişim")


@legal_bp.route('/account-management')
def account_management_page():
    """
    Kullanıcının hesabını yönetebileceği HTML sayfasını sunar.
    Kimlik ve kilit durumu kontrolü frontend'de JavaScript ile yapılır.
    """
    return render_template('legal/account_management.html', title="Hesap Yönetimi")

@legal_bp.route('/download-my-data', methods=['GET'])
@token_required
def download_my_data(current_user_obj):
    try:
        user_data = {
            'profile': {
                'id': current_user_obj.id,
                'username': current_user_obj.username,
                'email': current_user_obj.email,
                'score': current_user_obj.score,
                'is_premium': current_user_obj.has_active_premium,
                'premium_expiration_date': current_user_obj.premium_expiration_date.isoformat() if current_user_obj.premium_expiration_date else None,
                'created_at': current_user_obj.created_at.isoformat() if current_user_obj.created_at else None,
            },
            'submitted_questions': [{'id': q.id, 'text': q.text, 'status': q.status, 'created_at': q.created_at.isoformat()} for q in current_user_obj.submitted_questions],
            'answers': [{'question_id': a.question_id, 'selected_option': a.selected_option, 'is_correct': a.is_correct, 'timestamp': a.timestamp.isoformat()} for a in current_user_obj.answers],
            'liked_questions_ids': [q.id for q in current_user_obj.liked_questions],
            'saved_questions_ids': [q.id for q in current_user_obj.saved_questions],
            'reports': [{'question_id': r.question_id, 'reason': r.reason, 'status': r.status, 'created_at': r.created_at.isoformat()} for r in current_user_obj.reports],
            'payments': [{'transaction_id': p.payment_gateway_transaction_id, 'plan_type': p.plan_type, 'amount_paid': str(p.amount_paid), 'status': p.status, 'created_at': p.created_at.isoformat()} for p in current_user_obj.payments]
        }

        json_string = json.dumps(user_data, indent=4, ensure_ascii=False)
        timestamp = datetime.utcnow().strftime('%Y-%m-%d')
        filename = f"sorugram_verilerim_{current_user_obj.username}_{timestamp}.json"

        return Response(
            json_string,
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )
    except Exception as e:
        current_app.logger.error(f"Veri indirme hatası, kullanıcı ID {current_user_obj.id}: {e}", exc_info=True)
        return jsonify({"message": "Verileriniz hazırlanırken bir hata oluştu."}), 500

@legal_bp.route('/delete-my-account', methods=['POST'])
@token_required
def delete_my_account(current_user_obj):
    user_id = current_user_obj.id
    username = current_user_obj.username
    email = current_user_obj.email

    try:
        # Bağımlı verileri sil
        UserAnswer.query.filter_by(user_id=user_id).delete()
        QuestionReport.query.filter_by(reported_by_user_id=user_id).delete()
        Payment.query.filter_by(user_id=user_id).delete()
        MailingList.query.filter_by(email=email).delete()
        
        # Association table'lardaki kayıtları sil
        db.session.execute(question_likes.delete().where(question_likes.c.user_id == user_id))
        db.session.execute(question_saves.delete().where(question_saves.c.user_id == user_id))

        # Kullanıcının gönderdiği soruları anonimleştir
        Question.query.filter_by(submitted_by_user_id=user_id).update({'submitted_by_user_id': 1, 'user_id': 1})
        
        # Son olarak kullanıcıyı sil
        db.session.delete(current_user_obj)
        db.session.commit()
        
        current_app.logger.info(f"Hesap başarıyla silindi: {username} (ID: {user_id})")
        return jsonify({'message': 'Hesabınız ve tüm verileriniz kalıcı olarak silinmiştir. Sizi tekrar aramızda görmeyi dileriz.'}), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Hesap silme hatası, kullanıcı: {username} (ID: {user_id}): {e}", exc_info=True)
        return jsonify({'message': 'Hesabınız silinirken beklenmedik bir hata oluştu. Lütfen destek ekibiyle iletişime geçin.'}), 500
