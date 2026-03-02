# ============================================================================
# tests/test_session_store.py - Session Store Testleri
# ============================================================================

import os
import tempfile
import pytest

os.environ.setdefault("USE_EMBEDDINGS", "false")


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Her test için geçici SQLite DB kullan."""
    db_path = tmp_path / "test_sessions.db"
    import app.services.session_store as store
    monkeypatch.setattr(store, "_DB_PATH", db_path)
    store.init_db()
    yield store
    # Cleanup otomatik (tmp_path ile)


class TestSessionStore:
    def test_save_and_get_history(self, temp_db):
        store = temp_db
        store.save_message("sess-1", "user", "merhaba")
        store.save_message("sess-1", "bot", "Selam!")

        history = store.get_history("sess-1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["text"] == "merhaba"
        assert history[1]["role"] == "bot"
        assert history[1]["text"] == "Selam!"

    def test_empty_session_returns_empty(self, temp_db):
        store = temp_db
        history = store.get_history("nonexistent-session")
        assert history == []

    def test_limit_enforced(self, temp_db):
        store = temp_db
        # MAX_HISTORY (20) + 5 fazla kayıt ekle
        for i in range(25):
            store.save_message("sess-limit", "user", f"mesaj {i}")

        history = store.get_history("sess-limit", limit=20)
        assert len(history) <= 20

    def test_get_or_fallback_uses_store(self, temp_db):
        store = temp_db
        store.save_message("sess-fb", "user", "stored message")

        result = store.get_or_fallback("sess-fb", [{"role": "user", "text": "client fallback"}])
        assert any(m["text"] == "stored message" for m in result)

    def test_get_or_fallback_uses_client_when_store_empty(self, temp_db):
        store = temp_db
        client_history = [{"role": "user", "text": "client message"}]
        result = store.get_or_fallback("new-session-xyz", client_history)
        assert result == client_history

    def test_prune_old_sessions(self, temp_db):
        """Prune çalışmalı ve 0 döndürmeli (yeni kayıtlar silinmez)."""
        store = temp_db
        store.save_message("sess-prune", "user", "yeni mesaj")
        deleted = store.prune_old_sessions(days=7)
        assert isinstance(deleted, int)
        # Yeni kayıt silinmemeli
        assert deleted == 0

    def test_none_session_id_returns_fallback(self, temp_db):
        store = temp_db
        fallback = [{"role": "user", "text": "fallback"}]
        result = store.get_or_fallback(None, fallback)
        assert result == fallback
