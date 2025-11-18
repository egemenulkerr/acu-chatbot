# app/api/endpoints/chat.py

from fastapi import APIRouter, HTTPException
# '...' importları 'app/api/endpoints' klasöründen 'app' kök dizinine çıkıp
# 'schemas' ve 'core' klasörlerine inmeyi sağlar.
from ...schemas.chat import ChatRequest, ChatResponse
from ...core.classifier import classify_intent
# from ...services.llm_client import get_llm_response # Gelecekte eklenecek

# Hatanın çözümü: 'router' değişkenini burada tanımlıyoruz
router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def handle_chat_message(request: ChatRequest):
    
    # Niyet Sınıflandırıcı'yı çağır
    intent = classify_intent(request.message)
    
    if intent:
        # HIZLI YOL BAŞARILI
        
        # TODO: Eğer intent.response_type == "DATA_LOOKUP" ise
        # web_scraper'dan (services/web_scraper.py) veriyi çek.
        # Şimdilik direkt content'i dönüyoruz.
        
        return ChatResponse(
            response=intent["response_content"],
            source="Hızlı Yol",
            intent_name=intent["intent_name"]
        )
    else:
        # AKILLI YOL (LLM) GEREKLİ
        
        # llm_response = await get_llm_response(request.message) # Gelecekte
        
        # Şimdilik geçici bir cevap dönüyoruz
        return ChatResponse(
            response="Bu karmaşık bir soru. Henüz LLM modülüm (Akıllı Yol) aktif değil.",
            source="LLM Yönlendirici",
            intent_name=None
        )