# ============================================================================
# backend/app/main.py - FastAPI Ana Uygulama
# ============================================================================

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .api.endpoints import chat as chat_router
from .core.classifier import load_intent_data
from .core.limiter import limiter
from .services.device_registry import initialize_device_db, update_device_database
from .services.web_scraper.manager import update_system_data_fast, update_system_data


# ============================================================================
# GLOBAL STATE
# ============================================================================

scheduler: AsyncIOScheduler = AsyncIOScheduler()


# ============================================================================
# BACKGROUND INITIALIZATION
# ============================================================================

async def _load_nlp_module() -> None:
    print("⚙️  NLP motoru yükleniyor (Zemberek JVM)...")
    from .core.nlp import get_morphology
    await asyncio.to_thread(get_morphology)
    print("✅ NLP motoru yüklendi.")


async def _load_intent_data_module() -> None:
    print("📚 Intent verileri yükleniyor...")
    await asyncio.to_thread(load_intent_data)
    print("✅ Intent verileri yüklendi.")


async def _load_device_registry() -> None:
    print("🔧 Cihaz veritabanı yükleniyor...")
    await asyncio.to_thread(initialize_device_db)
    print("✅ Cihaz veritabanı yüklendi.")


async def _load_menu_data() -> None:
    print("🍽️  Yemek listesi güncelleniyor...")
    await asyncio.to_thread(update_system_data_fast)
    print("✅ Yemek listesi güncellendi.")


def _setup_scheduled_jobs() -> None:
    scheduler.add_job(update_device_database, 'interval', hours=24, id='update_devices')
    scheduler.add_job(update_system_data, 'interval', hours=6, id='update_system_data')
    scheduler.start()
    print("⏰ Zamanlayıcılar başlatıldı: Cihazlar 24h, Web verileri 6h")


async def _background_initialization() -> None:
    """
    Startup'ta ağır initialization'ı arka planda yap.
    NLP + Intent sıralı (bağımlı), ardından Cihaz + Yemek paralel.
    """
    try:
        await _load_nlp_module()
        await _load_intent_data_module()
        # Cihaz ve yemek birbirinden bağımsız — paralel çalıştır
        await asyncio.gather(
            _load_device_registry(),
            _load_menu_data(),
        )
        _setup_scheduled_jobs()
    except Exception as e:
        print(f"❌ Background initialization hatası: {e}")


# ============================================================================
# LIFESPAN (FastAPI 0.93+ önerilen yöntem — on_event deprecated)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("⚡ Uygulama başlatıldı, background yükleme devam ediyor...")
    asyncio.create_task(_background_initialization())
    yield
    # Shutdown
    try:
        scheduler.shutdown()
        print("✅ Scheduler kapatıldı.")
    except Exception as e:
        print(f"⚠️  Scheduler kapatma hatası: {e}")


# ============================================================================
# APP INITIALIZATION
# ============================================================================

app: FastAPI = FastAPI(
    title="AÇÜ Chatbot API",
    description="Artvin Çoruh Üniversitesi Asistan Chatbotu",
    version="1.1.0",
    lifespan=lifespan
)

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
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
# ROUTES
# ============================================================================

app.include_router(chat_router.router, prefix="/api", tags=["chat"])


# ============================================================================
# HEALTH & INFO
# ============================================================================

@app.get("/", tags=["info"])
def read_root() -> dict:
    return {
        "proje": "AÇÜ Hibrit Sohbet Robotu API",
        "versiyon": "1.1.0",
        "durum": "Hazır"
    }


@app.get("/health", tags=["health"])
def health_check() -> dict:
    return {
        "status": "ok",
        "use_embeddings": os.getenv("USE_EMBEDDINGS", "false").lower() == "true"
    }
