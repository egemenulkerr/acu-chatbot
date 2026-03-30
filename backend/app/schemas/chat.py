# ============================================================================
# backend/app/schemas/chat.py - Pydantic Data Models
# ============================================================================

import re

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List

_SESSION_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")
_VALID_ROLES = {"user", "bot", "model"}
_MAX_HISTORY_ITEMS = 20
_MAX_HISTORY_TEXT_LEN = 2000


class HistoryItem(BaseModel):
    role: str = Field(..., pattern=r"^(user|bot|model)$")
    text: str = Field(..., max_length=_MAX_HISTORY_TEXT_LEN)


class ChatRequest(BaseModel):
    """
    POST /api/chat endpoint'ine gelen request body modeli.
    """

    message: str = Field(
        ...,
        title="Kullanıcı Mesajı",
        description="Chatbot'a gönderilecek metin",
        min_length=1,
        max_length=1000,
    )

    session_id: Optional[str] = Field(
        None,
        title="Session ID",
        description="Kullanıcı session'ı takip etmek için",
        max_length=64,
    )

    history: List[HistoryItem] = Field(
        default_factory=list,
        title="Konuşma Geçmişi",
        description="Son mesajlar — max 20 öğe",
        max_length=_MAX_HISTORY_ITEMS,
    )

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not _SESSION_RE.match(v):
            raise ValueError("session_id yalnızca harf, rakam, _ ve - içerebilir (max 64 karakter)")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Bugün yemek nedir?",
                "session_id": "session_abc123",
                "history": [
                    {"role": "user", "text": "Merhaba"},
                    {"role": "bot", "text": "Merhaba! Size nasıl yardımcı olabilirim?"}
                ],
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
