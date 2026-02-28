# ============================================================================
# backend/app/services/device_registry.py - Cihaz Katalogu Yönetimi
# ============================================================================
# Açıklama:
#   Üniversite laboratuvarlarında bulunan cihazları yönetir. Selenium web
#   scraper ile site'den verileri çeker, JSON'a kaydeder ve RAM'de cache'ler.
#   Arama ve fuzzy matching özelliği sağlar.
#
#   Data Flow: Web Site → Selenium → JSON File → RAM Cache → Search
# ============================================================================

import logging
import json
import os
from typing import Optional
from difflib import get_close_matches

from .web_scraper.lab_scrapper import scrape_lab_devices


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logger: logging.Logger = logging.getLogger(__name__)


# ============================================================================
# CONFIGURATION
# ============================================================================

# Cihaz veritabanının disk'te saklandığı yer
DATA_FILE: str = "app/data/devices.json"

# RAM'de cache edilen cihaz veritabanı
DEVICE_DB: dict[str, dict] = {}


# ============================================================================
# DATABASE INITIALIZATION & MANAGEMENT
# ============================================================================

def load_devices_from_disk() -> bool:
    """
    Disk'teki JSON veritabanını RAM'e yükle.

    Behavior:
      - Dosya varsa: JSON'ı oku ve DEVICE_DB'ye yaz
      - Dosya yoksa: Hata log'la ve False döndür
      - Success: True döndür

    Returns:
        bool: Başarıyı gösteren boolean
    """
    global DEVICE_DB

    try:
        if not os.path.exists(DATA_FILE):
            logger.warning(f"Cihaz veritabanı dosyası bulunamadı: {DATA_FILE}")
            return False

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            DEVICE_DB = json.load(f)

        logger.info(
            f"✅ Cihaz verisi diskten yüklendi. Toplam {len(DEVICE_DB)} cihaz."
        )
        return True

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse hatası ({DATA_FILE}): {e}")
        return False

    except Exception as e:
        logger.error(f"❌ Dosya okuma hatası: {e}")
        return False


def save_devices_to_disk(data: dict[str, dict]) -> bool:
    """
    Cihaz veritabanını disk'e JSON olarak kaydet.

    Args:
        data (dict): Cihaz veritabanı

    Returns:
        bool: Başarıyı gösteren boolean
    """
    try:
        # Dizin oluştur (yoksa)
        os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)

        # JSON'a kaydet
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"✅ Cihaz veritabanı disk'e kaydedildi ({len(data)} cihaz)")
        return True

    except Exception as e:
        logger.error(f"❌ Dosya yazma hatası: {e}")
        return False


def update_device_database() -> bool:
    """
    Cihaz veritabanını Selenium ile güncelleyi, kaydediyi ve cache'le.

    Process:
      1. Selenium scraper ile site'yi tara
      2. Yeni veriyi disk'e kaydet
      3. RAM cache'i güncelle

    Returns:
        bool: Güncellemenin başarısını gösteren boolean
    """
    global DEVICE_DB

    logger.info("🔄 Cihaz veritabanı güncelleniyor (Selenium)...")

    try:
        # Step 1: Selenium ile site'yi tara
        new_data: Optional[dict] = scrape_lab_devices()

        if not new_data:
            logger.warning("⚠️  Scraper boş veri döndürdü, eski veri korunuyor.")
            return False

        # Step 2: Disk'e kaydet
        if not save_devices_to_disk(new_data):
            return False

        # Step 3: RAM cache'i güncelle
        DEVICE_DB = new_data

        logger.info("✅ Cihaz veritabanı başarıyla güncellendi.")
        return True

    except Exception as e:
        logger.error(f"❌ Update işleminde hata: {e}")
        return False


def initialize_device_db() -> None:
    """
    Uygulama başlatılırken cihaz veritabanını başlat.

    Process:
      1. Disk'ten yüklemeyi dene
      2. Başarısız olursa Selenium ile ilk taramayı yap

    Note: Blocking operation, startup'ta background task olarak çalışır
    """
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
    """
    Exact match ile cihaz ara.

    Kullanıcı mesajında cihaz adını doğrudan arar. Bulursa cihaz bilgisini
    döndür.

    Args:
        user_message (str): Kullanıcı tarafından yazılan mesaj

    Returns:
        dict | None: Cihaz bilgisi veya None

    Example:
        search_device("bilgisayar var mı?") → Device with "bilgisayar" key
    """
    if not DEVICE_DB:
        initialize_device_db()

    message_lower: str = user_message.lower()

    # Exact substring match
    for device_key, device_data in DEVICE_DB.items():
        if device_key in message_lower:
            return {
                "name": device_data.get("original_name", device_key.title()),
                "info": device_data
            }

    return None


def suggest_device(user_message: str) -> Optional[str]:
    """
    Fuzzy match ile cihaz öner.

    Kelimelerin benzer cihaz adlarını bulur (difflib.get_close_matches).
    Yaklaşık eşleşme durumunda cihaz önerir.

    Algorithm:
      1. Mesajı kelimelere böl
      2. 4+ karakterli kelimeler için fuzzy match yap
      3. En olası önerideyi döndür

    Args:
        user_message (str): Kullanıcı tarafından yazılan mesaj

    Returns:
        str | None: Önerilen cihaz adı veya None

    Example:
        suggest_device("bilkisayar") → "bilgisayar" (typo düzeltme)
    """
    if not DEVICE_DB:
        initialize_device_db()

    message_lower: str = user_message.lower()
    all_devices: list[str] = list(DEVICE_DB.keys())
    words: list[str] = message_lower.split()

    # Her kelime için fuzzy match dene
    for word in words:
        # Çok kısa kelimeler skip et
        if len(word) < 4:
            continue

        # get_close_matches: n=1 (1 sonuç), cutoff=0.6 (60% benzerlik)
        matches: list[str] = get_close_matches(
            word,
            all_devices,
            n=1,
            cutoff=0.6
        )

        if matches:
            return matches[0]

    return None


def get_device_info(device_name_key: str) -> Optional[dict]:
    """
    Cihaz adı (key) ile cihaz bilgisi getir.

    Args:
        device_name_key (str): Cihaz'ın arama anahtarı

    Returns:
        dict | None: Cihaz bilgisi veya None

    Example:
        get_device_info("bilgisayar") → {
            "name": "Bilgisayar",
            "info": { "description": "...", "stock": "..." }
        }
    """
    if not DEVICE_DB:
        initialize_device_db()

    if device_name_key in DEVICE_DB:
        device_data: dict = DEVICE_DB[device_name_key]
        return {
            "name": device_data.get("original_name", device_name_key.title()),
            "info": device_data
        }

    logger.debug(f"⚠️  Cihaz bulunamadı: '{device_name_key}'")
    return None