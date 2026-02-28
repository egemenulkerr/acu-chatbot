# ============================================================================
# backend/app/services/web_scraper/manager.py - Web Scraper Yöneticisi
# ============================================================================
# Açıklama:
#   Akademik takvim, yemek listesi ve diğer web verilerini tarayıp
#   intents.json'da saklar. İki mod destekler:
#     - FAST (startup'ta): Sadece yemek
#     - FULL (scheduler'da): Takvim + yemek
#
#   Data Flow: Scraper → Format → intents.json → Intent Classification
# ============================================================================

import json
import os
import logging
from typing import Optional, dict

from .calendar_scraper import scrape_all_calendars
from .food_scrapper import scrape_daily_menu


# ============================================================================
# LOGGING & CONFIGURATION
# ============================================================================

logger: logging.Logger = logging.getLogger(__name__)

# Intent'lerin saklandığı JSON dosyası
DATA_FILE: str = "app/data/intents.json"


# ============================================================================
# FORMATTING HELPERS
# ============================================================================

def _format_menu_message(daily_menu: Optional[str]) -> str:
    """
    Yemek verilerini kullanıcı-dostu formata dönüştür.

    Cases:
      - Gerçek yemek: Formatlı menü + emoji
      - HAFTA SONU: Kapalı mesajı
      - None/Hata: Fallback statik mesaj

    Args:
        daily_menu (str | None): Yemekçi'den gelen yemek verisi

    Returns:
        str: Formatlı yemek mesajı
    """
    if daily_menu and daily_menu != "HAFTA SONU":
        return f"🍽️ **Günün Menüsü:**\n\n{daily_menu}\n\nAfiyet olsun! 😋"

    elif daily_menu == "HAFTA SONU":
        return (
            f"🍽️ **Hafta Sonu:**\n\n{daily_menu}\n\n"
            f"Lütfen Pazartesi günü tekrar deneyin. 😊"
        )

    else:
        return "🍽️ Şu an yemek bilgisi alınamıyor. Lütfen daha sonra deneyin."


# ============================================================================
# FAST UPDATE - STARTUP
# ============================================================================

def update_system_data_fast() -> None:
    """
    HIZLI STARTUP modu: Sadece yemek verilerini güncelle.

    Kullanım: Uygulama startup'ta arka planda çalışır.
    Zaman: ~2-3 saniye (takvim scraper'ı skip edilir)

    Note:
      Takvim scraper'ı 16 PDF işlediği için yavaş (~30 saniye).
      Bunun yerine scheduler'da yer alan full update'i kullanalım.
    """
    logger.info("⚡ HIZLI BAŞLATMA: Yemek verileri güncelleniyor...")

    daily_menu: Optional[str] = scrape_daily_menu()
    _update_menu_in_json(daily_menu)

    logger.info("✅ Hızlı yemek güncellemesi tamamlandı.")


# ============================================================================
# FULL UPDATE - SCHEDULER
# ============================================================================

def update_system_data() -> dict[str, str]:
    """
    FULL UPDATE modu: Takvim + yemek verilerini güncelle.

    Kullanım: APScheduler'da her 6 saatte bir çalışır (üretimde)
    İşlemler:
      1. Akademik takvim verilerini çek (PDF parsing)
      2. Yemek listesini çek
      3. Verileri formatlayıp intents.json'a kaydet

    Returns:
        dict: Güncelleme sonucu (status, message)

    Error Handling:
      - Dosya yoksa: Error response
      - Scraper başarısızsa: Warning log, eski veri korunur
      - JSON yazma hatası: Error response
    """
    logger.info("🔄 FULL UPDATE: Tüm web verileri güncelleniyor...")

    # -------- STEP 1: VERİ ÇEK --------
    calendars: Optional[dict] = scrape_all_calendars()
    daily_menu: Optional[str] = scrape_daily_menu()

    # -------- STEP 2: JSON'I YÜKLEYİP GÜNCELLE --------
    try:
        if not os.path.exists(DATA_FILE):
            logger.error(f"❌ Veritabanı dosyası bulunamadı: {DATA_FILE}")
            return {"status": "error", "message": "Veritabanı yok"}

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data: dict = json.load(f)

        updated: bool = False

        # JSON içindeki intent'leri gez
        for intent in data.get("intents", []):
            intent_name: str = intent.get("intent_name", "")

            # A. Akademik takvim güncelleme
            if intent_name == "akademik_takvim" and calendars:
                if "current" in calendars:
                    intent["response_content"] = calendars["current"]
                intent["extra_data"] = calendars
                updated = True
                logger.info("✅ Akademik takvim güncellendi.")

            # B. Yemek listesi güncelleme
            elif intent_name == "yemek_listesi":
                formatted_menu: str = _format_menu_message(daily_menu)
                old_content: str = intent.get("response_content", "")

                if old_content != formatted_menu:
                    intent["response_content"] = formatted_menu
                    intent["response_type"] = "TEXT"
                    updated = True
                    logger.info("✅ Yemek listesi güncellendi.")

        # STEP 3: Değişiklikler varsa diske kaydet
        if updated:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info("✅ JSON dosyası başarıyla kaydedildi.")
            return {"status": "success", "message": "Tüm veriler güncellendi."}

        return {"status": "skipped", "message": "Değişiklik yok"}

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse hatası: {e}")
        return {"status": "error", "message": f"JSON hatası: {e}"}

    except Exception as e:
        logger.error(f"❌ Güncelleme hatası: {e}")
        return {"status": "error", "message": str(e)}


# ============================================================================
# HELPER FUNCTION - FAST MENU UPDATE
# ============================================================================

def _update_menu_in_json(daily_menu: Optional[str]) -> None:
    """
    Sadece yemek listesini JSON'da güncelle (takvim hariç).

    Kullanım: Fast startup update'te çalışır
    İşlem: Yemek verilerini formatlayıp intent'te güncelle

    Args:
        daily_menu (str | None): Yemekçi'den gelen yemek verisi

    Error Handling:
      - Dosya yoksa: Error log ve return
      - JSON hatası: Error log ve return
    """
    try:
        if not os.path.exists(DATA_FILE):
            logger.error(f"❌ Veritabanı dosyası bulunamadı: {DATA_FILE}")
            return

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data: dict = json.load(f)

        # Intent'leri gez ve yemek_listesi'ni bul
        for intent in data.get("intents", []):
            if intent.get("intent_name") == "yemek_listesi":
                formatted_menu: str = _format_menu_message(daily_menu)
                old_content: str = intent.get("response_content", "")

                # Değişiklik varsa güncelle
                if old_content != formatted_menu:
                    intent["response_content"] = formatted_menu
                    intent["response_type"] = "TEXT"

        # Dosyaya kaydet
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info("✅ Yemek listesi başarıyla güncellendi.")

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse hatası: {e}")

    except Exception as e:
        logger.error(f"❌ Yemek güncelleme hatası: {e}")