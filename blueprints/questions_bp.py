# blueprints/questions_bp.py
import os
import uuid
from flask import Blueprint, render_template, request, jsonify, current_app, url_for
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
from flask_jwt_extended import jwt_required, get_jwt_identity # For newer token endpoints

from models import db, Question, User, Subtopic, UserAnswer, QuestionReport # Removed QuestionLike, SavedQuestion models
# Use association tables directly or through User model's relationships
from utils import allowed_file
from decorators import token_required # For older token_required endpoints

questions_bp = Blueprint('questions_bp', __name__, url_prefix='/api')


@questions_bp.route('/questions/bulk/<int:course_id>', methods=['GET'])
@token_required # Eğer bu route için kullanıcı doğrulaması gerekiyorsa
def get_questions_bulk(current_user_obj, course_id):
    # 1. E-posta Doğrulama Kontrolü
    if not hasattr(current_user_obj, 'email_verified') or not current_user_obj.email_verified:
        return jsonify({'message': 'Soruları görmek için lütfen e-postanızı doğrulayın.'}), 403

    # 2. İstek Parametrelerini Al
    subtopic_id = request.args.get('subtopic_id', type=int)
    limit = request.args.get('limit', 10, type=int)
    limit = max(1, min(limit, 20)) # Limiti 1 ile 20 arasında sınırla
    from models import Course

    try:
        # 3. Temel Filtreleri Oluştur
        # Kullanıcının doğru cevapladığı soruların ID'lerini içeren alt sorgu
        # NOT: Bu subquery'nin amacı "henüz DOĞRU cevaplanmamış" soruları getirmekse Question.id.not_in() kullanılmalı.
        # Eğer amaç "sadece DOĞRU cevaplanmış" soruları getirmekse Question.id.in() kalmalı.
        # Genellikle yeni sorular istendiği için .not_in() daha yaygındır.
        # Aşağıdaki örnekte, daha önce doğru cevaplanmamış soruları getirecek şekilde (not_in) ayarlandı.
        correct_answered_subquery = db.session.query(UserAnswer.question_id)\
            .filter(UserAnswer.user_id == current_user_obj.id, UserAnswer.is_correct == True).subquery()

        base_filters = [
            Question.status == 'approved',
            Question.id.not_in(correct_answered_subquery) # Henüz doğru cevaplanmamış sorular
        ]

        # Premium üyelik kontrolü
        if not hasattr(current_user_obj, 'has_active_premium') or not current_user_obj.has_active_premium:
            base_filters.append(Question.is_premium_only == False)

        # 4. Alt Konu veya Ders Bazlı Filtreleme
        if subtopic_id:
            subtopic = Subtopic.query.get(subtopic_id)
            if not subtopic or subtopic.course_id != course_id:
                return jsonify({'message': 'Alt konu belirtilen derse ait değil veya bulunamadı.'}), 400
            base_filters.append(Question.subtopic_id == subtopic_id)
        else:
            course = Course.query.get(course_id)
            if not course:
                 return jsonify({'message': 'Belirtilen ders bulunamadı.'}), 404
            subtopic_ids_for_course = [st.id for st in course.subtopics]
            if not subtopic_ids_for_course: # Dersin alt konusu yoksa
                return jsonify([]), 200 # Boş dizi döndür
            base_filters.append(Question.subtopic_id.in_(subtopic_ids_for_course))

        # 5. Soruları Veritabanından Çek
        questions_query = Question.query.options(
            db.joinedload(Question.subtopic).joinedload(Subtopic.course), # Subtopic ve Course bilgilerini önden yükle
            db.joinedload(Question.user),      # Soruyu oluşturan kullanıcı (eğer varsa)
            db.joinedload(Question.submitter)  # Soruyu gönderen kullanıcı (eğer varsa)
        )

        questions = questions_query.filter(*base_filters)\
            .order_by(db.func.random()) \
            .limit(limit).all()

        # 6. Sonuçları Frontend'in Beklediği Formatta Hazırla
        result = []
        # Kullanıcının beğendiği ve kaydettiği soruların ID'lerini bir kerede çekmek daha verimli olabilir
        liked_question_ids = {q.id for q in current_user_obj.liked_questions} if hasattr(current_user_obj, 'liked_questions') else set()
        saved_question_ids = {q.id for q in current_user_obj.saved_questions} if hasattr(current_user_obj, 'saved_questions') else set()

        for q in questions:
            author_user = q.user or q.submitter # Soruyu oluşturan veya gönderen
            author_info = {
                'id': author_user.id if author_user else None,
                'username': author_user.username if author_user else "Bilinmiyor"
            }
            
            # image_url için Question modelinizde get_image_url() metodu olduğunu varsayıyorum
            image_url = q.get_image_url() if hasattr(q, 'get_image_url') else None
            # options için Question modelinizde get_options_dict() metodu olduğunu varsayıyorum
            options_dict = q.get_options_dict() if hasattr(q, 'get_options_dict') else {}


            result.append({
                'id': q.id,
                'text': q.text,
                'options': options_dict,
                'image_url': image_url,
                'link_id': q.link_id,
                'subtopic_id': q.subtopic_id,
                'subtopic_name': q.subtopic.name if q.subtopic else None,
                'course_id': q.subtopic.course.id if q.subtopic and q.subtopic.course else None, # course_id eklendi
                'course_name': q.subtopic.course.name if q.subtopic and q.subtopic.course else None,
                'is_premium_only': q.is_premium_only,
                'liked': q.id in liked_question_ids, # Frontend'in anlık UI güncellemesi için
                'saved': q.id in saved_question_ids, # Frontend'in anlık UI güncellemesi için
                'author': author_info,
                # Backend'den gelmesi gereken diğer Question modeli alanları
                'correct_option': q.correct_option, # Frontend'in cevabı göstermesi için (gerekirse)
                                                    # Normalde bu bilgi cevaplama sonrası dönülür,
                                                    # ama sorular listelenirken de gönderilebilir.
                                                    # Eğer sadece cevaplama sonrası gönderilecekse buradan çıkarın.
            })
        
        # 7. JSON Dizisi Olarak Yanıt Döndür
        return jsonify(result), 200

    except Exception as e:
        # Hata loglama (gerçek bir uygulamada daha detaylı loglama yapılmalı)
        print(f"Error in get_questions_bulk: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'message': 'Sunucu hatası oluştu.', 'error': str(e)}), 500


@questions_bp.route('/questions/share/<string:link_id>', methods=['GET']) # Blueprint'inizi kullanın
@token_required # VEYA @optional_token_required (yukarıdaki nota bakın)
def get_shared_question_customized(current_user_obj, link_id): # current_user_obj, token varsa kullanıcı nesnesi, yoksa None olmalı
    is_authenticated = current_user_obj is not None
    app_deep_link = f"sorugramapp://question/{link_id}" # Genel deep link

    question = Question.query.filter_by(link_id=link_id, status='approved').first()

    if not question:
        error_message = 'Soru bulunamadı veya onaylanmamış.'
        if is_authenticated:
            # Kimliği doğrulanmış kullanıcı için JSON hata
            return jsonify({'message': error_message, 'app_deep_link': app_deep_link}), 404
        else:
            # Anonim kullanıcı için HTML hata
            return render_template('shared_question_page.html', question=None, error_message=error_message, app_deep_link=app_deep_link), 404

    # --- Kimliği Doğrulanmış Kullanıcı İşlemleri ---
    if is_authenticated:
        # E-posta doğrulaması kontrolü
        if not hasattr(current_user_obj, 'email_verified') or not current_user_obj.email_verified:
            error_message = 'Bu içeriği görmek için lütfen e-postanızı doğrulayın.'
            return jsonify({'message': error_message, 'app_deep_link': app_deep_link}), 403

        # Premium soru kontrolü
        if question.is_premium_only and (not hasattr(current_user_obj, 'has_active_premium') or not current_user_obj.has_active_premium):
            error_message = 'Bu bir premium sorudur. Görmek için premium üyelik gereklidir.'
            return jsonify({'message': error_message, 'app_deep_link': app_deep_link}), 403
        
        # Kişiselleştirilmiş verileri al (liked, saved)
        liked = False
        if hasattr(current_user_obj, 'liked_questions'):
            liked = current_user_obj.liked_questions.filter(Question.id == question.id).first() is not None
        
        saved = False
        if hasattr(current_user_obj, 'saved_questions'):
            saved = current_user_obj.saved_questions.filter(Question.id == question.id).first() is not None
            
    # --- Anonim Kullanıcı İşlemleri (veya kimliği doğrulanmış kullanıcı için kontrollerden sonra) ---
    else: # is_authenticated == False (Belirteç yok)
        if question.is_premium_only:
            error_message = 'Bu bir premium sorudur. İçeriği tam olarak görebilmek için giriş yapmanız ve premium üyeliğinizin olması gerekebilir.'
            # Anonim kullanıcı ve premium soru ise HTML hata
            return render_template('shared_question_page.html', question=None, error_message=error_message, app_deep_link=app_deep_link), 403
        
        # Anonim kullanıcı için kişiselleştirilmiş veriler varsayılan olarak False
        liked = False
        saved = False

    # --- Ortak Soru Verilerini Hazırlama ---
    course_name = "Bilinmeyen Ders"
    subtopic_name = "Bilinmiyor Alt Konu"
    course_id_val = None

    if question.subtopic:
        subtopic_name = question.subtopic.name
        if question.subtopic.course:
            course_name = question.subtopic.course.name
            course_id_val = question.subtopic.course.id
    
    author_user = question.user or question.submitter
    author_info = {
        'id': author_user.id if author_user else None,
        'username': author_user.username if author_user else "Bilinmiyor"
    }

    image_url = question.get_image_url() if hasattr(question, 'get_image_url') else None
    options_dict = question.get_options_dict() if hasattr(question, 'get_options_dict') else {}

    question_data = {
        'id': question.id,
        'text': question.text,
        'options': options_dict,
        'image_url': image_url,
        'link_id': question.link_id,
        'course_name': course_name,
        'course_id': course_id_val,
        'subtopic_name': subtopic_name,
        'subtopic_id': question.subtopic_id,
        'is_premium_only': question.is_premium_only,
        'liked': liked, # Kimliği doğrulanmışsa kişisel, değilse False
        'saved': saved,  # Kimliği doğrulanmışsa kişisel, değilse False
        'author': author_info,
        'status': question.status,
        # 'correct_option': question.correct_option # Genellikle paylaşım linkinde doğru cevap hemen gösterilmez
        'app_deep_link': app_deep_link # Bilgi amaçlı eklenebilir
    }

    # --- Yanıtı Döndürme ---
    if is_authenticated:
        # Kimliği doğrulanmış kullanıcı için JSON yanıt
        return jsonify(question_data), 200
    else:
        # Anonim kullanıcı için HTML yanıt
        return render_template('shared_question_page.html', question=question_data, error_message=None, app_deep_link=app_deep_link)



@questions_bp.route('/submit-answer', methods=['POST'])
@token_required # Custom decorator
def submit_answer_api(current_user_obj):
    if not current_user_obj.email_verified: return jsonify({'message': 'Lütfen e-postanızı doğrulayın.'}), 403

    data = request.get_json()
    question_id = data.get('questionId')
    selected_option = data.get('selectedOption', '').upper()

    if not question_id or not selected_option or selected_option not in ['A', 'B', 'C', 'D', 'E', 'F']:
        return jsonify({'message': 'Soru ID ve geçerli seçenek (A-F) gereklidir.'}), 400

    question = Question.query.get(question_id)
    if not question or question.status != 'approved':
        return jsonify({'message': 'Soru bulunamadı veya henüz onaylanmamış.'}), 404

    if UserAnswer.query.filter_by(user_id=current_user_obj.id, question_id=question_id, is_correct=True).first():
        return jsonify({
            'message': 'Bu soruyu zaten doğru cevapladınız.', 'is_correct': True,
            'correct_option': question.correct_option.upper(), 'new_score': current_user_obj.score,
            'show_ad_trigger': False
        }), 200

    is_correct = None
    points_gained = 0
    feedback_message = ""

    if selected_option == 'F':
        is_correct = None
        points_gained = current_app.config['POINTS_BLANK_ANSWER']
        feedback_message = "Soru boş bırakıldı."
    else:
        is_correct = (selected_option == question.correct_option.upper())
        points_gained = current_app.config['POINTS_CORRECT_ANSWER'] if is_correct else current_app.config['POINTS_WRONG_ANSWER']
        feedback_message = "Doğru cevap!" if is_correct else f"Yanlış cevap. Doğru seçenek: {question.correct_option.upper()}"

    user_answer = UserAnswer(user_id=current_user_obj.id, question_id=question.id,
                             selected_option=selected_option, is_correct=is_correct)
    db.session.add(user_answer)

    if selected_option != 'F':
        current_user_obj.score = max(0, (current_user_obj.score or 0) + points_gained)

    db.session.commit()

    total_answers_by_user = UserAnswer.query.filter_by(user_id=current_user_obj.id).count()
    show_ad = (not current_user_obj.has_active_premium) and \
              (total_answers_by_user % current_app.config['SHOW_AD_AFTER_N_ANSWERS'] == 0) and \
              selected_option != 'F'

    return jsonify({
        'message': feedback_message, 'is_correct': is_correct,
        'correct_option': question.correct_option.upper(), 'new_score': current_user_obj.score,
        'show_ad_trigger': show_ad
    }), 200


@questions_bp.route('/questions/report', methods=['POST'])
@token_required # Custom decorator
def report_question_api(current_user_obj):
    data = request.get_json()
    question_id = data.get('question_id')
    reason = data.get('reason', '')

    if not question_id: return jsonify({'message': 'Soru ID gereklidir.'}), 400
    question = Question.query.get(question_id)
    if not question: return jsonify({'message': 'Bildirilecek soru bulunamadı.'}), 404

    if QuestionReport.query.filter_by(question_id=question_id, reported_by_user_id=current_user_obj.id).first():
        return jsonify({'message': 'Bu soruyu zaten bildirdiniz.'}), 409

    report = QuestionReport(question_id=question_id, reported_by_user_id=current_user_obj.id,
                            reason=reason, status='new')
    if question.status == 'approved':
        question.status = 'reported'
        question.updated_at = datetime.utcnow()

    db.session.add(report)
    db.session.commit()
    return jsonify({'message': 'Soru başarıyla bildirildi. İncelenecektir.'}), 200


@questions_bp.route('/questions/submit', methods=['POST'])
@token_required # Custom decorator
def submit_new_question_api(current_user_obj):
    if not current_user_obj.email_verified:
        return jsonify({'message': 'Lütfen e-postanızı doğrulayın.'}), 403

    required_fields = ['subtopic_id', 'text', 'option_a', 'option_b', 'option_c', 'option_d', 'option_e', 'correct_option']
    if not all(field in request.form for field in required_fields):
        missing = ", ".join(f for f in required_fields if f not in request.form)
        return jsonify({'message': f'Eksik form verisi: {missing}'}), 400

    correct_option = request.form['correct_option'].upper()
    if correct_option not in ['A', 'B', 'C', 'D', 'E']:
        return jsonify({'message': 'Geçersiz doğru seçenek. A, B, C, D veya E olmalıdır.'}), 400

    subtopic = Subtopic.query.get(request.form['subtopic_id'])
    if not subtopic: return jsonify({'message': 'Belirtilen alt konu bulunamadı.'}), 404

    filename = None
    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename != '' and allowed_file(file.filename):
            filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
            file.save(os.path.join(current_app.config['UPLOAD_FOLDER'], filename))
        elif file.filename != '':
            return jsonify({'message': 'İzin verilmeyen dosya türü.'}), 400

    is_premium_only_from_form = request.form.get('is_premium_only', 'false').lower() == 'true'

    new_question = Question(
        subtopic_id=subtopic.id, text=request.form['text'],
        option_a=request.form['option_a'], option_b=request.form['option_b'],
        option_c=request.form['option_c'], option_d=request.form['option_d'],
        option_e=request.form['option_e'], correct_option=correct_option,
        image_filename=filename, status='pending',
        submitted_by_user_id=current_user_obj.id, # Explicitly using current_user_obj from decorator
        user_id=current_user_obj.id, # Also setting user_id for the 'user' relationship if it's the author
        is_premium_only=is_premium_only_from_form
    )
    db.session.add(new_question)
    db.session.commit()
    return jsonify({'message': 'Sorunuz onay için başarıyla gönderildi!'}), 201

# --- Like/Save Question Routes (using flask_jwt_extended) ---

@questions_bp.route('/questions/<int:question_id>/like', methods=['POST'])
@token_required
def toggle_like(current_user_obj, question_id): # current_user_obj parametresi eklendi
    # user_id = get_jwt_identity() # Artık current_user_obj doğrudan geliyor
    # user = User.query.get(user_id) # Bu satıra gerek kalmayabilir
    user = current_user_obj # Dekoratörden gelen kullanıcıyı kullan
    question = Question.query.get_or_404(question_id)

    if not user: # Bu kontrol, token_required düzgün çalışıyorsa gereksiz olabilir ama güvenlik için kalabilir.
        return jsonify({"msg": "Kullanıcı bulunamadı veya yetkilendirilmemiş."}), 404

    # liked_questions ilişkisinin User modelinizde tanımlı olduğunu varsayıyorum
    if not hasattr(user, 'liked_questions'):
        return jsonify({"msg": "Kullanıcı modelinde 'liked_questions' ilişkisi bulunamadı."}), 500
        
    if question in user.liked_questions:
        user.liked_questions.remove(question)
        liked = False
        status_code = 200 # Beğeniyi kaldırma
    else:
        user.liked_questions.append(question)
        liked = True
        status_code = 201 # Yeni beğeni oluşturma
    
    db.session.commit()
    return jsonify({'liked': liked, 'question_id': question.id}), status_code


@questions_bp.route('/questions/<int:question_id>/save', methods=['POST'])
@token_required
def toggle_save(current_user_obj, question_id):
    user = current_user_obj
    question = Question.query.get_or_404(question_id)

    if not user: # Bu kontrol, token_required düzgün çalışıyorsa gereksiz olabilir.
        return jsonify({"msg": "Kullanıcı bulunamadı veya yetkilendirilmemiş."}), 404

    # saved_questions ilişkisinin User modelinizde tanımlı olduğunu varsayıyorum
    if not hasattr(user, 'saved_questions'):
        return jsonify({"msg": "Kullanıcı modelinde 'saved_questions' ilişkisi bulunamadı."}), 500

    if question in user.saved_questions:
        user.saved_questions.remove(question)
        saved = False
        status_code = 200 # Kaydı kaldırma
    else:
        user.saved_questions.append(question)
        saved = True
        status_code = 201 # Yeni kayıt oluşturma
        
    db.session.commit()
    return jsonify({'saved': saved, 'question_id': question.id}), status_code

# --- Search Routes ---
@questions_bp.route('/search/questions', methods=['GET'])
@token_required
def search_questions(current_user_obj):
    """
    Soru metninde arama yapar ve sonuçları listeler.
    Yanıt artık 'link_id' alanını da içerir.
    """
    query = request.args.get('q', '').strip()
    if not query:
        return jsonify({'message': 'Arama terimi boş olamaz.'}), 400

    # Premium olmayan kullanıcıların premium soruları görmesini engelle
    filters = [Question.status == 'approved', Question.text.ilike(f"%{query}%")]
    if not current_user_obj.has_active_premium:
        filters.append(Question.is_premium_only == False)

    results = Question.query.filter(*filters)\
        .order_by(Question.id.desc()).limit(50).all()
    
    # Soruyu gönderen kullanıcıyı bulmak için yardımcı fonksiyon
    author_user_func = lambda q: q.user or q.submitter

    # JSON yanıtını oluştur
    return jsonify([{
        'id': q.id,
        'text': q.text,
        'image_url': q.get_image_url(),
        'link_id': q.link_id,  # <<< YENİ EKLENEN ALAN
        'subtopic_id': q.subtopic_id,
        'subtopic_name': q.subtopic.name if q.subtopic else None,
        'course_name': q.subtopic.course.name if q.subtopic and q.subtopic.course else None,
        'is_premium_only': q.is_premium_only,
        'author_username': author_user_func(q).username if author_user_func(q) else "Bilinmiyor"
    } for q in results])