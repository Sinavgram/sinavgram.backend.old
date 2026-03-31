# blueprints/user_bp.py
import base64
import json
import os
import uuid
from flask import Blueprint, g, jsonify, request, current_app
from datetime import datetime, timezone, timedelta

import jwt
from sqlalchemy import func, literal_column
from sqlalchemy.orm.attributes import flag_modified
from models import Subtopic, db, User, UserAnswer, Question, Payment # Ensure Question is imported
from decorators import token_required # For endpoints using the custom decorator
from utils import allowed_file, send_payment_receipt_email
import requests 
from google.oauth2 import service_account
from googleapiclient.discovery import build

user_bp = Blueprint('user_bp', __name__, url_prefix='/api/user')


@user_bp.route('/stats', methods=['GET'])
@token_required # Custom decorator
def get_user_stats_api(current_user_obj):
    if current_user_obj.is_premium and current_user_obj.premium_expiration_date:
        exp_date_aware = current_user_obj.premium_expiration_date
        if exp_date_aware.tzinfo is None: exp_date_aware = exp_date_aware.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > exp_date_aware:
            current_user_obj.is_premium = False
            db.session.commit()

    total_answered = UserAnswer.query.filter_by(user_id=current_user_obj.id).count()
    correct_answers = UserAnswer.query.filter_by(user_id=current_user_obj.id, is_correct=True).count()
    incorrect_answers = UserAnswer.query.filter_by(user_id=current_user_obj.id, is_correct=False).count()
    blank_answers = UserAnswer.query.filter_by(user_id=current_user_obj.id, selected_option='F').count()

    answered_non_blank = total_answered - blank_answers
    accuracy_excluding_blanks = (correct_answers / answered_non_blank * 100) if answered_non_blank > 0 else 0

    rates = {}
    if total_answered > 0:
        rates['true'] = round((correct_answers / total_answered) * 100, 2)
        rates['false'] = round((incorrect_answers / total_answered) * 100, 2)
        rates['blank'] = round((blank_answers / total_answered) * 100, 2)

    return jsonify({
        'username': current_user_obj.username, 'score': current_user_obj.score,
        'total_answered_questions': total_answered, 'correctly_answered_questions': correct_answers,
        'incorrectly_answered_questions': incorrect_answers, 'blank_answered_questions': blank_answers,
        'accuracy_rate_excluding_blanks': round(accuracy_excluding_blanks, 2), 'rates': rates,
        'email_verified': current_user_obj.email_verified, 'is_premium': current_user_obj.is_premium,
        'has_active_premium': current_user_obj.has_active_premium, 'is_active': current_user_obj.is_active,
        'premium_expiration_date': current_user_obj.premium_expiration_date.isoformat() if current_user_obj.premium_expiration_date else None
    }), 200

@user_bp.route('/liked-questions', methods=['GET'])
@token_required # Custom decorator
def get_liked_questions(current_user_obj):
    query = current_user_obj.liked_questions.filter(Question.status == 'approved')
    if not current_user_obj.has_active_premium:
        query = query.filter(Question.is_premium_only == False)
    
    liked_questions = query.order_by(Question.id.desc()).all()
    author_user_func = lambda q: q.user or q.submitter

    return jsonify([{
        'id': q.id, 'text': q.text, 'image_url': q.get_image_url(),
        'subtopic_id': q.subtopic_id,
        'subtopic_name': q.subtopic.name if q.subtopic else None,
        'course_name': q.subtopic.course.name if q.subtopic and q.subtopic.course else None,
        'is_premium_only': q.is_premium_only,
        'author_username': author_user_func(q).username if author_user_func(q) else None,
        'link_id': q.link_id  # Eğer Question modelinizde varsa
    } for q in liked_questions])

@user_bp.route('/saved-questions', methods=['GET'])
@token_required # Custom decorator
def get_saved_questions(current_user_obj):
    query = current_user_obj.saved_questions.filter(Question.status == 'approved')
    if not current_user_obj.has_active_premium:
        query = query.filter(Question.is_premium_only == False)

    saved_questions = query.order_by(Question.id.desc()).all()
    author_user_func = lambda q: q.user or q.submitter

    return jsonify([{
        'id': q.id, 'text': q.text, 'image_url': q.get_image_url(),
        'subtopic_id': q.subtopic_id,
        'subtopic_name': q.subtopic.name if q.subtopic else None,
        'course_name': q.subtopic.course.name if q.subtopic and q.subtopic.course else None,
        'is_premium_only': q.is_premium_only,
        'author_username': author_user_func(q).username if author_user_func(q) else None,
        'link_id': q.link_id  # Eğer Question modelinizde varsa
    } for q in saved_questions])


