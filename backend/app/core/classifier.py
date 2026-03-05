# ============================================================================
# backend/app/core/classifier.py - Intent Sınıflandırma Motoru
# ============================================================================

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .nlp import preprocess_text
from ..config import settings


# ============================================================================
# LOGGING
# ============================================================================

logger: logging.Logger = logging.getLogger(__name__)


# ============================================================================
# GLOBAL STATE
# ============================================================================

MODEL: Optional[any] = None
INTENTS_DATA: list[dict] = []
INTENT_EMBEDDINGS: dict[str, any] = {}

USE_EMBEDDINGS: bool = settings.use_embeddings

KEYWORD_THRESHOLD: float = 6.0
SIMILARITY_THRESHOLD: float = 0.65

# Dosya yolu — modüle göre relative (CWD'den bağımsız)
DATA_FILE: Path = Path(__file__).parent.parent / "data" / "intents.json"

# Module import edildiğinde intent verisini bir kez yüklemeyi dene.
try:
    with open(DATA_FILE, "r", encoding="utf-8") as _f:
        _data: dict = json.load(_f)
    INTENTS_DATA = _data.get("intents", [])
    # Çok agresif eşiklerin basit mesajları (\"merhaba\" vb.) kaçırmaması için
    # üst sınırı 6.0'da tutuyoruz.
    KEYWORD_THRESHOLD = min(_data.get("keyword_threshold", KEYWORD_THRESHOLD), 6.0)
    SIMILARITY_THRESHOLD = _data.get("similarity_threshold", SIMILARITY_THRESHOLD)
    logger.info(
        f"⚙️  Initial config: keyword_threshold={KEYWORD_THRESHOLD}, "
        f"similarity_threshold={SIMILARITY_THRESHOLD}, intents={len(INTENTS_DATA)}"
    )
except FileNotFoundError:
    logger.error(f"❌ {DATA_FILE} dosyası bulunamadı (initial load)!")
except json.JSONDecodeError as e:
    logger.error(f"❌ JSON parse hatası (initial load): {e}")
except Exception as e:
    logger.error(f"❌ Intent data initial load hatası: {e}", exc_info=True)


# ============================================================================
# MODEL LOADING
# ============================================================================

def load_model() -> None:
    global MODEL

    if not USE_EMBEDDINGS:
        logger.info("Embeddings devre dışı (USE_EMBEDDINGS=false)")
        return

    try:
        from fastembed import TextEmbedding
        logger.info("📊 Semantic model yükleniyor (fastembed/ONNX)...")
        MODEL = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        logger.info("✅ Semantic model yüklendi.")
    except ImportError as e:
        logger.error(f"❌ Fastembed import hatası: {e}")
    except Exception as e:
        logger.error(f"❌ Model yükleme hatası: {e}")


# ============================================================================
# DATA LOADING
# ============================================================================

def load_intent_data() -> None:
    global INTENTS_DATA, KEYWORD_THRESHOLD, SIMILARITY_THRESHOLD, INTENT_EMBEDDINGS
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data: dict = json.load(f)

        INTENTS_DATA = data.get("intents", [])
        KEYWORD_THRESHOLD = min(data.get("keyword_threshold", KEYWORD_THRESHOLD), 6.0)
        SIMILARITY_THRESHOLD = data.get("similarity_threshold", 0.65)

        logger.info(
            f"⚙️  Config: keyword_threshold={KEYWORD_THRESHOLD}, "
            f"similarity_threshold={SIMILARITY_THRESHOLD}"
        )

        if USE_EMBEDDINGS and MODEL:
            import numpy as np
            logger.info("📊 Intent embedding'leri oluşturuluyor...")
            for intent in INTENTS_DATA:
                intent_name: str = intent["intent_name"]
                examples: list[str] = intent.get("examples", [])
                if examples:
                    INTENT_EMBEDDINGS[intent_name] = np.array(list(MODEL.embed(examples)))
            logger.info(f"✅ {len(INTENT_EMBEDDINGS)} intent embedding'i oluşturuldu.")

        logger.info(f"✅ {len(INTENTS_DATA)} intent yüklendi.")

    except FileNotFoundError:
        logger.error(f"❌ {DATA_FILE} dosyası bulunamadı!")
        INTENTS_DATA = []
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse hatası: {e}")
        INTENTS_DATA = []
    except Exception as e:
        # Beklenmeyen hata durumunda mevcut INTENTS_DATA'yı koru ki
        # en azından daha önce yüklenmiş veriler kullanılabilsin.
        logger.error(f"❌ Intent data yükleme hatası: {e}", exc_info=True)


