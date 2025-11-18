# app/core/nlp.py

import string
import logging
from zemberek import (
    TurkishSpellChecker,
    TurkishMorphology,
    TurkishSentenceNormalizer
)

# --- Zemberek Başlatma ---
MORPHOLOGY = None

def get_morphology():
    """
    Zemberek TurkishMorphology sınıfını bir kez yükler (Singleton pattern).
    JVM'in tekrar tekrar başlamasını engeller.
    """
    global MORPHOLOGY
    if MORPHOLOGY is None:
        try:
            logging.info("Zemberek Kütüphanesi (Morphology) yükleniyor...")
            MORPHOLOGY = TurkishMorphology.create_with_defaults()
            logging.info("Zemberek Kütüphanesi başarıyla yüklendi.")
        except Exception as e:
            logging.error(f"Zemberek yüklenirken KRİTİK HATA: {e}")
            raise
    return MORPHOLOGY

# --- Metin Ön İşleme Fonksiyonu ---

def preprocess_text(text: str) -> list[str]:
    """
    Kullanıcıdan gelen ham metni alır, Zemberek ile işler ve kök (stem) listesi döndürür.
    """
    
    # 1. Metni normalize et (küçük harf)
    normalized_text = text.lower()
    
    # 2. Noktalama işaretlerini kaldır
    normalized_text = normalized_text.translate(str.maketrans('', '', string.punctuation))
    
    # 3. Zemberek Morfoloji modülünü yükle/getir
    try:
        morphology = get_morphology()
    except Exception as e:
        logging.warning("Zemberek çalışmadığı için basit ayırma yapılıyor.")
        return normalized_text.split()

    # 4. Metni analiz et ve kökleri (stems) çıkar
    stems = []
    analysis = morphology.analyze(normalized_text)
    
    for word_analysis in analysis:
        best_analysis = word_analysis.best
        stem = best_analysis.get_stem()
        
        if stem:
            stems.append(stem)
            
    if not stems:
        return normalized_text.split()
        
    return stems