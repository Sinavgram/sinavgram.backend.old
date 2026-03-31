# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from threading import Thread
from flask import current_app, render_template
from flask_mail import Message
from extensions import mail  # mail nesnesini extensions'dan import edin
import random
import string
import imaplib
import email
import ssl
from email.header import decode_header
from email.utils import parseaddr

# ==============================================================================
# STANDART ASENKRON E-POSTA GÖNDERME MOTORU
# ==============================================================================
def send_async_email(flask_app, msg_params):
    """
    Tüm e-postaları arka planda gönderen merkezi fonksiyon.
    Message nesnesini burada oluşturarak tutarlılık sağlar.
    """
    with flask_app.app_context():
        try:
            # charset='utf-8' parametresi burada eklenerek tüm e-postalarda
            # Türkçe karakter sorunu kökten çözülür.
            if 'charset' not in msg_params:
                msg_params['charset'] = 'utf-8'
            
            msg = Message(**msg_params)
            mail.send(msg)
            flask_app.logger.info(f"Asenkron e-posta başarıyla gönderildi: {msg.recipients}")
        except Exception as e:
            flask_app.logger.error(f"Asenkron e-posta gönderimi başarısız: {e}", exc_info=True)

# ==============================================================================
# E-POSTA GÖNDERİMİNİ TETİKLEYEN YARDIMCI FONKSİYONLAR
# ==============================================================================

def send_verification_email(to_email, user_username, verify_url):
    """Kullanıcıya e-posta doğrulama linki gönderir."""
    flask_app = current_app._get_current_object()
    subject = f"{flask_app.config['APP_NAME']} E-posta Doğrulama"
    html_body = render_template('emails/email_verification.html', user_username=user_username,
                                verify_url=verify_url, current_year=datetime.utcnow().year)
    
    msg_params = {
        'subject': subject,
        'recipients': [to_email],
        'html': html_body,
        'sender': flask_app.config['MAIL_DEFAULT_SENDER']
    }
    Thread(target=send_async_email, args=[flask_app, msg_params]).start()

def send_password_reset_email(to_email, user_username, reset_url_on_web_param):
    """Kullanıcıya şifre sıfırlama linki gönderir."""
    flask_app = current_app._get_current_object()
    subject = f"{flask_app.config['APP_NAME']} Şifre Sıfırlama İsteği"
    html_body = render_template('emails/email_password_reset.html',
                                user_username=user_username,
                                reset_url_on_web=reset_url_on_web_param,
                                app_name=flask_app.config['APP_NAME'],
                                expiration_minutes=flask_app.config['PASSWORD_RESET_TOKEN_EXPIRATION_SECONDS'] // 60,
                                current_year=datetime.utcnow().year)
    
    msg_params = {
        'subject': subject,
        'recipients': [to_email],
        'html': html_body,
        'sender': flask_app.config['MAIL_DEFAULT_SENDER']
    }
    Thread(target=send_async_email, args=[flask_app, msg_params]).start()
    current_app.logger.info(f"Şifre sıfırlama e-postası kuyruğa eklendi: {to_email}")

def send_payment_receipt_email(user_obj, payment_obj):
    """Kullanıcıya ödeme makbuzu gönderir."""
    flask_app = current_app._get_current_object()
    subject = f"{flask_app.config['APP_NAME']} - Premium Üyelik Makbuzu ({payment_obj.payment_gateway_transaction_id})"
    html_body = render_template('emails/email_payment_receipt.html', user=user_obj, payment=payment_obj)
    
    msg_params = {
        'subject': subject,
        'recipients': [user_obj.email],
        'html': html_body,
        'sender': flask_app.config['MAIL_DEFAULT_SENDER']
    }
    Thread(target=send_async_email, args=[flask_app, msg_params]).start()
    flask_app.logger.info(f"Ödeme makbuzu e-postası kuyruğa eklendi: {user_obj.email}")

def send_admin_login_code_email(to_email, username, code):
    """Admin kullanıcısına 2FA giriş kodu gönderir."""
    flask_app = current_app._get_current_object()
    subject = f"{flask_app.config['APP_NAME']} Admin Giriş Kodu"
    html_body = render_template('emails/email_admin_login_code.html',
                                user_username=username,
                                login_code=code,
                                app_name=flask_app.config['APP_NAME'],
                                expiration_minutes=flask_app.config['ADMIN_2FA_CODE_EXPIRATION_MINUTES'])
    
    msg_params = {
        'subject': subject,
        'recipients': [to_email],
        'html': html_body,
        'sender': flask_app.config['MAIL_DEFAULT_SENDER']
    }
    Thread(target=send_async_email, args=[flask_app, msg_params]).start()
    flask_app.logger.info(f"Admin 2FA giriş kodu gönderildi: {to_email}")

def send_new_login_notification_email(user, ip_address, invalidation_url):
    """Kullanıcıya yeni bir konumdan giriş yapıldığına dair bildirim gönderir."""
    flask_app = current_app._get_current_object()
    subject = f"[{flask_app.config['APP_NAME']}] Güvenlik Uyarısı: Hesabınıza Yeni Bir Cihazdan Giriş Yapıldı"
    html_body = render_template('emails/email_new_login_notification.html',
                                user=user,
                                ip_address=ip_address,
                                invalidation_url=invalidation_url,
                                timestamp=datetime.now(timezone.utc))
    
    msg_params = {
        'subject': subject,
        'recipients': [user.email],
        'html': html_body,
        'sender': flask_app.config['MAIL_DEFAULT_SENDER']
    }
    Thread(target=send_async_email, args=[flask_app, msg_params]).start()
    flask_app.logger.info(f"Yeni giriş bildirimi e-postası kuyruğa eklendi: {user.email}")

def send_newsletter_broadcast(subject, html_body, recipients):
    """
    Tüm abonelere tek tek e-posta göndererek bülten dağıtımı yapar.
    Bu yöntem, BCC'nin SMTP sunucuları tarafından reddedilmesini önlemek için kullanılır.
    """
    flask_app = current_app._get_current_object()
    
    # Her bir alıcı için döngü oluştur ve ayrı bir e-posta gönder.
    for recipient_email in recipients:
        msg_params = {
            'subject': subject,
            'html': html_body,
            'sender': flask_app.config['MAIL_DEFAULT_SENDER'],
            'recipients': [recipient_email]  # Alıcı listesi sadece tek bir e-posta içerir
        }
        
        # Her e-posta için ayrı bir thread başlat
        Thread(target=send_async_email, args=[flask_app, msg_params]).start()
        
    flask_app.logger.info(f"{len(recipients)} aboneye bülten gönderme işlemi için thread'ler başlatıldı.")


# ==============================================================================
# DİĞER YARDIMCI FONKSİYONLAR
# ==============================================================================

def allowed_file(filename):
    """Yüklenen dosyanın uzantısının izin verilenler arasında olup olmadığını kontrol eder."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def generate_verification_code(length=6):
    """Rastgele sayısal bir doğrulama kodu üretir."""
    return "".join(random.choices(string.digits, k=length))

