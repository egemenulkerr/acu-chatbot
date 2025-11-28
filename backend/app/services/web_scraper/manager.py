import json
import os
import logging
# Hem takvim hem de yemek scraper'ını çağırıyoruz
from .calendar_scraper import scrape_all_calendars
from .food_scrapper import scrape_daily_menu # <-- YENİ EKLENEN

logger = logging.getLogger(__name__)
DATA_FILE = "app/data/intents.json"

def update_system_data_fast():
    """
    HIZLI STARTUP: Sadece yemek scraper'ını çalıştır.
    Takvim scraper'ı slow olduğu için (16 PDF), bunu scheduler'a bırak.
    """
    logger.info("🔄 HIZLI BAŞLANGAÇ: Yemek Verileri Güncelleniyor...")
    
    daily_menu = scrape_daily_menu()
    _update_menu_in_json(daily_menu)


def update_system_data():
    """
    FULL UPDATE: Hem takvim hem yemek scraper'ını çalıştır.
    Scheduler'da 6 saatte bir çalışır.
    """
    logger.info("🔄 FULL UPDATE: Tüm Web Verileri Güncelleniyor...")
    
    # 1. Verileri Çek
    calendars = scrape_all_calendars()
    daily_menu = scrape_daily_menu() # <-- YEMEK LİSTESİNİ ÇEK
    
    try:
        if not os.path.exists(DATA_FILE):
            return {"status": "error", "message": "Veritabanı yok"}

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        updated = False
        
        # JSON içindeki niyetleri gez
        for intent in data.get("intents", []):
            
            # A. AKADEMİK TAKVİM GÜNCELLEME
            if intent["intent_name"] == "akademik_takvim" and calendars:
                if "current" in calendars:
                    intent["response_content"] = calendars["current"]
                intent["extra_data"] = calendars
                updated = True

            # B. YEMEK LİSTESİ GÜNCELLEME (YENİ)
            if intent["intent_name"] == "yemek_listesi":
                if daily_menu and daily_menu != "HAFTA SONU":
                    # Gerçek yemek verisi var
                    formatted_menu = f"🍽️ **Günün Menüsü:**\n\n{daily_menu}\n\nAfiyet olsun! 😋"
                    logger.info("Yemek listesi siteden çekildi ve güncellendi.")
                elif daily_menu == "HAFTA SONU":
                    # Hafta sonu - yemekçi kapalı
                    formatted_menu = f"🍽️ **Hafta Sonu:**\n\n{daily_menu}\n\nLütfen Pazartesi günü tekrar deneyin. 😊"
                    logger.info("Hafta sonu - yemekçi kapalı.")
                else:
                    # Scraper başarısız - statik fallback
                    formatted_menu = intent.get("response_content", "Şu an yemek bilgisi alınamıyor. Lütfen daha sonra deneyin.")
                    logger.warning("Yemek scraper'ı başarısız, statik veri kullanılıyor.")

                # İçerik değiştiyse güncelle
                if intent.get("response_content") != formatted_menu:
                    intent["response_content"] = formatted_menu
                    # Response type'ı TEXT yapalım
                    intent["response_type"] = "TEXT" 
                    updated = True
                    logger.info("Yemek listesi veritabanına işlendi.")

        if updated:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return {"status": "success", "message": "Tüm veriler güncellendi."}
        
        return {"status": "skipped", "message": "Değişiklik yok"}

    except Exception as e:
        logger.error(f"Güncelleme hatası: {e}")
        return {"status": "error", "message": str(e)}


def _update_menu_in_json(daily_menu):
    """
    Helper: Sadece yemek listesini JSON'da güncelle.
    Takvim scraper'ını çalıştırmadan.
    """
    try:
        if not os.path.exists(DATA_FILE):
            logger.error("Veritabanı yok")
            return

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for intent in data.get("intents", []):
            if intent["intent_name"] == "yemek_listesi":
                if daily_menu and daily_menu != "HAFTA SONU":
                    formatted_menu = f"🍽️ **Günün Menüsü:**\n\n{daily_menu}\n\nAfiyet olsun! 😋"
                    logger.info("✅ Yemek listesi siteden çekildi ve güncellendi.")
                elif daily_menu == "HAFTA SONU":
                    formatted_menu = f"🍽️ **Hafta Sonu:**\n\n{daily_menu}\n\nLütfen Pazartesi günü tekrar deneyin. 😊"
                    logger.info("⏱️ Hafta sonu - yemekçi kapalı.")
                else:
                    formatted_menu = intent.get("response_content", "Şu an yemek bilgisi alınamıyor.")
                    logger.warning("⚠️ Yemek scraper'ı başarısız, statik veri kullanılıyor.")

                if intent.get("response_content") != formatted_menu:
                    intent["response_content"] = formatted_menu
                    intent["response_type"] = "TEXT"

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"Yemek güncelleme hatası: {e}")