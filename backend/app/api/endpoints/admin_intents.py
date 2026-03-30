from __future__ import annotations

# ============================================================================
# backend/app/api/endpoints/admin_intents.py - Intent Yönetim & Debug API'leri
# ============================================================================

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from ...security import require_admin
from ...core.classifier import (
    INTENTS_DATA,
    classify_intent,
    _classify_by_keywords,
    _classify_by_semantic_similarity,
)


router = APIRouter()


@router.get("/intents", tags=["admin-intents"])
def list_intents(_: None = Depends(require_admin)) -> Dict[str, Any]:
    """
    Mevcut intent'leri ve temel konfigürasyonlarını döndür.
    """
    intents: List[Dict[str, Any]] = []
    for intent in INTENTS_DATA:
        intents.append(
            {
                "intent_name": intent.get("intent_name"),
                "category": intent.get("category"),
                "priority": intent.get("priority", 0),
                "keyword_count": len(intent.get("keywords", {}) or {}),
                "example_count": len(intent.get("examples", []) or []),
                "use_semantic": intent.get("use_semantic"),
                "semantic_threshold": intent.get("semantic_threshold"),
            }
        )
    return {"count": len(intents), "intents": intents}


@router.get("/intents/{intent_name}", tags=["admin-intents"])
def get_intent(intent_name: str, _: None = Depends(require_admin)) -> Dict[str, Any]:
    """
    Belirli bir intent'in tam tanımını döndür.
    """
    for intent in INTENTS_DATA:
        if intent.get("intent_name") == intent_name:
            return intent
    raise HTTPException(status_code=404, detail="Intent bulunamadı.")


@router.post("/debug/classify", tags=["admin-intents"])
def debug_classify(
    body: Dict[str, Any],
    _: None = Depends(require_admin),
) -> Dict[str, Any]:
    """
    Verilen metin için sınıflandırma kararını detaylı şekilde döndür.

    Body:
        { "text": "kullanıcı mesajı" }
    """
    text = str(body.get("text", "")).strip()
    if not text:
        raise HTTPException(status_code=400, detail="text alanı zorunludur.")

    # Normal akış
    final_intent: Optional[dict] = classify_intent(text)

    # Ayrı ayrı keyword ve semantic kararlarını incele
    kw_intent = _classify_by_keywords(text)
    sem_intent = _classify_by_semantic_similarity(text)

    return {
        "text": text,
        "final_intent": final_intent.get("intent_name") if final_intent else None,
        "keyword_intent": kw_intent.get("intent_name") if kw_intent else None,
        "semantic_intent": sem_intent.get("intent_name") if sem_intent else None,
        "raw_final": final_intent,
        "raw_keyword": kw_intent,
        "raw_semantic": sem_intent,
    }

