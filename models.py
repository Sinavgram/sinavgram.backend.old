# models.py
import os
import uuid
import jwt # PyJWT
from datetime import datetime, timedelta, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app, url_for
from extensions import db # Import db from extensions
import secrets

# Association tables for many-to-many relationships
question_likes = db.Table('question_likes',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('question_id', db.Integer, db.ForeignKey('question.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

question_saves = db.Table('saved_questions',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('question_id', db.Integer, db.ForeignKey('question.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow)
)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    score = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_premium = db.Column(db.Boolean, default=False, nullable=False)
    premium_expiration_date = db.Column(db.DateTime, nullable=True)
    avatar = db.Column(db.String(255), nullable=True) # Assuming avatar filename
    badges = db.Column(db.JSON, nullable=True)
    known_ips = db.Column(db.JSON, nullable=True) # Bilinen IP adreslerini JSON listesi olarak saklar
    token_version = db.Column(db.Integer, nullable=False, default=0) # Tüm oturumları geçersiz kılmak için
    security_token = db.Column(db.String(64), unique=True, nullable=True) # Tek kullanımlık güvenlik token'ı
    security_token_expiration = db.Column(db.DateTime(timezone=True), nullable=True)# Güvenlik token'ı son kullanma tarihi

    submitted_questions = db.relationship('Question',
                                    foreign_keys='Question.submitted_by_user_id',
                                    back_populates='submitter',
                                    lazy=True)
    answers = db.relationship('UserAnswer', backref='user', lazy=True)
    reports = db.relationship('QuestionReport', backref='reporter', lazy=True)
    payments = db.relationship('Payment', backref='user', lazy='dynamic')

    liked_questions = db.relationship('Question', secondary=question_likes,
                                      back_populates='liked_by', lazy='dynamic')
    saved_questions = db.relationship('Question', secondary=question_saves,
                                      back_populates='saved_by', lazy='dynamic')

    def generate_invalidation_token(self, expires_in=86400):
        """
        Yeni giriş bildirimi e-postasındaki "Girişleri İptal Et" linki için
        tek kullanımlık, güvenli bir token oluşturur.
        """
        self.security_token = secrets.token_urlsafe(32)
        self.security_token_expiration = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        return self.security_token

    def get_avatar_url(self):
        # Consider using a more dynamic way to get API_BASE_URL or url_for
        api_base_url = current_app.config.get('API_BASE_URL', 'http://192.168.1.76:5000')
        if self.avatar:
            return f"{api_base_url}/static/uploads/avatars/{self.avatar}"
        else:
            return f"{api_base_url}/static/default_avatar.png"

    def set_password(self, password): self.password_hash = generate_password_hash(password)
    def check_password(self, password): return check_password_hash(self.password_hash, password)

    def get_email_verification_token(self, expires_in=3600):
        return jwt.encode(
            {"verify_email_for_user_id": self.id, "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in)},
            current_app.config['SECRET_KEY'],
            algorithm="HS256"
        )

    @staticmethod
    def verify_email_verification_token(token):
        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            user_id = payload.get('verify_email_for_user_id')
            return User.query.get(user_id) if user_id else None
        except jwt.ExpiredSignatureError: return 'expired'
        except jwt.InvalidTokenError: return 'invalid'
        except Exception: return None

    def get_password_reset_token(self, expires_in=None):
        if expires_in is None:
            expires_in = current_app.config['PASSWORD_RESET_TOKEN_EXPIRATION_SECONDS']
        return jwt.encode(
            {"reset_password_for_user_id": self.id, "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in)},
            current_app.config['SECRET_KEY'],
            algorithm="HS256"
        )

    @staticmethod
    def verify_password_reset_token(token):
        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=["HS256"])
            user_id = payload.get('reset_password_for_user_id')
            if not user_id:
                return 'invalid_payload'
            user = User.query.get(user_id)
            if not user or not user.is_active:
                return 'user_not_found_or_inactive'
            return user
        except jwt.ExpiredSignatureError:
            return 'expired'
        except jwt.InvalidTokenError:
            return 'invalid_token'
        except Exception as e:
            current_app.logger.error(f"Şifre sıfırlama token doğrulama hatası: {e}")
            return 'error'

    @property
    def has_active_premium(self):
        if self.is_premium and self.premium_expiration_date:
            exp_date_aware = self.premium_expiration_date
            if exp_date_aware.tzinfo is None or exp_date_aware.tzinfo.utcoffset(exp_date_aware) is None:
                exp_date_aware = exp_date_aware.replace(tzinfo=timezone.utc)
            return datetime.now(timezone.utc) < exp_date_aware
        return False
    def __repr__(self): return f'<User {self.username}>'

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    subtopics = db.relationship('Subtopic', backref='course', lazy='dynamic')
    def __repr__(self): return f'<Course {self.name}>'

class Subtopic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    pdf_filename = db.Column(db.String(255), nullable=True)
    questions = db.relationship('Question', backref='subtopic', lazy='dynamic')
    __table_args__ = (db.UniqueConstraint('name', 'course_id', name='_subtopic_name_course_id_uc'),)
    def __repr__(self): return f'<Subtopic {self.name} (Course ID: {self.course_id})>'

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subtopic_id = db.Column(db.Integer, db.ForeignKey('subtopic.id'), nullable=False)
    text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(255), nullable=False)
    option_b = db.Column(db.String(255), nullable=False)
    option_c = db.Column(db.String(255), nullable=False)
    option_d = db.Column(db.String(255), nullable=False)
    option_e = db.Column(db.String(255), nullable=False)
    correct_option = db.Column(db.String(1), nullable=False)
    image_filename = db.Column(db.String(255), nullable=True)
    link_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    status = db.Column(db.String(20), default='pending', nullable=False)
    submitted_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_premium_only = db.Column(db.Boolean, default=False, nullable=False)

    submitter = db.relationship('User',
                            foreign_keys=[submitted_by_user_id],
                            back_populates='submitted_questions')
    answers = db.relationship('UserAnswer', backref='question', lazy=True)
    reports = db.relationship('QuestionReport', backref='question', lazy=True)

    liked_by = db.relationship('User', secondary=question_likes,
                               back_populates='liked_questions', lazy='dynamic')
    saved_by = db.relationship('User', secondary=question_saves,
                               back_populates='saved_questions', lazy='dynamic')
    
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Add this if a general 'user' (author) is needed
    user = db.relationship('User', foreign_keys=[user_id], backref=db.backref('questions_authored', lazy=True)) # Change backref name


    def get_options_dict(self): return {"A": self.option_a, "B": self.option_b, "C": self.option_c, "D": self.option_d, "E": self.option_e}
    def get_image_url(self):
        if self.image_filename:
            # Ensure this 'uploaded_file_route' matches the route in your main_bp or a dedicated static file blueprint
            return url_for('main_bp.uploaded_file_route', filename=self.image_filename, _external=True)
        return None
    def __repr__(self): return f'<Question {self.id}: {self.text[:30]}... (Subtopic ID: {self.subtopic_id})>'

class UserAnswer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    selected_option = db.Column(db.String(1), nullable=False)
    is_correct = db.Column(db.Boolean, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    def __repr__(self): return f'<UserAnswer by {self.user_id} for Q{self.question_id}>'

class QuestionReport(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'), nullable=False)
    reported_by_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='new', nullable=False) # new, reviewed, resolved, dismissed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    def __repr__(self): return f'<QuestionReport {self.id} for Q{self.question_id}>'

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    payment_gateway_transaction_id = db.Column(db.String(120), unique=True, nullable=False)
    conversation_id = db.Column(db.String(120), nullable=True)
    plan_type = db.Column(db.String(20), nullable=False)
    amount_paid = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='TRY')
    status = db.Column(db.String(30), nullable=False, default='succeeded')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    def __repr__(self): return f'<Payment {self.id} - PGTID: {self.payment_gateway_transaction_id}>'

class MailingList(db.Model):
    __tablename__ = 'mailing_list'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<MailingList {self.email}>'