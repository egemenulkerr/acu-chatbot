# ============================================================================
# backend/app/api/endpoints/chat.py - Chat API Endpoint'leri
# ============================================================================

import re
import os
import asyncio
import logging
import random
import json
from time import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from fastapi.responses import StreamingResponse

from ...schemas.chat import ChatRequest, ChatResponse
from ...core.classifier import classify_intent
from ...core.limiter import limiter
from ...services.web_scraper.manager import update_system_data, _format_menu_message
from ...services.web_scraper.food_scrapper import scrape_daily_menu
from ...services.web_scraper.duyurular_scraper import scrape_announcements
from ...services.weather import get_weather
from ...services.llm_client import get_llm_response, stream_llm_response
from ...services.device_registry import (
    search_device,
    suggest_device,
    get_device_info
)


# ============================================================================
# LOGGER & ANALYTICS
# ============================================================================

logger: logging.Logger = logging.getLogger("uvicorn")

# Analytics logu: her soru → hangi intent, kaynak, süre
_ANALYTICS_FILE = Path(__file__).parent.parent.parent / "data" / "analytics.jsonl"


def _log_analytics(message: str, intent_name: str, source: str, elapsed_ms: float) -> None:
    """Her chat isteğini analytics dosyasına JSONL formatında yaz."""
    try:
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "q": message[:120],
            "intent": intent_name,
            "source": source,
            "ms": round(elapsed_ms),
        }
        with open(_ANALYTICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Analytics logu asla ana akışı bozmasın


# ============================================================================
# ROUTER
# ============================================================================

router: APIRouter = APIRouter()


# ============================================================================
# STATE: PENDING CONFIRMATIONS (TTL destekli)
# ============================================================================

# session_id → (cihaz_adı, timestamp)
PENDING_CONFIRMATIONS: dict[str, tuple[str, float]] = {}
CONFIRMATION_TTL: float = 300.0  # 5 dakika

# ============================================================================
# STATE: YEMEK GÜNLÜK CACHE
# ============================================================================

# Her gün ilk istekte scrape yapılır, gün değişene kadar cache'de tutulur
_FOOD_CACHE: dict = {"date": None, "response": None}

# Duyurular: saatlik cache
_DUYURU_CACHE: dict = {"ts": 0.0, "response": None}
_DUYURU_TTL: float = 3600.0  # 1 saat

# Hava durumu: 30 dakikalık cache
_WEATHER_CACHE: dict = {"ts": 0.0, "response": None}
_WEATHER_TTL: float = 1800.0  # 30 dakika


def _cleanup_expired_confirmations() -> None:
    """Süresi geçmiş cihaz onay bekleyen oturumları temizle."""
    now = time()
    expired = [k for k, (_, ts) in PENDING_CONFIRMATIONS.items() if now - ts > CONFIRMATION_TTL]
    for k in expired:
        del PENDING_CONFIRMATIONS[k]


def _get_pending_device(session_id: str) -> Optional[str]:
    """Aktif ve süresi geçmemiş bir onay bekliyorsa cihaz adını döndür."""
    if session_id in PENDING_CONFIRMATIONS:
        device, ts = PENDING_CONFIRMATIONS[session_id]
        if time() - ts <= CONFIRMATION_TTL:
            return device
        del PENDING_CONFIRMATIONS[session_id]
    return None


def _set_pending_device(session_id: str, device_name: str) -> None:
    PENDING_CONFIRMATIONS[session_id] = (device_name, time())


# ============================================================================
# AUTH: /api/update-data için admin token
# ============================================================================

async def _verify_admin_token(x_admin_token: str = Header(...)) -> None:
    """
    X-Admin-Token header'ını doğrula.
    ADMIN_SECRET_TOKEN env var ile karşılaştır.
    """
    expected = os.getenv("ADMIN_SECRET_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=503, detail="Admin token yapılandırılmamış.")
    if x_admin_token != expected:
        raise HTTPException(status_code=403, detail="Yetkisiz erişim.")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_confirmation_response(device_name: str) -> Optional[ChatResponse]:
    device_data: Optional[dict] = get_device_info(device_name)
    if device_data:
        info = device_data.get("info", {})
        return ChatResponse(
            response=(
                f"Anlaşıldı. İşte bilgiler:\n\n"
                f"**{device_data['name']}**\n\n"
                f"{info.get('description', '')}\n\n"
                f"{info.get('stock', '')}"
            ),
            source="Cihaz Katalogu (Onaylı)",
            intent_name="cihaz_bilgisi"
        )
    return None


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
            lines = ["📅 **2025-2026 Önemli Tarihler**\n"]
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
        response=f"📅 **Güncel Akademik Takvim (2025-2026)**\n{intent['response_content']}",
        source="Hızlı Yol",
        intent_name="akademik_takvim"
    )


def _handle_device_query(message: str, user_id: str) -> ChatResponse:
    device_data: Optional[dict] = search_device(message)
    if device_data:
        info = device_data.get("info", {})
        return ChatResponse(
            response=(
                f"**{device_data['name']}**\n\n"
                f"{info.get('description', '')}\n\n"
                f"{info.get('stock', '')}"
            ),
            source="Cihaz Katalogu",
            intent_name="cihaz_bilgisi"
        )

    suggestion: Optional[str] = suggest_device(message)
    if suggestion:
        _set_pending_device(user_id, suggestion)
        return ChatResponse(
            response=f"Tam bulamadım ama şunu mu demek istediniz: **{suggestion.title()}**? (Evet/Hayır)",
            source="Akıllı Öneri Sistemi",
            intent_name="cihaz_bilgisi_onay"
        )

    return ChatResponse(
        response="Maalesef o cihazı bulamadım. Başka bir şey sormak ister misiniz?",
        source="Hata",
        intent_name="cihaz_bilgisi_hata"
    )


async def _handle_food_query() -> ChatResponse:
    """
    Yemek menüsünü live olarak scrape et. Günlük in-memory cache kullanır:
    aynı gün tekrar sorulursa scrape yapılmaz, cache'den döner.
    """
    today = date.today()
    if _FOOD_CACHE["date"] == today and _FOOD_CACHE["response"] is not None:
        return ChatResponse(
            response=_FOOD_CACHE["response"],
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
    _FOOD_CACHE["date"] = today
    _FOOD_CACHE["response"] = formatted

    return ChatResponse(
        response=formatted,
        source="Yemek Servisi",
        intent_name="yemek_listesi"
    )


async def _handle_duyurular_query() -> ChatResponse:
    """Duyuruları live scrape et, saatlik cache kullan."""
    now = time()
    if _DUYURU_CACHE["response"] and now - _DUYURU_CACHE["ts"] < _DUYURU_TTL:
        return ChatResponse(response=_DUYURU_CACHE["response"], source="Duyurular (cache)", intent_name="duyurular")

    try:
        result: Optional[str] = await asyncio.wait_for(
            asyncio.to_thread(scrape_announcements), timeout=12.0
        )
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Duyurular scraper hatası: {e}")
        result = None

    if result:
        _DUYURU_CACHE["ts"] = now
        _DUYURU_CACHE["response"] = result
        return ChatResponse(response=result, source="Duyurular", intent_name="duyurular")

    return ChatResponse(
        response="📢 Duyurulara şu an ulaşılamıyor.\nDetay: https://www.artvin.edu.tr/tr/duyurular",
        source="Duyurular (hata)",
        intent_name="duyurular"
    )


async def _handle_weather_query() -> ChatResponse:
    """Hava durumunu live çek, 30 dakikalık cache kullan."""
    now = time()
    if _WEATHER_CACHE["response"] and now - _WEATHER_CACHE["ts"] < _WEATHER_TTL:
        return ChatResponse(response=_WEATHER_CACHE["response"], source="Hava Durumu (cache)", intent_name="hava_durumu")

    try:
        result: str = await asyncio.wait_for(
            asyncio.to_thread(get_weather), timeout=10.0
        )
    except (asyncio.TimeoutError, Exception) as e:
        logger.warning(f"Hava durumu hatası: {e}")
        result = "🌤️ Hava durumu bilgisi alınamadı. https://www.mgm.gov.tr"

    _WEATHER_CACHE["ts"] = now
    _WEATHER_CACHE["response"] = result
    return ChatResponse(response=result, source="Hava Durumu", intent_name="hava_durumu")


def _handle_generic_intent(intent: dict) -> ChatResponse:
    raw_response = intent["response_content"]
    final_response: str = random.choice(raw_response) if isinstance(raw_response, list) else raw_response
    return ChatResponse(
        response=final_response,
        source="Hızlı Yol",
        intent_name=intent["intent_name"]
    )


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
    _cleanup_expired_confirmations()

    user_id: str = body.session_id or "default_user"
    message: str = body.message.lower().strip()
    history: list[dict] = body.history or []
    t_start = time()

    logger.info(f"📨 Gelen Mesaj: {body.message[:80]}")

    # -------- ADIM 1: CONFIRMATION KONTROLÜ --------
    pending_device = _get_pending_device(user_id)
    if pending_device:
        positive_answers = ["evet", "aynen", "he", "hıhı", "onayla", "yes", "doğru", "tabi"]
        if any(ans in message for ans in positive_answers):
            del PENDING_CONFIRMATIONS[user_id]
            response = _get_confirmation_response(pending_device)
            if response:
                _log_analytics(body.message, response.intent_name, response.source, (time() - t_start) * 1000)
                return response
        else:
            del PENDING_CONFIRMATIONS[user_id]

    # -------- ADIM 2: INTENT CLASSIFICATION --------
    intent: Optional[dict] = classify_intent(body.message)

    if intent:
        logger.info(f"✅ Intent: {intent['intent_name']}")
        intent_name: str = intent["intent_name"]

        if intent_name == "akademik_takvim":
            result = _handle_academic_calendar(intent, body.message)
        elif intent_name == "yemek_listesi":
            result = await _handle_food_query()
        elif intent_name == "cihaz_bilgisi":
            result = _handle_device_query(body.message, user_id)
        elif intent_name == "duyurular":
            result = await _handle_duyurular_query()
        elif intent_name == "hava_durumu":
            result = await _handle_weather_query()
        else:
            result = _handle_generic_intent(intent)

        _log_analytics(body.message, result.intent_name, result.source, (time() - t_start) * 1000)
        return result

    # -------- ADIM 3: LLM FALLBACK --------
    result = await _fallback_to_llm(body.message, history)
    _log_analytics(body.message, result.intent_name, result.source, (time() - t_start) * 1000)
    return result


@router.post("/chat/stream")
@limiter.limit("20/minute")
async def stream_chat_message(request: Request, body: ChatRequest) -> StreamingResponse:
    """
    Streaming chat endpoint — Gemini cevabını SSE (text/event-stream) olarak akıtır.
    Lokal intent'ler tek seferde, LLM token token gönderilir.
    """
    user_id: str = body.session_id or "default_user"
    message: str = body.message.lower().strip()
    history: list[dict] = body.history or []
    t_start = time()

    # Lokal intent kontrolü
    _cleanup_expired_confirmations()
    pending_device = _get_pending_device(user_id)

    async def event_stream():
        nonlocal t_start

        # Onay kontrolü
        if pending_device:
            positive = ["evet", "aynen", "he", "hıhı", "onayla", "yes", "doğru", "tabi"]
            if any(ans in message for ans in positive):
                del PENDING_CONFIRMATIONS[user_id]
                conf = _get_confirmation_response(pending_device)
                if conf:
                    yield _sse(conf.response, done=True)
                    return

        intent: Optional[dict] = classify_intent(body.message)

        if intent:
            intent_name = intent["intent_name"]
            if intent_name == "akademik_takvim":
                r = _handle_academic_calendar(intent, body.message)
            elif intent_name == "yemek_listesi":
                r = await _handle_food_query()
            elif intent_name == "cihaz_bilgisi":
                r = _handle_device_query(body.message, user_id)
            elif intent_name == "duyurular":
                r = await _handle_duyurular_query()
            elif intent_name == "hava_durumu":
                r = await _handle_weather_query()
            else:
                r = _handle_generic_intent(intent)

            _log_analytics(body.message, r.intent_name, r.source, (time() - t_start) * 1000)
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

        asyncio.get_event_loop().run_in_executor(None, _run_stream)

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
        yield _sse("", done=True)

    return StreamingResponse(event_stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(data: str, done: bool) -> str:
    """SSE formatında event oluştur."""
    import json as _json
    payload = _json.dumps({"token": data, "done": done}, ensure_ascii=False)
    return f"data: {payload}\n\n"


@router.post("/update-data", dependencies=[Depends(_verify_admin_token)])
async def trigger_data_update() -> dict:
    """
    Manuel veri güncelleme — X-Admin-Token header gerektirir.
    """
    logger.info("🔄 Manuel veri güncelleme başlatıldı...")
    result: dict = await asyncio.to_thread(update_system_data)
    return result
