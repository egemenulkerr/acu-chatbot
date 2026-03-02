# ============================================================================
# backend/app/api/endpoints/analytics.py - Analytics API Endpoint'leri
# ============================================================================

import json
import logging
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

router = APIRouter()
logger = logging.getLogger(__name__)

_ANALYTICS_FILE = Path(__file__).parent.parent.parent / "data" / "analytics.jsonl"
_ADMIN_TOKEN = os.getenv("ADMIN_SECRET_TOKEN", "")

security = HTTPBearer(auto_error=False)


# ============================================================================
# AUTH HELPER
# ============================================================================

def _require_admin(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> None:
    """Admin token doğrulama. Token yoksa veya yanlışsa 401 döner."""
    if not _ADMIN_TOKEN:
        raise HTTPException(status_code=503, detail="Admin token yapılandırılmamış.")
    if credentials is None or credentials.credentials != _ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Geçersiz veya eksik admin token.")


# ============================================================================
# HELPERS
# ============================================================================

def _load_entries(since: Optional[datetime] = None) -> list[dict]:
    """analytics.jsonl dosyasını okuyup isteğe göre filtreler."""
    if not _ANALYTICS_FILE.exists():
        return []

    entries: list[dict] = []
    try:
        with open(_ANALYTICS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if since:
                        ts_str = entry.get("ts", "")
                        try:
                            ts = datetime.fromisoformat(ts_str)
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            if ts < since:
                                continue
                        except ValueError:
                            pass
                    entries.append(entry)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error(f"Analytics dosyası okunamadı: {e}")

    return entries


def _build_summary(entries: list[dict]) -> dict:
    """Girdi listesinden özet istatistikler üretir."""
    total = len(entries)
    if total == 0:
        return {
            "total_messages": 0,
            "intent_distribution": {},
            "source_distribution": {},
            "avg_response_ms": None,
        }

    intent_counts: Counter = Counter(e.get("intent", "unknown") for e in entries)
    source_counts: Counter = Counter(e.get("source", "unknown") for e in entries)

    ms_values = [e["ms"] for e in entries if isinstance(e.get("ms"), (int, float))]
    avg_ms = round(sum(ms_values) / len(ms_values)) if ms_values else None

    intent_dist = {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in intent_counts.most_common()}
    source_dist = {k: {"count": v, "pct": round(v / total * 100, 1)} for k, v in source_counts.most_common()}

    return {
        "total_messages": total,
        "intent_distribution": intent_dist,
        "source_distribution": source_dist,
        "avg_response_ms": avg_ms,
    }


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/summary", tags=["analytics"])
def analytics_summary(
    period: str = Query("7d", description="Zaman aralığı: '24h', '7d', '30d', 'all'"),
):
    """
    Genel analytics özeti döndürür. Herkese açık (hassas veri içermez).

    - **period**: `24h` | `7d` | `30d` | `all`
    """
    now = datetime.now(timezone.utc)
    since: Optional[datetime] = None

    if period == "24h":
        since = now - timedelta(hours=24)
    elif period == "7d":
        since = now - timedelta(days=7)
    elif period == "30d":
        since = now - timedelta(days=30)
    elif period != "all":
        raise HTTPException(status_code=400, detail="Geçersiz period. Kabul edilenler: 24h, 7d, 30d, all")

    entries = _load_entries(since=since)
    summary = _build_summary(entries)
    summary["period"] = period
    summary["generated_at"] = now.isoformat()

    return summary


@router.get("/recent", tags=["analytics"])
def analytics_recent(
    limit: int = Query(50, ge=1, le=500, description="Döndürülecek maksimum kayıt sayısı"),
    _: None = Depends(_require_admin),
):
    """
    Son N analytics kaydını döndürür. **Admin token gerektirir.**

    Authorization header: `Bearer <ADMIN_SECRET_TOKEN>`
    """
    entries = _load_entries()
    recent = entries[-limit:] if len(entries) > limit else entries
    recent.reverse()

    return {
        "count": len(recent),
        "entries": recent,
    }
