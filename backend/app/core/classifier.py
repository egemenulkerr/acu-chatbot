# ============================================================================
# backend/app/core/classifier.py - Intent Sınıflandırma Motoru
# ============================================================================
# Açıklama:
#   3-aşamalı intent sınıflandırma sistemi:
#     1. Keyword Matching (Zemberek morphology ile)
#     2. Semantic Search (Embeddings ile - opsiyonel)
#     3. LLM Fallback (başarısız olursa None dön)
#
#   Configuration: app/data/intents.json
#   Environment: USE_EMBEDDINGS (true/false), thresholds
# ============================================================================

import json
import logging
import os
from typing import Optional

from .nlp import preprocess_text


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


# ============================================================================
# GLOBAL STATE
# ============================================================================

# Semantic search modeli (lazy-loaded)
MODEL: Optional[any] = None

# Tüm intent'ler ve keyword'ler
INTENTS_DATA: list[dict] = []

# Her intent'in embedding vektörleri (opsiyonel)
INTENT_EMBEDDINGS: dict[str, any] = {}

# Configuration flags
USE_EMBEDDINGS: bool = (
    os.getenv("USE_EMBEDDINGS", "false").lower() == "true"
)

# Sınıflandırma eşikleri
KEYWORD_THRESHOLD: float = 8.0
SIMILARITY_THRESHOLD: float = 0.65


# ============================================================================
# MODEL LOADING
# ============================================================================

def load_model() -> None:
    """
    Semantic search modelini (sentence-transformers) opsiyonel olarak yükle.

    USE_EMBEDDINGS=true ise model yüklenir, aksi takdirde skip edilir.
    Model yükleme başarısız olursa warning log'lanır.
    """
    global MODEL

    if not USE_EMBEDDINGS:
        logger.info("Embeddings devre dışı (USE_EMBEDDINGS=false)")
        return

    try:
        from sentence_transformers import SentenceTransformer

        logger.info("📊 Semantic model yükleniyor...")
        MODEL = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        logger.info("✅ Semantic model yüklendi.")

    except ImportError as e:
        logger.error(f"❌ Sentence-transformers import hatası: {e}")
        logger.warning("Embeddings devreden çıkarıldı - keyword matching kullanılacak")

    except Exception as e:
        logger.error(f"❌ Model yükleme hatası: {e}")
        logger.warning("Embeddings devreden çıkarıldı - keyword matching kullanılacak")


# ============================================================================
# DATA LOADING
# ============================================================================

def load_intent_data() -> None:
    """
    Intent'ler ve configuration'ı intents.json'dan yükle.

    İşlemler:
      1. JSON dosyasını oku
      2. Threshold değerlerini ayarla
      3. Embeddings modeli gerekirse yükle
      4. Her intent için embedding vektörleri oluştur (opsiyonel)
    """
    global INTENTS_DATA, KEYWORD_THRESHOLD, SIMILARITY_THRESHOLD, INTENT_EMBEDDINGS

    if USE_EMBEDDINGS and MODEL is None:
        load_model()

    try:
        with open("app/data/intents.json", "r", encoding="utf-8") as f:
            data: dict = json.load(f)
            INTENTS_DATA = data.get("intents", [])

            # Configuration değerlerini al
            KEYWORD_THRESHOLD = data.get("keyword_threshold", 8.0)
            SIMILARITY_THRESHOLD = data.get("similarity_threshold", 0.65)

            logger.info(
                f"⚙️  Configuration: "
                f"keyword_threshold={KEYWORD_THRESHOLD}, "
                f"similarity_threshold={SIMILARITY_THRESHOLD}"
            )

            # Embedding vektörleri oluştur (opsiyonel)
            if USE_EMBEDDINGS and MODEL:
                logger.info("📊 Intent embedding'leri oluşturuluyor...")
                for intent in INTENTS_DATA:
                    intent_name: str = intent["intent_name"]
                    examples: list[str] = intent.get("examples", [])

                    if examples:
                        embeddings: any = MODEL.encode(examples)
                        INTENT_EMBEDDINGS[intent_name] = embeddings

                logger.info(
                    f"✅ {len(INTENT_EMBEDDINGS)} intent'in embedding'i oluşturuldu."
                )

            logger.info(f"✅ {len(INTENTS_DATA)} intent başarıyla yüklendi.")

    except FileNotFoundError:
        logger.error("❌ app/data/intents.json dosyası bulunamadı!")
        INTENTS_DATA = []

    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse hatası: {e}")
        INTENTS_DATA = []

    except Exception as e:
        logger.error(f"❌ Intent data yükleme hatası: {e}")
        INTENTS_DATA = []


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _calculate_keyword_score(
    message_stems: list[str],
    intent_keywords: dict[str, float]
) -> float:
    """
    Keyword puanlama: Her eşleşen keyword için weight ekle.

    Args:
        message_stems (list): Mesajın stem'leri
        intent_keywords (dict): Intent'in keyword-weight mapping'i

    Returns:
        float: Toplam puantaj
    """
    score: float = 0.0
    for stem in message_stems:
        if stem in intent_keywords:
            score += intent_keywords[stem]
    return score


