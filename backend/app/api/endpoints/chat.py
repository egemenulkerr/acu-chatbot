# backend/app/api/endpoints/chat.py

from fastapi import APIRouter
import re
import logging
import random

# Pydantic Modelleri
from ...schemas.chat import ChatRequest, ChatResponse

# Modüller
from ...core.classifier import classify_intent
from ...services.web_scraper.manager import update_system_data
from ...services.llm_client import get_llm_response

# Cihaz Registry Modülleri
from ...services.device_registry import search_device, suggest_device, get_device_info

# Logger
logger = logging.getLogger("uvicorn")

router = APIRouter()

# --- HAFIZA (Context) ---
# Kullanıcıya bir soru sorduğumuzda cevabını beklemek için buraya kaydediyoruz
PENDING_CONFIRMATIONS = {}

@router.post("/chat", response_model=ChatResponse)
async def handle_chat_message(request: ChatRequest):
    
    user_id = request.session_id or "default_user"
    message = request.message.lower().strip()
    
    logger.info(f"📨 Gelen Mesaj: {request.message}")

    # --- 1. HAFIZA KONTROLÜ (Cihaz önerisi onayı bekliyor muyuz?) ---
    if user_id in PENDING_CONFIRMATIONS:
        expected_device = PENDING_CONFIRMATIONS[user_id]
        positive_answers = ["evet", "aynen", "he", "hıhı", "onayla", "yes", "doğru", "tabi"]
        
        # Kullanıcı olumlu cevap verdiyse
        if any(ans in message for ans in positive_answers):
            del PENDING_CONFIRMATIONS[user_id] # Hafızadan sil
            
            device_data = get_device_info(expected_device)
            if device_data:
                info = device_data["info"]
                return ChatResponse(
                    response=f"✅ Anlaşıldı. İşte bilgiler:\n\n🔧 **{device_data['name']}**\n📝 {info['description']}\n💰 {info['price']}\n📦 {info['stock']}",
                    source="Cihaz Katalogu (Onaylı)",
                    intent_name="cihaz_bilgisi"
                )
        else:
            # Olumsuz cevap gelirse hafızayı silip normal akışa devam et
            del PENDING_CONFIRMATIONS[user_id]

    # --- 2. NİYET ANALİZİ (Normal Akış) ---
    intent = classify_intent(request.message)
    
    if intent:
        logger.info(f"✅ Yerel Niyet Bulundu: {intent['intent_name']}")
        
        # A. Akademik Takvim Mantığı
        if intent["intent_name"] == "akademik_takvim":
            year_match = re.search(r'(20\d{2})|(\d{2}-\d{2})', request.message)
            calendars = intent.get("extra_data", {})
            
            if year_match and calendars:
                user_year = year_match.group(0)
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

        # B. Cihaz Bilgisi Mantığı
        if intent["intent_name"] == "cihaz_bilgisi":
            # 1. Tam Eşleşme
            device_data = search_device(request.message)
            if device_data:
                info = device_data["info"]
                return ChatResponse(
                    response=f"🔧 **{device_data['name']}**\n📝 {info['description']}\n💰 {info['price']}\n📦 {info['stock']}",
                    source="Cihaz Katalogu",
                    intent_name="cihaz_bilgisi"
                )
            
            # 2. Öneri (Fuzzy Search)
            suggestion = suggest_device(request.message)
            if suggestion:
                PENDING_CONFIRMATIONS[user_id] = suggestion
                return ChatResponse(
                    response=f"🤔 Tam bulamadım ama şunu mu demek istediniz: **{suggestion.title()}**? (Evet/Hayır)",
                    source="Akıllı Öneri Sistemi",
                    intent_name="cihaz_bilgisi_onay"
                )

        # C. Diğer Niyetler (Yemek listesi vb.)
        raw_response = intent["response_content"]
        
        # Eğer cevap bir liste ise (Selamlaşma gibi), içinden rastgele birini seç
        if isinstance(raw_response, list):
            final_response = random.choice(raw_response)
        else:
            final_response = raw_response

        return ChatResponse(
            response=final_response, # Artık kesinlikle string
            source="Hızlı Yol",
            intent_name=intent["intent_name"]
        )
        
    
    else:
        # --- 3. LLM (Gemini) ---
        logger.warning(f"⚠️ Yerel eşleşme yok. LLM'e (Gemini) gidiliyor...")
        try:
            ai_response = get_llm_response(request.message)
            return ChatResponse(
                response=ai_response,
                source="Gemini AI (Akıllı Yol)",
                intent_name="genel_sohbet"
            )
        except Exception as e:
            logger.error(f"Hata: {str(e)}")
            return ChatResponse(
                response="Servis hatası.",
                source="Error",
                intent_name="error"
            )

@router.post("/update-data")
async def trigger_data_update():
    result = update_system_data()
    return result