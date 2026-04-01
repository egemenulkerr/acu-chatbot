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
PHRASE_INTENT_WEIGHTS: dict[str, dict[str, float]] = {}
INTENT_NEGATIVE_KEYWORDS: dict[str, set[str]] = {}
INTENT_EXAMPLE_MAP: dict[str, str] = {}  # normalized example → intent_name

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
    global INTENTS_DATA, KEYWORD_THRESHOLD, SIMILARITY_THRESHOLD, INTENT_EMBEDDINGS, STEM_INTENT_WEIGHTS, PHRASE_INTENT_WEIGHTS, INTENT_NEGATIVE_KEYWORDS, INTENT_EXAMPLE_MAP
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

        STEM_INTENT_WEIGHTS = {}
        PHRASE_INTENT_WEIGHTS = {}
        INTENT_NEGATIVE_KEYWORDS = {}
        for intent in INTENTS_DATA:
            intent_name: str = intent.get("intent_name", "")
            kw: dict = intent.get("keywords", {}) or {}
            neg_kw: dict | list | None = intent.get("negative_keywords")

            for key, weight in kw.items():
                if not isinstance(key, str):
                    continue
                stem = key.strip().lower()
                if not stem:
                    continue
                if " " in stem:
                    PHRASE_INTENT_WEIGHTS.setdefault(stem, {})[intent_name] = float(weight)
                else:
                    STEM_INTENT_WEIGHTS.setdefault(stem, {})[intent_name] = float(weight)

            neg_set: set[str] = set()
            if isinstance(neg_kw, dict):
                neg_set = {k.strip().lower() for k in neg_kw.keys() if k.strip()}
            elif isinstance(neg_kw, list):
                neg_set = {str(k).strip().lower() for k in neg_kw if str(k).strip()}
            if neg_set:
                INTENT_NEGATIVE_KEYWORDS[intent_name] = neg_set

        logger.info(
            f"📊 Keyword maps: {len(STEM_INTENT_WEIGHTS)} stems, "
            f"{len(PHRASE_INTENT_WEIGHTS)} phrases"
        )

        INTENT_EXAMPLE_MAP = {}
        for intent in INTENTS_DATA:
            intent_name = intent.get("intent_name", "")
            for ex in intent.get("examples", []) or []:
                normalized = _normalize_for_match(ex)
                if normalized:
                    INTENT_EXAMPLE_MAP[normalized] = intent_name
        logger.info(f"📊 Exact example map: {len(INTENT_EXAMPLE_MAP)} entries")

        INTENT_EMBEDDINGS = {}
        if USE_EMBEDDINGS and MODEL:
            import numpy as np
            logger.info("📊 Intent embedding'leri oluşturuluyor (batch)...")

            all_examples: list[str] = []
            index_map: list[tuple[str, int, int]] = []
            for intent in INTENTS_DATA:
                intent_name = intent.get("intent_name", "")
                if intent.get("use_semantic") is False:
                    continue
                examples: list[str] = intent.get("examples", []) or []
                if examples:
                    start = len(all_examples)
                    all_examples.extend(examples)
                    index_map.append((intent_name, start, start + len(examples)))

            if all_examples:
                all_vectors = np.array(list(MODEL.embed(all_examples)))
                for intent_name, start, end in index_map:
                    INTENT_EMBEDDINGS[intent_name] = all_vectors[start:end]

            logger.info(
                f"✅ {len(INTENT_EMBEDDINGS)} intent embedding'i oluşturuldu "
                f"({len(all_examples)} örnek, tek batch)."
            )

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

import re as _re

def _normalize_for_match(text: str) -> str:
    """Exact match için normalize: lowercase, noktalamasız, tek boşluk."""
    t = text.lower().strip()
    t = _re.sub(r'[^\w\s]', '', t, flags=_re.UNICODE)
    return ' '.join(t.split())


def _classify_by_exact_example(user_message: str) -> Optional[dict]:
    """Kısa mesajlarda (~1-5 kelime) exact/near-exact örnek eşleşmesi."""
    normalized = _normalize_for_match(user_message)
    if not normalized:
        return None

    intent_name = INTENT_EXAMPLE_MAP.get(normalized)
    if intent_name:
        intent = next((i for i in INTENTS_DATA if i.get("intent_name") == intent_name), None)
        if intent:
            logger.info(f"✅ Intent (Exact Example): {intent_name}")
            return intent

    return None


_STOPWORDS: frozenset[str] = frozenset({
    "ve", "ile", "de", "da", "mi", "mı", "mu", "mü", "ki", "ya",
    "ama", "fakat", "lakin", "veya", "şu", "bu", "o", "bir", "ben",
    "sen", "bana", "sana", "için", "ne", "nasıl", "var", "yok",
})


