# app.py
import os
import hashlib
import html
from datetime import datetime, timedelta, timezone
from flask import Flask, request, send_from_directory, session, current_app, abort, render_template # Added render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import request, jsonify, render_template
from config import Config
Config.create_folders() # Create folders on import/startup

from extensions import db, migrate, mail, cors, jwt_manager
from models import User, Question, QuestionReport, Subtopic, Course # Import models used by context processors or before_request
# Make sure commands.py exists in your project directory.
# If it's in a subfolder (e.g., 'utils/commands.py'), adjust the import accordingly:
# from utils.commands import register_commands # For CLI

from commands import add_initial_data, register_commands # For CLI

# Import Blueprints
from blueprints.auth_bp import auth_bp, admin_auth_bp
from blueprints.main_bp import main_bp
from blueprints.courses_bp import courses_bp
from blueprints.questions_bp import questions_bp
from blueprints.user_bp import user_bp
from blueprints.admin_panel_bp import admin_panel_bp
from blueprints.community_bp import community_bp
from blueprints.legal_bp import legal_bp
from blueprints.ai_bp import ai_bp

def create_app(config_class=Config):
    app = Flask(__name__,
                instance_path=config_class.INSTANCE_FOLDER_PATH, # From Config
                template_folder=config_class.TEMPLATES_FOLDER,   # From Config
                static_folder=config_class.STATIC_FOLDER)       # From Config
    app.config.from_object(config_class)

    # Initialize Flask extensions
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    # CORS configuration should be specific if not global
    cors.init_app(app, resources={r"/api/*": {"origins": app.config.get("CORS_ALLOWED_ORIGINS")}})
    jwt_manager.init_app(app) # Initialize Flask-JWT-Extended

    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_auth_bp) # Register the new admin auth blueprint
    app.register_blueprint(main_bp)
    app.register_blueprint(courses_bp)
    app.register_blueprint(questions_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_panel_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(legal_bp)
    app.register_blueprint(ai_bp)
    
    # Register CLI commands
    register_commands(app)

    # --- IP Kısıtlama Fonksiyonu (Adminler için) ---
    @app.before_request
    def limit_admin_access_by_ip():
        # Apply this only to admin panel blueprint paths, not admin_auth_bp paths like /admin/login
        if request.blueprint == 'admin_panel_bp': # Check if current request is for admin_panel_bp
            client_ip = request.remote_addr
            try:
                hashed_client_ip = hashlib.sha256(client_ip.encode('utf-8')).hexdigest()
            except Exception as e:
                app.logger.error(f"İstemci IP'si hashlenirken hata: {client_ip}, Hata: {e}")
                abort(403); return

            allowed_ip_hashes = set()
            admin_ips_file_path = app.config['ADMIN_IPS_FILE']

            if os.path.exists(admin_ips_file_path):
                try:
                    with open(admin_ips_file_path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and ':' in line:
                                try: _name, hashed_ip_val = line.split(':', 1); allowed_ip_hashes.add(hashed_ip_val.strip())
                                except ValueError: app.logger.warning(f"Admin IP dosyasında hatalı format: '{line}'")
                except Exception as e:
                    app.logger.error(f"Admin IP dosyası ({admin_ips_file_path}) okunurken hata: {e}")
                    if app.debug and client_ip == '127.0.0.1':
                        app.logger.warning(f"Admin IP dosyası okunamadı, yerel {client_ip} için {request.path} yoluna izin verildi.")
                        return
                    abort(403)

            if not allowed_ip_hashes:
                if app.debug and client_ip == '127.0.0.1':
                    app.logger.info(f"Admin IP listesi boş, yerel {client_ip} için {request.path} yoluna izin verildi.")
                    return
                app.logger.warning(f"Admin IP listesi boş. IP {client_ip} (Hash: {hashed_client_ip}) için {request.path} engellendi.")
                abort(403)

            if hashed_client_ip not in allowed_ip_hashes:
                app.logger.warning(f"Yetkisiz IP ({client_ip}, Hash: {hashed_client_ip}) {request.path} denemesi engellendi.")
                abort(403)

    # --- Context Processors ---
    @app.context_processor
    def inject_global_vars():
        current_time_utc_aware = datetime.now(timezone.utc)
        context = {
            'now': current_time_utc_aware,
            'now_utc': current_time_utc_aware,
            'app_name': app.config['APP_NAME'],
            'config': app.config, # Expose entire config if needed, or specific items
            'admin_user': None,
            'pending_count': 0,
            'reported_count': 0
        }
        if 'admin_id' in session:
            admin_user_ctx = User.query.get(session['admin_id'])
            if admin_user_ctx and admin_user_ctx.is_admin and admin_user_ctx.is_active:
                context['admin_user'] = admin_user_ctx
                context['pending_count'] = Question.query.filter_by(status='pending').count()
                context['reported_count'] = QuestionReport.query.join(Question, QuestionReport.question_id == Question.id)\
                    .filter(QuestionReport.status == 'new', Question.status != 'rejected').count()
        return context

    @app.context_processor
    def utility_processor():
        def get_course_name_from_subtopic(subtopic_id):
            subtopic = Subtopic.query.get(subtopic_id)
            return html.escape(subtopic.course.name) if subtopic and subtopic.course else "Bilinmeyen Ders"
        def get_subtopic_name(subtopic_id):
            subtopic = Subtopic.query.get(subtopic_id)
            return html.escape(subtopic.name) if subtopic else "Bilinmeyen Alt Konu"
        def get_user_username(user_id):
            user = User.query.get(user_id)
            return html.escape(user.username) if user else "Bilinmiyor"
        return dict(get_course_name_from_subtopic=get_course_name_from_subtopic,
                    get_subtopic_name=get_subtopic_name,
                    get_user_username=get_user_username)
    
    # Session lifetime for admin
    @app.before_request
    def make_session_permanent():
        session.permanent = True
        app.permanent_session_lifetime = timedelta(days=current_app.config.get('ADMIN_SESSION_LIFETIME_DAYS', 7))

    return app

app = create_app()

@app.errorhandler(404)
def page_not_found(e):
    # Bir 404 hatası oluştuğunda error.html sayfasını gösterir
    return render_template('error.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    # Bu hata için de aynı şablonu kullanabiliriz, ancak
    # daha spesifik bir hata sayfası oluşturmak daha iyi olabilir
    return render_template('error.html'), 500

@app.errorhandler(Exception) # Veya @app.errorhandler(500)
def handle_error(e):
    # Eğer istek bir API endpoint'ine yapılıyorsa (URL /api/ ile başlıyorsa)
    if request.path.startswith('/api/'):
        # Hata ne olursa olsun JSON formatında bir yanıt döndür.
        # Gerçek hatayı loglamak daha iyi bir pratiktir.
        # from werkzeug.exceptions import HTTPException
        # if isinstance(e, HTTPException):
        #    return jsonify(error=e.description), e.code
        
        return jsonify(message="Sunucuda beklenmedik bir hata oluştu."), 500
    
    # Eğer istek normal bir web sayfası içinse, HTML hata sayfasını göster.
    return render_template("error.html"), 500