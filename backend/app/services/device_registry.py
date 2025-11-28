# backend/app/services/device_registry.py

import logging
import json
import os
import difflib

# ÖNEMLİ: Scraper modülünü tam yol (Absolute Import) ile çağırıyoruz
from .web_scraper.lab_scrapper import scrape_lab_devices

logger = logging.getLogger(__name__)

# Veritabanı Dosyası (Kalıcı Hafıza)
DATA_FILE = "app/data/devices.json"

# RAM'deki hızlı erişim kopyası
DEVICE_DB = {}

def load_devices_from_disk():
    """
    Diskteki JSON dosyasını okuyup RAM'e yükler.
    """
    global DEVICE_DB
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                DEVICE_DB = json.load(f)
            logger.info(f"📂 Cihaz verisi diskten yüklendi. Toplam {len(DEVICE_DB)} cihaz.")
            return True
    except Exception as e:
        logger.error(f"Veri okuma hatası: {e}")
    return False

def update_device_database():
    """
    Selenium'u çalıştırır, veriyi çeker ve diske kaydeder.
    """
    global DEVICE_DB
    logger.info("🔄 Cihaz veritabanı güncelleniyor (Selenium başlatılıyor)...")
    
    # 1. Siteyi Tara
    new_data = scrape_lab_devices()
    
    if new_data:
        # 2. Diske Kaydet
        try:
            os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
            
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(new_data, f, ensure_ascii=False, indent=2)
            
            # 3. RAM'i Güncelle
            DEVICE_DB = new_data
            logger.info("✅ Cihaz veritabanı başarıyla güncellendi ve kaydedildi.")
            return True
        except Exception as e:
            logger.error(f"Dosya yazma hatası: {e}")
    else:
        logger.warning("⚠️ Scraper boş veri döndürdü, eski veri korunuyor.")
    
    return False

def initialize_device_db():
    """
    Uygulama başladığında çalışır.
    """
    # Diskten yüklemeyi dene, başaramazsan (dosya yoksa) tarama yap
    if not load_devices_from_disk():
        logger.warning("Disk boş! İlk tarama başlatılıyor...")
        update_device_database()

# --- ARAMA FONKSİYONLARI ---

def search_device(user_message: str):
    if not DEVICE_DB:
        initialize_device_db()
        
    message_lower = user_message.lower()
    for device_key, data in DEVICE_DB.items():
        if device_key in message_lower:
            return {"name": data.get("original_name", device_key.title()), "info": data}
    return None

def suggest_device(user_message: str):
    if not DEVICE_DB:
        initialize_device_db()
    
    message_lower = user_message.lower()
    all_devices = list(DEVICE_DB.keys())
    words = message_lower.split()
    
    for word in words:
        if len(word) < 4: continue
        
        matches = difflib.get_close_matches(word, all_devices, n=1, cutoff=0.6)
        if matches:
            return matches[0]
            
    return None

def get_device_info(device_name_key: str):
    if not DEVICE_DB:
        initialize_device_db()
    
    if device_name_key in DEVICE_DB:
        info = DEVICE_DB[device_name_key]
        return {"name": info.get("original_name", device_name_key.title()), "info": info}
    return None