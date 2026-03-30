# ============================================================================
# backend/app/main.py - FastAPI Ana Uygulama
# ============================================================================

import asyncio
import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .config import settings
from .api.endpoints import chat as chat_router
from .api.endpoints import analytics as analytics_router
from .api.endpoints import admin_intents as admin_intents_router
from .core.classifier import load_intent_data
from .core.limiter import limiter, llm_limiter
from .services.device_registry import initialize_device_db, update_device_database
from .services.session_store import init_db as init_session_db, prune_old_sessions
from .services.web_scraper.manager import update_system_data_fast, update_system_data


def _configure_logging() -> logging.Logger:
    """Ortama göre logging formatını yapılandır ve ana logger'ı döndür."""
    log_level = settings.log_level.upper()
    environment = settings.environment

    if environment == "production":
        logging.basicConfig(
            level=log_level,
            format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    else:
        logging.basicConfig(
            level=log_level,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )

    logger_ = logging.getLogger(__name__)

    sentry_dsn = settings.sentry_dsn
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            traces_sample_rate=0.2,
            profiles_sample_rate=0.1,
            send_default_pii=False,
        )
        logger_.info("Sentry hata izleme aktif.")

    return logger_


logger = _configure_logging()


# ============================================================================
# GLOBAL STATE
# ============================================================================

scheduler: AsyncIOScheduler = AsyncIOScheduler()


# ============================================================================
# BACKGROUND INITIALIZATION
# ============================================================================

async def _load_nlp_module() -> None:
    logger.info("NLP motoru yukleniyor...")
    from .core.nlp import get_morphology
    await asyncio.to_thread(get_morphology)
    logger.info("NLP motoru yuklendi.")


async def _load_intent_data_module() -> None:
    logger.info("Intent verileri yukleniyor...")
    await asyncio.to_thread(load_intent_data)
    logger.info("Intent verileri yuklendi.")


async def _load_device_registry() -> None:
    logger.info("Cihaz veritabani yukleniyor...")
    await asyncio.to_thread(initialize_device_db)
    logger.info("Cihaz veritabani yuklendi.")


async def _load_menu_data() -> None:
    logger.info("Yemek listesi guncelleniyor...")
    await asyncio.to_thread(update_system_data_fast)
    logger.info("Yemek listesi guncellendi.")


def _setup_scheduled_jobs() -> None:
    scheduler.add_job(update_device_database, 'interval', hours=24, id='update_devices')
    scheduler.add_job(update_system_data, 'interval', hours=6, id='update_system_data')
    scheduler.add_job(prune_old_sessions, 'interval', hours=24, id='prune_sessions')
    scheduler.start()
    logger.info("Zamanlayicilar baslatildi: Cihazlar 24h, Web verileri 6h, Session temizleme 24h")


async def _background_initialization() -> None:
    """
    Startup'ta agir initialization'i arka planda yap.
    NLP + Intent siralı (bagimli), ardindan Cihaz + Yemek paralel.
    """
    try:
        init_session_db()
        await _load_nlp_module()
        await _load_intent_data_module()
        await asyncio.gather(
            _load_device_registry(),
            _load_menu_data(),
        )
        _setup_scheduled_jobs()
    except Exception as e:
        logger.error(f"Background initialization hatasi: {e}", exc_info=True)


# ============================================================================
# LIFESPAN (FastAPI 0.93+ önerilen yöntem — on_event deprecated)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Uygulama baslatildi, background yukleme devam ediyor...")
    asyncio.create_task(_background_initialization())
    yield
    try:
        scheduler.shutdown()
        logger.info("Scheduler kapatildi.")
    except Exception as e:
        logger.error(f"Scheduler kapatma hatasi: {e}")


# ============================================================================
# APP INITIALIZATION
# ============================================================================

app: FastAPI = FastAPI(
    title="AÇÜ Chatbot API",
    description="Artvin Çoruh Üniversitesi Asistan Chatbotu",
    version="1.1.0",
    lifespan=lifespan
)

# Rate limiting — hem genel hem LLM limiteri exception handler ile kayıt altına al
app.state.limiter = limiter
app.state.llm_limiter = llm_limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
)


# ============================================================================
# ROUTES
# ============================================================================

app.include_router(chat_router.router, prefix="/api", tags=["chat"])
app.include_router(analytics_router.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(admin_intents_router.router, prefix="/api/admin", tags=["admin-intents"])


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
    from .core.classifier import INTENTS_DATA as _intents, MODEL as _model
    from .services.device_registry import DEVICE_DB as _devices
    from .core.nlp import MORPHOLOGY as _morph, ZEMBEREK_AVAILABLE as _zemb
    from .services.llm_client import GOOGLE_API_KEY as _gkey
    from .config import settings as _settings
    return {
        "status": "ok",
        "version": "1.1.0",
        "components": {
            "nlp": _morph is not None or not _zemb,
            "embeddings": _model is not None,
            "intents_loaded": len(_intents),
            "devices_loaded": len(_devices),
            "gemini_configured": bool(_gkey),
            "zemberek_available": _zemb,
        },
        "use_embeddings": _settings.use_embeddings,
    }