@user_bp.route('/profile/me/update', methods=['PUT'])
@token_required
def update_user_profile_api(current_user):
    user = current_user
    if not user:
        return jsonify({'message': 'Kullanıcı bulunamadı veya token geçersiz.'}), 401

    username = request.form.get('username', user.username)

    if username != user.username:
        if not username or len(username) < 3:
            return jsonify({'message': 'Kullanıcı adı en az 3 karakter olmalıdır.'}), 400
        if User.query.filter(User.username == username, User.id != user.id).first():
            return jsonify({'message': 'Bu kullanıcı adı zaten alınmış.'}), 409
        user.username = username

    avatar_file = request.files.get('avatar')
    if avatar_file:
        if allowed_file(avatar_file.filename):
            if user.avatar:
                old_avatar_path = os.path.join(current_app.config['UPLOAD_FOLDER_AVATARS'], user.avatar)
                if os.path.exists(old_avatar_path):
                    try: os.remove(old_avatar_path)
                    except OSError as e: current_app.logger.error(f"Eski avatar silinemedi: {e}")
            
            filename = (f"{uuid.uuid4()}_{avatar_file.filename}")
            avatar_path = os.path.join(current_app.config['UPLOAD_FOLDER_AVATARS'], filename)
            try:
                avatar_file.save(avatar_path)
                user.avatar = filename
            except Exception as e:
                current_app.logger.error(f"Avatar kaydedilirken hata: {e}")
                return jsonify({'message': 'Avatar yüklenirken bir sorun oluştu.'}), 500
        else:
            return jsonify({'message': 'İzin verilmeyen dosya türü.'}), 400

    try:
        db.session.commit()
        updated_user_data = {
            'id': user.id, 'username': user.username, 'email': user.email,
            'avatar_url': user.get_avatar_url(), 'is_premium': user.is_premium,
            'has_active_premium': user.has_active_premium, 'score': user.score,
            'email_verified': user.email_verified,
        }
        return jsonify({'message': 'Profil başarıyla güncellendi.', 'user': updated_user_data}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Profil güncellenirken veritabanı hatası: {e}")
        return jsonify({'message': 'Profil güncellenirken bir sunucu hatası oluştu.'}), 500

@user_bp.route('/profile/me', methods=['GET'])
@token_required
def get_own_profile(current_user_obj):
    current_app.logger.info(f"Fetching profile for user: {current_user_obj.id} - {current_user_obj.username}")
    is_locked = False
    if current_user_obj.security_token and current_user_obj.security_token_expiration:
        if datetime.now(timezone.utc) < current_user_obj.security_token_expiration:
            is_locked = True
    try:
        # Avatar URL'sini güvenli bir şekilde al
        avatar_url = current_user_obj.get_avatar_url() if hasattr(current_user_obj, 'get_avatar_url') else None

        approved_questions_list = []
        if hasattr(current_user_obj, 'submitted_questions'): # submitted_questions ilişkisi var mı kontrol et
            approved_questions_query = Question.query.filter(
                Question.submitted_by_user_id == current_user_obj.id,
                Question.status == 'approved'
            )
            approved_questions = approved_questions_query.order_by(Question.created_at.desc()).all()

            for q in approved_questions:
                approved_questions_list.append({
                    'id': q.id,
                    'text_preview': (q.text[:70] + '...') if q.text and len(q.text) > 70 else q.text,
                    'status': q.status,
                    'is_premium_only': q.is_premium_only,
                    'subtopic_id': q.subtopic_id,
                    'subtopic_name': q.subtopic.name if q.subtopic else "N/A",
                    'course_name': q.subtopic.course.name if q.subtopic and q.subtopic.course else "N/A",
                    'link_id': q.link_id
                })

        profile_data = {
            'user_id': current_user_obj.id,
            'username': current_user_obj.username or "N/A",
            'email': current_user_obj.email or "N/A",
            'avatar_url': avatar_url or current_app.config.get('DEFAULT_AVATAR_URL', ''), # Varsayılan avatar URL'si ekle
            'score': current_user_obj.score if current_user_obj.score is not None else 0,
            'has_active_premium': current_user_obj.has_active_premium,
            'is_account_locked': is_locked,
            'email_verified': current_user_obj.email_verified,
            'created_at': current_user_obj.created_at.isoformat() if current_user_obj.created_at else None,
            'approved_questions_count': len(approved_questions_list), # Doğrudan liste uzunluğunu kullan
            'approved_questions_preview': approved_questions_list
        }
        current_app.logger.info(f"Profile data to be returned: {profile_data}")
        return jsonify(profile_data), 200

    except Exception as e:
        current_app.logger.error(f"Error in get_own_profile for user {current_user_obj.id}: {str(e)}", exc_info=True)
        return jsonify({'message': 'Profil verileri alınırken sunucu hatası oluştu.'}), 500

@user_bp.route('/profile/<int:user_id>', methods=['GET'])
@token_required
def get_user_profile(current_requesting_user, user_id):
    """
    Belirtilen kullanıcının profilini, soruları için sayfalama desteği ile döndürür.
    """
    user_to_view = User.query.get_or_404(user_id)

    if not user_to_view.is_active:
        return jsonify({'message': 'Kullanıcı profili bulunamadı veya aktif değil.'}), 404
    
    page = request.args.get('page', 1, type=int)
    per_page = 15

    approved_questions_query = Question.query.filter(
        Question.submitted_by_user_id == user_to_view.id,
        Question.status == 'approved'
    )
    if not current_requesting_user.has_active_premium:
        approved_questions_query = approved_questions_query.filter(Question.is_premium_only == False)

    pagination = approved_questions_query.order_by(Question.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    questions_for_page = pagination.items

    return jsonify({
        'user_id': user_to_view.id,
        'username': user_to_view.username,
        'avatar_url': user_to_view.get_avatar_url(),
        'score': user_to_view.score,
        'is_premium': user_to_view.has_active_premium,
        'approved_questions': {
            'items': [
                {
                    'id': q.id,
                    'text_preview': q.text[:70] + '...' if len(q.text) > 70 else q.text,
                    'link_id': q.link_id,
                    'subtopic_name': q.subtopic.name if q.subtopic else "N/A",
                    'course_name': q.subtopic.course.name if q.subtopic and q.subtopic.course else "N/A",
                    'is_premium_only': q.is_premium_only
                } for q in questions_for_page
            ],
            'page': pagination.page,
            'per_page': pagination.per_page,
            'total_items': pagination.total,
            'total_pages': pagination.pages,
            'has_next': pagination.has_next
        }
    }), 200


@user_bp.route('/search/users', methods=['GET'])
@token_required
def search_users(current_user_obj):
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'message': 'Arama terimi boş olamaz.'}), 400

    results = User.query.filter(
        User.username.ilike(f"%{query}%"),
        User.is_active == True,
        User.email_verified == True
    ).order_by(User.username).limit(50).all()

    return jsonify([{
        'id': u.id,
        'username': u.username,
        'avatar_url': u.get_avatar_url()
    } for u in results])

