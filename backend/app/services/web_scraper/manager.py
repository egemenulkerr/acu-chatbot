import json
import os
import logging
# Hem takvim hem de yemek scraper'ını çağırıyoruz
from .calendar_scraper import scrape_all_calendars
from .food_scrapper import scrape_daily_menu # <-- YENİ EKLENEN

logger = logging.getLogger(__name__)
DATA_FILE = "app/data/intents.json"

def update_system_data():
    logger.info("🔄 Tüm Web Verileri Güncelleniyor...")
    
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
            if intent["intent_name"] == "yemek_listesi" and daily_menu:
                # Menüyü şablonlu bir mesaja dönüştür
                if daily_menu != "HAFTA SONU":
                    formatted_menu = f"{daily_menu}"
                else:
                    formatted_menu = f"🍽️ **Günün Menüsü:**\n\n{daily_menu}\n\nAfiyet olsun! 😋"

                # İçerik değiştiyse güncelle
                if intent.get("response_content") != formatted_menu:
                    intent["response_content"] = formatted_menu
                    # Response type'ı TEXT yapalım ki link sanmasın
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