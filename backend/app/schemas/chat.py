# ============================================================================
# backend/app/schemas/chat.py - Pydantic Data Models
# ============================================================================
# Açıklama:
#   Chat API'nin request/response şemalarını tanımlar. Pydantic ile
#   type validation ve automatic documentation sağlar.
# ============================================================================

from pydantic import BaseModel, Field
from typing import Optional


# ============================================================================
# REQUEST SCHEMA
# ============================================================================

class ChatRequest(BaseModel):
    """
    POST /api/chat endpoint'ine gelen request body modeli.

    Fields:
        message (str): Kullanıcı tarafından yazılan metin mesajı
        session_id (str | None): Opsiyonel session identifier
                                  (conversation history için)

    Example:
        {
            "message": "Merhaba, nasıl yardımcı olabilirsin?",
            "session_id": "user-123"
        }
    """

    message: str = Field(
        ...,
        title="Kullanıcı Mesajı",
        description="Chatbot'a gönderilecek metin",
        min_length=1,
        max_length=1000
    )

    session_id: Optional[str] = Field(
        None,
        title="Session ID",
        description="Kullanıcı session'ı takip etmek için",
        max_length=100
    )

    class Config:
        """Pydantic configuration"""
        schema_extra = {
            "example": {
                "message": "Bugün yemek nedir?",
                "session_id": "user-456"
            }
        }


# ============================================================================
# RESPONSE SCHEMA
# ============================================================================

class ChatResponse(BaseModel):
    """
    POST /api/chat endpoint'ından dönen response body modeli.

    Fields:
        response (str): Chatbot'un cevap metni
        source (str): Cevabın kaynağı (debug/analytics için)
                      Değerleri: "Hızlı Yol", "Gemini AI", "Cihaz Katalogu" vb.
        intent_name (str | None): Sınıflandırılan intent adı (opsiyonel)

    Example:
        {
            "response": "Bugün pasta ve salata var. Afiyet olsun!",
            "source": "Hızlı Yol",
            "intent_name": "yemek_listesi"
        }
    """

    response: str = Field(
        ...,
        title="Chatbot Cevabı",
        description="Chatbot tarafından üretilen cevap metni",
        min_length=1
    )

    source: str = Field(
        ...,
        title="Cevap Kaynağı",
        description="Cevabın hangi sistemden üretildiği",
        example="Hızlı Yol"
    )

    intent_name: Optional[str] = Field(
        None,
        title="Intent Adı",
        description="Sınıflandırılan intent'in adı",
        example="yemek_listesi"
    )

    class Config:
        """Pydantic configuration"""
        schema_extra = {
            "example": {
                "response": "Merhaba! AÇÜ Asistan'a hoş geldin. 😊",
                "source": "Hızlı Yol",
                "intent_name": "selamlasma"
            }
        }