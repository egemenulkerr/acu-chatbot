import google.generativeai as genai
import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 1. Ortam değişkenlerini yükle
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

def get_llm_response(user_message: str):
    """
    Kullanıcının mesajını Google Gemini modeline gönderir.
    Model ismini tahmin etmek yerine, API'den mevcut modelleri sorar ve çalışanı seçer.
    """
    try:
        if not GOOGLE_API_KEY:
            logger.error("GOOGLE_API_KEY eksik!")
            return "Sistem yapılandırma hatası: API anahtarı eksik."

        # 2. API'yi Ayarla
        genai.configure(api_key=GOOGLE_API_KEY)

        # 3. AKILLI MODEL SEÇİMİ
        # Mevcut modelleri listele ve 'generateContent' destekleyen ilkini bul
        target_model_name = None
        
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    # Tercihen 'flash' veya 'pro' modellerini ara
                    if 'gemini' in m.name:
                        target_model_name = m.name
                        # Eğer flash bulursan onu öncelikli seç (daha hızlı)
                        if 'flash' in m.name:
                            break
            
            if not target_model_name:
                logger.error("Hiçbir uygun Gemini modeli bulunamadı.")
                return "API anahtarınızla erişilebilen uygun bir yapay zeka modeli bulunamadı."
                
        except Exception as list_err:
            logger.error(f"Model listeleme hatası: {list_err}")
            # Listeleme başarısız olursa varsayılanı dene
            target_model_name = 'models/gemini-1.5-flash'

        logger.info(f"Seçilen Model: {target_model_name}")

        # 4. Modeli Başlat
        model = genai.GenerativeModel(target_model_name)

        # 5. Bot Kimliği
        system_instruction = """
        Sen Artvin Çoruh Üniversitesi (AÇÜ) asistanısın.
        Samimi, yardımsever ve kısa cevaplar ver.
        """

        full_prompt = f"{system_instruction}\n\nKullanıcı: {user_message}\nAsistan:"
        
        response = model.generate_content(full_prompt)
        return response.text.strip()

    except Exception as e:
        logger.error(f"LLM Hatası: {e}")
        return f"Üzgünüm, şu an yapay zeka servisine bağlanamıyorum. (Hata: {str(e)})"