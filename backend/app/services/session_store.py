# ============================================================================
# backend/app/services/session_store.py - SQLite Konuşma Geçmişi
# ============================================================================
#
# Her session için son N mesajı SQLite'da saklar. Client-side history'ye
# fallback olarak da çalışır: session store boşsa client'tan gelen history
# kullanılır, ikisi çakışırsa store önceliklidir.
#
# Tablo: messages(session_id TEXT, role TEXT, text TEXT, ts TEXT)
# ============================================================================

import logging
import sqlite3
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent / "data" / "sessions.db"
_MAX_HISTORY = 20
_RETENTION_DAYS = 7

_conn: Optional[sqlite3.Connection] = None
_lock = threading.Lock()


# ============================================================================
# DB INIT
# ============================================================================

def _get_conn() -> sqlite3.Connection:
    """Tek paylaşımlı bağlantı döndürür (WAL + busy_timeout ile)."""
    global _conn
    if _conn is not None:
        return _conn
    with _lock:
        if _conn is not None:
            return _conn
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        _conn = conn
    return _conn


def init_db() -> None:
    """Tabloyu oluştur (yoksa). Uygulama başlangıcında çağrılır."""
    try:
        conn = _get_conn()
        with _lock:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT    NOT NULL,
                    role      TEXT    NOT NULL CHECK(role IN ('user', 'bot')),
                    text      TEXT    NOT NULL,
                    ts        TEXT    NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id, id)")
            conn.commit()
        logger.info("Session store DB hazır (WAL mode).")
    except Exception as e:
        logger.error(f"Session store init hatası: {e}")


# ============================================================================
# PUBLIC API
# ============================================================================

def save_message(session_id: str, role: str, text: str) -> None:
    """Tek bir mesajı kaydeder. Ardından eski kayıtları _MAX_HISTORY'ye kırpar."""
    if not session_id:
        return
    ts = datetime.now(timezone.utc).isoformat()
    try:
        conn = _get_conn()
        with _lock:
            conn.execute(
                "INSERT INTO messages (session_id, role, text, ts) VALUES (?, ?, ?, ?)",
                (session_id, role, text[:2000], ts),
            )
            conn.execute(
                """
                DELETE FROM messages
                WHERE session_id = ? AND id NOT IN (
                    SELECT id FROM messages WHERE session_id = ?
                    ORDER BY id DESC LIMIT ?
                )
                """,
                (session_id, session_id, _MAX_HISTORY),
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Mesaj kaydedilemedi (session={session_id}): {e}")


def get_history(session_id: str, limit: int = 10) -> list[dict]:
    """
    Verilen session için son `limit` mesajı [{role, text}] listesi olarak döner.
    Kronolojik sırada (eskiden yeniye).
    """
    if not session_id:
        return []
    try:
        conn = _get_conn()
        with _lock:
            rows = conn.execute(
                """
                SELECT role, text FROM (
                    SELECT id, role, text FROM messages
                    WHERE session_id = ?
                    ORDER BY id DESC LIMIT ?
                ) ORDER BY id ASC
                """,
                (session_id, limit),
            ).fetchall()
        return [{"role": r["role"], "text": r["text"]} for r in rows]
    except Exception as e:
        logger.warning(f"Geçmiş alınamadı (session={session_id}): {e}")
        return []


def prune_old_sessions(days: int = _RETENTION_DAYS) -> int:
    """
    `days` günden eski mesajları siler.
    Silinien satır sayısını döner.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        conn = _get_conn()
        with _lock:
            cursor = conn.execute(
                "DELETE FROM messages WHERE ts < ?",
                (cutoff,),
            )
            deleted = cursor.rowcount
            conn.commit()
        logger.info(f"Session store temizlendi: {deleted} eski kayıt silindi.")
        return deleted
    except Exception as e:
        logger.warning(f"Session temizleme hatası: {e}")
        return 0


def get_or_fallback(session_id: Optional[str], client_history: list[dict]) -> list[dict]:
    """
    session_id varsa store'dan geçmişi döner.
    Store boşsa client_history'yi fallback olarak kullanır.
    """
    if not session_id:
        return client_history

    stored = get_history(session_id)
    return stored if stored else client_history
