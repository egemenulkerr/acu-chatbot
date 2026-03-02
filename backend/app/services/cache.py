# ============================================================================
# backend/app/services/cache.py - Adaptif Cache Katmanı
# ============================================================================
#
# REDIS_URL env var varsa Redis kullanır, yoksa process-içi dict cache devam eder.
# Bu sayede geliştirme ortamında Redis gerektirmez; production'da opsiyonel olarak
# etkinleştirilebilir.
#
# Kullanım:
#   from .cache import cache_get, cache_set
#   val = cache_get("yemek:2025-03-02")
#   cache_set("yemek:2025-03-02", "...", ttl=86400)
# ============================================================================

import json
import logging
import os
import time
from typing import Optional, Any

logger = logging.getLogger(__name__)

_REDIS_URL = os.getenv("REDIS_URL", "")
_redis_client = None
_dict_cache: dict[str, tuple[Any, float]] = {}  # key → (value, expires_at)


# ============================================================================
# REDIS INIT (lazy)
# ============================================================================

def _get_redis():
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    if not _REDIS_URL:
        return None

    try:
        import redis
        _redis_client = redis.from_url(_REDIS_URL, decode_responses=True, socket_timeout=2)
        _redis_client.ping()
        logger.info(f"Redis bağlantısı kuruldu: {_REDIS_URL}")
        return _redis_client
    except Exception as e:
        logger.warning(f"Redis bağlantısı kurulamadı, dict cache kullanılacak: {e}")
        _redis_client = None
        return None


# ============================================================================
# PUBLIC API
# ============================================================================

def cache_get(key: str) -> Optional[Any]:
    """Cache'den değer oku. Yoksa veya süresi geçmişse None döner."""
    r = _get_redis()

    if r is not None:
        try:
            raw = r.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception as e:
            logger.warning(f"Redis get hatası ({key}): {e}")
            return None

    # Dict cache fallback
    entry = _dict_cache.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if expires_at > 0 and time.time() > expires_at:
        del _dict_cache[key]
        return None
    return value


def cache_set(key: str, value: Any, ttl: int = 3600) -> None:
    """Cache'e değer yaz. ttl=0 ise kalıcı (dict cache'de 24 saat)."""
    r = _get_redis()

    if r is not None:
        try:
            serialized = json.dumps(value, ensure_ascii=False)
            if ttl > 0:
                r.setex(key, ttl, serialized)
            else:
                r.set(key, serialized)
            return
        except Exception as e:
            logger.warning(f"Redis set hatası ({key}): {e}")

    # Dict cache fallback
    expires_at = (time.time() + ttl) if ttl > 0 else (time.time() + 86400)
    _dict_cache[key] = (value, expires_at)


def cache_delete(key: str) -> None:
    """Cache'den değer sil."""
    r = _get_redis()

    if r is not None:
        try:
            r.delete(key)
            return
        except Exception as e:
            logger.warning(f"Redis delete hatası ({key}): {e}")

    _dict_cache.pop(key, None)


def is_redis_available() -> bool:
    """Redis bağlantısı aktif mi?"""
    return _get_redis() is not None
