# ============================================================================
# backend/app/services/llm_client.py - Google Gemini API Client
# ============================================================================
# Açıklama:
#   Google Generative AI (Gemini) API'sini kullanarak sohbet cevapları
#   oluşturur. Model örneği module seviyesinde cache'lenir — her istekte
#   yeniden oluşturulmaz. Konuşma geçmişini destekler.
# ============================================================================

import os
import logging
from typing import Optional

from dotenv import load_dotenv
import google.generativeai as genai


# ============================================================================
# CONFIGURATION
# ============================================================================

logger: logging.Logger = logging.getLogger(__name__)

load_dotenv()
GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")

SYSTEM_PROMPT: str = """
Sen Artvin Çoruh Üniversitesi (AÇÜ) asistanısın.
Kullanıcıların akademik, idari ve kampüs-ilgili sorularına cevap verirsin.
Samimi, yardımsever ve kısa cevaplar ver.
Eğer sorunun konu dışı ise nazikçe konuya döndürmeye çalış.
"""

# Module-level singleton — model yalnızca bir kez başlatılır
_CACHED_MODEL: Optional[genai.GenerativeModel] = None


# ============================================================================
# MODEL INITIALIZATION (CACHED)
# ============================================================================

def _get_model() -> Optional[genai.GenerativeModel]:
    """
    Gemini model örneğini döndür. İlk çağrıda başlatır, sonrasında cache'den verir.
    """
    global _CACHED_MODEL

    if _CACHED_MODEL is not None:
        return _CACHED_MODEL

    if not GOOGLE_API_KEY:
        logger.error("❌ GOOGLE_API_KEY environment variable eksik!")
        return None

    try:
        genai.configure(api_key=GOOGLE_API_KEY)

        logger.info("🔍 Gemini modelleri aranıyor...")
        available_models = list(genai.list_models())

        gemini_models = [
            m for m in available_models
            if 'generateContent' in m.supported_generation_methods
            and 'gemini' in m.name
        ]

        model_name = "models/gemini-1.5-flash"

        for m in gemini_models:
            if 'flash' in m.name:
                model_name = m.name
                break
        else:
            for m in gemini_models:
                if 'pro' in m.name:
                    model_name = m.name
                    break
            else:
                if gemini_models:
                    model_name = gemini_models[0].name

        logger.info(f"✅ Gemini modeli seçildi ve cache'lendi: {model_name}")
        _CACHED_MODEL = genai.GenerativeModel(
            model_name,
            system_instruction=SYSTEM_PROMPT
        )
        return _CACHED_MODEL

    except Exception as e:
        logger.error(f"❌ Model başlatma hatası: {e}", exc_info=True)
        return None


# ============================================================================
# MAIN LLM FUNCTION
# ============================================================================

def stream_llm_response(user_message: str, history: list[dict] | None = None):
    """
    Gemini cevabını token token yield eden sync generator.
    asyncio.to_thread + asyncio.Queue ile async endpoint'lerden kullanılmalı.
    """
    model = _get_model()
    if not model:
        yield "⚙️ AI servisi başlatılamadı."
        return

    try:
        gemini_history = []
        if history:
            for msg in history[-10:]:
                role = "user" if msg.get("role") == "user" else "model"
                text = msg.get("text", "").strip()
                if text:
                    gemini_history.append({"role": role, "parts": [text]})

        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(user_message, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        logger.error(f"❌ Streaming LLM Hatası: {e}", exc_info=True)
        yield "Üzgünüm, şu anda AI servisine bağlanamıyorum."


def get_llm_response(user_message: str, history: list[dict] | None = None) -> str:
    """
    Kullanıcı mesajını Gemini'ye gönder ve cevap al.

    Bu fonksiyon sync'tir — async endpoint'lerden asyncio.to_thread ile çağrılmalı.

    Args:
        user_message : Kullanıcının son mesajı
        history      : [{role: "user"|"bot", text: "..."}] formatında geçmiş

    Returns:
        str: Gemini'nin yanıtı veya hata mesajı
    """
    model = _get_model()

    if not model:
        return "⚙️ Sistem yapılandırma hatası: AI servisi başlatılamadı. Lütfen yöneticiye başvurun."

    try:
        # Geçmişi Gemini'nin beklediği formata dönüştür
        gemini_history = []
        if history:
            for msg in history[-10:]:  # Son 5 tur (10 mesaj)
                role = "user" if msg.get("role") == "user" else "model"
                text = msg.get("text", "").strip()
                if text:
                    gemini_history.append({"role": role, "parts": [text]})

        chat = model.start_chat(history=gemini_history)
        response = chat.send_message(user_message)
        response_text = response.text.strip()

        logger.info(f"✅ LLM yanıtı oluşturuldu ({len(response_text)} karakter)")
        return response_text

    except Exception as e:
        logger.error(f"❌ LLM Hatası: {e}", exc_info=True)
        return "Üzgünüm, şu anda AI servisine bağlanamıyorum. Lütfen daha sonra tekrar deneyin."
