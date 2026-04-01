# ============================================================================
# backend/app/api/endpoints/chat.py - Chat API Endpoint'leri
# ============================================================================

import re
import asyncio
import logging
import random
import json
from time import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel as _BaseModel, Field

from ...schemas.chat import ChatRequest, ChatResponse


def _current_academic_year() -> str:
    """Mevcut tarihten akademik yılı hesapla (ör. Eylül 2025 → '2025-2026')."""
    today = date.today()
    start = today.year if today.month >= 9 else today.year - 1
    return f"{start}-{start + 1}"
from ...core.classifier import classify_intent
from ...core.limiter import limiter, llm_limiter
from ...services.web_scraper.manager import update_system_data, _format_menu_message
from ...services.web_scraper.food_scrapper import scrape_daily_menu
from ...services.web_scraper.duyurular_scraper import scrape_announcements
from ...services.weather import get_weather
from ...services.llm_client import get_llm_response, stream_llm_response
from ...services.session_store import save_message, get_or_fallback
from ...services.web_scraper.library_site_scraper import scrape_library_info, format_library_response
from ...services.web_scraper.sks_scrapper import scrape_sks_events, format_sks_response
from ...services.web_scraper.main_site_scrapper import scrape_main_site_news, format_main_news_response
from ...services.cache import cache_get, cache_set
from ...security import require_admin

from .chat_device import (
    cleanup_expired_confirmations,
    get_confirmation_response,
    get_pending_device,
    handle_device_query,
    handle_device_search_flow,
)


# ============================================================================
# LOGGER & ANALYTICS
# ============================================================================

logger: logging.Logger = logging.getLogger("uvicorn")

# Analytics logu: her soru → hangi intent, kaynak, süre
_ANALYTICS_FILE = Path(__file__).parent.parent.parent / "data" / "analytics.jsonl"
_ANALYTICS_MAX_BYTES = 50 * 1024 * 1024  # 50 MB


