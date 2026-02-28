# ============================================================================
# backend/app/api/endpoints/chat.py - Chat API Endpoint'leri
# ============================================================================

import re
import os
import asyncio
import logging
import random
from time import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Request

from ...schemas.chat import ChatRequest, ChatResponse
from ...core.classifier import classify_intent
from ...core.limiter import limiter
from ...services.web_scraper.manager import update_system_data
from ...services.llm_client import get_llm_response
from ...services.device_registry import (
    search_device,
    suggest_device,
    get_device_info
)


# ============================================================================
# LOGGER
# ============================================================================

logger: logging.Logger = logging.getLogger("uvicorn")


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
    year_match: Optional[object] = re.search(r'(20\d{2})|(\d{2}-\d{2})', message)
    calendars: dict = intent.get("extra_data", {})

    if year_match and calendars:
        user_year: str = year_match.group(0)
        for key, url in calendars.items():
            if user_year in key:
                return ChatResponse(
                    response=f"{key} Akademik Takvimi: {url}",
                    source="Akıllı Arşiv",
                    intent_name="akademik_takvim"
                )
        return ChatResponse(
            response=f"{user_year} yılı bulunamadı. Güncel: {intent['response_content']}",
            source="Hızlı Yol",
            intent_name="akademik_takvim"
        )

    return ChatResponse(
        response=intent["response_content"],
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

    logger.info(f"📨 Gelen Mesaj: {body.message[:80]}")

    # -------- ADIM 1: CONFIRMATION KONTROLÜ --------
    pending_device = _get_pending_device(user_id)
    if pending_device:
        positive_answers = ["evet", "aynen", "he", "hıhı", "onayla", "yes", "doğru", "tabi"]
        if any(ans in message for ans in positive_answers):
            del PENDING_CONFIRMATIONS[user_id]
            response = _get_confirmation_response(pending_device)
            if response:
                return response
        else:
            del PENDING_CONFIRMATIONS[user_id]

    # -------- ADIM 2: INTENT CLASSIFICATION --------
    intent: Optional[dict] = classify_intent(body.message)

    if intent:
        logger.info(f"✅ Intent: {intent['intent_name']}")
        intent_name: str = intent["intent_name"]

        if intent_name == "akademik_takvim":
            return _handle_academic_calendar(intent, body.message)
        elif intent_name == "cihaz_bilgisi":
            return _handle_device_query(body.message, user_id)
        else:
            return _handle_generic_intent(intent)

    # -------- ADIM 3: LLM FALLBACK --------
    return await _fallback_to_llm(body.message, history)


@router.post("/update-data", dependencies=[Depends(_verify_admin_token)])
async def trigger_data_update() -> dict:
    """
    Manuel veri güncelleme — X-Admin-Token header gerektirir.
    """
    logger.info("🔄 Manuel veri güncelleme başlatıldı...")
    result: dict = await asyncio.to_thread(update_system_data)
    return result
