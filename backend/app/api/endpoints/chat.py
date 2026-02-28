# ============================================================================
# backend/app/api/endpoints/chat.py - Chat API Endpoint'leri
# ============================================================================
# Açıklama:
#   Ana chat endpoint'ini ve veri güncelleme endpoint'ini içerir. Intent
#   classification, cihaz önerisi, akademik takvim ve LLM fallback logic'ini
#   yönetir. Session-based confirmation sistemi ile cihaz önerilerini takip eder.
# ============================================================================

import re
import logging
import random
from typing import Optional

from fastapi import APIRouter

from ...schemas.chat import ChatRequest, ChatResponse
from ...core.classifier import classify_intent
from ...services.web_scraper.manager import update_system_data
from ...services.llm_client import get_llm_response
from ...services.device_registry import (
    search_device,
    suggest_device,
    get_device_info
)


# ============================================================================
# LOGGER CONFIGURATION
# ============================================================================

logger: logging.Logger = logging.getLogger("uvicorn")


# ============================================================================
# ROUTER INITIALIZATION
# ============================================================================

router: APIRouter = APIRouter()


# ============================================================================
# STATE MANAGEMENT
# ============================================================================

# Cihaz önerisi onayı beklenen kullanıcıları takip eden dictionary
PENDING_CONFIRMATIONS: dict[str, str] = {}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _get_confirmation_response(
    device_name: str,
    pending_confirmations: dict[str, str]
) -> Optional[ChatResponse]:
    """
    Cihaz önerisi onayı kontrolü.

    Kullanıcının daha önceki bir cihaz önerisine "Evet" veya "Hayır" diye
    cevap verip vermediğini kontrol eder.

    Args:
        device_name (str): Kontrol edilecek cihaz adı
        pending_confirmations (dict): Pending confirmations state

    Returns:
        ChatResponse | None: Onaylı cihaz bilgisi veya None
    """
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
    """
    Akademik takvim intent'ini işle.

    Kullanıcının sorduğu yıl için akademik takvim linkini döndür.

    Args:
        intent (dict): Intent classification result
        message (str): Orijinal kullanıcı mesajı

    Returns:
        ChatResponse: Akademik takvim bilgisi
    """
    year_match: Optional[object] = re.search(
        r'(20\d{2})|(\d{2}-\d{2})',
        message
    )
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
            response=(
                f"{user_year} yılı bulunamadı. "
                f"Güncel: {intent['response_content']}"
            ),
            source="Hızlı Yol",
            intent_name="akademik_takvim"
        )

    # Fallback: Genel takvim bilgisi
    return ChatResponse(
        response=intent["response_content"],
        source="Hızlı Yol",
        intent_name="akademik_takvim"
    )


def _handle_device_query(message: str, user_id: str) -> ChatResponse:
    """
    Cihaz bilgisi intent'ini işle.

    Sıra:
      1. Tam eşleşme (search_device)
      2. Fuzzy eşleşme (suggest_device) + confirmation pending
      3. Cevap bulunamaz

    Args:
        message (str): Kullanıcı mesajı
        user_id (str): Session ID

    Returns:
        ChatResponse: Cihaz bilgisi veya öneri
    """
    # 1. Tam eşleşme
    device_data: Optional[dict] = search_device(message)
    if device_data:
        info = device_data.get("info", {})
        return ChatResponse(
            response=(
                f"\n\n*{device_data['name']}*\n\n"
                f"{info.get('description', '')}\n\n"
                f"{info.get('stock', '')}"
            ),
            source="Cihaz Katalogu",
            intent_name="cihaz_bilgisi"
        )

    # 2. Fuzzy eşleşme + Confirmation
    suggestion: Optional[str] = suggest_device(message)
    if suggestion:
        PENDING_CONFIRMATIONS[user_id] = suggestion
        return ChatResponse(
            response=(
                f"🤔 Tam bulamadım ama şunu mu demek istediniz: "
                f"**{suggestion.title()}**? (Evet/Hayır)"
            ),
            source="Akıllı Öneri Sistemi",
            intent_name="cihaz_bilgisi_onay"
        )

    # 3. Fallback
    return ChatResponse(
        response="Maalesef o cihazı bulamadım. Başka bir şey sormak ister misiniz?",
        source="Hata",
        intent_name="cihaz_bilgisi_hata"
    )


