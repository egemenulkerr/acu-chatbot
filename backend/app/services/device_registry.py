# ============================================================================
# backend/app/services/device_registry.py - Cihaz Katalogu Yönetimi
# ============================================================================

import logging
import json
import os
from pathlib import Path
from typing import Optional
from difflib import get_close_matches

from .web_scraper.lab_scrapper import scrape_lab_devices


# ============================================================================
# LOGGING & CONFIGURATION
# ============================================================================

logger: logging.Logger = logging.getLogger(__name__)

# Dosya yolu — CWD'den bağımsız, modüle göre relative
DATA_FILE: Path = Path(__file__).parent.parent / "data" / "devices.json"

DEVICE_DB: dict[str, dict] = {}


# ============================================================================
# DATABASE INITIALIZATION & MANAGEMENT
# ============================================================================

def load_devices_from_disk() -> bool:
    global DEVICE_DB

    try:
        if not DATA_FILE.exists():
            logger.warning(f"Cihaz veritabanı dosyası bulunamadı: {DATA_FILE}")
            return False

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            DEVICE_DB = json.load(f)

        logger.info(f"✅ Cihaz verisi diskten yüklendi. Toplam {len(DEVICE_DB)} cihaz.")
        return True

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse hatası ({DATA_FILE}): {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Dosya okuma hatası: {e}")
        return False


def save_devices_to_disk(data: dict[str, dict]) -> bool:
    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Cihaz veritabanı disk'e kaydedildi ({len(data)} cihaz)")
        return True

    except Exception as e:
        logger.error(f"❌ Dosya yazma hatası: {e}")
        return False


def update_device_database() -> bool:
    global DEVICE_DB

    logger.info("🔄 Cihaz veritabanı güncelleniyor (Selenium)...")

    try:
        new_data: Optional[dict] = scrape_lab_devices()

        if not new_data:
            logger.warning("⚠️  Scraper boş veri döndürdü, eski veri korunuyor.")
            return False

        if not save_devices_to_disk(new_data):
            return False

        DEVICE_DB = new_data
        logger.info("✅ Cihaz veritabanı başarıyla güncellendi.")
        return True

    except Exception as e:
        logger.error(f"❌ Update işleminde hata: {e}")
        return False


def initialize_device_db() -> None:
    logger.info("🔧 Cihaz veritabanı başlatılıyor...")

    if load_devices_from_disk():
        logger.info(f"✅ Veritabanı hazır ({len(DEVICE_DB)} cihaz).")
    else:
        logger.warning("⚠️  Disk boş! İlk tarama başlatılıyor...")
        if update_device_database():
            logger.info(f"✅ İlk tarama başarılı ({len(DEVICE_DB)} cihaz).")
        else:
            logger.error("❌ İlk tarama başarısız oldu.")


# ============================================================================
# SEARCH FUNCTIONS
# ============================================================================

def search_device(user_message: str) -> Optional[dict]:
    if not DEVICE_DB:
        initialize_device_db()

    message_lower = user_message.lower()
    for device_key, device_data in DEVICE_DB.items():
        if device_key in message_lower:
            return {
                "name": device_data.get("original_name", device_key.title()),
                "info": device_data
            }
    return None


def suggest_device(user_message: str) -> Optional[str]:
    if not DEVICE_DB:
        initialize_device_db()

    message_lower = user_message.lower()
    all_devices = list(DEVICE_DB.keys())

    for word in message_lower.split():
        if len(word) < 4:
            continue
        matches = get_close_matches(word, all_devices, n=1, cutoff=0.6)
        if matches:
            return matches[0]

    return None


def get_device_info(device_name_key: str) -> Optional[dict]:
    if not DEVICE_DB:
        initialize_device_db()

    if device_name_key in DEVICE_DB:
        device_data = DEVICE_DB[device_name_key]
        return {
            "name": device_data.get("original_name", device_name_key.title()),
            "info": device_data
        }

    logger.debug(f"⚠️  Cihaz bulunamadı: '{device_name_key}'")
    return None
