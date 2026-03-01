# ============================================================================
# backend/app/core/nlp.py - Türkçe Doğal Dil İşleme
# ============================================================================
# Açıklama:
#   Zemberek kütüphanesi kullanarak Türkçe morfolojik analiz yapılır.
#   Kelimelerin köklerini (stem) bularak intent sınıflandırmasında kullanılır.
#
#   Zemberek: Java-based Turkish NLP library
#   Singleton Pattern: JVM'in tek kez başlaması için
# ============================================================================

import string
import logging
from typing import Optional

logger: logging.Logger = logging.getLogger(__name__)

# Lazy import — zemberek Python 3.12+ ile uyumsuz olabilir (antlr4-python3-runtime 4.8)
try:
    from zemberek import TurkishMorphology
    ZEMBEREK_AVAILABLE = True
except Exception as _zemberek_err:
    logger.warning(f"⚠️  Zemberek yüklenemedi, basit tokenization kullanılacak: {_zemberek_err}")
    TurkishMorphology = None
    ZEMBEREK_AVAILABLE = False


# ============================================================================
# GLOBAL STATE - SINGLETON PATTERN
# ============================================================================

MORPHOLOGY: Optional[any] = None


# ============================================================================
# MORPHOLOGY INITIALIZATION
# ============================================================================

def get_morphology() -> Optional[any]:
    """
    Zemberek TurkishMorphology'yi singleton pattern ile yükle.
    Zemberek mevcut değilse None döndürür (fallback aktif olur).
    """
    global MORPHOLOGY

    if not ZEMBEREK_AVAILABLE:
        return None

    if MORPHOLOGY is not None:
        return MORPHOLOGY

    try:
        logger.info("⚙️  Zemberek TurkishMorphology yükleniyor...")
        MORPHOLOGY = TurkishMorphology.create_with_defaults()
        logger.info("✅ Zemberek başarıyla yüklendi.")
        return MORPHOLOGY

    except Exception as e:
        logger.warning(f"⚠️  Zemberek yüklenemedi, fallback kullanılıyor: {e}")
        return None


# ============================================================================
# TEXT PREPROCESSING
# ============================================================================

def _normalize_text(text: str) -> str:
    """
    Ham metni normalize et.

    İşlemler:
      1. Küçük harfe çevir
      2. Noktalama işaretlerini kaldır
      3. Fazla boşlukları temizle

    Args:
        text (str): Orijinal metin

    Returns:
        str: Normalize edilmiş metin
    """
    # Küçük harfe çevir
    normalized: str = text.lower()

    # Noktalama işaretlerini kaldır
    translation_table: dict = str.maketrans('', '', string.punctuation)
    normalized = normalized.translate(translation_table)

    # Fazla boşlukları temizle
    normalized = ' '.join(normalized.split())

    return normalized


def _tokenize_text(text: str) -> list[str]:
    """
    Metni kelimelere böl (tokenization).

    Args:
        text (str): Normalize edilmiş metin

    Returns:
        list[str]: Kelimeler listesi
    """
    return text.split()


def _analyze_word(word: str, morphology: any) -> str:
    """
    Tek bir kelimeyi Zemberek ile analiz et ve kökünü (stem) döndür.

    İşlemler:
      1. Kelimeyi morfolojik olarak analiz et
      2. En olası analiz sonucunu al (index 0)
      3. Kökü (stem) çıkar
      4. Hata durumunda: Kelimeyi olduğu gibi döndür

    Args:
        word (str): Analiz edilecek kelime
        morphology (TurkishMorphology): Zemberek morfoloji nesnesi

    Returns:
        str: Kelime stem'i veya orijinal kelime
    """
    try:
        # Kelimeyi analiz et
        analysis_results: any = morphology.analyze(word)

        # Analiz başarılı mı?
        if analysis_results and analysis_results.analysis_results:
            # En olası sonucu al (başında sıralanmış)
            best_analysis: any = analysis_results.analysis_results[0]

            # Stem'i çıkar
            stem: str = str(best_analysis.get_stem())
            return stem
        else:
            # Tanınamayan kelime: olduğu gibi döndür
            logger.debug(f"Zemberek '{word}' kelimesini tanımadı")
            return word

    except Exception as e:
        logger.warning(f"⚠️  Kelime analizi hatası ('{word}'): {e}")
        return word


# ============================================================================
# MAIN PREPROCESSING FUNCTION
# ============================================================================

def preprocess_text(text: str) -> list[str]:
    """
    Ham Türkçe metni işle ve kelimelerin stem'lerini döndür.

    Pipeline:
      1. Metni normalize et (lowercase, noktalama kaldır)
      2. Kelimelere böl (tokenize)
      3. Zemberek ile her kelimeyi analiz et
      4. Stem'leri listede topla

    Örnek:
      Input:  "Merhaba nasılsın? İyi misin?"
      Output: ["merhaba", "nasıl", "iyi", "mi"]  (yaklaşık)

    Args:
        text (str): İşlenecek Türkçe metin

    Returns:
        list[str]: Kelimelerin stem'leri

    Error Handling:
      - Zemberek hatası: Basit kelime ayırması fallback olarak kullanılır
      - Kelime analizi hatası: Kelime olduğu gibi döndürülür
    """
    # -------- ADIM 1: NORMALIZE ET --------
    normalized_text: str = _normalize_text(text)

    # -------- ADIM 2: TOKENIZE ET --------
    words: list[str] = _tokenize_text(normalized_text)

    # -------- ADIM 3: MORFOLOJI ANALIZ --------
    stems: list[str] = []

    try:
        morphology: TurkishMorphology = get_morphology()

        # Her kelimeyi analiz et
        for word in words:
            if word:  # Boş kelimeler skip et
                stem: str = _analyze_word(word, morphology)
                stems.append(stem)

    except Exception as e:
        logger.warning(
            f"⚠️  Zemberek hatası, basit kelime ayırması yapılıyor: {e}"
        )
        # Fallback: Normalize metindeki kelimeler
        stems = words

    logger.debug(f"Preprocess: '{text}' -> {stems}")
    return stems