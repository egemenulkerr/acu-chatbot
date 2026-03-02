# chatbot-uni

Graduation project – simple full-stack chatbot demo.

## 📋 Ön Gereksinimler

**Tek seferlik kurulumlar (yeni bilgisayarda):**

- **Python 3.11+** (backend için)
- **Java (OpenJDK 21)** - Zemberek NLP kütüphanesi için gerekli
- **Node.js 18+** (frontend için)

Bu araçlar kuruluysa devam edebilirsiniz.

## 🚀 Kurulum Adımları

### 1. Projeyi İndirin

```bash
git pull
```

### 2. Backend Kurulumu

```bash
cd backend

# Virtual environment oluştur (ilk kurulumda)
python -m venv .venv

# Virtual environment'ı aktifleştir
# Linux/Mac:
source .venv/bin/activate
# Windows:
# .venv\Scripts\activate

# Bağımlılıkları yükle
pip install -r requirements.txt
```

### 3. Backend Environment Variables

`.env` dosyası git'te yok, elle oluşturmanız gerekiyor:

**Yöntem 1:** `.env.example` dosyasını kopyalayın:
```bash
cp backend/.env.example backend/.env
```

**Yöntem 2:** Manuel olarak `backend/.env` dosyasını oluşturun:

```bash
GOOGLE_API_KEY=senin_api_keyin
ENVIRONMENT=development
USE_EMBEDDINGS=true
LOG_LEVEL=INFO
```

Sonra dosyayı düzenleyip `GOOGLE_API_KEY` değerini kendi API key'inizle değiştirin.

**Opsiyonel değişkenler:**
- `GEMINI_MODEL` - Model adı, varsayılan: `gemini-1.5-flash`
- `ALLOWED_ORIGINS` - CORS için izin verilen origin'ler (virgülle ayrılmış)
- `ADMIN_SECRET_TOKEN` - `/api/update-data` endpoint'i için admin token
- `OPENWEATHER_API_KEY` - Hava durumu servisi için (opsiyonel)
- `SENTRY_DSN` - Hata izleme için Sentry DSN (opsiyonel)

**Not:** API key yoksa backend rule-based intent classifier'a geri döner.

### 4. Backend'i Çalıştır

```bash
# Development modu (hot reload ile)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Veya root dizinden:
uvicorn backend.main:app --reload
```

Backend `http://localhost:8000` adresinde çalışacak.

### 5. Frontend Kurulumu

```bash
cd frontend

# Bağımlılıkları yükle (node_modules git'te yok)
npm install
```

### 6. Frontend Environment Variables

`.env` dosyası git'te yok, elle oluşturmanız gerekiyor:

**Yöntem 1:** `.env.example` dosyasını kopyalayın:
```bash
cp frontend/chatbot-arayuzu/.env.example frontend/chatbot-arayuzu/.env
```

**Yöntem 2:** Manuel olarak `frontend/chatbot-arayuzu/.env` dosyasını oluşturun:

```bash
REACT_APP_BACKEND_URL=http://localhost:8000
```

**Production için:**
```bash
REACT_APP_BACKEND_URL=https://your-backend-url.com
```

### 7. Frontend'i Çalıştır

```bash
npm start
```

Frontend `http://localhost:3000` adresinde açılacak.

## 📝 Hızlı Kurulum Özeti

Mevcut bir bilgisayarda (ön gereksinimler kuruluysa):

```bash
# 1. Projeyi güncelle
git pull

# 2. Backend
cd backend
pip install -r requirements.txt
cp .env.example .env  # .env dosyasını oluştur ve düzenle

# 3. Frontend
cd ../frontend
npm install
cp chatbot-arayuzu/.env.example chatbot-arayuzu/.env  # .env dosyasını oluştur
```

## 🔧 Environment Variables Detayları

### Backend (`backend/.env`)

| Değişken | Açıklama | Zorunlu |
|----------|----------|---------|
| `GOOGLE_API_KEY` | Google AI Studio / Gemini API key | Hayır (fallback var) |
| `ENVIRONMENT` | `development` veya `production` | Hayır |
| `USE_EMBEDDINGS` | Semantic similarity için embeddings kullan | Hayır (varsayılan: `true`) |
| `LOG_LEVEL` | Log seviyesi (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | Hayır |
| `GEMINI_MODEL` | Gemini model adı | Hayır |
| `ALLOWED_ORIGINS` | CORS için izin verilen origin'ler | Hayır |
| `ADMIN_SECRET_TOKEN` | Admin endpoint için token | Hayır |
| `OPENWEATHER_API_KEY` | Hava durumu API key | Hayır |
| `SENTRY_DSN` | Sentry hata izleme DSN | Hayır |

### Frontend (`frontend/.env`)

| Değişken | Açıklama | Zorunlu |
|----------|----------|---------|
| `REACT_APP_BACKEND_URL` | Backend API URL'i | Hayır (varsayılan: `http://localhost:8000`) |

## 🐳 Docker ile Çalıştırma

```bash
docker-compose up
```

Backend `http://localhost:8080` adresinde çalışacak.

## 📚 Daha Fazla Bilgi

- Production deployment için: `DEPLOYMENT.md`
- Backend API dokümantasyonu: `http://localhost:8000/docs` (çalışırken)
