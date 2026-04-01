# AÇÜ Chatbot

Artvin Çoruh Üniversitesi için yapay zeka destekli chatbot — Bitirme Projesi.

## 📋 Ön Gereksinimler

- **Python 3.11+**
- **Java (OpenJDK 21)** — Zemberek NLP kütüphanesi için
- **Node.js 18+** — Frontend geliştirme için
- **Docker** — Container ile çalıştırmak isteyenler için

## 🚀 Kurulum

### 1. Projeyi Klonlayın / Güncelleyin

```bash
git clone https://github.com/<user>/acu-chatbot.git
cd acu-chatbot
# veya mevcut klonu güncelle:
git pull
```

### 2. Backend

```bash
cd backend

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
```

### 3. Backend Environment Variables

`backend/.env` dosyası oluşturun (git'e dahil değildir):

```bash
cp backend/.env.example backend/.env
```

veya manuel:

```dotenv
GOOGLE_API_KEY=senin_api_keyin
ENVIRONMENT=development
USE_EMBEDDINGS=true
LOG_LEVEL=INFO
```

### 4. Backend'i Çalıştır

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend `http://localhost:8000` adresinde çalışacak.  
API dökümantasyonu: `http://localhost:8000/docs`

### 5. Frontend

```bash
cd frontend
npm install
```

`frontend/.env` dosyası (gerekirse):

```dotenv
REACT_APP_BACKEND_URL=http://localhost:8000
```

```bash
npm start
```

Frontend `http://localhost:3000` adresinde açılacak.

## 🐳 Docker ile Çalıştırma

```bash
docker build -t acu-chatbot .
docker run -p 8080:8080 \
  -e GOOGLE_API_KEY=senin_api_keyin \
  -e USE_EMBEDDINGS=true \
  acu-chatbot
```

Backend `http://localhost:8080` adresinde çalışacak.

## ☁️ DigitalOcean App Platform

Proje `app.yaml` üzerinden DigitalOcean App Platform'a otomatik deploy edilir.  
GitHub `main` branch'ine push yapıldığında auto-deploy tetiklenir.

Environment variable'lar DigitalOcean dashboard'undan yönetilir.

## 🔧 Environment Variables

### Backend (`backend/.env`)

| Değişken | Açıklama | Zorunlu |
|----------|----------|---------|
| `GOOGLE_API_KEY` | Gemini API key | Hayır (fallback var) |
| `ENVIRONMENT` | `development` veya `production` | Hayır |
| `USE_EMBEDDINGS` | Semantic similarity embeddings | Hayır (varsayılan: `true`) |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR` | Hayır |
| `GEMINI_MODEL` | Gemini model adı | Hayır |
| `ALLOWED_ORIGINS` | CORS origin'leri (virgülle ayrılmış) | Hayır |
| `ADMIN_SECRET_TOKEN` | Admin endpoint token | Hayır |
| `OPENWEATHER_API_KEY` | Hava durumu API key | Hayır |
| `SENTRY_DSN` | Sentry DSN | Hayır |
| `REDIS_URL` | Redis bağlantı URL'i | Hayır |

### Frontend (`frontend/.env`)

| Değişken | Açıklama | Zorunlu |
|----------|----------|---------|
| `REACT_APP_BACKEND_URL` | Backend API URL'i | Hayır (varsayılan: `http://localhost:8000`) |
