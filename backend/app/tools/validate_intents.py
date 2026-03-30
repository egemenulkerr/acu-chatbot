from __future__ import annotations

"""
backend/app/tools/validate_intents.py

Intent tanımlarını (intents.json) Pydantic ile doğrulamak için yardımcı script.

Kullanım (backend klasöründen):
    python -m app.tools.validate_intents
"""

from pathlib import Path
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, ValidationError


class IntentDefinition(BaseModel):
    intent_name: str = Field(..., min_length=1)
    keywords: Dict[str, float] = Field(default_factory=dict)
    examples: List[str] = Field(default_factory=list)
    response_type: str = Field(..., min_length=1)
    # TEXT, RANDOM_TEXT, vb. olabilir — burada type enforcement yapmıyoruz.
    response_content: Union[str, List[str], Dict[str, object]]

    # Opsiyonel alanlar – plan doğrultusunda
    extra_data: Dict[str, object] = Field(default_factory=dict)
    priority: int = Field(default=0)
    category: Optional[str] = Field(default=None)
    negative_keywords: Dict[str, float] = Field(
        default_factory=dict,
        description="Yanlış eşleşmeleri engellemek için negatif anahtarlar",
    )
    use_semantic: Optional[bool] = Field(
        default=None,
        description="Bu intent için semantic (embedding) katmanı kullanılmalı mı?",
    )
    semantic_threshold: Optional[float] = Field(
        default=None,
        description="Bu intent için özel semantic eşik değeri (SIMILARITY_THRESHOLD override).",
    )


class IntentsFile(BaseModel):
    keyword_threshold: float = 8.0
    similarity_threshold: float = 0.65
    intents: List[IntentDefinition]


def validate_intents_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"intents.json bulunamadı: {path}")

    raw = path.read_text(encoding="utf-8")
    data = IntentsFile.model_validate_json(raw)

    # Intent isimlerinin benzersiz olduğunu kontrol et
    names = [i.intent_name for i in data.intents]
    duplicates = {n for n in names if names.count(n) > 1}
    if duplicates:
        raise ValueError(f"Tekrarlayan intent_name değerleri var: {sorted(duplicates)}")

    # Örnek ve keyword sayıları için basit uyarılar
    weak_intents = [
        i.intent_name
        for i in data.intents
        if len(i.examples) < 3 or len(i.keywords) == 0
    ]

    print(f"✅ intents.json doğrulandı: {len(data.intents)} intent, "
          f"keyword_threshold={data.keyword_threshold}, "
          f"similarity_threshold={data.similarity_threshold}")

    if weak_intents:
        print(f"⚠️ Daha fazla örnek/keyword eklenmesi faydalı olabilecek intent'ler: "
              f"{', '.join(sorted(weak_intents))}")


def main() -> None:
    base = Path(__file__).parent.parent
    intents_path = base / "data" / "intents.json"
    try:
        validate_intents_file(intents_path)
    except (FileNotFoundError, ValidationError, ValueError) as exc:
        print(f"❌ intents.json doğrulama hatası: {exc}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()

