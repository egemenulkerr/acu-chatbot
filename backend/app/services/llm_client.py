# ============================================================================
# backend/app/services/llm_client.py - Google Gemini API Client
# ============================================================================
# Açıklama:
#   Google Generative AI (Gemini) API'sini kullanarak sohbet cevapları
#   oluşturur. Intent sınıflandırması başarısız olduğunda fallback olarak
#   çalışır. Model seçimi dinamik ve API key tabanlıdır.
#
#   Supported Models:
#     - gemini-1.5-flash (hızlı, düşük cost)
#     - gemini-1.5-pro (daha güçlü)
#     - gemini-2.0-flash (en yeni)
# ============================================================================

import os
from typing import Optional
from dotenv import load_dotenv
import logging

import google.generativeai as genai


# ============================================================================
# LOGGING & CONFIGURATION
# ============================================================================

logger: logging.Logger = logging.getLogger(__name__)

# Environment variables'dan API key'i yükle
load_dotenv()
GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")

# Sistem prompt (bot kimliği)
SYSTEM_PROMPT: str = """
Sen Artvin Çoruh Üniversitesi (AÇÜ) asistanısın.
Kullanıcıların akademik, idari ve kampüs-ilgili sorularına cevap verirsin.
Samimi, yardımsever ve kısa cevaplar ver.
Eğer sorunun konu dışı ise nazikçe konuya döndürmeye çalış.
"""


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _validate_api_key() -> bool:
    """
    API key'in mevcut ve geçerli olup olmadığını kontrol et.

    Returns:
        bool: API key mevcutsa True, yoksa False
    """
    if not GOOGLE_API_KEY:
        logger.error("❌ GOOGLE_API_KEY environment variable'ı eksik!")
        return False
    return True


def _find_available_model() -> Optional[str]:
    """
    Gemini API'den mevcut olan ve generateContent destekleyen modeli bul.

    Preference Order:
      1. gemini-*-flash (hızlı, düşük maliyet)
      2. gemini-*-pro (daha güçlü)
      3. Herhangi bir gemini modeli

    Returns:
        str | None: Model adı veya None (model bulunamadı)

    Error Handling:
      - API hatası olursa: varsayılan model (gemini-1.5-flash) döndür
    """
    try:
        logger.info("🔍 Mevcut Gemini modelleri aranıyor...")

        # API'den modelleri listele
        available_models: list = list(genai.list_models())

        # generateContent destekleyen gemini modellerini filtrele
        gemini_models: list = [
            m for m in available_models
            if 'generateContent' in m.supported_generation_methods
            and 'gemini' in m.name
        ]

        if not gemini_models:
            logger.warning("⚠️  Mevcut Gemini modeli bulunamadı!")
            return None

        # Flash modelini tercih et (daha hızlı ve daha ucuz)
        for model in gemini_models:
            if 'flash' in model.name:
                logger.info(f"✅ Seçilen model: {model.name}")
                return model.name

        # Flash yoksa pro'yu dene
        for model in gemini_models:
            if 'pro' in model.name:
                logger.info(f"✅ Seçilen model: {model.name}")
                return model.name

        # Yoksa herhangi bir Gemini modeli seç
        logger.info(f"✅ Seçilen model: {gemini_models[0].name}")
        return gemini_models[0].name

    except Exception as e:
        logger.error(f"❌ Model listeleme hatası: {e}")
        logger.info("⚠️  Varsayılan model (gemini-1.5-flash) kullanılıyor...")
        return "models/gemini-1.5-flash"


# ============================================================================
# MAIN LLM FUNCTION
# ============================================================================

def get_llm_response(user_message: str) -> str:
    """
    Kullanıcı mesajını Google Gemini'ye gönder ve cevap al.

    Process:
      1. API key kontrol et
      2. Gemini API'yi ayarla
      3. Uygun modeli bul
      4. Sistemsel talimatları (system prompt) ekle
      5. Cevap oluştur

    Args:
        user_message (str): Kullanıcı tarafından yazılan mesaj

    Returns:
        str: Gemini tarafından üretilen cevap veya error message

    Error Handling:
      - API key eksik → Error message döndür
      - Model bulunamadı → Error message döndür
      - API call hatası → Error message döndür
    """
    # -------- ADIM 1: API KEY KONTROL --------
    if not _validate_api_key():
        return (
            "⚙️  Sistem yapılandırma hatası: API anahtarı eksik. "
            "Lütfen yöneticiye başvurun."
        )

    try:
        # -------- ADIM 2: API AYARLA --------
        genai.configure(api_key=GOOGLE_API_KEY)

        # -------- ADIM 3: MODELI BUL --------
        target_model_name: Optional[str] = _find_available_model()

        if not target_model_name:
            logger.error("❌ Uygun Gemini modeli bulunamadı.")
            return (
                "Maalesef şu anda AI servisine erişilemiyor. "
                "Lütfen daha sonra tekrar deneyin."
            )

        logger.info(f"📊 Kullanılan Model: {target_model_name}")

        # -------- ADIM 4: MODELİ BAŞLAT --------
        model: any = genai.GenerativeModel(target_model_name)

        # -------- ADIM 5: CEVAP OLUŞTUR --------
        full_prompt: str = (
            f"{SYSTEM_PROMPT}\n\n"
            f"Kullanıcı: {user_message}\n"
            f"Asistan:"
        )

        response: any = model.generate_content(full_prompt)
        response_text: str = response.text.strip()

        logger.info(f"✅ LLM cevabı oluşturuldu ({len(response_text)} karakter)")
        return response_text

    except Exception as e:
        logger.error(f"❌ LLM Hatası: {str(e)}")
        return (
            f"Üzgünüm, şu anda AI servisine bağlanamıyorum. "
            f"Hata: {str(e)[:50]}..."
        )