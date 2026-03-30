# AÇÜ Chatbot — Proje teknoloji ve altyapı envanteri

Bu belge, repodaki dosyalara ve yapılandırmaya dayanarak projede kullanılan yazılımlar, harici servisler ve dağıtım akışını özetler. **Repoda adı geçmeyen** barındırıcılar (ör. Guzal Hosting) için yalnızca mimari olarak nereye oturdukları not edilmiştir.

---

## 1. Genel mimari

| Katman | Rol | Nerede barınır (yapılandırmaya göre) |
|--------|-----|--------------------------------------|
| **Frontend** | React tek sayfa uygulaması (sohbet arayüzü) | Üretimde `https://egemenulker.com/chatbot/` (`package.json` → `homepage`) |
| **Backend API** | FastAPI (REST, sohbet, analytics, admin) | DigitalOcean App Platform (`*.ondigitalocean.app`) |
| **Kaynak kod** | Git | GitHub: `egemenulkerr/acu-chatbot`, dal: `main` |
| **Otomatik dağıtım** | Push sonrası yeniden derleme | DigitalOcean `deploy_on_push: true` (`app.yaml`) |

Frontend tarayıcıdan doğrudan backend URL’ine (`REACT_APP_BACKEND_URL`) istek atar; CORS, backend’de `ALLOWED_ORIGINS` ile tanımlı origin’lere göre açılır.

---

## 2. Frontend teknolojileri

| Bileşen | Açıklama |
|---------|----------|
| **Çatı** | Create React App (`react-scripts` 5.x) |
| **UI kütüphanesi** | React 19, React DOM 19 |
| **Test** | Jest (CRA ile), Testing Library (`@testing-library/react`, `jest-dom`, `user-event`) |
| **Diğer** | `web-vitals` |
| **Ortam değişkeni** | `REACT_APP_BACKEND_URL` — backend API tabanı (ör. `frontend/.env.production` içinde DigitalOcean URL’i) |
| **Statik varlıklar** | `frontend/public/` — örn. `chatbot-widget.js`, `widget-embed.html` (ana sitede gömülü widget senaryosu) |

**Not:** `chatbot-arayuzu` klasörü README’de eski/alternatif `.env` yolu olarak geçer; asıl `package.json` `frontend/` kökündedir.

---

## 3. Backend teknolojileri

| Bileşen | Açıklama |
|---------|----------|
| **Dil / runtime** | Python 3.11 |
| **Web çatısı** | FastAPI |
| **ASGI sunucu** | Uvicorn |
| **Veri doğrulama / ayar** | Pydantic v2, pydantic-settings, python-dotenv |
| **Sınırlandırma** | slowapi (rate limit) |
| **Zamanlanmış işler** | APScheduler (ör. cihaz güncelleme, web verisi, session temizliği) |
| **NLP (Türkçe morfoloji)** | zemberek-python — **Java 21 JRE** gerektirir (Docker ve yerel kurulum) |
| **Anlamsal benzerlik (embedding)** | fastembed (ONNX), model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` |
| **LLM** | Google Generative AI SDK (`google-generativeai`) — Gemini (ör. `gemini-1.5-flash`) |
| **Web kazıma (scraping)** | Selenium, BeautifulSoup4; Firefox ESR + GeckoDriver (`backend/Dockerfile` içinde) |
| **HTTP istemcisi** | requests, httpx |
| **Dayanıklılık** | tenacity |
| **Hata izleme (opsiyonel)** | sentry-sdk |
| **Önbellek (opsiyonel)** | redis (py) — `REDIS_URL` yoksa process içi önbellek |
| **Test** | pytest, pytest-asyncio, httpx |

---

## 4. Veri depolama (dosya / gömülü)

| Depo | Teknoloji / format | Konum (özet) |
|------|-------------------|--------------|
| Intent tanımları | JSON | `backend/app/data/intents.json` |
| Cihaz listesi | JSON | `backend/app/data/devices.json` |
| Konuşma geçmişi (sunucu tarafı) | **SQLite** | `backend/app/data/sessions.db` |
| Analytics log | **JSON Lines** | `backend/app/data/analytics.jsonl` |

PostgreSQL için `.env.example` içinde yorum satırı örneği vardır; mevcut uygulama akışı bu repoda **zorunlu Postgres** kullanmıyor.

---

## 5. Harici servisler ve API’ler

| Servis | Kullanım | Yapılandırma |
|--------|----------|--------------|
| **Google AI / Gemini** | Sohbet ve sınıflandırma yedekleri | `GOOGLE_API_KEY`, isteğe bağlı `GEMINI_MODEL` |
| **OpenWeather** | Hava durumu (opsiyonel intent) | `OPENWEATHER_API_KEY` |
| **Sentry** | Üretim hata raporlama | `SENTRY_DSN` |
| **Redis** | Dağıtık önbellek (opsiyonel) | `REDIS_URL` |
| **Hugging Face / model CDN** | fastembed model indirme | `backend/Dockerfile` build aşamasında warmup; `FASTEMBED_CACHE_PATH` |
| **Mozilla GeckoDriver** | Selenium için (tam backend imajı) | GitHub releases üzerinden indirme (`backend/Dockerfile`) |

---

## 6. GitHub

- **Repo:** `https://github.com/egemenulkerr/acu-chatbot`
- **Dal:** `main` (DigitalOcean ve `app.yaml` ile uyumlu)
- **CI:** Bu repoda **`.github/workflows`** altında tanımlı GitHub Actions iş akışı yok; kalite kontrolü yerelde `pytest` ve isteğe bağlı `python -m app.tools.validate_intents` ile yapılabilir.

