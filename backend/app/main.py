# ============================================================================
# backend/app/main.py - FastAPI Ana Uygulama
# ============================================================================
# Açıklama:
#   FastAPI uygulamasının ana giriş noktası. CORS yapılandırması, startup/
#   shutdown işlemlerini ve route'ları yönetir. Background threadlerde ağır
#   initialization işlemlerini yaparak hızlı health check sağlar.
# ============================================================================

import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from .api.endpoints import chat as chat_router
from .core.classifier import load_intent_data
from .services.device_registry import initialize_device_db, update_device_database
from .services.web_scraper.manager import update_system_data_fast, update_system_data


# ============================================================================
# GLOBAL CONFIGURATION
# ============================================================================

app: FastAPI = FastAPI(
    title="AÇÜ Chatbot API",
    description="Artvin Çoruh Üniversitesi Asistan Chatbotu",
    version="1.0.0"
)

# Scheduler örneği - background job'ları yönetir
scheduler: AsyncIOScheduler = AsyncIOScheduler()

# Startup tamamlandı mı? (health check için)
STARTUP_COMPLETE: bool = False

# ============================================================================
# CORS MIDDLEWARE YAPLANDIRMASI
# ============================================================================

ALLOWED_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://localhost:5173",
    "https://egemenulker.com",
    "https://www.egemenulker.com",
    "https://king-prawn-app-t5y4u.ondigitalocean.app",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
)


# ============================================================================
# BACKGROUND INITIALIZATION FUNCTIONS
# ============================================================================

async def _load_nlp_module() -> None:
    """
    Zemberek NLP motorunu arka planda yükle.

    Not: İlk yüklenişte 2-3 saniye sürer (JVM başlatılması).
    """
    print("⚙️  NLP motorunu yükleniyor (Zemberek JVM)...")
    try:
        from .core.nlp import get_morphology
        await asyncio.to_thread(get_morphology)
        print("✅ NLP motoru başarıyla yüklendi.")
    except Exception as e:
        print(f"❌ NLP yükleme hatası: {e}")
        raise


async def _load_intent_data_module() -> None:
    """Intent verilerini ve embeddings modelini arka planda yükle."""
    print("📚 Intent verileri yükleniyor...")
    try:
        await asyncio.to_thread(load_intent_data)
        print("✅ Intent verileri yüklendi.")
    except Exception as e:
        print(f"❌ Intent yükleme hatası: {e}")
        raise


async def _load_device_registry() -> None:
    """Cihaz katalog veritabanını arka planda yükle."""
    print("🔧 Cihaz veritabanı yükleniyor...")
    try:
        await asyncio.to_thread(initialize_device_db)
        print("✅ Cihaz veritabanı yüklendi.")
    except Exception as e:
        print(f"❌ Cihaz veritabanı yükleme hatası: {e}")
        raise


async def _load_menu_data() -> None:
    """Günlük yemek listesini hızlı şekilde yükle."""
    print("🍽️  Yemek listesi güncelleniyor...")
    try:
        await asyncio.to_thread(update_system_data_fast)
        print("✅ Yemek listesi güncellendi.")
    except Exception as e:
        print(f"❌ Yemek listesi güncelleme hatası: {e}")
        raise


def _setup_scheduled_jobs() -> None:
    """
    APScheduler'da periyodik background job'larını ayarla.

    Jobs:
      - update_device_database: Her 24 saatte bir (Selenium scraper)
      - update_system_data: Her 6 saatte bir (Takvim + Yemek)
    """
    try:
        scheduler.add_job(
            update_device_database,
            'interval',
            hours=24,
            id='update_devices'
        )
        scheduler.add_job(
            update_system_data,
            'interval',
            hours=6,
            id='update_system_data'
        )
        scheduler.start()
        print("⏰ Otomatik güncelleme zamanlayıcıları başlatıldı:")
        print("   - Cihazlar: Her 24 saatte")
        print("   - Web Verileri: Her 6 saatte")
    except Exception as e:
        print(f"❌ Scheduler başlatma hatası: {e}")


async def _background_initialization() -> None:
    """
    Tüm ağır initialization işlemlerini arka planda paralel yap.

    Sıra:
      1. NLP motorunu yükle
      2. Intent verilerini yükle
      3. Cihaz veritabanını yükle
      4. Yemek listesini güncelle
      5. Scheduler'ı başlat
    """
    try:
        await _load_nlp_module()
        await _load_intent_data_module()
        await _load_device_registry()
        await _load_menu_data()
        _setup_scheduled_jobs()
    except Exception as e:
        print(f"❌ Background initialization hatası: {e}")


# ============================================================================
# APPLICATION LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event() -> None:
    """
    FastAPI startup event handler.

    İşlemler:
      - Hızlı health check için STARTUP_COMPLETE = True ayarla
      - Ağır işlemleri arka planda başlat (non-blocking)
    """
    global STARTUP_COMPLETE

    print("⚡ App başlatıldı (background loading devam ediyor)...")
    asyncio.create_task(_background_initialization())
    STARTUP_COMPLETE = True


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """
    FastAPI shutdown event handler.

    İşlemler:
      - APScheduler'ı düzgün şekilde kapat
    """
    try:
        scheduler.shutdown()
        print("✅ Scheduler kapatıldı.")
    except Exception as e:
        print(f"⚠️  Scheduler kapatma hatası: {e}")


# ============================================================================
# ROUTE REGISTRATION
# ============================================================================

app.include_router(
    chat_router.router,
    prefix="/api",
    tags=["chat"]
)


# ============================================================================
# HEALTH & INFO ENDPOINTS
# ============================================================================

@app.get("/", tags=["info"])
def read_root() -> dict:
    """
    Kök endpoint - proje bilgisini döndür.

    Returns:
        dict: Proje adı ve açıklaması
    """
    return {
        "Proje": "AÇÜ Hibrit Sohbet Robotu API",
        "Versiyon": "1.0.0",
        "Durum": "Hazır"
    }


@app.get("/health", tags=["health"])
def health_check() -> dict:
    """
    Health check endpoint.

    Returns:
        dict: Sistem durumu ve configuration bilgileri
    """
    use_embeddings: bool = (
        os.getenv("USE_EMBEDDINGS", "false").lower() == "true"
    )

    return {
        "status": "ok",
        "startup_complete": STARTUP_COMPLETE,
        "use_embeddings": use_embeddings
    }