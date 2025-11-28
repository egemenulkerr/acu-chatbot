# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .api.endpoints import chat as chat_router
from .core.classifier import load_intent_data
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from .services.device_registry import initialize_device_db, update_device_database
from .services.web_scraper.manager import update_system_data_fast, update_system_data
import asyncio

app = FastAPI()

# --- CORS AYARLARI ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://egemenulker.com",
        "https://www.egemenulker.com",
        "https://king-prawn-app-t5y4u.ondigitalocean.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
)

scheduler = AsyncIOScheduler()
STARTUP_COMPLETE = False


@app.on_event("startup")
async def startup_event():
    """Uygulama başlarken yapılacaklar.

    Ağır yüklenen bileşenleri (model, Zemberek, cihaz verisi) ARKA PLANDA yüklüyoruz.
    Sağlık kontrolü hemen başarılı olur.
    """
    global STARTUP_COMPLETE
    
    # Hızlı başlatma: health check'i hemen açık tut
    print("⚡ App başlatıldı (background loading devam ediyor)...")
    
    # Ağır işlemleri background task olarak başlat
    asyncio.create_task(_background_initialization())
    
    STARTUP_COMPLETE = True


async def _background_initialization():
    """Ağır initialization işlemlerini arka planda yap."""
    try:
        # 0) Zemberek'i yükle (JVM başlatma - ilk kez uzun sürer)
        print("⚙️ NLP motorunu yükleniyor (Zemberek JVM)...")
        from .core.nlp import get_morphology
        await asyncio.to_thread(get_morphology)
        print("✅ NLP motoru başarıyla yüklendi.")

        # 1) Intent verilerini yükle
        print("📚 Intent verileri ve modeller yükleniyor...")
        await asyncio.to_thread(load_intent_data)

        # 2) Cihaz veritabanını yükle
        print("🔧 Cihaz veritabanı yükleniyor...")
        await asyncio.to_thread(initialize_device_db)

        # 3) Yemek verilerini güncelle
        print("🍽️ Yemek listesi güncelleniyor...")
        await asyncio.to_thread(update_system_data_fast)

        # 4) Rutin güncelleme zamanlayıcılarını başlat
        try:
            # Cihazları her 24 saatte bir güncelle
            scheduler.add_job(update_device_database, 'interval', hours=24)
            # Web verilerini (yemek, takvim) her 6 saatte bir güncelle - FULL
            scheduler.add_job(update_system_data, 'interval', hours=6)
            scheduler.start()
            print("⏰ Otomatik veri güncelleme zamanlayıcıları başlatıldı.")
            print("   - Cihazlar: 24 saatte bir")
            print("   - Web Verileri (yemek, takvim): 6 saatte bir")
        except Exception as e:
            print(f"Zamanlayıcı başlatılırken hata: {e}")
    except Exception as e:
        print(f"Background initialization hatası: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    try:
        scheduler.shutdown()
    except Exception:
        pass


# API endpoint'lerini dahil et
app.include_router(chat_router.router, prefix="/api")


@app.get("/")
def read_root():
    return {"Proje": "AÇÜ Hibrit Sohbet Robotu API - Hazır"}


@app.get("/health")
def health_check():
    """Hızlı health check - başlatma tamamlanmamış olsa da OK döner."""
    return {"status": "ok", "startup_complete": STARTUP_COMPLETE}