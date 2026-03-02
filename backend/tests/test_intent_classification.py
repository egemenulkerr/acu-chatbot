# ============================================================================
# tests/test_intent_classification.py - Intent Sınıflandırma Testleri
# ============================================================================
"""
Intent classification motor testleri.
USE_EMBEDDINGS=false modunda çalışır (hızlı, model gerektirmez).
"""

import os
import pytest

# Embeddings'i devre dışı bırak — bu testler için model gerekmez
os.environ.setdefault("USE_EMBEDDINGS", "false")


@pytest.fixture(autouse=True)
def load_intents():
    """Her testten önce intent verisini yükle."""
    from app.core.classifier import load_intent_data, INTENTS_DATA
    if not INTENTS_DATA:
        load_intent_data()


class TestKeywordClassification:
    """Keyword tabanlı intent eşleştirme testleri."""

    def test_yemek_intent(self):
        from app.core.classifier import classify_intent
        result = classify_intent("bugün öğle yemeği ne var")
        assert result is not None
        assert result["intent_name"] == "yemek_listesi"

    def test_selamlasma_intent(self):
        from app.core.classifier import classify_intent
        result = classify_intent("merhaba")
        assert result is not None
        assert result["intent_name"] == "selamlasma"

    def test_obs_intent(self):
        from app.core.classifier import classify_intent
        result = classify_intent("obs şifremi unuttum")
        assert result is not None
        assert result["intent_name"] == "obs_sistemi"

    def test_hava_durumu_intent(self):
        from app.core.classifier import classify_intent
        result = classify_intent("artvin hava durumu nasıl")
        assert result is not None
        assert result["intent_name"] == "hava_durumu"

    def test_kutuphane_intent(self):
        from app.core.classifier import classify_intent
        result = classify_intent("kütüphane saat kaçta açılıyor")
        assert result is not None
        assert result["intent_name"] == "kutuphane"

    def test_burs_intent(self):
        from app.core.classifier import classify_intent
        result = classify_intent("burs başvurusu nasıl yapılır")
        assert result is not None
        assert result["intent_name"] == "burs_bilgisi"

    def test_yurt_intent(self):
        from app.core.classifier import classify_intent
        result = classify_intent("kyk yurt başvurusu")
        assert result is not None
        assert result["intent_name"] == "yurt_bilgisi"

    def test_akademik_takvim_intent(self):
        from app.core.classifier import classify_intent
        result = classify_intent("final sınavları ne zaman")
        assert result is not None
        assert result["intent_name"] == "akademik_takvim"

    def test_unknown_returns_none(self):
        from app.core.classifier import classify_intent
        # Tamamen alakasız mesaj → None (LLM'e düşer)
        result = classify_intent("xyzabc bilinmeyen kelime zort")
        assert result is None


class TestIntentDataLoading:
    """Intent veri yükleme testleri."""

    def test_intents_loaded(self):
        from app.core.classifier import INTENTS_DATA
        assert len(INTENTS_DATA) > 10, "En az 10 intent yüklü olmalı"

    def test_each_intent_has_examples(self):
        from app.core.classifier import INTENTS_DATA
        for intent in INTENTS_DATA:
            name = intent.get("intent_name", "?")
            examples = intent.get("examples", [])
            assert len(examples) >= 4, f"'{name}' intent'i çok az örneğe sahip: {len(examples)}"

    def test_each_intent_has_keywords(self):
        from app.core.classifier import INTENTS_DATA
        for intent in INTENTS_DATA:
            name = intent.get("intent_name", "?")
            keywords = intent.get("keywords", {})
            assert len(keywords) > 0, f"'{name}' intent'inin keyword'ü yok"

    def test_new_intents_exist(self):
        from app.core.classifier import INTENTS_DATA
        intent_names = {i["intent_name"] for i in INTENTS_DATA}
        assert "sks_etkinlik" in intent_names, "sks_etkinlik intent'i yok"
        assert "guncel_haberler" in intent_names, "guncel_haberler intent'i yok"
        assert "mezuniyet" in intent_names, "mezuniyet intent'i yok"
        assert "psikolojik_destek" in intent_names, "psikolojik_destek intent'i yok"