---

## 7. DigitalOcean App Platform

- **Tanım dosyası:** Kök dizinde `app.yaml`
  - Uygulama adı: `acu-chatbot-backend`
  - **GitHub entegrasyonu:** `repo: egemenulkerr/acu-chatbot`, `branch: main`
  - **Autodeploy:** `deploy_on_push: true` → `main`’e push sonrası yeniden deploy
  - **Dockerfile:** Kök `Dockerfile` (`dockerfile_path: Dockerfile`)
  - **HTTP port:** 8080
  - **Health check:** `GET /health`
  - **Ortam:** `ALLOWED_ORIGINS` (egemenulker.com varyantları + örnek DO app URL), `ENVIRONMENT=production`, `LOG_LEVEL`, `USE_EMBEDDINGS`; `GOOGLE_API_KEY` secret olarak eklenmeli
- **Ek rehber:** `DEPLOYMENT.md` (adım adım DO kurulumu, loglar, rollback)

**Önemli:** Kök `Dockerfile` **Firefox/GeckoDriver içermez** (daha hafif imaj). Tam tarayıcı destekli imaj `backend/Dockerfile` içindedir; üretimde hangi dosyanın kullanıldığına göre Selenium tabanlı işler farklı davranabilir.

---

## 8. Docker ve yerel çalıştırma

| Dosya | Amaç |
|-------|------|
| `docker-compose.yml` | Backend’i `backend/Dockerfile` ile derleyip `8080`’e yayınlar |
| Kök `Dockerfile` | DO ve minimal üretim: Java 21 + Python bağımlılıkları, `backend/app` kopyalanır |
| `backend/Dockerfile` | Geliştirme/tam özellik: Firefox ESR, geckodriver, fastembed warmup, non-root kullanıcı |

---

## 9. Alan adı ve statik hosting (Guzal vb.)

Repoda **“Guzal”** veya **“Guzal Hosting”** metni geçmez. Yapılandırma şunu gösterir:

- Frontend üretim `homepage`: `https://egemenulker.com/chatbot/`
- CORS / origin listeleri: `egemenulker.com` (http/https, www dahil) ve DigitalOcean uygulama URL’leri
- Widget örnekleri: `egemenulker.com` üzerinden script/iframe kullanımı

**Sonuç:** Statik dosyalar (`npm run build` çıktısı) ve isteğe bağlı widget JS büyük ihtimalle **paylaşımlı hosting veya cPanel** (sizin tercih ettiğiniz Guzal Hosting gibi) üzerinde `public_html/.../chatbot/` altına yüklenir; bu adım repoda otomatikleştirilmemiştir — **manuel FTP/cPanel deploy** veya hosting sağlayıcınızın Git entegrasyonu ile yapılır.

---

## 10. API özeti (backend)

| Önek yol | Açıklama |
|----------|----------|
| `GET /` | API bilgisi |
| `GET /health` | Sağlık + bileşen durumu |
| `POST /api/chat` | Sohbet |
| `POST /api/chat/stream` | Akışlı yanıt |
| `POST /api/update-data` | Veri güncelleme (admin token) |
| `POST /api/feedback` | Geri bildirim |
| `GET /api/analytics/summary` | Analytics özeti |
| `GET /api/analytics/recent` | Son kayıtlar |
| `GET /api/analytics/intent/{intent_name}` | Intent bazlı (admin) |
| `GET /api/admin/intents` | Intent listesi (admin) |
| `GET /api/admin/intents/{intent_name}` | Tek intent (admin) |
| `POST /api/admin/debug/classify` | Sınıflandırma debug (admin) |
| `GET /docs` | OpenAPI (Swagger) |

Admin uçları `ADMIN_SECRET_TOKEN` ile korunur (`require_admin`).

---

## 11. Güvenlik ve gizlilik (kısa)

- API anahtarları ve admin token **git’e konmamalı**; `.env` / DO “App-Level Environment Variables” kullanılmalı.
- Rate limiting uygulanır (`slowapi`).
- Sentry açıksa hata raporları üçüncü tarafa gider (`send_default_pii=False` ile yapılandırılmış).

---

## 12. Belge ile repo senkronu

Bu envanter, repodaki şu kaynaklara dayanır: `README.md`, `DEPLOYMENT.md`, `app.yaml`, `docker-compose.yml`, kök ve `backend/Dockerfile`, `frontend/package.json`, `backend/requirements.txt`, `backend/app/config.py`, `backend/app/main.py`, `.env.example` dosyaları. Hosting sağlayıcı isimleri repoda yoksa burada **çıkarım / kullanıcı beyanı** olarak ayrıca belirtilmiştir.

---

*Son güncelleme: repo taraması ile oluşturulmuştur.*