def _handle_generic_intent(intent: dict) -> ChatResponse:
    """
    Genel intent'leri (selamlasma, yemek listesi vb.) işle.

    Response list ise rastgele seç, string ise direkt döndür.

    Args:
        intent (dict): Intent classification result

    Returns:
        ChatResponse: Intent response
    """
    raw_response: any = intent["response_content"]

    # List ise rastgele seç, string ise direkt kullan
    if isinstance(raw_response, list):
        final_response: str = random.choice(raw_response)
    else:
        final_response: str = raw_response

    return ChatResponse(
        response=final_response,
        source="Hızlı Yol",
        intent_name=intent["intent_name"]
    )


async def _fallback_to_llm(message: str) -> ChatResponse:
    """
    Intent sınıflandırması başarısız olduğunda LLM'e yönlendir.

    Google Gemini API'sini kullanarak genel sohbet cevapları oluştur.

    Args:
        message (str): Kullanıcı mesajı

    Returns:
        ChatResponse: LLM tarafından üretilen cevap veya error
    """
    logger.warning("⚠️  Yerel eşleşme yok. LLM'e (Gemini) yönlendiriliyor...")
    try:
        ai_response: str = get_llm_response(message)
        return ChatResponse(
            response=ai_response,
            source="Gemini AI (Akıllı Yol)",
            intent_name="genel_sohbet"
        )
    except Exception as e:
        logger.error(f"❌ LLM Hatası: {str(e)}")
        return ChatResponse(
            response="Üzgünüm, şu anda AI servisine bağlanamıyorum.",
            source="Error",
            intent_name="error"
        )


# ============================================================================
# MAIN ENDPOINTS
# ============================================================================

@router.post("/chat", response_model=ChatResponse)
async def handle_chat_message(request: ChatRequest) -> ChatResponse:
    """
    Ana chat endpoint'i.

    İşlem sırası:
      1. Session-based confirmation kontrolü (pending cihaz önerisi)
      2. Intent classification (Keyword > Semantic > LLM)
      3. Intent-specific handler'ları çağır
      4. LLM fallback

    Args:
        request (ChatRequest): İstenen chat mesajı

    Returns:
        ChatResponse: Chatbot cevabı + metadata
    """
    user_id: str = request.session_id or "default_user"
    message: str = request.message.lower().strip()

    logger.info(f"📨 Gelen Mesaj: {request.message}")

    # -------- ADIM 1: CONFIRMATION KONTROLÜ --------
    if user_id in PENDING_CONFIRMATIONS:
        expected_device: str = PENDING_CONFIRMATIONS[user_id]
        positive_answers: list[str] = [
            "evet",
            "aynen",
            "he",
            "hıhı",
            "onayla",
            "yes",
            "doğru",
            "tabi"
        ]

        # Olumlu cevap gelirse cihaz bilgisini döndür
        if any(ans in message for ans in positive_answers):
            del PENDING_CONFIRMATIONS[user_id]
            confirmation_response = _get_confirmation_response(
                expected_device,
                PENDING_CONFIRMATIONS
            )
            if confirmation_response:
                return confirmation_response
        else:
            # Olumsuz cevap: hafızayı sil, normal akışa devam et
            del PENDING_CONFIRMATIONS[user_id]

    # -------- ADIM 2: INTENT CLASSIFICATION --------
    intent: Optional[dict] = classify_intent(request.message)

    if intent:
        logger.info(f"✅ Intent Bulundu: {intent['intent_name']}")

        # -------- ADIM 3: INTENT-SPECIFIC HANDLERS --------
        intent_name: str = intent["intent_name"]

        if intent_name == "akademik_takvim":
            return _handle_academic_calendar(intent, request.message)

        elif intent_name == "cihaz_bilgisi":
            return _handle_device_query(request.message, user_id)

        else:
            # Selamlasma, yemek listesi vb.
            return _handle_generic_intent(intent)

    # -------- ADIM 4: LLM FALLBACK --------
    else:
        return await _fallback_to_llm(request.message)


@router.post("/update-data")
async def trigger_data_update() -> dict:
    """
    Manuel veri güncelleme trigger'ı.

    Takvim, yemek listesi ve cihaz verilerini anında güncelle.

    Returns:
        dict: Güncelleme işleminin sonucu
    """
    logger.info("🔄 Manuel veri güncelleme başlatıldı...")
    result: dict = update_system_data()
    return result