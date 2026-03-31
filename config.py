# config.py
import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'zkm231'
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    INSTANCE_FOLDER_PATH = os.path.join(BASE_DIR, 'instance')
    TEMPLATES_FOLDER = os.path.join(BASE_DIR, 'templates')
    STATIC_FOLDER = os.path.join(BASE_DIR, 'static')

    # --- PostgreSQL Configuration ---
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'postgresql://postgres:password@localhost:5432/sinavgram'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(STATIC_FOLDER, 'uploads', 'question_images')
    UPLOAD_FOLDER_AVATARS = os.path.join(STATIC_FOLDER, 'uploads', 'avatars') # Kullanıcı avatarları için klasör
    SUBTOPIC_PDF_FOLDER = os.path.join(STATIC_FOLDER, 'uploads', 'subtopic_pdfs') # Alt konu PDF'leri için klasör
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    API_BASE_URL = os.environ.get('API_BASE_URL') or "your-api-base-url" # Uygulamanızın temel URL'i
    APP_NAME = "Sınavgram"
    
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'your-mail-server.com' # Örneğin: 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ('true', '1', 't')
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'your-mail@yourdomain.com' # E-posta adresiniz
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'password' # E-posta şifreniz veya uygulama şifreniz
    MAIL_DEFAULT_SENDER = (APP_NAME + ' Destek', MAIL_USERNAME)

    POINTS_CORRECT_ANSWER = 1000
    POINTS_WRONG_ANSWER = -250
    POINTS_BLANK_ANSWER = 0
    SHOW_AD_AFTER_N_ANSWERS = 1 # Premium olmayan kullanıcılar için kaç cevapta bir reklam gösterileceği
    CORS_ALLOWED_ORIGINS = os.environ.get('CORS_ALLOWED_ORIGINS', 'http://localhost:8081,http://127.0.0.1:8000,null').split(',')

    PREMIUM_PRICE_MONTHLY_TRY = 49.99
    PREMIUM_DURATION_MONTHLY_DAYS = 30
    PREMIUM_PRICE_YEARLY_TRY = 499.99
    PREMIUM_DURATION_YEARLY_DAYS = 365

    ADMIN_IPS_FILE = os.path.join(INSTANCE_FOLDER_PATH, "admin_ips.txt")
    USE_PROXY_FIX = False # Eğer bir proxy arkasında çalışıyorsanız True yapın
    ADMIN_2FA_CODE_EXPIRATION_MINUTES = 10
    PASSWORD_RESET_TOKEN_EXPIRATION_SECONDS = 3600 # Şifre sıfırlama token geçerlilik süresi (1 saat)

    GOOGLE_CREDENTIALS_PATH = os.path.join(INSTANCE_FOLDER_PATH, 'credentials.json')
    # Google Play Console'daki uygulamanızın paket adı.
    GOOGLE_PACKAGE_NAME = 'com.developer.sinavgram'

    JWT_SECRET_KEY = SECRET_KEY # For flask_jwt_extended
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    APPLE_SHARED_SECRET = "apple-secret-key" #
    GEMINI_API_KEY = 'gemini-api-key'
    def create_folders():
        folders_to_create = [
            Config.INSTANCE_FOLDER_PATH, Config.UPLOAD_FOLDER,
            Config.TEMPLATES_FOLDER, os.path.join(Config.TEMPLATES_FOLDER, 'admin'),
            os.path.join(Config.TEMPLATES_FOLDER, 'includes'),
            Config.STATIC_FOLDER, os.path.join(Config.STATIC_FOLDER, 'css'),
            Config.SUBTOPIC_PDF_FOLDER # PDF klasörünü de oluştur
        ]
        for folder in folders_to_create:
            if not os.path.exists(folder):
                os.makedirs(folder)
                print(f"Created directory: {folder}")

# Call folder creation at import time if needed, or call it explicitly in app.py
# Config.create_folders() # You might want to call this in your main app.py after app creation