# app/core/classifier.py

import json
import logging
import os
from .nlp import preprocess_text  # Zemberek modülümüz

# Loglama
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global Değişkenler
MODEL = None
INTENTS_DATA = []
INTENT_EMBEDDINGS = {}
USE_EMBEDDINGS = os.getenv("USE_EMBEDDINGS", "false").lower() == "true"  # Default: disabled

# Eşik Değerleri (Varsayılanlar)
KEYWORD_THRESHOLD = 8       # Adım 1 Eşiği (Puan)
SIMILARITY_THRESHOLD = 0.65 # Adım 2 Eşiği (Yüzde)

def load_model():
    """Yapay zeka modelini yükler (opsiyonel)."""
    global MODEL
    if not USE_EMBEDDINGS:
        logger.info("Embeddings devre dışı (USE_EMBEDDINGS=false)")
        return
    
    try:
        from sentence_transformers import SentenceTransformer
        logger.info("Adım 2 için Yapay Zeka Modeli yükleniyor...")
        MODEL = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        logger.info("Model yüklendi.")
    except Exception as e:
        logger.error(f"Model hatası: {e}")
        logger.warning("Embeddings devreden çıkartıldı - keyword matching kullanılacak")

def load_intent_data():
    """Verileri hem puanlama hem de vektör için hazırlar."""
    global INTENTS_DATA, KEYWORD_THRESHOLD, SIMILARITY_THRESHOLD, INTENT_EMBEDDINGS
    
    if USE_EMBEDDINGS and MODEL is None:
        load_model()

    try:
        with open("app/data/intents.json", "r", encoding="utf-8") as f:
            data = json.load(f)
            INTENTS_DATA = data["intents"]
            
            # Ayarları al
            KEYWORD_THRESHOLD = data.get("keyword_threshold", 8)
            SIMILARITY_THRESHOLD = data.get("similarity_threshold", 0.65)
            
            # Adım 2 için vektörleri hazırla (opsiyonel)
            if USE_EMBEDDINGS:
                for intent in INTENTS_DATA:
                    examples = intent.get("examples", [])
                    if examples and MODEL:
                        embeddings = MODEL.encode(examples)
                        INTENT_EMBEDDINGS[intent["intent_name"]] = embeddings
            
            logger.info("Tüm niyet verileri (Keywords) başarıyla yüklendi.")
            
    except Exception as e:
        logger.error(f"Veri yükleme hatası: {e}")
        INTENTS_DATA = []

def classify_intent(user_message: str):
    """
    KADEMELİ SINIFLANDIRMA MANTIĞI
    1. Adım: Kelime Puanlama (Keyword Scoring)
    2. Adım: Anlamsal Arama (Semantic Search) - opsiyonel
    3. Adım: Başarısızsa None dön (LLM'e git)
    """
    
    # --- 1. ADIM: AĞIRLIKLANDIRILMIŞ ANAHTAR KELİME (ZEMBEREK) ---
    stems = preprocess_text(user_message) # Kökleri bul
    best_keyword_score = 0
    best_keyword_intent = None
    
    for intent in INTENTS_DATA:
        score = 0
        keywords = intent.get("keywords", {})
        for stem in stems:
            if stem in keywords:
                score += keywords[stem]
        
        if score > best_keyword_score:
            best_keyword_score = score
            best_keyword_intent = intent

    print(f"### DEBUG Adım 1 (Keyword): En iyi '{best_keyword_intent['intent_name'] if best_keyword_intent else 'Yok'}' - Puan: {best_keyword_score}")

    # Eşik Kontrolü 1
    if best_keyword_score >= KEYWORD_THRESHOLD:
        print(">>> Adım 1 (Hızlı Yol) ile çözüldü.")
        return best_keyword_intent

    # Embeddings devre dışıysa LLM'e yönlendir
    if not USE_EMBEDDINGS:
        print(">>> Embeddings devre dışı. LLM'e yönlendiriliyor...")
        return None

    # --- 2. ADIM: ANLAMSAL EŞLEŞTİRME (EMBEDDING) ---
    # Eğer model yüklenemediyse veya veri yoksa pas geç
    if not MODEL or not INTENT_EMBEDDINGS:
        return None

    try:
        from sentence_transformers import util
        
        user_embedding = MODEL.encode(user_message) # Cümleyi vektöre çevir
        best_sim_score = -1
        best_sim_intent = None

        for intent in INTENTS_DATA:
            name = intent["intent_name"]
            if name in INTENT_EMBEDDINGS:
                intent_vectors = INTENT_EMBEDDINGS[name]
                # Benzerlik hesapla
                scores = util.cos_sim(user_embedding, intent_vectors)[0]
                max_score = float(scores.max())
                
                if max_score > best_sim_score:
                    best_sim_score = max_score
                    best_sim_intent = intent

        print(f"### DEBUG Adım 2 (Semantic): En iyi '{best_sim_intent['intent_name'] if best_sim_intent else 'Yok'}' - Skor: {best_sim_score:.4f}")

        # Eşik Kontrolü 2
        if best_sim_score >= SIMILARITY_THRESHOLD:
            print(">>> Adım 2 (Akıllı Yol) ile çözüldü.")
            return best_sim_intent
    except ImportError:
        logger.warning("Sentence-transformers not available, skipping semantic matching")
        return None
        
    
    # --- 3. ADIM: HİÇBİRİ TUTMADI ---
    print(">>> Hiçbir yerel eşleşme bulunamadı. LLM'e yönlendiriliyor...")
    return None