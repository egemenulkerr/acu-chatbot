# ============================================================================
# tests/conftest.py - pytest yapılandırması
# ============================================================================

import os
import sys

# backend/ klasörünü Python path'e ekle (app modülü için)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Test ortamı varsayılanları
os.environ.setdefault("USE_EMBEDDINGS", "false")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("GOOGLE_API_KEY", "test-placeholder-key")
