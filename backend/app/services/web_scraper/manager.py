# ============================================================================
# backend/app/services/web_scraper/manager.py - Web Scraper Yöneticisi
# ============================================================================

import json
import os
import logging
import tempfile
import threading
from pathlib import Path
from typing import Optional

from .calendar_scraper import scrape_all_calendars
from .food_scrapper import scrape_daily_menu


# ============================================================================
# LOGGING & CONFIGURATION
# ============================================================================

logger: logging.Logger = logging.getLogger(__name__)

# Dosya yolu — CWD'den bağımsız, modüle göre relative
DATA_FILE: Path = Path(__file__).parent.parent.parent / "data" / "intents.json"

# JSON dosyasına eş zamanlı erişimi önleyen kilit
_json_lock = threading.RLock()


# ============================================================================
# ATOMIC FILE WRITE
# ============================================================================

def _write_json_atomic(data: dict) -> None:
    """
    JSON'ı atomic olarak yaz: önce temp dosyaya, sonra os.replace ile taşı.
    Race condition ve yarım yazma riskini ortadan kaldırır.
    """
    with _json_lock:
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=DATA_FILE.parent, suffix=".tmp"
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, str(DATA_FILE))
        except Exception:
            os.unlink(tmp_path)
            raise


# ============================================================================
# FORMATTING HELPERS
# ============================================================================

def _format_menu_message(daily_menu: Optional[str]) -> str:
    """
    Yemek verilerini kullanıcı-dostu formata dönüştür.

    Sentinel değerler: food_scrapper "KAPAL" döndürüyor, bunu ele alıyoruz.
    Scraping başarısız olursa uydurma menü GÖSTERILMEZ — dürüst hata mesajı döner.
    """
    if daily_menu is None:
        return "🍽️ Şu an yemek bilgisi alınamıyor. Lütfen üniversite web sitesini kontrol edin."

    if "KAPAL" in daily_menu or "hafta sonu" in daily_menu.lower():
        return "🍽️ **Hafta Sonu:** Yemekhane bugün kapalı. Pazartesi görüşmek üzere! 😊"

    return f"🍽️ **Günün Menüsü:**\n\n{daily_menu}\n\nAfiyet olsun! 😋"


# ============================================================================
# FAST UPDATE (startup)
# ============================================================================

def update_system_data_fast() -> None:
    """Sadece yemek verisini güncelle (startup modu — hızlı)."""
    logger.info("⚡ HIZLI BAŞLATMA: Yemek verileri güncelleniyor...")
    daily_menu: Optional[str] = scrape_daily_menu()
    _update_menu_in_json(daily_menu)
    logger.info("✅ Hızlı yemek güncellemesi tamamlandı.")


# ============================================================================
# FULL UPDATE (scheduler — her 6 saatte)
# ============================================================================

def update_system_data() -> dict:
    """Takvim + yemek verilerini güncelle (tam güncelleme modu)."""
    logger.info("🔄 FULL UPDATE: Tüm web verileri güncelleniyor...")

    calendars: Optional[dict] = scrape_all_calendars()
    daily_menu: Optional[str] = scrape_daily_menu()

    try:
        if not DATA_FILE.exists():
            logger.error(f"❌ Veritabanı dosyası bulunamadı: {DATA_FILE}")
            return {"status": "error", "message": "Veritabanı yok"}

        with _json_lock:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data: dict = json.load(f)

        updated: bool = False

        for intent in data.get("intents", []):
            intent_name: str = intent.get("intent_name", "")

            if intent_name == "akademik_takvim" and calendars:
                if "current" in calendars:
                    intent["response_content"] = calendars["current"]
                intent["extra_data"] = calendars
                updated = True
                logger.info("✅ Akademik takvim güncellendi.")

            elif intent_name == "yemek_listesi":
                formatted_menu: str = _format_menu_message(daily_menu)
                if intent.get("response_content") != formatted_menu:
                    intent["response_content"] = formatted_menu
                    intent["response_type"] = "TEXT"
                    updated = True
                    logger.info("✅ Yemek listesi güncellendi.")

        if updated:
            _write_json_atomic(data)
            logger.info("✅ JSON dosyası başarıyla kaydedildi.")
            return {"status": "success", "message": "Tüm veriler güncellendi."}

        return {"status": "skipped", "message": "Değişiklik yok"}

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse hatası: {e}")
        return {"status": "error", "message": "JSON hatası"}

    except Exception as e:
        logger.error(f"❌ Güncelleme hatası: {e}", exc_info=True)
        return {"status": "error", "message": "Güncelleme başarısız"}


# ============================================================================
# HELPER: SADECE YEMEK GÜNCELLEMESİ (fast startup için)
# ============================================================================

def _update_menu_in_json(daily_menu: Optional[str]) -> None:
    try:
        if not DATA_FILE.exists():
            logger.error(f"❌ Veritabanı dosyası bulunamadı: {DATA_FILE}")
            return

        with _json_lock:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data: dict = json.load(f)

        for intent in data.get("intents", []):
            if intent.get("intent_name") == "yemek_listesi":
                formatted_menu: str = _format_menu_message(daily_menu)
                if intent.get("response_content") != formatted_menu:
                    intent["response_content"] = formatted_menu
                    intent["response_type"] = "TEXT"

        _write_json_atomic(data)
        logger.info("✅ Yemek listesi başarıyla güncellendi.")

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse hatası: {e}")

    except Exception as e:
        logger.error(f"❌ Yemek güncelleme hatası: {e}", exc_info=True)
