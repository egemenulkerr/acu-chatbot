# app/schemas/chat.py

from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    """
    Kullanıcıdan /chat endpoint'ine gelecek JSON'un modeli.
    """
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    """
    Kullanıcıya /chat endpoint'inden dönecek JSON'un modeli.
    """
    response: str
    source: str  # "Hızlı Yol", "LLM Yönlendirici" vb.
    intent_name: Optional[str] = None