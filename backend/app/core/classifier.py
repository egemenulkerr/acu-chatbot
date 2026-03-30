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
STEM_INTENT_WEIGHTS: dict[str, dict[str, float]] = {}
INTENT_NEGATIVE_KEYWORDS: dict[str, set[str]] = {}

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
    global INTENTS_DATA, KEYWORD_THRESHOLD, SIMILARITY_THRESHOLD, INTENT_EMBEDDINGS, STEM_INTENT_WEIGHTS, INTENT_NEGATIVE_KEYWORDS
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

        # Keyword → intent ağırlık haritalarını hazırla
        STEM_INTENT_WEIGHTS = {}
        INTENT_NEGATIVE_KEYWORDS = {}
        for intent in INTENTS_DATA:
            intent_name: str = intent.get("intent_name", "")
            kw: dict = intent.get("keywords", {}) or {}
            neg_kw: dict | list | None = intent.get("negative_keywords")  # opsiyonel

            # Pozitif keyword'ler (tek kelime ve ifade)
            for key, weight in kw.items():
                if not isinstance(key, str):
                    continue
                stem = key.strip().lower()
                if not stem:
                    continue
                # Sadece tek kelimelik anahtarları stem tabanlı map'e koy
                if " " not in stem:
                    STEM_INTENT_WEIGHTS.setdefault(stem, {})[intent_name] = float(weight)

            # Negatif keyword'ler: küçük harfe çevir, set olarak sakla
            neg_set: set[str] = set()
            if isinstance(neg_kw, dict):
                neg_set = {k.strip().lower() for k in neg_kw.keys() if k.strip()}
            elif isinstance(neg_kw, list):
                neg_set = {str(k).strip().lower() for k in neg_kw if str(k).strip()}
            if neg_set:
                INTENT_NEGATIVE_KEYWORDS[intent_name] = neg_set

        # Semantic embedding'leri yeniden hazırla
        INTENT_EMBEDDINGS = {}
        if USE_EMBEDDINGS and MODEL:
            import numpy as np
            logger.info("📊 Intent embedding'leri oluşturuluyor...")
            for intent in INTENTS_DATA:
                intent_name = intent.get("intent_name", "")
                examples: list[str] = intent.get("examples", []) or []
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

def _classify_by_keywords(user_message: str) -> Optional[dict]:
    """
    Keyword tabanlı intent sınıflandırma.

    Optimizasyonlar:
      - preprocess_text çıktısı bir kez hesaplanır
      - stem → {intent: weight} map'i üzerinden O(nStem) zamanda skorlanır
      - negative_keywords içeren intent'ler, ilgili kelime metinde geçiyorsa diskalifiye edilir
    """
    stems: list[str] = preprocess_text(user_message)
    if not stems or not STEM_INTENT_WEIGHTS:
        return None

    # Basit Türkçe stopword listesi — keyword skoruna katkı vermesin
    STOPWORDS: set[str] = {
        "ve", "ile", "de", "da", "mi", "mı", "mu", "mü", "ki", "ya", "ya da",
        "ama", "fakat", "lakin", "veya", "ya da", "şu", "bu", "o",
    }

    scores: dict[str, float] = {}
    for stem in stems:
        s = stem.strip().lower()
        if not s or s in STOPWORDS:
            continue
        intent_weights = STEM_INTENT_WEIGHTS.get(s)
        if not intent_weights:
            continue
        for intent_name, w in intent_weights.items():
            scores[intent_name] = scores.get(intent_name, 0.0) + float(w)

    if not scores:
        return None

    # Negatif keyword'ler: eğer mesajda geçiyorsa ilgili intent'i ele
    text_lower = user_message.lower()
    for intent_name, neg_set in INTENT_NEGATIVE_KEYWORDS.items():
        if any(neg in text_lower for neg in neg_set):
            scores.pop(intent_name, None)

    if not scores:
        return None

    best_intent_name = max(scores, key=scores.get)
    best_score = scores[best_intent_name]

    best_intent = next((i for i in INTENTS_DATA if i.get("intent_name") == best_intent_name), None)
    if best_intent:
        logger.debug(f"Keyword: intent={best_intent_name}, score={best_score}")

    if best_intent and best_score >= KEYWORD_THRESHOLD:
        logger.info(f"✅ Intent (Keyword): {best_intent_name}")
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
            intent_name = intent.get("intent_name", "")
            if intent_name not in INTENT_EMBEDDINGS:
                continue

            # Intent bazlı semantic kullanım flag'i
            use_semantic_flag = intent.get("use_semantic")
            if use_semantic_flag is False:
                continue

            max_sim = _cosine_similarity(user_embedding, INTENT_EMBEDDINGS[intent_name])

            if max_sim > best_similarity:
                best_similarity = max_sim
                best_intent = intent

        if best_intent:
            logger.debug(f"Semantic: intent={best_intent['intent_name']}, sim={best_similarity:.4f}")
        # Intent'e özel eşik tanımlanmışsa onu kullan
        intent_specific_threshold = None
        if best_intent is not None:
            intent_specific_threshold = best_intent.get("semantic_threshold")

        threshold = float(intent_specific_threshold or SIMILARITY_THRESHOLD)
        if best_intent is not None and best_similarity >= threshold:
            logger.info(f"✅ Intent (Semantic): {best_intent['intent_name']} (sim={best_similarity:.4f}, th={threshold})")
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
