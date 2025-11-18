# app/core/classifier.py

import json
from .nlp import preprocess_text # Zemberek'i çağıran fonksiyonu nlp.py'den al

# Bu veriyi main.py'de uygulama başlarken yükleyeceğiz
INTENTS_DATA = {}
CLASSIFICATION_THRESHOLD = 15

def load_intent_data():
    """Uygulama başlarken intents.json dosyasını hafızaya yükler."""
    global INTENTS_DATA, CLASSIFICATION_THRESHOLD
    try:
        # ÖNEMLİ: Dockerfile'daki WORKDIR /app olduğu için yolu düzeltiyoruz
        with open("app/data/intents.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            INTENTS_DATA = data["intents"]
            CLASSIFICATION_THRESHOLD = data["classification_threshold"]
            print("Niyet verisi başarıyla yüklendi.") # Terminalde bu mesajı görmeliyiz
    except Exception as e:
        print(f"HATA: Niyet verisi yüklenemedi: {e}")
        # Hata durumunda uygulama çökmesin diye boş veri atayalım
        INTENTS_DATA = []
        CLASSIFICATION_THRESHOLD = 999 

def classify_intent(user_message: str):
    """
    Ana sınıflandırma fonksiyonu.
    1. Metni Zemberek ile işler.
    2. Puanlama yapar.
    3. Eşiği kontrol eder ve Hızlı Yol veya Akıllı Yol'a karar verir.
    """
    
    # Adım 1: Zemberek NLP Modülü
    stems = preprocess_text(user_message) # ['final', 'tarih', 'ne', 'zaman']
    
    intent_scores = {}
    
    # Adım 2: Puanlama
    for intent in INTENTS_DATA:
        score = 0
        for stem in stems:
            if stem in intent["keywords"]:
                score += intent["keywords"][stem]
        intent_scores[intent["intent_name"]] = score

    # Adım 3: En yüksek puanlı niyeti bul
    if not intent_scores or not INTENTS_DATA:
        return None # LLM'e yönlendir

    best_intent_name = max(intent_scores, key=intent_scores.get)
    best_score = intent_scores[best_intent_name]

    # Adım 4: Karar Mekanizması (Eşik Kontrolü)
    if best_score >= CLASSIFICATION_THRESHOLD:
        # Hızlı Yol
        # Eşleşen niyetin detaylarını bul
        for intent in INTENTS_DATA:
            if intent["intent_name"] == best_intent_name:
                return intent # Niyetin tamamını döndür (response_content vb. içerir)
    else:
        # Akıllı Yol (LLM)
        return None