# +++ NEW ENDPOINT START +++
@user_bp.route('/submitted-questions', methods=['GET'])
@token_required # Or @jwt_required() if you are using flask_jwt_extended consistently
def get_submitted_questions_sqlalchemy_query(current_user_obj): # Fonksiyon adını ayırt etmek için değiştirdim
    try:
        # Hangi statüdeki soruları almak istediğinizi belirtin
        allowed_statuses = request.args.getlist('status') # Örneğin ?status=approved&status=pending
        if not allowed_statuses:
            allowed_statuses = ['approved', 'pending', 'rejected'] # Varsayılan olarak tümü

        # Question modeli üzerinden SQLAlchemy sorgusu oluşturma
        query = Question.query.filter(
            Question.submitted_by_user_id == current_user_obj.id,
            Question.status.in_(allowed_statuses)
        ).options(
            db.joinedload(Question.subtopic).joinedload(Subtopic.course) # Artık Subtopic tanımlı olmalı
        ).order_by(
            Question.created_at.desc()
        )
        
        filtered_questions_by_sqlalchemy = query.all()
        
        # Soruları frontend'in beklediği formata dönüştür
        result = []
        for q in filtered_questions_by_sqlalchemy:
            # Question modelinizdeki get_image_url ve get_options_dict metotlarının
            # var olduğunu veya bu bilgileri doğrudan alacağınızı varsayıyorum.
            image_url = q.get_image_url() if hasattr(q, 'get_image_url') else None
            options_dict = q.get_options_dict() if hasattr(q, 'get_options_dict') else {}

            author_info = {
                'id': current_user_obj.id, # Soruyu gönderen zaten mevcut kullanıcı
                'username': current_user_obj.username
            }

            result.append({
                'id': q.id,
                'text': q.text,
                'options': options_dict,
                'image_url': image_url,
                'link_id': q.link_id, # Question modelinizde varsa
                'status': q.status,
                'is_premium_only': q.is_premium_only, # Question modelinizde varsa
                'subtopic_id': q.subtopic_id,
                'subtopic_name': q.subtopic.name if q.subtopic else None,
                'course_id': q.subtopic.course.id if q.subtopic and q.subtopic.course else None,
                'course_name': q.subtopic.course.name if q.subtopic and q.subtopic.course else None,
                'author': author_info,
                'created_at': q.created_at.isoformat() if hasattr(q, 'created_at') and q.created_at else None,
                'updated_at': q.updated_at.isoformat() if hasattr(q, 'updated_at') and q.updated_at else None,
                # Diğer gerekli alanlar...
            })
            
        return jsonify(result), 200

    except Exception as e:
        print(f"Error in get_submitted_questions_sqlalchemy_query: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'message': 'Sunucu hatası oluştu.', 'error': str(e)}), 500
@user_bp.route('/get-rank', methods=['GET'])
@token_required
def get_user_rank(current_user_obj):
    """
    Giriş yapmış kullanıcının puan sıralamasını hesaplar,
    hak ettiği yeni rozetleri verir ve bu bilgileri döndürür.
    """
    # Decorator'dan geçerli bir kullanıcı objesi geldiğinden emin olmak için bir kontrol ekleyelim.
    if not current_user_obj:
        return jsonify({"message": "Kimlik doğrulama hatası: Kullanıcı bulunamadı."}), 401

    try:
        # Veritabanında kullanıcıları puanlarına göre sıralayan bir alt sorgu oluştur.
        # Sadece aktif ve admin olmayan kullanıcıları sıralamaya dahil et.
        ranked_users_subquery = db.session.query(
            User.id,
            func.rank().over(order_by=User.score.desc()).label('rank')
        ).filter(
            User.is_active == True,
            User.is_admin == False
        ).subquery()

        # Mevcut kullanıcının bu sıralamadaki yerini bul.
        user_rank_result = db.session.query(
            ranked_users_subquery.c.rank
        ).filter(
            ranked_users_subquery.c.id == current_user_obj.id
        ).first()

        # Toplam sıralamaya giren kullanıcı sayısını al.
        total_ranked_users = db.session.query(func.count(User.id)).filter(
            User.is_active == True, User.is_admin == False
        ).scalar()
        
        user_rank = user_rank_result.rank if user_rank_result else None

        # Sıralaması olan kullanıcılar için rozet mantığını çalıştır.
        if user_rank:
            # Kullanıcının rozet listesini başlat (eğer boşsa).
            if current_user_obj.badges is None:
                current_user_obj.badges = []
            
            # Değişiklikleri takip etmek için mevcut rozetlerin bir kopyasını oluşturalım.
            current_badges = list(current_user_obj.badges)
            new_badge_earned = False

            # Rozet kazanma koşullarını kontrol et.
            if user_rank <= 100 and 'gold' not in current_badges:
                current_badges.append('gold')
                new_badge_earned = True
            
            if user_rank <= 1000 and 'silver' not in current_badges:
                current_badges.append('silver')
                new_badge_earned = True

            if user_rank <= 10000 and 'bronze' not in current_badges:
                current_badges.append('bronze')
                new_badge_earned = True

            # Eğer yeni bir rozet kazanıldıysa, veritabanını güncelle.
            if new_badge_earned:
                current_user_obj.badges = current_badges
                flag_modified(current_user_obj, "badges")
                db.session.commit()

        # Her durumda JSON yanıtı döndür.
        return jsonify({
            'rank': user_rank,
            'total_users': total_ranked_users,
            'badges': current_user_obj.badges or [] # Rozet listesi boşsa veya None ise boş liste döndür.
        }), 200

    except Exception as e:
        # Bir hata oluşursa, veritabanı oturumunda yapılan değişiklikleri geri al.
        db.session.rollback()
        # Hatayı sunucu loglarına detaylıca yazdır. Bu, sorunu teşhis etmen için kritiktir.
        current_app.logger.error(f"Kullanıcı sıralaması alınırken hata (user_id: {current_user_obj.id}): {e}", exc_info=True)
        # İstemciye (Flutter uygulamasına) genel bir JSON hata mesajı gönder.
        return jsonify({"message": "Sıralama bilgileri alınırken bir sunucu hatası oluştu."}), 500