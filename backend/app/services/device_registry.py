# ============================================================================
# backend/app/services/device_registry.py - Cihaz Katalogu Yönetimi
# ============================================================================

import json
import logging
import tempfile
import threading
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
_DB_LOCK = threading.Lock()

_DEVICE_EMBEDDINGS: dict[str, "any"] = {}
_SEMANTIC_THRESHOLD: float = 0.60


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
            data = json.load(f)

        with _DB_LOCK:
            DEVICE_DB = data

        logger.info(f"✅ Cihaz verisi diskten yüklendi. Toplam {len(DEVICE_DB)} cihaz.")
        return True

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse hatası ({DATA_FILE}): {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Dosya okuma hatası: {e}")
        return False


def save_devices_to_disk(data: dict[str, dict]) -> bool:
    """Atomic write: önce temp dosyaya yaz, sonra rename ile değiştir."""
    try:
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

        fd, tmp_path = tempfile.mkstemp(
            dir=DATA_FILE.parent, suffix=".tmp", prefix="devices_"
        )
        try:
            with open(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            Path(tmp_path).replace(DATA_FILE)
        except Exception:
            Path(tmp_path).unlink(missing_ok=True)
            raise

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

        with _DB_LOCK:
            DEVICE_DB = new_data
        logger.info("✅ Cihaz veritabanı başarıyla güncellendi.")
        return True

    except Exception as e:
        logger.error(f"❌ Update işleminde hata: {e}")
        return False


def _build_device_embeddings() -> None:
    """
    Mevcut DEVICE_DB için cihaz adı embedding'lerini oluşturur.
    Sadece USE_EMBEDDINGS=true ise çalışır; MODEL yüklü olmalıdır.
    """
    global _DEVICE_EMBEDDINGS

    from ..config import settings
    if not settings.use_embeddings or not DEVICE_DB:
        return

    try:
        from ..core.classifier import MODEL
        if MODEL is None:
            logger.debug("Semantic model henüz yüklenmedi, cihaz embedding'i atlandı.")
            return

        import numpy as np
        device_names = list(DEVICE_DB.keys())
        logger.info(f"📊 {len(device_names)} cihaz için semantic embedding oluşturuluyor...")
        embeddings = list(MODEL.embed(device_names))
        _DEVICE_EMBEDDINGS = {
            name: np.array(emb)
            for name, emb in zip(device_names, embeddings)
        }
        logger.info(f"✅ Cihaz semantic embedding hazır ({len(_DEVICE_EMBEDDINGS)} cihaz).")
    except Exception as e:
        logger.warning(f"Cihaz embedding oluşturulamadı: {e}")


def initialize_device_db() -> None:
    logger.info("🔧 Cihaz veritabanı başlatılıyor...")

    if load_devices_from_disk():
        logger.info(f"✅ Veritabanı hazır ({len(DEVICE_DB)} cihaz).")
        _build_device_embeddings()
    else:
        logger.warning("⚠️  Disk boş! İlk tarama başlatılıyor...")
        if update_device_database():
            logger.info(f"✅ İlk tarama başarılı ({len(DEVICE_DB)} cihaz).")
            _build_device_embeddings()
        else:
            logger.error("❌ İlk tarama başarısız oldu.")


# ============================================================================
# SEARCH FUNCTIONS
# ============================================================================

def search_device(user_message: str) -> Optional[dict]:
    if not DEVICE_DB:
        initialize_device_db()

    # 1. Substring eşleşme (hızlı yol)
    message_lower = user_message.lower()
    for device_key, device_data in DEVICE_DB.items():
        if device_key in message_lower:
            return {
                "name": device_data.get("original_name", device_key.title()),
                "info": device_data
            }

    # 2. Semantic search (yavaş ama hassas)
    return search_device_semantic(user_message)


def search_device_semantic(query: str) -> Optional[dict]:
    """
    MiniLM embedding'leri ile cosine similarity tabanlı cihaz arama.
    Substring eşleşmesi başarısız olduğunda devreye girer.
    """
    if not _DEVICE_EMBEDDINGS:
        return None

    try:
        import numpy as np
        from ..core.classifier import MODEL
        if MODEL is None:
            return None

        query_emb = np.array(list(MODEL.embed([query])))[0]
        query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-10)

        best_sim = -1.0
        best_key: Optional[str] = None

        for device_key, device_emb in _DEVICE_EMBEDDINGS.items():
            norm = np.linalg.norm(device_emb) + 1e-10
            sim = float(np.dot(device_emb / norm, query_norm))
            if sim > best_sim:
                best_sim = sim
                best_key = device_key

        if best_key and best_sim >= _SEMANTIC_THRESHOLD:
            logger.info(f"✅ Semantic cihaz eşleşmesi: '{best_key}' (sim={best_sim:.3f})")
            device_data = DEVICE_DB[best_key]
            return {
                "name": device_data.get("original_name", best_key.title()),
                "info": device_data
            }

        return None

    except Exception as e:
        logger.warning(f"Semantic cihaz arama hatası: {e}")
        return None


_DEVICE_SEARCH_STOPWORDS: set[str] = {
    "cihaz", "cihazı", "cihazlar", "cihazları", "hakkında", "hakkinda",
    "bilgi", "bilgisi", "bilgisini", "ver", "verir", "verin",
    "istiyorum", "istiyormusunuz", "söyle", "söyleyin", "anlat", "anlatin",
    "nedir", "nelerdir", "nasıl", "nasil", "nerede", "nereden",
    "laboratuvar", "laboratuvarda", "laboratuvarlar", "laboratuvarlari",
    "üniversite", "universite", "okul", "fakülte", "fakulte",
    "mevcut", "olan", "hangi", "hangileri",
}


def suggest_device(user_message: str) -> Optional[str]:
    if not DEVICE_DB:
        initialize_device_db()

    message_lower = user_message.lower()
    all_devices = list(DEVICE_DB.keys())

    for word in message_lower.split():
        if len(word) < 5:
            continue
        if word in _DEVICE_SEARCH_STOPWORDS:
            continue
        matches = get_close_matches(word, all_devices, n=1, cutoff=0.75)
        if matches:
            return matches[0]

    return None


def get_all_devices() -> dict[str, dict]:
    """Tüm cihaz veritabanını döndür. Boşsa disk/scrape'den yükle."""
    if not DEVICE_DB:
        initialize_device_db()
    return DEVICE_DB


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


def _parse_description_fields(description: str) -> dict[str, str]:
    """
    Serbest metin description içinden temel alanları çekmeye çalış.

    Beklenen tipik format:
        \"Birim: X, Lab: Y, Marka: Z, Sorumlu: Q\"
    """
    if not description:
        return {}
    parts = [p.strip() for p in description.split(",")]
    result: dict[str, str] = {}
    for part in parts:
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key.startswith("birim"):
            result["unit"] = value
        elif key.startswith("lab"):
            result["lab"] = value
        elif key.startswith("marka"):
            result["brand"] = value
        elif key.startswith("sorumlu"):
            result["responsible"] = value
    return result


def search_devices_by_field(field: str, query: str) -> dict[str, dict]:
    """
    unit/lab/responsible gibi alanlara göre cihaz ara.
    Basit case-insensitive substring eşleşmesi kullanır.
    """
    if not DEVICE_DB:
        initialize_device_db()

    q = query.lower()
    results: dict[str, dict] = {}
    for key, data in DEVICE_DB.items():
        desc = str(data.get("description", ""))
        parsed = _parse_description_fields(desc)
        value = parsed.get(field, "").lower()
        if value and q in value:
            results[key] = data
    return results