def _classify_by_keywords(user_message: str) -> Optional[dict]:
    """
    Keyword + phrase (bigram/trigram) tabanlı intent sınıflandırma.

    1) Çok kelimeli ifadeleri (phrase) normalize metin üzerinde arar
    2) Tek kelime stem'leri STEM_INTENT_WEIGHTS'ten skorlar
    3) Mesaj uzunluğuna göre normalize eder (kısa mesaj avantajsız olmasın)
    4) Negatif keyword filtreleme uygular
    5) İlk iki aday yakınsa semantic tie-breaking yapar
    """
    stems: list[str] = preprocess_text(user_message)
    if not stems:
        return None

    scores: dict[str, float] = {}
    text_lower: str = user_message.lower()

    # --- Phase 1: Multi-word phrase matching on raw lowered text ---
    for phrase, intent_weights in PHRASE_INTENT_WEIGHTS.items():
        if phrase in text_lower:
            for intent_name, w in intent_weights.items():
                scores[intent_name] = scores.get(intent_name, 0.0) + w

    # --- Phase 2: Single-stem matching ---
    meaningful_count = 0
    for stem in stems:
        s = stem.strip().lower()
        if not s or s in _STOPWORDS:
            continue
        meaningful_count += 1
        intent_weights = STEM_INTENT_WEIGHTS.get(s)
        if not intent_weights:
            continue
        for intent_name, w in intent_weights.items():
            scores[intent_name] = scores.get(intent_name, 0.0) + w

    if not scores:
        return None

    # --- Phase 3: Score normalization ---
    # Long messages accumulate more hits; normalize so short messages
    # aren't penalized. Uses log-based dampening.
    if meaningful_count > 3:
        import math
        factor = 1.0 + 0.3 * math.log(meaningful_count / 3.0)
        scores = {k: v / factor for k, v in scores.items()}

    # --- Phase 4: Negative keyword filtering ---
    for intent_name, neg_set in INTENT_NEGATIVE_KEYWORDS.items():
        if intent_name in scores and any(neg in text_lower for neg in neg_set):
            scores.pop(intent_name, None)

    if not scores:
        return None

    sorted_intents = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_intent_name, best_score = sorted_intents[0]

    logger.debug(f"Keyword scores (top-3): {sorted_intents[:3]}")

    if best_score < KEYWORD_THRESHOLD:
        return None

    # --- Phase 5: Tie-breaking via semantic similarity ---
    if (
        len(sorted_intents) >= 2
        and USE_EMBEDDINGS
        and MODEL
        and sorted_intents[1][1] >= best_score * 0.85
    ):
        tie_candidates = [
            name for name, sc in sorted_intents[:3] if sc >= best_score * 0.80
        ]
        logger.debug(f"Tie-break candidates: {tie_candidates}")
        try:
            user_emb = _encode_user_message(user_message)
            tie_best_sim = -1.0
            tie_winner = best_intent_name
            for cand in tie_candidates:
                if cand in INTENT_EMBEDDINGS:
                    sim = _cosine_similarity(user_emb, INTENT_EMBEDDINGS[cand])
                    if sim > tie_best_sim:
                        tie_best_sim = sim
                        tie_winner = cand
            if tie_winner != best_intent_name:
                logger.info(
                    f"🔀 Tie-break: {best_intent_name} → {tie_winner} "
                    f"(sim={tie_best_sim:.4f})"
                )
                best_intent_name = tie_winner
        except Exception as e:
            logger.debug(f"Tie-break semantic error (ignored): {e}")

    best_intent = next(
        (i for i in INTENTS_DATA if i.get("intent_name") == best_intent_name), None
    )
    if best_intent:
        logger.info(f"✅ Intent (Keyword): {best_intent_name} (score={best_score:.1f})")
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


_SEMANTIC_FLOOR: float = 0.65


def _has_known_vocabulary(user_message: str) -> bool:
    """Mesajda bilinen intent kelime dağarcığından en az bir eşleşme var mı?"""
    text_lower = user_message.lower()
    for phrase in PHRASE_INTENT_WEIGHTS:
        if phrase in text_lower:
            return True
    stems = preprocess_text(user_message)
    for stem in stems:
        s = stem.strip().lower()
        if s and s not in _STOPWORDS and s in STEM_INTENT_WEIGHTS:
            return True
    return False


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

            use_semantic_flag = intent.get("use_semantic")
            if use_semantic_flag is False:
                continue

            max_sim = _cosine_similarity(user_embedding, INTENT_EMBEDDINGS[intent_name])

            if max_sim > best_similarity:
                best_similarity = max_sim
                best_intent = intent

        if best_intent:
            logger.debug(f"Semantic: intent={best_intent['intent_name']}, sim={best_similarity:.4f}")

        if best_similarity < _SEMANTIC_FLOOR:
            logger.info(f"⚠️  Semantic floor altında (sim={best_similarity:.4f} < {_SEMANTIC_FLOOR}), eşleşme reddedildi.")
            return None

        intent_specific_threshold = None
        if best_intent is not None:
            intent_specific_threshold = best_intent.get("semantic_threshold")

        threshold = max(float(intent_specific_threshold or SIMILARITY_THRESHOLD), _SEMANTIC_FLOOR)
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
    """4-aşamalı intent sınıflandırma: Exact → Keyword → Semantic → None (LLM fallback)."""
    if not INTENTS_DATA:
        logger.warning("⚠️  Intent data yüklenmedi!")
        return None

    intent = _classify_by_exact_example(user_message)
    if intent:
        return intent

    intent = _classify_by_keywords(user_message)
    if intent:
        return intent

    if _has_known_vocabulary(user_message):
        intent = _classify_by_semantic_similarity(user_message)
        if intent:
            return intent
    else:
        logger.info("⚠️  Bilinen kelime dağarcığı yok, semantic atlanıyor.")

    logger.info("⚠️  Intent sınıflandırılamadı. LLM'e yönlendiriliyor...")
    return None
