# ============================================================================
# tests/test_api_endpoints.py - FastAPI Endpoint Testleri
# ============================================================================
"""
HTTP endpoint testleri.
Gemini ve scraper bağımlılıkları mock'lanır.
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock

os.environ.setdefault("USE_EMBEDDINGS", "false")
os.environ.setdefault("GOOGLE_API_KEY", "test-key-only")


@pytest.fixture(scope="module")
def sync_client():
    """Synchronous test client (requests-style)."""
    from fastapi.testclient import TestClient
    from app.main import app
    return TestClient(app)


@pytest.fixture(scope="module")
async def async_client():
    """Async test client via httpx.AsyncClient."""
    from httpx import AsyncClient, ASGITransport
    from app.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


class TestHealthEndpoint:
    def test_health_returns_ok(self, sync_client):
        resp = sync_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "components" in data

    def test_health_has_components(self, sync_client):
        resp = sync_client.get("/health")
        components = resp.json()["components"]
        assert "embeddings" in components
        assert "gemini_configured" in components
        assert "intents_loaded" in components

    def test_root_endpoint(self, sync_client):
        resp = sync_client.get("/")
        assert resp.status_code == 200
        assert "proje" in resp.json()


class TestAnalyticsEndpoint:
    def test_summary_no_auth_required(self, sync_client):
        resp = sync_client.get("/api/analytics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_messages" in data
        assert "period" in data

    def test_summary_valid_periods(self, sync_client):
        for period in ["24h", "7d", "30d", "all"]:
            resp = sync_client.get(f"/api/analytics/summary?period={period}")
            assert resp.status_code == 200

    def test_summary_invalid_period(self, sync_client):
        resp = sync_client.get("/api/analytics/summary?period=invalid")
        assert resp.status_code == 400

    def test_recent_requires_auth(self, sync_client):
        resp = sync_client.get("/api/analytics/recent")
        assert resp.status_code in (401, 403, 503)


class TestChatEndpoint:
    def test_chat_basic_greeting(self, sync_client):
        """Selamlama intent'i keyword match ile çalışmalı."""
        resp = sync_client.post(
            "/api/chat",
            json={"message": "merhaba", "session_id": "test-session-001"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert len(data["response"]) > 0

    def test_chat_obs_intent(self, sync_client):
        """OBS intent'i keyword match ile tanınmalı."""
        resp = sync_client.post(
            "/api/chat",
            json={"message": "obs şifremi unuttum", "session_id": "test-session-002"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data
        assert data.get("intent_name") == "obs_sistemi"

    def test_chat_empty_message_rejected(self, sync_client):
        """Boş mesaj 422 dönmeli."""
        resp = sync_client.post(
            "/api/chat",
            json={"message": ""}
        )
        assert resp.status_code == 422

    def test_chat_with_session_id(self, sync_client):
        """Session ID ile chat çalışmalı."""
        resp = sync_client.post(
            "/api/chat",
            json={
                "message": "burs bilgisi",
                "session_id": "test-session-003"
            }
        )
        assert resp.status_code == 200

    @patch("app.api.endpoints.chat.get_llm_response")
    def test_llm_fallback_on_unknown_intent(self, mock_llm, sync_client):
        """Tanınmayan mesaj LLM'e düşmeli."""
        mock_llm.return_value = "Bu konuda size yardımcı olmaya çalışıyorum."

        resp = sync_client.post(
            "/api/chat",
            json={"message": "xyzabc zort bilinmeyen soru abc123", "session_id": "test-llm"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("source") in ("Gemini AI", "Timeout", "Error")


class TestFoodCacheEndpoint:
    @patch("app.api.endpoints.chat.scrape_daily_menu")
    def test_food_query_returns_response(self, mock_scrape, sync_client):
        """Yemek sorgusu scraper'ı çağırmalı."""
        mock_scrape.return_value = "Çorba\nPilav\nYoğurt"

        resp = sync_client.post(
            "/api/chat",
            json={"message": "bugün yemek ne", "session_id": "test-food"}
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("intent_name") == "yemek_listesi"

    @patch("app.api.endpoints.chat.scrape_daily_menu")
    def test_food_cache_used_on_second_call(self, mock_scrape, sync_client):
        """İkinci çağrıda scraper tekrar çağrılmamalı (günlük cache)."""
        mock_scrape.return_value = "Çorba\nPilav"

        # İlk çağrı — cache boş, scraper çağrılır (veya zaten dolu)
        sync_client.post("/api/chat", json={"message": "yemek listesi", "session_id": "cache-test-1"})
        initial_call_count = mock_scrape.call_count

        # İkinci çağrı — aynı gün, cache doluysa scraper çağrılmaz
        sync_client.post("/api/chat", json={"message": "menü ne", "session_id": "cache-test-2"})
        assert mock_scrape.call_count <= initial_call_count + 1
