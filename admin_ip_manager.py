import sys
import hashlib
import os
from functools import partial
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QMessageBox, QGroupBox, QFrame
)
from PyQt6.QtCore import Qt

# --- Configuration ve Helper Functions (Değişiklik yok) ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_FOLDER_PATH = os.path.join(BASE_DIR, 'instance')
ADMIN_IPS_FILE = os.path.join(INSTANCE_FOLDER_PATH, "admin_ips.txt")

def hash_ip(ip_address: str) -> str: return hashlib.sha256(ip_address.encode('utf-8')).hexdigest()
def ensure_instance_folder():
    if not os.path.exists(INSTANCE_FOLDER_PATH):
        try: os.makedirs(INSTANCE_FOLDER_PATH)
        except OSError as e: print(f"Error: Could not create instance folder at {INSTANCE_FOLDER_PATH}: {e}"); return False
    return True
def load_ips_from_file() -> tuple[dict, str | None]:
    if not ensure_instance_folder(): return {}, "Instance folder could not be created."
    ips = {}
    if not os.path.exists(ADMIN_IPS_FILE): return ips, None
    try:
        with open(ADMIN_IPS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and ':' in line:
                    try: name, hashed_ip_val = line.split(':', 1); ips[name.strip()] = hashed_ip_val.strip()
                    except ValueError: print(f"Warning: Malformed line in {ADMIN_IPS_FILE}: '{line}'")
    except Exception as e: return {}, f"Failed to read the IP list file: {e}"
    return ips, None
def save_ips_to_file(ips_data: dict) -> str | None:
    if not ensure_instance_folder(): return "Instance folder could not be created."
    try:
        with open(ADMIN_IPS_FILE, 'w', encoding='utf-8') as f:
            for name, hashed_ip_val in sorted(ips_data.items()): f.write(f"{name}:{hashed_ip_val}\n")
        return None
    except Exception as e: return f"Failed to write to the IP list file: {e}"

# --- Main GUI Application ---
class AdminIPManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        # __init__ içindeki her şey aynı kalıyor, DOKUNMAYIN
        self.setWindowTitle("Admin IP Manager (PyQt6)")
        self.setGeometry(100, 100, 700, 600)
        self.ips_data = {}
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        input_groupbox = QGroupBox("Yeni IP Ekle")
        form_layout = QFormLayout()
        self.name_entry = QLineEdit()
        self.name_entry.setPlaceholderText("e.g., Office_Static_IP")
        form_layout.addRow("Tanımlayıcı:", self.name_entry)
        self.ip_entry = QLineEdit()
        self.ip_entry.setPlaceholderText("e.g., 203.0.113.45")
        form_layout.addRow("IP Adresi:", self.ip_entry)
        self.add_button = QPushButton("Yeni IP Ekle")
        self.add_button.setFixedHeight(35)
        form_layout.addRow(self.add_button)
        input_groupbox.setLayout(form_layout)
        main_layout.addWidget(input_groupbox)
        list_groupbox = QGroupBox("Kayıtlı IP Listesi (Tanımlayıcı: Hash)")
        list_vbox = QVBoxLayout()
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        scroll_content_widget = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_content_widget)
        self.scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(scroll_content_widget)
        list_vbox.addWidget(self.scroll_area)
        list_groupbox.setLayout(list_vbox)
        main_layout.addWidget(list_groupbox)
        self.add_button.clicked.connect(self.add_ip_gui)
        self.statusBar()
        
        self.refresh_list_gui()

    # show_dialog ve update_status fonksiyonları aynı, DOKUNMAYIN
    def show_dialog(self, title, message, dialog_type="info", buttons="ok"):
        msg_box = QMessageBox(self); msg_box.setWindowTitle(title); msg_box.setText(message)
        if dialog_type == "error": msg_box.setIcon(QMessageBox.Icon.Critical)
        elif dialog_type == "warning": msg_box.setIcon(QMessageBox.Icon.Warning)
        elif dialog_type == "askyesno": msg_box.setIcon(QMessageBox.Icon.Question)
        else: msg_box.setIcon(QMessageBox.Icon.Information)
        if buttons == "askyesno": msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        else: msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        result = msg_box.exec()
        if buttons == "askyesno": return result == QMessageBox.StandardButton.Yes
        return None
    def update_status(self, message, success=True):
        color = "green" if success else "red"; self.statusBar().setStyleSheet(f"color: {color};"); self.statusBar().showMessage(f"Durum: {message}", 7000)

    # add_ip_gui fonksiyonu aynı, DOKUNMAYIN
    def add_ip_gui(self):
        name = self.name_entry.text().strip()
        ip = self.ip_entry.text().strip()
        if not name or not ip: self.show_dialog("Giriş Hatası", "Tanımlayıcı ve IP adresi alanları boş olamaz.", "error"); return
        if name in self.ips_data: self.show_dialog("İsim Hatası", f"'{name}' tanımlayıcısı zaten kullanılıyor. Lütfen farklı bir tane seçin.", "error"); return
        hashed_ip = hash_ip(ip)
        for existing_name, existing_hash in self.ips_data.items():
            if existing_hash == hashed_ip:
                result = self.show_dialog("IP Zaten Mevcut Uyarısı", f"Bu IP ({ip}) zaten '{existing_name}' olarak kayıtlı.\n'{name}' adıyla tekrar eklemek istiyor musunuz?", "askyesno")
                if not result: self.update_status("Ekleme iptal edildi (IP tekrarı).", success=False); return
                break
        self.ips_data[name] = hashed_ip
        error = save_ips_to_file(self.ips_data)
        if error:
            self.show_dialog("Dosya Kaydetme Hatası", error, "error")
            self.update_status("Dosyaya kaydedilemedi!", success=False)
            self.ips_data, _ = load_ips_from_file()
        else:
            self.update_status(f"'{name}' ({ip}) eklendi.", success=True)
            self.name_entry.clear()
            self.ip_entry.clear()
            self._redraw_ip_list() 
    
    # --- DEĞİŞİKLİK: SİLME FONKSİYONU TAMAMEN YENİLENDİ ---
    def remove_ip_gui(self, name_to_remove: str):
        """
        Onay sormadan, belirtilen IP'yi verilerden siler ve ilgili satırı arayüzden kaldırır.
        """
        # 1. Veri katmanını güncelle (bellek ve disk)
        if name_to_remove in self.ips_data:
            self.ips_data.pop(name_to_remove)
            error = save_ips_to_file(self.ips_data)

            if error:
                # Eğer dosyaya kaydetme başarısız olursa, kritik bir hata göster ve her şeyi yeniden yükle.
                self.show_dialog("Kritik Hata!", "IP silindi ancak dosyaya kaydedilemedi! Liste tutarsız olabilir.", "error")
                self.refresh_list_gui()
                return

            # 2. Arayüz katmanını güncelle (hedefli silme)
            # Sinyali gönderen butonu bul
            sender_button = self.sender()
            if sender_button:
                # Butonun içinde bulunduğu satırı (parent widget'ı olan QFrame) bul
                row_to_delete = sender_button.parent()
                if row_to_delete:
                    # O satırı layout'tan kaldır ve daha sonra silinmesi için işaretle
                    self.scroll_layout.removeWidget(row_to_delete)
                    row_to_delete.deleteLater()
            
            self.update_status(f"'{name_to_remove}' silindi.", success=True)
            
    # _redraw_ip_list ve refresh_list_gui fonksiyonları aynı, DOKUNMAYIN
    def _redraw_ip_list(self):
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        if not self.ips_data:
            self.scroll_layout.addWidget(QLabel("Kayıtlı IP bulunamadı."))
            return
        for name, hashed_ip in sorted(self.ips_data.items()):
            item_frame = QFrame()
            item_layout = QHBoxLayout(item_frame)
            item_layout.setContentsMargins(0, 0, 0, 0)
            label_text = f"{name}:  {hashed_ip}"
            ip_label = QLabel(label_text)
            ip_label.setWordWrap(True)
            remove_button = QPushButton("Sil", parent=item_frame) # Parent'ı belirtmek sender() için önemlidir.
            remove_button.setFixedWidth(60)
            remove_button.setStyleSheet("background-color: #D32F2F; color: white;")
            remove_button.clicked.connect(partial(self.remove_ip_gui, name))
            item_layout.addWidget(ip_label)
            item_layout.addStretch()
            item_layout.addWidget(remove_button)
            self.scroll_layout.addWidget(item_frame)
            
    def refresh_list_gui(self):
        self.ips_data, error = load_ips_from_file()
        if error:
            self.show_dialog("Dosya Yükleme Hatası", error, "error")
        self._redraw_ip_list()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AdminIPManagerApp()
    window.show()
    sys.exit(app.exec())