def _rotate_analytics_if_needed() -> None:
    """Dosya boyutu limiti aşıldığında eski kayıtların yarısını silerek küçültür."""
    try:
        if not _ANALYTICS_FILE.exists():
            return
        size = _ANALYTICS_FILE.stat().st_size
        if size < _ANALYTICS_MAX_BYTES:
            return
        with open(_ANALYTICS_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()
        keep = lines[len(lines) // 2:]
        with open(_ANALYTICS_FILE, "w", encoding="utf-8") as f:
            f.writelines(keep)
        logger.info(f"Analytics rotate: {len(lines)} → {len(keep)} satır.")
    except Exception:
        pass


def _log_analytics(message: str, intent_name: str, source: str, elapsed_ms: float) -> None:
    """Her chat isteğini analytics dosyasına JSONL formatında yaz."""
    try:
        _rotate_analytics_if_needed()
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "q": message[:120],
            "intent": intent_name,
            "source": source,
            "ms": round(elapsed_ms),
        }
        with open(_ANALYTICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ============================================================================
# ROUTER
# ============================================================================

router: APIRouter = APIRouter()


# ============================================================================
# CACHE KEYS & TTL CONSTANTS (scrape / dış servis yanıtları)
# ============================================================================

_FOOD_CACHE_TTL: int = 86400    # 24 saat (gün bazlı key zaten unique)
_DUYURU_CACHE_TTL: int = 3600   # 1 saat
_WEATHER_CACHE_TTL: int = 1800  # 30 dakika
_LIBRARY_CACHE_TTL: int = 21600 # 6 saat
_SKS_CACHE_TTL: int = 21600     # 6 saat
_NEWS_CACHE_TTL: int = 3600     # 1 saat


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _handle_academic_calendar(intent: dict, message: str) -> ChatResponse:
    msg_lower = message.lower()
    calendars: dict = intent.get("extra_data", {})
    key_dates: dict = calendars.get("key_dates", {})

    # Önemli tarih anahtar kelimeleri → direkt cevap
    _DATE_KEYWORDS: list[tuple[list[str], str]] = [
        (["vize", "ara sınav", "midterm"], "Vize Sınavları"),
        (["final", "yarıyıl sonu sınav"], "Final Sınavları"),
        (["bütünleme", "mazeret"], "Bütünleme Sınavları"),
        (["ara tatil", "sömestr", "yarıyıl tatil"], "Ara Tatil"),
        (["yaz tatil", "yaz dönemi", "yıl sonu"], "Yaz Tatili"),
        (["kayıt yenile", "ders kaydı", "kayıt"], "Kayıt Yenileme"),
        (["güz", "güz dönemi", "güz başlangıç"], "Güz Dönemi Başlangıç"),
        (["bahar", "bahar dönemi", "bahar başlangıç"], "Bahar Dönemi Başlangıç"),
    ]

    if key_dates:
        for keywords, label in _DATE_KEYWORDS:
            if any(kw in msg_lower for kw in keywords):
                if label in key_dates:
                    return ChatResponse(
                        response=f"📅 **{label}:** {key_dates[label]}",
                        source="Takvim (HTML)",
                        intent_name="akademik_takvim"
                    )

        # "ne zaman" gibi genel soru → önemli tarihlerin özeti
        if any(kw in msg_lower for kw in ["ne zaman", "tarih", "takvim"]):
            lines = [f"📅 **{_current_academic_year()} Önemli Tarihler**\n"]
            for label, date_val in key_dates.items():
                lines.append(f"• **{label}:** {date_val}")
            lines.append(f"\n🔗 Tam takvim: {calendars.get('current', intent['response_content'])}")
            return ChatResponse(
                response="\n".join(lines),
                source="Takvim (HTML)",
                intent_name="akademik_takvim"
            )

    # Belirli yıl aranıyor mu?
    year_match = re.search(r'(20\d{2}[-–]\d{2,4}|20\d{2})', message)
    if year_match and calendars:
        user_year: str = year_match.group(0).replace("–", "-")
        for key, url in calendars.items():
            if key in ("current", "key_dates"):
                continue
            if user_year[:4] in key:
                return ChatResponse(
                    response=f"📅 {key} Akademik Takvimi:\n{url}",
                    source="Akıllı Arşiv",
                    intent_name="akademik_takvim"
                )
        return ChatResponse(
            response=f"{user_year} yılı bulunamadı.\n📅 Güncel takvim: {intent['response_content']}",
            source="Hızlı Yol",
            intent_name="akademik_takvim"
        )

    return ChatResponse(
        response=f"📅 **Güncel Akademik Takvim ({_current_academic_year()})**\n{intent['response_content']}",
        source="Hızlı Yol",
        intent_name="akademik_takvim"
    )


async def _handle_food_query() -> ChatResponse:
    """
    Yemek menüsünü live olarak scrape et. Günlük cache kullanır:
    aynı gün tekrar sorulursa scrape yapılmaz, cache'den döner.
    """
    today = date.today()
    cache_key = f"food:{today.isoformat()}"
    cached = cache_get(cache_key)
    if cached:
        return ChatResponse(
            response=cached,
            source="Yemek Servisi (cache)",
            intent_name="yemek_listesi"
        )

    try:
        daily_menu: Optional[str] = await asyncio.wait_for(
            asyncio.to_thread(scrape_daily_menu),
            timeout=12.0
        )
    except asyncio.TimeoutError:
        logger.warning("⏱️ Yemek scraper zaman aşımı.")
        daily_menu = None
    except Exception as e:
        logger.error(f"❌ Yemek scraper hatası: {e}", exc_info=True)
        daily_menu = None

    formatted: str = _format_menu_message(daily_menu)
    cache_set(cache_key, formatted, ttl=_FOOD_CACHE_TTL)

    return ChatResponse(
        response=formatted,
        source="Yemek Servisi",
        intent_name="yemek_listesi"
    )


async def _handle_duyurular_query() -> ChatResponse:
    """Duyuruları live scrape et, saatlik cache kullan."""
    cached = cache_get("duyurular")
    if cached:
        return ChatResponse(response=cached, source="Duyurular (cache)", intent_name="duyurular")

    try:
        result: Optional[str] = await asyncio.wait_for(
            asyncio.to_thread(scrape_announcements), timeout=12.0
        )
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Duyurular scraper hatası: {e}")
        result = None

    if result:
        cache_set("duyurular", result, ttl=_DUYURU_CACHE_TTL)
        return ChatResponse(response=result, source="Duyurular", intent_name="duyurular")

    return ChatResponse(
        response="📢 Duyurulara şu an ulaşılamıyor.\nDetay: https://www.artvin.edu.tr/tr/duyuru/tumu",
        source="Duyurular (hata)",
        intent_name="duyurular"
    )


async def _handle_weather_query() -> ChatResponse:
    """Hava durumunu live çek, 30 dakikalık cache kullan."""
    cached = cache_get("weather:artvin")
    if cached:
        return ChatResponse(response=cached, source="Hava Durumu (cache)", intent_name="hava_durumu")

    try:
        result: str = await asyncio.wait_for(
            asyncio.to_thread(get_weather), timeout=10.0
        )
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Hava durumu hatası: {e}")
        result = "🌤️ Hava durumu bilgisi alınamadı. https://www.mgm.gov.tr"

    cache_set("weather:artvin", result, ttl=_WEATHER_CACHE_TTL)
    return ChatResponse(response=result, source="Hava Durumu", intent_name="hava_durumu")


async def _handle_library_query() -> ChatResponse:
    """Kütüphane bilgilerini live scrape et, 6 saatlik cache kullan."""
    cached = cache_get("library")
    if cached:
        return ChatResponse(response=cached, source="Kütüphane (cache)", intent_name="kutuphane")

    try:
        info = await asyncio.wait_for(asyncio.to_thread(scrape_library_info), timeout=12.0)
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Kütüphane scraper hatası: {e}")
        info = None

    result = format_library_response(info)
    cache_set("library", result, ttl=_LIBRARY_CACHE_TTL)
    return ChatResponse(response=result, source="Kütüphane Sitesi", intent_name="kutuphane")


async def _handle_sks_query() -> ChatResponse:
    """SKS etkinlik bilgilerini live scrape et, 6 saatlik cache kullan."""
    cached = cache_get("sks_events")
    if cached:
        return ChatResponse(response=cached, source="SKS (cache)", intent_name="sks_etkinlik")

    try:
        info = await asyncio.wait_for(asyncio.to_thread(scrape_sks_events), timeout=12.0)
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"SKS scraper hatası: {e}")
        info = None

    result = format_sks_response(info)
    cache_set("sks_events", result, ttl=_SKS_CACHE_TTL)
    return ChatResponse(response=result, source="SKS Sitesi", intent_name="sks_etkinlik")


async def _handle_news_query() -> ChatResponse:
    """Ana site haberlerini live scrape et, 1 saatlik cache kullan."""
    cached = cache_get("main_news")
    if cached:
        return ChatResponse(response=cached, source="Haberler (cache)", intent_name="guncel_haberler")

    try:
        news = await asyncio.wait_for(asyncio.to_thread(scrape_main_site_news), timeout=12.0)
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Haber scraper hatası: {e}")
        news = None

    result = format_main_news_response(news)
    cache_set("main_news", result, ttl=_NEWS_CACHE_TTL)
    return ChatResponse(response=result, source="Ana Site", intent_name="guncel_haberler")


def _handle_generic_intent(intent: dict) -> ChatResponse:
    raw_response = intent["response_content"]
    final_response: str = random.choice(raw_response) if isinstance(raw_response, list) else raw_response
    return ChatResponse(
        response=final_response,
        source="Hızlı Yol",
        intent_name=intent["intent_name"]
    )


async def _dispatch_intent(intent: dict, raw_message: str, user_id: str) -> ChatResponse:
    """Ortak intent dispatch — hem normal hem stream endpoint'i bu fonksiyonu kullanır."""
    intent_name: str = intent["intent_name"]

    if intent_name == "akademik_takvim":
        return _handle_academic_calendar(intent, raw_message)
    if intent_name == "yemek_listesi":
        return await _handle_food_query()
    if intent_name == "cihaz_bilgisi":
        return handle_device_query(raw_message, user_id)
    if intent_name == "duyurular":
        return await _handle_duyurular_query()
    if intent_name == "hava_durumu":
        return await _handle_weather_query()
    if intent_name in ("kutuphane", "kütüphane"):
        return await _handle_library_query()
    if intent_name in ("sks_etkinlik", "kulup_topluluk"):
        return await _handle_sks_query()
    if intent_name == "guncel_haberler":
        return await _handle_news_query()
    return _handle_generic_intent(intent)


async def _fallback_to_llm(message: str, history: list[dict]) -> ChatResponse:
    """Intent bulunamadığında Gemini'ye yönlendir. asyncio.to_thread ile event loop'u bloke etmez."""
    logger.warning("⚠️  Yerel eşleşme yok. LLM'e yönlendiriliyor...")
    try:
        ai_response: str = await asyncio.wait_for(
            asyncio.to_thread(get_llm_response, message, history),
            timeout=20.0
        )
        return ChatResponse(
            response=ai_response,
            source="Gemini AI",
            intent_name="genel_sohbet"
        )
    except asyncio.TimeoutError:
        logger.error("❌ Gemini API 20 saniye içinde yanıt vermedi.")
        return ChatResponse(
            response="Üzgünüm, AI servisi şu an yanıt vermiyor. Lütfen tekrar deneyin.",
            source="Timeout",
            intent_name="error"
        )
    except Exception as e:
        logger.error(f"❌ LLM Hatası: {e}", exc_info=True)
        return ChatResponse(
            response="Üzgünüm, şu anda AI servisine bağlanamıyorum.",
            source="Error",
            intent_name="error"
        )


# ============================================================================
# MAIN ENDPOINTS
# ============================================================================

@router.post("/chat", response_model=ChatResponse)
@limiter.limit("20/minute")
async def handle_chat_message(request: Request, body: ChatRequest) -> ChatResponse:
    """
    Ana chat endpoint'i — dakikada 20 istek sınırı.

    İşlem sırası:
      1. Süresi geçmiş onayları temizle
      2. Session-based cihaz onay kontrolü
      3. Intent classification
      4. Intent handler'ını çağır
      5. LLM fallback (async, 20s timeout)
    """
    cleanup_expired_confirmations()

    user_id: str = body.session_id or "default_user"
    message: str = body.message.lower().strip()
    client_history = [{"role": h.role, "text": h.text} for h in body.history]
    history: list[dict] = get_or_fallback(body.session_id, client_history)
    t_start = time()

    logger.info(f"📨 Gelen Mesaj: {body.message[:80]}")

    # -------- ADIM 1: CONFIRMATION KONTROLÜ --------
    pending_device = get_pending_device(user_id)
    if pending_device:
        positive_answers = ["evet", "aynen", "he", "hıhı", "onayla", "yes", "doğru", "tabi"]
        cache_set(f"pending_device:{user_id}", None, ttl=1)
        if any(ans in message for ans in positive_answers):
            response = get_confirmation_response(pending_device)
            if response:
                _log_analytics(body.message, response.intent_name, response.source, (time() - t_start) * 1000)
                return response
        else:
            result = ChatResponse(
                response="Anlaşıldı, başka bir konuda yardımcı olabilir miyim?",
                source="Sistem",
                intent_name="cihaz_bilgisi_red"
            )
            _log_analytics(body.message, result.intent_name, result.source, (time() - t_start) * 1000)
            return result

    # -------- ADIM 2: CIHAZ ARAMA AKIŞI (VARSA) --------
    device_search_response = handle_device_search_flow(user_id, body.message)
    if device_search_response is not None:
        save_message(body.session_id, "user", body.message)
        save_message(body.session_id, "bot", device_search_response.response)
        _log_analytics(body.message, device_search_response.intent_name or "cihaz_arama", device_search_response.source, (time() - t_start) * 1000)
        return device_search_response

    # -------- ADIM 3: INTENT CLASSIFICATION --------
    intent: Optional[dict] = classify_intent(body.message)

    if intent:
        logger.info(f"✅ Intent: {intent['intent_name']}")
        result = await _dispatch_intent(intent, body.message, user_id)
        save_message(body.session_id, "user", body.message)
        save_message(body.session_id, "bot", result.response)
        _log_analytics(body.message, result.intent_name, result.source, (time() - t_start) * 1000)
        return result

    # -------- ADIM 4: LLM FALLBACK --------
    result = await _fallback_to_llm(body.message, history)
    save_message(body.session_id, "user", body.message)
    save_message(body.session_id, "bot", result.response)
    _log_analytics(body.message, result.intent_name, result.source, (time() - t_start) * 1000)
    return result


@router.post("/chat/stream")
@limiter.limit("20/minute")
@llm_limiter.limit("10/minute")
async def stream_chat_message(request: Request, body: ChatRequest) -> StreamingResponse:
    """
    Streaming chat endpoint — Gemini cevabını SSE (text/event-stream) olarak akıtır.
    Lokal intent'ler tek seferde, LLM token token gönderilir.
    """
    user_id: str = body.session_id or "default_user"
    message: str = body.message.lower().strip()
    client_history = [{"role": h.role, "text": h.text} for h in body.history]
    history: list[dict] = get_or_fallback(body.session_id, client_history)
    t_start = time()

    cleanup_expired_confirmations()
    pending_device = get_pending_device(user_id)

    async def event_stream():
        nonlocal t_start
        try:
            # İlk byte'ı hemen gönder; gateway/proxy timeout (504) önlenir
            yield _sse("", done=False)
            # Onay kontrolü
            if pending_device:
                positive = ["evet", "aynen", "he", "hıhı", "onayla", "yes", "doğru", "tabi"]
                cache_set(f"pending_device:{user_id}", None, ttl=1)
                if any(ans in message for ans in positive):
                    conf = get_confirmation_response(pending_device)
                    if conf:
                        yield _sse(conf.response, done=True)
                        return
                else:
                    yield _sse("Anlaşıldı, başka bir konuda yardımcı olabilir miyim?", done=True)
                    return

            # Cihaz arama akışı (varsa) — streaming için de tek parça cevap döneriz.
            device_search_response = handle_device_search_flow(user_id, body.message)
            if device_search_response is not None:
                _log_analytics(body.message, device_search_response.intent_name or "cihaz_arama", device_search_response.source, (time() - t_start) * 1000)
                save_message(body.session_id, "user", body.message)
                save_message(body.session_id, "bot", device_search_response.response)
                yield _sse(device_search_response.response, done=True)
                return

            intent: Optional[dict] = classify_intent(body.message)

            if intent:
                r = await _dispatch_intent(intent, body.message, user_id)
                _log_analytics(body.message, r.intent_name, r.source, (time() - t_start) * 1000)
                save_message(body.session_id, "user", body.message)
                save_message(body.session_id, "bot", r.response)
                yield _sse(r.response, done=True)
                return

            # LLM Streaming
            queue: asyncio.Queue = asyncio.Queue()

            def _run_stream():
                try:
                    for token in stream_llm_response(body.message, history):
                        queue.put_nowait(token)
                except Exception as e:
                    logger.error(f"Stream thread hatası: {e}")
                finally:
                    queue.put_nowait(None)  # sentinel

            asyncio.get_running_loop().run_in_executor(None, _run_stream)

            accumulated = ""
            try:
                while True:
                    token = await asyncio.wait_for(queue.get(), timeout=25.0)
                    if token is None:
                        break
                    accumulated += token
                    yield _sse(token, done=False)
            except asyncio.TimeoutError:
                yield _sse("\n\n⏱️ Zaman aşımı.", done=True)
                return

            _log_analytics(body.message, "genel_sohbet", "Gemini AI (stream)", (time() - t_start) * 1000)
            save_message(body.session_id, "user", body.message)
            save_message(body.session_id, "bot", accumulated)
            yield _sse("", done=True)

        except Exception as e:
            logger.error(f"❌ Stream generator hatası: {e}", exc_info=True)
            yield _sse("⚠️ Bir hata oluştu, lütfen tekrar deneyin.", done=True)

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(data: str, done: bool) -> str:
    """SSE formatında event oluştur."""
    import json as _json
    payload = _json.dumps({"token": data, "done": done}, ensure_ascii=False)
    return f"data: {payload}\n\n"


@router.post("/update-data", dependencies=[Depends(require_admin)])
async def trigger_data_update() -> dict:
    """
    Manuel veri güncelleme — admin token gerektirir.
    """
    logger.info("🔄 Manuel veri güncelleme başlatıldı...")
    result: dict = await asyncio.to_thread(update_system_data)
    return result


# ── Feedback endpoint ────────────────────────────────────────────────────────

class _FeedbackRequest(_BaseModel):
    msg_id: int
    value: Optional[str] = Field(None, max_length=10)
    text: str = Field("", max_length=500)


@router.post("/feedback")
@limiter.limit("10/minute")
async def submit_feedback(body: _FeedbackRequest, request: Request) -> dict:
    """
    Kullanıcı geri bildirimini analytics.jsonl'a kaydet.
    """
    session_id = request.headers.get("X-Session-Id", "")
    try:
        entry = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "type": "feedback",
            "session": session_id[:32],
            "msg_id": body.msg_id,
            "value": body.value,
            "text": body.text[:200],
        }
        with open(_ANALYTICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return {"status": "ok"}