def _classify_by_keywords(user_message: str) -> Optional[dict]:
    """
    ADIM 1: Keyword matching ile intent'i sınıflandır.

    Zemberek ile kelimelerin stem'ini bul, intent'lerin keyword'leri ile
    karşılaştır ve en yüksek puanı al.

    Args:
        user_message (str): Kullanıcı mesajı

    Returns:
        dict | None: Intent veya None
    """
    # Metni preprocess et (stem'leri bul)
    stems: list[str] = preprocess_text(user_message)

    best_score: float = 0.0
    best_intent: Optional[dict] = None

    # Her intent'i değerlendir
    for intent in INTENTS_DATA:
        keywords: dict = intent.get("keywords", {})
        score: float = _calculate_keyword_score(stems, keywords)

        if score > best_score:
            best_score = score
            best_intent = intent

    logger.debug(
        f"Keyword scoring: intent='{best_intent['intent_name'] if best_intent else 'None'}', "
        f"score={best_score}"
    )

    # Eşik kontrol
    if best_score >= KEYWORD_THRESHOLD:
        logger.info(f"✅ Intent bulundu (Keyword): {best_intent['intent_name']}")
        return best_intent

    return None


def _classify_by_semantic_similarity(user_message: str) -> Optional[dict]:
    """
    ADIM 2: Semantic search ile intent'i sınıflandır (opsiyonel).

    Sentence-Transformers modelini kullanarak kullanıcı mesajının her
    intent'in examples'ı ile benzerliğini hesapla.

    Args:
        user_message (str): Kullanıcı mesajı

    Returns:
        dict | None: Intent veya None
    """
    if not USE_EMBEDDINGS or not MODEL:
        return None

    try:
        from sentence_transformers import util

        # User message embedding'i oluştur
        user_embedding: any = MODEL.encode(user_message)

        best_similarity: float = -1.0
        best_intent: Optional[dict] = None

        # Her intent'i değerlendir
        for intent in INTENTS_DATA:
            intent_name: str = intent["intent_name"]

            if intent_name not in INTENT_EMBEDDINGS:
                continue

            intent_vectors: any = INTENT_EMBEDDINGS[intent_name]

            # Cosine similarity hesapla
            similarities: any = util.cos_sim(user_embedding, intent_vectors)[0]
            max_similarity: float = float(similarities.max())

            if max_similarity > best_similarity:
                best_similarity = max_similarity
                best_intent = intent

        logger.debug(
            f"Semantic scoring: intent='{best_intent['intent_name'] if best_intent else 'None'}', "
            f"similarity={best_similarity:.4f}"
        )

        # Eşik kontrol
        if best_similarity >= SIMILARITY_THRESHOLD:
            logger.info(f"✅ Intent bulundu (Semantic): {best_intent['intent_name']}")
            return best_intent

        return None

    except ImportError:
        logger.warning("Sentence-transformers library not available")
        return None

    except Exception as e:
        logger.error(f"Semantic similarity hesaplama hatası: {e}")
        return None


# ============================================================================
# MAIN CLASSIFICATION FUNCTION
# ============================================================================

def classify_intent(user_message: str) -> Optional[dict]:
    """
    3-aşamalı intent sınıflandırma.

    Sıra:
      1. Keyword matching (hızlı, varsayılan)
      2. Semantic search (embed model gerekli, opsiyonel)
      3. Başarısız → None (LLM fallback için)

    Args:
        user_message (str): Kullanıcı tarafından yazılan mesaj

    Returns:
        dict | None: Sınıflandırılan intent veya None
    """
    if not INTENTS_DATA:
        logger.warning("⚠️  Intent data yüklenmedi!")
        return None

    # -------- ADIM 1: KEYWORD MATCHING --------
    intent: Optional[dict] = _classify_by_keywords(user_message)
    if intent:
        return intent

    # -------- ADIM 2: SEMANTIC SIMILARITY --------
    intent = _classify_by_semantic_similarity(user_message)
    if intent:
        return intent

    # -------- ADIM 3: BAŞARISIZ --------
    logger.info("⚠️  Intent sınıflandırılamadı. LLM'e yönlendiriliyor...")
    return None