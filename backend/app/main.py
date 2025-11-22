# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware # <-- İŞTE BU SATIR EKSİKTİ
from .api.endpoints import chat as chat_router
from .core.classifier import load_intent_data
from apscheduler.schedulers.asyncio import AsyncIOScheduler # <-- YENİ
from .services.device_registry import initialize_device_db, update_device_database

app = FastAPI()

# --- CORS AYARLARI ---
# Frontend'in (React) Backend'e erişmesine izin veriyoruz
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Geliştirme aşamasında tüm kaynaklara izin ver
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ---------------------

scheduler = AsyncIOScheduler()

@app.on_event("startup")
async def startup_event():
    """Uygulama başlarken yapılacaklar."""
    
    # 1. Niyetleri Yükle (Mevcut kodunuz)
    load_intent_data()
    
    # 2. Cihazları Yükle (Varsa diskten, yoksa tara)
    # initialize_device_db senkron olduğu için direkt çağırabiliriz
    initialize_device_db()
    
    # 3. Rutin Güncellemeyi Başlat (Örn: Her 24 saatte bir)
    # Bu işlem arka planda çalışır, sunucuyu kilitlemez.
    scheduler.add_job(update_device_database, 'interval', hours=24)
    scheduler.start()
    print("⏰ Otomatik veri güncelleme zamanlayıcısı başlatıldı (24 saatte bir).")

@app.on_event("shutdown")
async def shutdown_event():
    scheduler.shutdown()

@app.on_event("startup")
def startup_event():
    """Uygulama başlarken Niyet Verisini hafızaya yükle."""
    load_intent_data()

# API endpoint'lerini dahil et
app.include_router(chat_router.router, prefix="/api")

@app.get("/")
def read_root():
    return {"Proje": "AÇÜ Hibrit Sohbet Robotu API - Hazır"}