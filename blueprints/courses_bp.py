# blueprints/courses_bp.py
import os
from flask import Blueprint, jsonify, current_app, request, url_for, make_response, send_from_directory
from models import Course, Subtopic, UserAnswer, Question # Assuming User is for @token_required
from decorators import token_required # If you use token_required here
from extensions import db # If doing db queries like .func.random()

courses_bp = Blueprint('courses_bp', __name__, url_prefix='/api')

@courses_bp.route('/courses', methods=['GET'])
@token_required
def get_courses_api(current_user_obj):
    if not current_user_obj.email_verified:
        return jsonify({'message': 'Lütfen e-postanızı doğrulayın.'}), 403
    courses = Course.query.order_by(Course.name).all()
    return jsonify([{'id': course.id, 'name': course.name} for course in courses]), 200

@courses_bp.route('/course/<int:course_id>/subtopics', methods=['GET'])
@token_required
def get_subtopics_for_course_api(current_user_obj, course_id):
    if not current_user_obj.email_verified:
        return jsonify({'message': 'Lütfen e-postanızı doğrulayın.'}), 403
    course = Course.query.get_or_404(course_id)
    subtopics = Subtopic.query.filter_by(course_id=course.id).order_by(Subtopic.name).all()
    subtopics_data = []
    for st in subtopics:
        pdf_url = None
        if st.pdf_filename:
            # This endpoint 'courses_bp.download_subtopic_pdf' must exist
            pdf_url = url_for('courses_bp.download_subtopic_pdf', subtopic_id=st.id, _external=False)
        subtopics_data.append({'id': st.id, 'name': st.name, 'course_id': st.course_id, 'pdf_url': pdf_url})
    return jsonify(subtopics_data), 200


@courses_bp.route('/subtopic/<int:subtopic_id>/pdf', methods=['GET'])
# Add if PDF download requires login
def download_subtopic_pdf(subtopic_id):
    subtopic = Subtopic.query.get_or_404(subtopic_id)
    if not subtopic.pdf_filename:
        return jsonify({'message': 'Bu alt konu için PDF dosyası bulunmamaktadır.'}), 404

    pdf_folder = current_app.config['SUBTOPIC_PDF_FOLDER']
    try:
        response = make_response(send_from_directory(pdf_folder, subtopic.pdf_filename))
        # response.headers['Content-Disposition'] = f'inline; filename="{subtopic.pdf_filename}"' # Optional: suggest filename
        return response
    except FileNotFoundError:
        current_app.logger.error(f"PDF dosyası bulunamadı: {os.path.join(pdf_folder, subtopic.pdf_filename)}")
        return jsonify({'message': 'PDF dosyası sunucuda bulunamadı.'}), 404
    except Exception as e:
        current_app.logger.error(f"PDF gönderilirken hata: {e}")
        return jsonify({'message': 'PDF dosyası gönderilirken bir hata oluştu.'}), 500