# ============================================================================
# HELPERS
# ============================================================================

def _calculate_keyword_score(
    message_stems: list[str],
    intent_keywords: dict[str, float]
) -> float:
    return sum(intent_keywords[s] for s in message_stems if s in intent_keywords)


def _classify_by_keywords(user_message: str) -> Optional[dict]:
    stems: list[str] = preprocess_text(user_message)

    best_score: float = 0.0
    best_intent: Optional[dict] = None

    for intent in INTENTS_DATA:
        score = _calculate_keyword_score(stems, intent.get("keywords", {}))
        if score > best_score:
            best_score = score
            best_intent = intent

    if best_intent:
        logger.debug(f"Keyword: intent={best_intent['intent_name']}, score={best_score}")

    if best_score >= KEYWORD_THRESHOLD:
        logger.info(f"✅ Intent (Keyword): {best_intent['intent_name']}")
        return best_intent

    return None


@lru_cache(maxsize=256)
def _encode_user_message(message: str):
    """Kullanıcı mesajı vektörünü cache'le — aynı mesaj tekrar encode edilmez."""
    import numpy as np
    return np.array(list(MODEL.embed([message])))[0]


def _cosine_similarity(a, b_matrix) -> float:
    """a: (dim,), b_matrix: (n, dim) — maksimum cosine similarity döndürür."""
    import numpy as np
    a_norm = a / (np.linalg.norm(a) + 1e-10)
    norms = np.linalg.norm(b_matrix, axis=1, keepdims=True) + 1e-10
    b_normed = b_matrix / norms
    return float(np.dot(b_normed, a_norm).max())


def _classify_by_semantic_similarity(user_message: str) -> Optional[dict]:
    if not USE_EMBEDDINGS or not MODEL:
        return None

    try:
        user_embedding = _encode_user_message(user_message)

        best_similarity: float = -1.0
        best_intent: Optional[dict] = None

        for intent in INTENTS_DATA:
            intent_name = intent["intent_name"]
            if intent_name not in INTENT_EMBEDDINGS:
                continue

            max_sim = _cosine_similarity(user_embedding, INTENT_EMBEDDINGS[intent_name])

            if max_sim > best_similarity:
                best_similarity = max_sim
                best_intent = intent

        if best_intent:
            logger.debug(f"Semantic: intent={best_intent['intent_name']}, sim={best_similarity:.4f}")

        if best_similarity >= SIMILARITY_THRESHOLD:
            logger.info(f"✅ Intent (Semantic): {best_intent['intent_name']}")
            return best_intent

        return None

    except Exception as e:
        logger.error(f"Semantic similarity hatası: {e}")
        return None


# ============================================================================
# MAIN CLASSIFICATION FUNCTION
# ============================================================================

def classify_intent(user_message: str) -> Optional[dict]:
    """3-aşamalı intent sınıflandırma: Keyword → Semantic → None (LLM fallback)."""
    if not INTENTS_DATA:
        logger.warning("⚠️  Intent data yüklenmedi!")
        return None

    intent = _classify_by_keywords(user_message)
    if intent:
        return intent

    intent = _classify_by_semantic_similarity(user_message)
    if intent:
        return intent

    logger.info("⚠️  Intent sınıflandırılamadı. LLM'e yönlendiriliyor...")
    return None
