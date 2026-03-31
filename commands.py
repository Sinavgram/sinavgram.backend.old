# commands.py
import click
import html # For escaping in initial data display if any
from flask import current_app, url_for
from flask.cli import with_appcontext
from extensions import db # Assuming db is initialized in extensions.py
from models import User, Course, Subtopic, Question # Import all necessary models
# from config import Config # Not strictly needed here unless accessing specific config values directly

def add_initial_data():
    """Adds initial admin user, courses, subtopics, and sample questions."""
    db.create_all() # Usually handled by migrations or main app init if not using Flask-Migrate

    # Use current_app.config for accessing configuration values
    new_admin_email = current_app.config.get('MAIL_USERNAME', 'mehmetalperkocaoglu@gmail.com')
    new_admin_username = 'mehmetalper04' # Or from config
    admin_pass = current_app.config.get('ADMIN_DEFAULT_PASSWORD', 'adminpass') # Get from config or use a default

    admin_user = User.query.filter_by(username=new_admin_username).first() or \
                 User.query.filter_by(email=new_admin_email).first()
    if not admin_user:
        admin_user = User(username=new_admin_username, email=new_admin_email,
                          is_admin=True, email_verified=True, is_active=True)
        admin_user.set_password(admin_pass)
        db.session.add(admin_user)
        click.echo(f"Default admin user created: {new_admin_username}")
    else:
        admin_user.is_admin = True # Ensure flags are set
        admin_user.is_active = True
        admin_user.email_verified = True
        # Optionally update password if needed, but be careful
        # admin_user.set_password(admin_pass) # Uncomment if you want to reset password on init
        click.echo(f"Default admin user ({new_admin_username}) already exists, status updated.")
    db.session.commit() # Commit admin first to get ID

    # Re-fetch admin user to ensure it's session-bound and has an ID for relationships
    admin_user_for_q = User.query.filter_by(username=new_admin_username).first()
    if not admin_user_for_q:
        click.secho("Critical: Admin user not found after creation/update. Cannot add sample questions.", fg="red")
        # Potentially raise an error or exit if admin user is crucial for further steps
        return

    # Reduced for brevity, expand with your full data set from the original app.py
    all_courses_data = {
        "Fizik": {
            "TYT Konuları": ["Fiziğin Tanımı ve Özellikleri", "Fiziğin Alt Dalları", "Fiziğin Diğer Disiplinlerle İlişkisi", "Fiziksel Niceliklerin Sınıflandırılması", "Fizik ve Bilim Araştırma Merkezleri","Madde ve Özkütle", "Dayanıklılık", "Adezyon ve Kohezyon","Hareket (TYT)", "Kuvvet (TYT)", "Newton'un Hareket Yasaları (TYT)", "Sürtünme Kuvveti (TYT)","İş, Güç ve Enerji", "Mekanik Enerji", "Enerjinin Korunumu ve Enerji Dönüşümleri", "Verim", "Enerji Kaynakları","Isı ve Sıcaklık", "Hal Değişimi", "Isıl Denge", "Enerji İletim Yolları ve Enerji Tüketim Hızı", "Genleşme","Elektrik Yükü", "Elektrikle Yüklenme Çeşitleri", "Elektroskop", "İletken ve Yalıtkanlarda Yük Dağılımı", "Topraklama", "Coulomb Kuvveti", "Elektrik Alanı (TYT)","Elektrik Akımı, Potansiyel Farkı ve Direnci", "Elektrik Devreleri (TYT)", "Mıknatıs ve Manyetik Alan", "Akım ve Manyetik Alan","Basınç", "Kaldırma Kuvveti","Temel Dalga Bilgileri", "Yay Dalgası", "Su Dalgası", "Ses Dalgası", "Deprem Dalgaları","Aydınlanma", "Gölge", "Yansıma", "Düzlem Ayna", "Kırılma", "Mercekler", "Prizmalar"],
            "AYT Konuları": ["Vektörler", "Bağıl Hareket", "Newton'un Hareket Yasaları (AYT)", "Bir Boyutta Sabit İvmeli Hareket", "İki Boyutta Sabit İvmeli Hareket","Enerji ve Hareket (AYT)", "İtme ve Çizgisel Momentum", "Tork", "Denge (AYT)", "Basit Makineler","Elektriksel Kuvvet ve Elektrik Alanı (AYT)", "Elektriksel Potansiyel", "Düzgün Elektrik Alanı ve Sığa", "Manyetizma ve Elektromanyetik İndükleme", "Alternatif Akım", "Transformatörler","Düzgün Çembersel Hareket", "Dönerek Öteleme Hareketi", "Açısal Momentum", "Kütle Çekimi ve Kepler Kanunu","Basit Harmonik Hareket","Dalgalarda Kırınım, Girişim ve Doppler Olayı", "Elektromanyetik Dalgalar","Atom Kavramının Tarihsel Gelişimi", "Büyük Patlama ve Evrenin Oluşumu", "Radyoaktivite","Özel Görelelik", "Kuantum Fiziğine Giriş", "Fotoelektrik Olayı", "Compton Saçılması ve De Broglie Dalga Boyu","Görüntüleme Teknolojileri", "Yarı İletken Teknolojisi", "Süper İletkenler", "Nanoteknoloji", "Lazer Işınları"]
        },
        "Kimya": {
            "TYT Konuları": ["Kimya Bilimi", "Atom ve Yapısı (TYT)", "Periyodik Sistem (TYT)", "Kimyasal Türler Arası Etkileşimler", "Asitler-Bazlar ve Tuzlar", "Bileşikler", "Kimyasal Tepkimeler", "Kimyanın Temel Yasaları", "Maddenin Halleri", "Karışımlar", "Endüstride ve Canlılarda Enerji", "Kimya Her Yerde"],
            "AYT Konuları": ["Modern Atom Teorisi", "Kimyasal Hesaplamalar", "Gazlar", "Sıvı Çözeltiler (AYT)", "Kimya ve Enerji","Tepkimelerde Hız", "Kimyasal Denge", "Sıvı Çözeltilerde Denge", "Kimya ve Elektrik", "Karbon Kimyasına Giriş","Organik Bileşikler", "Hayatımızdaki Kimya"]
        },
        "Matematik": {
            "TYT Konuları": ["Sayılar (TYT)", "Sayı Basamakları (TYT)", "Bölme ve Bölünebilme", "OBEB-OKEK", "Rasyonel Sayılar (TYT)","Basit Eşitsizlikler (TYT)", "Mutlak Değer (TYT)", "Üslü Sayılar (TYT)", "Köklü Sayılar (TYT)", "Çarpanlara Ayırma (TYT)","Oran Orantı (TYT)", "Denklem Çözme (TYT)", "Problemler (TYT)", "Kümeler (TYT)", "Fonksiyonlar (TYT)","Permütasyon (TYT)", "Kombinasyon (TYT)", "Binom (TYT)", "Olasılık (TYT)", "İstatistik (TYT)","2. Dereceden Denklemler (TYT)", "Karmaşık Sayılar (TYT)", "Parabol (TYT)", "Polinomlar (TYT)"],
            "AYT Konuları": ["Temel Kavramlar (AYT)", "Sayı Basamakları (AYT)", "Rasyonel Sayılar (AYT)", "Ondalıklı Sayılar", "Basit Eşitsizlikler (AYT)","Mutlak Değer (AYT)", "Üslü Sayılar (AYT)", "Köklü Sayılar (AYT)", "Çarpanlara Ayırma (AYT)", "Denklem Çözme (AYT)","Oran-Orantı (AYT)", "Problemler (AYT)", "Fonksiyonlar (AYT)", "Kümeler (AYT)", "Permütasyon (AYT)","Kombinasyon (AYT)", "Binom (AYT)", "Olasılık (AYT)", "İstatistik (AYT)", "2. Dereceden Denklemler (AYT)","Karmaşık Sayılar (AYT)", "Parabol (AYT)", "Polinomlar (AYT)", "Mantık (AYT Matematik Altında)", "Modüler Aritmetik","Eşitsizlikler (AYT)", "Logaritma", "Diziler", "Seriler", "Limit ve Süreklilik", "Türev", "İntegral"]
        },
        "Geometri": {
            "TYT ve AYT Ortak Konular": ["Doğruda ve Üçgende Açılar", "Dik ve Özel Üçgenler", "Dik Üçgende Trigonometrik Bağıntılar", "İkizkenar ve Eşkenar Üçgen","Üçgende Alanlar", "Üçgende Açıortay Bağıntıları", "Üçgende Kenarortay Bağıntıları", "Üçgende Eşlik ve Benzerlik","Üçgende Açı-Kenar Bağıntıları", "Çokgenler", "Dörtgenler", "Yamuk", "Paralelkenar", "Eşkenar Dörtgen - Deltoid","Dikdörtgen", "Çemberde Açılar", "Çemberde Uzunluk", "Daire", "Prizmalar", "Piramitler", "Küre","Koordinat Düzlemi ve Noktanın Analitiği", "Vektörler-1 (Geometri)", "Doğrunun Analitiği", "Tekrar Eden, Dönen ve Yansıyan Şekiller","Uzay Geometri", "Dönüşümlerle Geometri", "Trigonometri (Geometri Altında)", "Çemberin Analitiği", "Genel Konik Tanımı (Dış Merkezlik)","Parabol (Geometri Altında)", "Elips", "Hiperbol"]
        },
        "Biyoloji": {
            "TYT ve AYT Ortak Konular": ["Biyoloji Bilimi, İnorganik Bileşikler", "Organik Bileşikler", "Hücre", "Madde Geçişleri", "DNA-RNA","Protein Sentezi", "Enzimler", "Canlıların Sınıflandırılması", "Ekoloji", "Hücre Bölünmeleri","Eşeysiz-Eşeyli Üreme", "İnsanda Üreme ve Gelişme", "Mendel Genetiği", "Kan Grupları", "Cinsiyete Bağlı Kalıtım","Biyoteknoloji", "Evrim", "Solunum", "Fotosentez", "Kemosentez", "Bitki Biyolojisi", "Sistemler (Biyoloji)", "Duyu Organları"]
        },
        "Türkçe": {
            "TYT Konuları": ["Sözcük Anlamı (Türkçe TYT)", "Söz Yorumu", "Deyim ve Atasözü", "Cümle Anlamı (Türkçe TYT)", "Cümle Yorumu","Paragrafta Anlatım Teknikleri", "Paragrafta Konu-Ana Düşünce", "Paragrafta Yapı (Türkçe TYT)", "Paragrafta Yardımcı Düşünce","Ses Bilgisi (Türkçe TYT)", "Yazım Kuralları (Türkçe TYT)", "Noktalama İşaretleri (Türkçe TYT)", "Sözcüğün Yapısı","Sözcük Türleri", "Fiiller (Türkçe TYT)", "Sözcük Grupları", "Cümlenin Ögeleri (Türkçe TYT)", "Cümle Türleri (Türkçe TYT)", "Anlatım Bozukluğu (Türkçe TYT)"]
        },
        "Türk Dili ve Edebiyatı": {
            "AYT Konuları": ["Sözcükte Anlam (Edebiyat AYT)", "Cümlede Anlam (Edebiyat AYT)", "Paragrafta Anlatım, Anlatım Biçimleri, Düşünceyi Geliştirme Yolları","Paragrafta Yapı (Edebiyat AYT)", "Paragrafta Anlam (Edebiyat AYT)", "Ses Bilgisi (Edebiyat AYT)", "Yazım Kuralları (Edebiyat AYT)","Noktalama İşaretleri (Edebiyat AYT)", "Sözcükte Yapı (Edebiyat AYT)", "Ad Soylu Sözcükler", "Fiil (Edebiyat AYT)","Cümlenin Ögeleri (Edebiyat AYT)", "Cümle Türleri (Edebiyat AYT)", "Anlatım Bozuklukları (Edebiyat AYT)", "Güzel Sanatlar ve Edebiyat","Metinlerin Sınıflandırılması", "Coşku ve Heyecanı Dile Getiren Metinler", "Şiir Bilgisi", "Öğretici Metinler","Sözlü Anlatım Türleri", "Edebi Sanatlar(Söz Sanatları)", "Nazım Biçimleri ve Türleri", "İslamiyet Kabulü Öncesi Türk Edebiyatı","İslami Dönem İlk Dil ve Edebiyat Ürünleri", "Oğuz Türkçesinin İlk Ürünleri", "Halk Edebiyatı", "Divan Edebiyatı","Tanzimat Edebiyatı", "Servet-i Fünun Edebiyatı", "Fecri-Âti Edebiyatı", "Milli Edebiyat","Cumhuriyet Döneminde Türk Edebiyatı", "Türkiye Dışındaki Türk Edebiyatı", "Edebi Akımlar", "Dünya Edebiyatı","Türk Edebiyatı Eser Özetleri", "Türk ve Dünya Edebiyatındaki İlkler"]
        },
        "Coğrafya": {
            "TYT Konuları": ["Harita Bilgisi (TYT)", "Dünyanın Şekli ve Hareketleri (TYT)", "İklim Bilgisi (TYT)", "Türkiye'nin İklimi ve Yer Şekilleri (TYT)","Yer'in Şekillenmesi (TYT)", "İç ve Dış Kuvvetler", "Toprak Tipleri", "Nüfus (TYT)", "Ortak Payda: Bölge","Ulaşım Yolları", "Çevre ve İnsan (TYT)", "Doğal Afetler (TYT)"],
            "AYT Konuları": ["AYT-Doğal Sistemler: Doğa ve İnsan", "AYT-Doğal Sistemler: Dünya'nın Şekli ve Hareketleri", "AYT-Doğal Sistemler: Coğrafi Konum","AYT-Doğal Sistemler: Harita Bilgisi", "AYT-Doğal Sistemler: İklim Bilgisi", "AYT-Doğal Sistemler: Yerin Şekillenmesi", "AYT-Doğal Sistemler: Doğanın Varlıkları","AYT-Beşeri Sistemler: Beşeri Yapı", "AYT-Beşeri Sistemler: Nüfusun Gelişimi, Dağılışı ve Niteliği", "AYT-Beşeri Sistemler: Göçlerin Nedenleri ve Sonuçları", "AYT-Beşeri Sistemler: Geçim Tarzları","AYT-Mekansal Sentez Türkiye: Türkiye'nin Yeryüzü Şekilleri ve Özellikleri", "AYT-Mekansal Sentez Türkiye: Türkiye İklimi ve Özellikleri","AYT-Mekansal Sentez Türkiye: Türkiye'nin Doğal Varlıkları", "AYT-Mekansal Sentez Türkiye: Türkiye'de Yerleşme, Nüfus ve Göç","AYT-Küresel Ortam: Bölge Türleri ve Sınırları", "AYT-Küresel Ortam: Konum ve Etkileşim", "AYT-Küresel Ortam: Coğrafi Keşifler","AYT-Çevre ve Toplum: Doğa ile İnsan Arasındaki Etkileşim", "AYT-Çevre ve Toplum: Doğal Afetler", "AYT-Ekonomik Faaliyetler"]
        },
        "Tarih": {
            "TYT Konuları": ["Tarih Bilimine Giriş (TYT)", "Uygarlığın Doğuşu ve İlk Uygarlıklar (TYT)", "Eski Türk Tarihi", "İslam Tarihi (TYT)","Türk-İslam Devletleri (10-13. yüzyıllar)", "Türkiye Tarihi (11-13. yüzyıllar)", "Beylikten Devlete(1300-1453) (TYT)","Dünya Gücü Osmanlı Devleti (1453-1600) (TYT)", "Yeniçağ Avrupası (1453-1789)", "Osmanlı Kültür ve Medeniyeti","Arayış Yılları(17. yüzyıl) (TYT)", "18. Yüzyılda Değişim ve Diplomasi", "Yakınçağ Avrupası (1789....)","En Uzun Yüzyıl (1800-1922) (TYT)", "20. Yüzyıl Başlarında Osmanlı Devleti", "1. Dünya Savaşı (TYT Tarih)","Milli Mücadeleye Hazırlık Dönemi (TYT)", "Kurtuluş Savaşında Cepheler (TYT)", "Türk İnkılabı (TYT)","Atatürkçülük ve Atatürk İlkeleri (TYT)", "Türk Dış Politikası (TYT)"],
            "AYT Konuları": ["Tarih Bilimi (AYT)", "Uygarlığın Doğuşu ve İlk Uygarlıklar (AYT)", "İlk Türk Devletleri", "İslam Tarihi ve Uygarlığı (AYT)","Türk-İslam Devletleri (AYT)", "Türkiye Tarihi (AYT)", "Beylikten Devlete (1300-1453) (AYT)", "Dünya Gücü: Osmanlı Devleti (1453-1600) (AYT)","Arayış Yılları (17. Yüzyıl) (AYT)", "Avrupa ve Osmanlı Devleti (18. Yüzyıl) (AYT)", "En Uzun Yüzyıl (1800-1922) (AYT)","1881'den 1919'a Mustafa Kemal", "1.Dünya Savaşı (AYT Tarih)", "Milli Mücadele'nin Hazırlık Dönemi (AYT)", "Kurtuluş Savaşı'nda Cepheler (AYT)","Türk İnkılabı (AYT)", "Atatürkçülük ve Atatürk İlkeleri (AYT)", "Atatürk Dönemi Türk Dış Politikası (AYT)", "Atatürk'ün Ölümü (AYT)","Yüzyılın Başlarında Dünya (AYT)", "İkinci Dünya Savaşı (AYT)", "Soğuk Savaş Dönemi (AYT)", "Yumuşama Dönemi ve Sonrası (AYT)", "Küreselleşen Dünya (AYT)","Türklerde Devlet Teşkilatı", "Türklerde Toplum Yapısı", "Türklerde Hukuk", "Türklerde Ekonomi", "Türklerde Eğitim", "Türklerde Sanat"]
        },
        "Felsefe": {
            "TYT Konuları": ["Felsefe'nin Konusu-Alanı", "Bilgi Felsefesi (TYT)", "Varlık Felsefesi (TYT)", "Ahlak Felsefesi (TYT)","Sanat Felsefesi (TYT)", "Din Felsefesi (TYT)", "Siyaset Felsefesi (TYT)", "Bilim Felsefesi (TYT)"],
            "AYT Konuları": ["Felsefenin Alanı (AYT)", "Bilgi Felsefesi (AYT)", "Bilim Felsefesi (AYT)", "Varlık Felsefesi (AYT)","Ahlak Felsefesi (AYT)", "Siyaset Felsefesi (AYT)", "Sanat Felsefesi (AYT)", "Din Felsefesi (AYT)","AYT Mantık: Mantığa Giriş", "AYT Mantık: Klasik Mantık", "AYT Mantık: Mantık ve Dil", "AYT Mantık: Sembolik Mantık","AYT Psikoloji: Psikolojinin Temel Süreçleri", "AYT Psikoloji: Öğrenme Bellek Düşünme", "AYT Psikoloji: Ruh Sağlığının Temelleri","AYT Sosyoloji: Birey ve Toplum", "AYT Sosyoloji: Toplumsal Yapı", "AYT Sosyoloji: Toplumsal Değişme ve Gelişme","AYT Sosyoloji: Toplum ve Kültür", "AYT Sosyoloji: Toplumsal Kurumlar"]
        },
        "Din Kültürü ve Ahlak Bilgisi": {
            "TYT Konuları": ["Kuran ve Yorumu", "Zekât", "Hz. Muhammed'in Hayatı (TYT)", "İslam Düşüncesinde Yorumlar (TYT)","İslam Dinine Göre Kötü Alışkanlıklar", "Hazreti Muhammed (TYT)", "İslam Düşüncesinde Tasavvuf","Vahiy ve Akıl Kur'an Yorumları", "Yaşayan Dinler ve Benzer Özellikler (TYT)", "İnanç", "İbadet (TYT)","Hz. Muhammed (S.A.V) (TYT)", "Vahiy ve Akıl", "Ahlak ve Değerler", "Din ve Laiklik", "Din, Kültür ve Medeniyet"],
            "AYT Konuları": ["Kur'an-ı Kerim'in Anlaşılması ve Kavranması", "İnsan ve Din", "İslam ve İbadetler", "İslam Düşüncesinde Yorumlar, Mezhepler (AYT)","Muhammed'in Hayatı, Örnekliği ve Onu Anlama (AYT)", "İslam ve Bilim, Estetik, Barış", "Yaşayan Dinler ve Benzer Özellikleri (AYT)"]
        }
    }


    for course_name_main, topic_types in all_courses_data.items():
        course_obj = Course.query.filter_by(name=course_name_main).first()
        if not course_obj:
            course_obj = Course(name=course_name_main)
            db.session.add(course_obj)
            # Must commit here to get course_obj.id for subtopics if it's a new course
            db.session.commit()
            # Re-fetch to ensure we have the ID if it was newly created
            course_obj = Course.query.filter_by(name=course_name_main).first()
            click.echo(f"Course added: {course_name_main}")
        else:
            click.echo(f"Course already exists: {course_name_main}")

        processed_subtopics_for_course = set() # To avoid duplicate subtopics under the same course
        for _topic_type, subtopic_list in topic_types.items(): # _topic_type (e.g., "TYT Konuları") is not used for Subtopic model directly
            for subtopic_name_raw in subtopic_list:
                subtopic_name = subtopic_name_raw.strip()
                # Ensure subtopic_name is not empty and course_obj has an id
                if not subtopic_name or not course_obj or course_obj.id is None:
                    click.secho(f"Skipping subtopic '{subtopic_name_raw}' due to missing name or course ID.", fg="yellow")
                    continue

                if (subtopic_name, course_obj.id) in processed_subtopics_for_course:
                    click.echo(f"  Subtopic '{subtopic_name}' already processed for course '{course_name_main}'. Skipping.")
                    continue

                subtopic_obj = Subtopic.query.filter_by(name=subtopic_name, course_id=course_obj.id).first()
                if not subtopic_obj:
                    subtopic_obj = Subtopic(name=subtopic_name, course_id=course_obj.id)
                    # Example PDF assignments (ensure these files exist in your SUBTOPIC_PDF_FOLDER)
                    if course_name_main == "Fizik" and subtopic_name == "Fiziğin Tanımı ve Özellikleri":
                        subtopic_obj.pdf_filename = "fizik_bilimine_giris.pdf"
                    elif course_name_main == "Kimya" and subtopic_name == "Kimya Bilimi":
                        subtopic_obj.pdf_filename = "kimya_bilimi_notlari.pdf"
                    db.session.add(subtopic_obj)
                    # Commit here to get subtopic_obj.id if needed for further relations, though not in this loop
                    # db.session.commit() # Or commit once per course outside this inner loop
                    click.echo(f"  Subtopic added: {subtopic_name} -> {course_name_main} (Course ID: {course_obj.id}, PDF: {subtopic_obj.pdf_filename or 'None'})")
                else:
                    click.echo(f"  Subtopic already exists: {subtopic_name} for course {course_name_main}")
                processed_subtopics_for_course.add((subtopic_name, course_obj.id))
        db.session.commit() # Commit subtopics for the current course

    try:
        db.session.commit() # Final commit for any pending changes
        click.secho("Database initial data successfully added/updated.", fg="green")
    except Exception as e:
        db.session.rollback()
        click.secho(f"Error during final commit of initial data: {e}", fg="red")
        current_app.logger.error(f"Initial data final commit error: {e}")


