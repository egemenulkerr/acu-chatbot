# ============================================================================
# backend/app/main.py - FastAPI Ana Uygulama
# ============================================================================

import asyncio
import logging
import os
import re
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded


# ============================================================================
# LOGGING SETUP — production'da JSON formatında, development'ta okunabilir
# ============================================================================

_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

if _ENVIRONMENT == "production":
    logging.basicConfig(
        level=_LOG_LEVEL,
        format='{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
else:
    logging.basicConfig(
        level=_LOG_LEVEL,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

logger = logging.getLogger(__name__)


# ============================================================================
# SENTRY — SENTRY_DSN env var varsa aktif et
# ============================================================================

_SENTRY_DSN = os.getenv("SENTRY_DSN", "")
if _SENTRY_DSN:
    sentry_sdk.init(
        dsn=_SENTRY_DSN,
        traces_sample_rate=0.2,
        profiles_sample_rate=0.1,
        send_default_pii=False,
    )
    logger.info("Sentry hata izleme aktif.")


from .api.endpoints import chat as chat_router
from .api.endpoints import analytics as analytics_router
from .core.classifier import load_intent_data
from .core.limiter import limiter, llm_limiter
from .services.device_registry import initialize_device_db, update_device_database
from .services.session_store import init_db as init_session_db, prune_old_sessions
from .services.web_scraper.manager import update_system_data_fast, update_system_data


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
    Kritik bileşenleri (session DB, NLP, intent + model) yükler.

    Bu fonksiyon lifespan içinde **await** edilerek çağrılır; uygulama istek kabul
    etmeye başlamadan önce en azından intent verisi ve (etkinse) embedding modeli
    hazır olur. Böylece /health ve ilk istekler "boş" global state görmez.
    """
    from .core.classifier import INTENTS_DATA, MODEL
    try:
        init_session_db()
        await _load_nlp_module()
        await _load_intent_data_module()
        intents_count = len(INTENTS_DATA)
        has_model = MODEL is not None
        logger.info(
            "Kritik baslangic tamamlandi: intents=%s, embeddings=%s",
            intents_count,
            has_model,
        )
    except Exception as e:
        logger.error("Kritik baslangic hatasi: %s", e, exc_info=True)


async def _post_startup_initialization() -> None:
    """
    Cihaz veritabanı, yemek listesi ve zamanlayıcıları arka planda hazırlar.

    Bu fonksiyon lifespan içinde, kritik başlangıç tamamlandıktan sonra
    `asyncio.create_task` ile tetiklenir; böylece ağır olmayan ama isteğe
    bağımlı olmayan işler uygulama çalışırken tamamlanır.
    """
    from .services.device_registry import DEVICE_DB

    try:
        await asyncio.gather(
            _load_device_registry(),
            _load_menu_data(),
        )
        _setup_scheduled_jobs()
        devices_count = len(DEVICE_DB)
        logger.info(
            "Arka plan baslangici tamamlandi: devices=%s",
            devices_count,
        )
    except Exception as e:
        logger.error("Arka plan baslangic hatasi: %s", e, exc_info=True)


# ============================================================================
# LIFESPAN (FastAPI 0.93+ önerilen yöntem — on_event deprecated)
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Uygulama baslatiliyor; kritik bilesenler yukleniyor (NLP + intent + model)...")
    await _background_initialization()
    logger.info("Kritik bilesenler yüklendi; istekler kabul ediliyor. Cihaz/yemek arka planda yuklenecek.")
    asyncio.create_task(_post_startup_initialization())
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

# CORS — ALLOWED_ORIGINS env var'dan okunur (virgülle ayrılmış liste).
# Env var yoksa geliştirme ortamı için varsayılan değerler kullanılır.
_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "")
ALLOWED_ORIGINS: list[str] = (
    [o.strip() for o in _ORIGINS_ENV.split(",") if o.strip()]
    if _ORIGINS_ENV
    else [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://egemenulker.com",
        "https://www.egemenulker.com",
        "https://king-prawn-app-t5y4u.ondigitalocean.app",
    ]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
)

# DigitalOcean App Platform: *.ondigitalocean.app origin'lerini de kabul et (CORS).
_DO_ORIGIN_RE = re.compile(r"^https://[a-z0-9-]+\.ondigitalocean\.app$", re.I)


class _DOCorsMiddleware:
    """Starlette uyumlu sınıf: *.ondigitalocean.app origin'lerine CORS header ekler."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        origin = None
        if scope.get("type") == "http":
            for name, value in scope.get("headers", []):
                if name == b"origin":
                    origin = value.decode()
                    break

        if (
            scope.get("type") == "http"
            and scope.get("method") == "OPTIONS"
            and origin
            and _DO_ORIGIN_RE.fullmatch(origin)
        ):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"access-control-allow-origin", origin.encode()),
                    (b"access-control-allow-methods", b"GET, POST, PUT, DELETE, OPTIONS"),
                    (b"access-control-allow-headers", b"*"),
                    (b"access-control-allow-credentials", b"true"),
                    (b"access-control-max-age", b"86400"),
                ],
            })
            await send({"type": "http.response.body", "body": b""})
            return

        async def send_wrapper(message):
            if (
                message.get("type") == "http.response.start"
                and origin
                and _DO_ORIGIN_RE.fullmatch(origin)
            ):
                headers = list(message.get("headers", []))
                if not any(h[0].lower() == b"access-control-allow-origin" for h in headers):
                    headers.append((b"access-control-allow-origin", origin.encode()))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)


app.add_middleware(_DOCorsMiddleware)


# ============================================================================
# ROUTES
# ============================================================================

app.include_router(chat_router.router, prefix="/api", tags=["chat"])
app.include_router(analytics_router.router, prefix="/api/analytics", tags=["analytics"])


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
    """
    Her zaman 200 döner; frontend 'çevrimiçi' sadece backend erişilebilir olduğunda gösterilir.
    Bileşenler (Gemini, NLP vb.) hazır olmasa bile 200 dönülür — aksi halde 500 olur ve
    kullanıcı sürekli 'çevrimdışı' görür.
    """
    out = {
        "status": "ok",
        "version": "1.1.0",
        "components": {
            "nlp": False,
            "embeddings": False,
            "intents_loaded": 0,
            "devices_loaded": 0,
            "gemini_configured": False,
            "zemberek_available": False,
        },
        "use_embeddings": os.getenv("USE_EMBEDDINGS", "true").lower() == "true",
    }
    try:
        from .core.classifier import INTENTS_DATA as _intents, MODEL as _model
        out["components"]["intents_loaded"] = len(_intents)
        out["components"]["embeddings"] = _model is not None
    except Exception:
        pass
    try:
        from .services.device_registry import DEVICE_DB as _devices
        out["components"]["devices_loaded"] = len(_devices)
    except Exception:
        pass
    try:
        from .core.nlp import MORPHOLOGY as _morph, ZEMBEREK_AVAILABLE as _zemb
        out["components"]["nlp"] = _morph is not None or not _zemb
        out["components"]["zemberek_available"] = _zemb
    except Exception:
        pass
    try:
        from .services.llm_client import GOOGLE_API_KEY as _gkey
        out["components"]["gemini_configured"] = bool(_gkey)
    except Exception:
        pass
    return out
