# backend/app/core/nlp.py

import string
import logging
from zemberek import (
    TurkishSpellChecker,
    TurkishMorphology,
    TurkishSentenceNormalizer
)

# --- Loglama Ayarları ---
logger = logging.getLogger(__name__)

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
            logger.info("Zemberek Kütüphanesi (Morphology) yükleniyor...")
            MORPHOLOGY = TurkishMorphology.create_with_defaults()
            logger.info("Zemberek Kütüphanesi başarıyla yüklendi.")
        except Exception as e:
            logger.error(f"Zemberek yüklenirken KRİTİK HATA: {e}")
            raise
    return MORPHOLOGY

# --- Metin Ön İşleme Fonksiyonu ---

def preprocess_text(text: str) -> list[str]:
    """
    Kullanıcıdan gelen ham metni alır, kelimelere böler, 
    Zemberek ile köklerini (stem) bulur ve liste döndürür.
    """
    
    # 1. Metni normalize et (küçük harf)
    # "Merhaba Nasılsın?" -> "merhaba nasılsın"
    normalized_text = text.lower()
    
    # 2. Noktalama işaretlerini kaldır
    # "merhaba, nasılsın?" -> "merhaba nasılsın"
    normalized_text = normalized_text.translate(str.maketrans('', '', string.punctuation))
    
    # 3. Cümleyi kelimelere ayır (Tokenization)
    words = normalized_text.split()
    
    stems = []
    
    # 4. Zemberek Yükle
    try:
        morphology = get_morphology()
    except Exception as e:
        logger.warning(f"Zemberek hatası, basit ayırma yapılıyor: {e}")
        return words

    # 5. Her kelimeyi tek tek analiz et
    for word in words:
        try:
            # Kelimeyi analiz et
            results = morphology.analyze(word)
            
            # Analiz sonucunda bir şeyler bulabildi mi?
            if results and results.analysis_results:
                # Zemberek sonuçları olasılığa göre sıralar. 
                # İlk sonuç (index 0) en olası olandır ("Best").
                best_result = results.analysis_results[0]
                
                # Kökü al (get_stem Java metodudur)
                stem = str(best_result.get_stem())
                stems.append(stem)
            else:
                # Zemberek tanıyamadıysa kelimeyi olduğu gibi ekle
                stems.append(word)
                
        except Exception as e:
            # Herhangi bir hata olursa kelimeyi olduğu gibi ekle
            logger.error(f"Kelime analizi hatası ({word}): {e}")
            stems.append(word)
            
    return stems