@click.command("init-db")
@with_appcontext
def init_db_command():
    """Initializes the database with tables and default data."""
    # For Flask-Migrate, table creation is handled by 'flask db upgrade'.
    # This command can be used to populate data after tables are created.
    # If you are not using Flask-Migrate, you might uncomment db.create_all()
    # with current_app.app_context():
    #     db.create_all() # Ensure tables are created if not using migrations
    # click.echo("Database tables checked/created (if not using migrations).")
    click.echo("Initializing database with default data...")
    add_initial_data()
    click.secho("Veritabanı başlatıldı ve varsayılan veriler eklendi.", fg="cyan")

@click.command("create-admin")
@click.argument("username")
@click.argument("email")
@click.argument("password")
@with_appcontext
def create_admin_command(username, email, password):
    """Creates a new admin user."""
    if User.query.filter((User.username == username) | (User.email == email)).first():
        click.secho(f"Hata: '{username}' veya '{email}' zaten mevcut.", fg="red", err=True); return
    if len(password) < 6: # Basic password policy
        click.secho("Hata: Şifre en az 6 karakter olmalıdır.", fg="red", err=True); return

    admin_user_cli = User(username=username, email=email, is_admin=True, email_verified=True, is_active=True)
    admin_user_cli.set_password(password)
    try:
        db.session.add(admin_user_cli)
        db.session.commit()
        click.secho(f"Admin kullanıcısı '{username}' başarıyla oluşturuldu.", fg="green")
    except Exception as e:
        db.session.rollback()
        click.secho(f"Admin oluşturulurken bir hata oluştu: {str(e)}", fg="red", err=True)
        current_app.logger.error(f"CLI create-admin error: {e}")

@click.command("list-routes")
@with_appcontext
def list_routes_command(): # Renamed to avoid conflict if 'list_routes' is imported elsewhere
    """Lists all available routes in the application."""
    import urllib
    output = []
    for rule in current_app.url_map.iter_rules():
        options = {arg: f"[{arg}]" for arg in rule.arguments}
        methods = ','.join(sorted(rule.methods)) # Sort methods for consistent output
        try:
            url = url_for(rule.endpoint, **options)
            line = urllib.parse.unquote(f"{rule.endpoint:50s} {methods:25s} {url}")
            output.append(line)
        except Exception as e:
            output.append(f"{rule.endpoint:50s} {methods:25s} Error generating URL: {e}")


    click.echo("\nKullanılabilir Rotalar:\n" + "="*75)
    for line in sorted(output): # Sort output for consistency
        click.echo(line)
    click.echo("="*75 + "\n")

def register_commands(app):
    """Registers all CLI commands with the Flask app."""
    app.cli.add_command(init_db_command)
    app.cli.add_command(create_admin_command)
    app.cli.add_command(list_routes_command)
