from fastapi import FastAPI
from .api.endpoints import chat as chat_router
from .core.classifier import load_intent_data

app = FastAPI()

@app.on_event("startup")
def startup_event():
    """Uygulama başlarken Niyet Verisini hafızaya yükle."""
    load_intent_data()

# API endpoint'lerini app/api/endpoints/chat.py dosyasından dahil et
app.include_router(chat_router.router, prefix="/api")

@app.get("/")
def read_root():
    return {"Proje": "AÇÜ Hibrit Sohbet Robotu API - Final Test"}