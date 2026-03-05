# ============================================================================
# backend/app/schemas/chat.py - Pydantic Data Models
# ============================================================================

from pydantic import BaseModel, Field
from typing import Optional, List


class ChatRequest(BaseModel):
    """
    POST /api/chat endpoint'ine gelen request body modeli.

    Fields:
        message    : Kullanıcı mesajı
        session_id : Opsiyonel session identifier (cihaz onay akışı için)
        history    : Son konuşma geçmişi — LLM'e bağlam sağlar
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

    history: list[dict] = Field(
        default_factory=list,
        title="Konuşma Geçmişi",
        description='Son mesajlar [{role: "user"|"bot", text: "..."}] — max 20 öğe',
    )

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Bugün yemek nedir?",
                "session_id": "session_abc123",
                "history": [
                    {"role": "user", "text": "Merhaba"},
                    {"role": "bot", "text": "Merhaba! Size nasıl yardımcı olabilirim?"}
                ]
            }
        }


class ChatOption(BaseModel):
    """
    Kullanıcıya sunulacak opsiyonel seçimler (ör. butonlar / quick reply).
    """

    id: str = Field(
        ...,
        title="Seçenek ID",
        description="Frontend tarafından seçimi tanımlamak için kullanılan içsel id",
        example="device_search_by_name",
    )
    label: str = Field(
        ...,
        title="Görünen Etiket",
        description="Kullanıcıya gösterilecek metin",
        example="Cihaz adına göre",
    )


class ChatResponse(BaseModel):
    """
    POST /api/chat endpoint'ından dönen response body modeli.
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

    options: Optional[List[ChatOption]] = Field(
        default=None,
        title="Seçilebilir Seçenekler",
        description="Kullanıcıya sunulan (varsa) buton/seçim listesi",
    )

    class Config:
        json_schema_extra = {
            "example": {
                "response": "Merhaba! AÇÜ Asistan'a hoş geldin.",
                "source": "Hızlı Yol",
                "intent_name": "selamlasma",
                "options": [
                    {
                        "id": "device_search_by_name",
                        "label": "Cihaz adına göre",
                    }
                ],
            }
        }
