# blueprints/ai_bp.py

import base64
import os
import json
from flask import Blueprint, request, jsonify, current_app

# Gerekli modelleri ve dekoratörü import ettiğinizden emin olun
from models import Question
from decorators import token_required

ai_bp = Blueprint('ai_bp', __name__, url_prefix='/api/ai')

@ai_bp.route('/solve-question', methods=['POST'])
@token_required
def solve_question_with_ai(current_user_obj):
    """
    Belirtilen bir soru için, mobil uygulamanın Gemini API'sine göndereceği
    isteği (payload ve URL) hazırlar ve Flutter uygulamasına geri döndürür.
    """
    data = request.get_json()
    question_id = data.get('question_id')
    user_selected_option = data.get('user_selected_option')

    if not question_id or not user_selected_option:
        return jsonify({'message': 'Soru ID\'si ve kullanıcı seçeneği gereklidir.'}), 400

    question = Question.query.get(question_id)
    if not question:
        return jsonify({'message': 'Soru bulunamadı.'}), 404

    # --- Gemini API için Prompt Hazırlama ---
    
    # DÜZELTME: Ayrı seçenek alanlarından bir sözlük oluşturuluyor.
    options_dict = {
        'a': question.option_a,
        'b': question.option_b,
        'c': question.option_c,
        'd': question.option_d,
        'e': question.option_e,
    }
    options_text = "\n".join([f"{key.upper()}) {value}" for key, value in options_dict.items()])
    
    prompt = f"""
    Sen bir uzman sınav öğretmenisin. Aşağıdaki soruyu adım adım çöz ve açıkla.

    SORU METNİ:
    {question.text}

    SEÇENEKLER:
    {options_text}

    DOĞRU CEVAP: {question.correct_option}
    ÖĞRENCİNİN İŞARETLEDİĞİ CEVAP: {user_selected_option}

    Lütfen aşağıdaki formata göre bir analiz yap:
    1.  **Sorunun Analizi:** Sorunun ne istediğini kısaca özetle.
    2.  **Adım Adım Çözüm:** Soruyu çözmek için gereken adımları mantıksal bir sırayla açıkla.
    3.  **Doğru Cevabın Açıklaması:** Neden '{question.correct_option}' seçeneğinin doğru olduğunu detaylandır.
    4.  **Öğrencinin Cevabının Analizi:** Öğrencinin seçtiği '{user_selected_option}' seçeneğinin neden yanlış olduğunu veya hangi yanılgıdan kaynaklanabileceğini açıkla.
    5.  **Soru Değerlendirmesi:** Eğer sorunun kendisinde, seçeneklerde veya belirtilen doğru cevapta bir hata, belirsizlik veya mantıksızlık varsa, bunu "SORU HATALI OLABİLİR" başlığı altında net bir şekilde belirt ve nedenini açıkla. Eğer soru geçerliyse bu bölümü ekleme.
    """

    # --- Gemini API Çağrısı için Payload Hazırlama ---
    gemini_parts = [{'text': prompt}]
    
    if question.image_filename:
        try:
            image_path = os.path.join(current_app.config['UPLOAD_FOLDER'], question.image_filename)
            if os.path.exists(image_path):
                with open(image_path, "rb") as image_file:
                    image_base64 = base64.b64encode(image_file.read()).decode('utf-8')
                
                gemini_parts.append({
                    "inline_data": {
                        "mime_type": "image/jpeg",
                        "data": image_base64
                    }
                })
        except Exception as e:
            current_app.logger.error(f"Soru resmi okunurken hata oluştu: {e}")

    payload = {"contents": [{"parts": gemini_parts}]}
    
    # --- Yanıtı Hazırlama ve Döndürme ---
    try:
        api_key = current_app.config.get('GEMINI_API_KEY')
        if not api_key:
            return jsonify({'message': 'Yapay zeka servisi yapılandırılmamış.'}), 500
            
        api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-lite:generateContent?key={api_key}"
        
        # Frontend'e Gemini API'sine göndereceği bilgileri döndür
        return jsonify({
            'gemini_payload': payload,
            'gemini_url': api_url
        }), 200

    except Exception as e:
        current_app.logger.error(f"Gemini API isteği hazırlanırken hata: {e}", exc_info=True)
        return jsonify({'message': 'Yapay zeka analizi sırasında beklenmedik bir hata oluştu.'}), 500
