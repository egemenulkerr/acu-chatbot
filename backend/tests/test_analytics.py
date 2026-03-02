# ============================================================================
# tests/test_analytics.py - Analytics Endpoint Testleri (izole)
# ============================================================================

import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("USE_EMBEDDINGS", "false")
os.environ.setdefault("ADMIN_SECRET_TOKEN", "test-admin-token-xyz")


@pytest.fixture
def analytics_file(tmp_path):
    """Test için geçici analytics.jsonl dosyası oluştur."""
    f = tmp_path / "analytics.jsonl"
    entries = [
        {"ts": "2026-01-01T10:00:00", "q": "yemek", "intent": "yemek_listesi", "source": "Yemek Servisi", "ms": 120},
        {"ts": "2026-01-01T11:00:00", "q": "hava", "intent": "hava_durumu", "source": "Hava Durumu", "ms": 200},
        {"ts": "2026-01-02T09:00:00", "q": "obs", "intent": "obs_sistemi", "source": "Hızlı Yol", "ms": 50},
    ]
    with open(f, "w") as fp:
        for entry in entries:
            fp.write(json.dumps(entry) + "\n")
    return f


class TestAnalyticsHelpers:
    def test_load_entries(self, analytics_file):
        import app.api.endpoints.analytics as analytics_module
        with patch.object(analytics_module, "_ANALYTICS_FILE", analytics_file):
            entries = analytics_module._load_entries()
        assert len(entries) == 3

    def test_build_summary_empty(self):
        from app.api.endpoints.analytics import _build_summary
        result = _build_summary([])
        assert result["total_messages"] == 0
        assert result["intent_distribution"] == {}

    def test_build_summary_with_data(self, analytics_file):
        import app.api.endpoints.analytics as analytics_module
        with patch.object(analytics_module, "_ANALYTICS_FILE", analytics_file):
            entries = analytics_module._load_entries()
        summary = analytics_module._build_summary(entries)
        assert summary["total_messages"] == 3
        assert "yemek_listesi" in summary["intent_distribution"]
        assert summary["avg_response_ms"] is not None

    def test_load_entries_missing_file(self, tmp_path):
        import app.api.endpoints.analytics as analytics_module
        nonexistent = tmp_path / "nonexistent.jsonl"
        with patch.object(analytics_module, "_ANALYTICS_FILE", nonexistent):
            entries = analytics_module._load_entries()
        assert entries == []


class TestAnalyticsEndpointRoutes:
    @pytest.fixture(scope="class")
    def client(self):
        from fastapi.testclient import TestClient
        from app.main import app
        return TestClient(app)

    def test_summary_endpoint_all_periods(self, client, analytics_file):
        import app.api.endpoints.analytics as analytics_module
        with patch.object(analytics_module, "_ANALYTICS_FILE", analytics_file):
            for period in ["24h", "7d", "30d", "all"]:
                resp = client.get(f"/api/analytics/summary?period={period}")
                assert resp.status_code == 200
                data = resp.json()
                assert "total_messages" in data

    def test_recent_with_valid_token(self, client, analytics_file):
        import app.api.endpoints.analytics as analytics_module
        with patch.object(analytics_module, "_ANALYTICS_FILE", analytics_file):
            with patch.object(analytics_module, "_ADMIN_TOKEN", "test-admin-token-xyz"):
                resp = client.get(
                    "/api/analytics/recent?limit=10",
                    headers={"Authorization": "Bearer test-admin-token-xyz"}
                )
                assert resp.status_code == 200
                data = resp.json()
                assert "entries" in data

    def test_recent_without_token_rejected(self, client):
        resp = client.get("/api/analytics/recent")
        assert resp.status_code in (401, 403, 503)
