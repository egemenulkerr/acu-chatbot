from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .classifier import IntentClassifier
from .gemini_client import GeminiClient
from .llm_handler import LLMHandler
from .settings import get_settings

BASE_DIR = Path(__file__).resolve().parent
INTENT_PATH = BASE_DIR / "data" / "intents.json"

app = FastAPI(
    title="Chatbot-UNI Backend",
    version="0.1.0",
    description="Basit intent sınıflandırma ile çalışan örnek FastAPI servisi.",
)

settings = get_settings()

# CORS yapılandırması
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
]

# Environment variable'dan ek origin'ler ekle
if settings.allowed_origins:
    allowed_origins.extend(settings.allowed_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_classifier = IntentClassifier(INTENT_PATH)

gemini_client = None
if settings.google_api_key:
    try:
        gemini_client = GeminiClient(
            api_key=settings.google_api_key,
            model_name=settings.gemini_model,
        )
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning("Gemini istemcisi başlatılamadı: %s", exc)

_llm_handler = LLMHandler(_classifier, gemini_client=gemini_client)


class ChatRequest(BaseModel):
    message: str = Field(..., description="Kullanıcının gönderdiği metin")


class ChatResponse(BaseModel):
    response: str
    intent: Optional[str]
    confidence: float


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}


@app.get("/config")
async def get_config() -> dict:
    """Frontend için backend URL'i döndürür."""
    return {
        "backend_url": settings.backend_url or "http://localhost:8000",
    }


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest) -> ChatResponse:
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Mesaj boş olamaz.")

    result = _llm_handler.generate_reply(request.message)
    return ChatResponse(
        response=result.response,
        intent=result.intent,
        confidence=round(result.confidence, 3),
    )
