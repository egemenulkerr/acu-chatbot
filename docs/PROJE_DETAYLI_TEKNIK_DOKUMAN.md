# AÇÜ Chatbot — Detaylı Teknik Döküman

Bu döküman projenin tüm bileşenlerini, kullanılan teknolojileri, her dosyanın görevini ve kod örnekleriyle çalışma mantığını açıklar.

---

## 1. Proje Genel Bakış

AÇÜ Chatbot, Artvin Çoruh Üniversitesi öğrencilerine yemekhane menüsü, akademik takvim, OBS, hava durumu, laboratuvar cihazları gibi konularda hızlı bilgi sunan bir yapay zeka asistanıdır.

**Mimari:** React Frontend → FastAPI Backend → Gemini LLM + NLP + Web Scraper

```
[React Arayüz] ──HTTP/SSE──▶ [FastAPI Backend]
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              [Classifier]   [Web Scrapers]   [Gemini LLM]
              (Zemberek +    (Selenium +       (Google AI)
               FastEmbed)    BeautifulSoup)
```

---

## 2. Teknoloji Tablosu

| Teknoloji | Versiyon | Nerede | Ne İçin |
|-----------|----------|--------|---------|
| **Python** | 3.11 | Backend | Ana programlama dili |
| **FastAPI** | 0.120.2 | Backend | REST API framework |
| **Uvicorn** | 0.38.0 | Backend | ASGI web sunucusu |
| **Pydantic** | 2.12.3 | Backend | Veri doğrulama ve şema tanımlama |
| **pydantic-settings** | 2.6.1 | Backend | Environment variable yönetimi |
| **Google Generative AI** | 0.8.1 | Backend | Gemini LLM entegrasyonu |
| **Zemberek** | 0.2.3 | Backend | Türkçe morfolojik analiz (kelime kökü bulma) |
| **FastEmbed** | 0.5.1 | Backend | Semantik benzerlik için embedding modeli |
| **Selenium** | 4.x | Backend | Tarayıcı tabanlı web scraping (lab cihazları) |
| **BeautifulSoup4** | 4.12+ | Backend | HTML parsing (yemek, duyuru, haber) |
| **APScheduler** | 3.10+ | Backend | Zamanlanmış arka plan görevleri |
| **SlowAPI** | 0.1.9+ | Backend | Rate limiting (istek sınırlama) |
| **Sentry** | 1.40+ | Backend | Hata izleme ve raporlama |
| **Redis** | 5.0+ | Backend | Opsiyonel cache (yoksa in-memory dict) |
| **SQLite** | Dahili | Backend | Session geçmişi depolama |
| **OpenWeatherMap API** | — | Backend | Artvin hava durumu verisi |
| **React** | 19 | Frontend | Kullanıcı arayüzü |
| **Create React App** | 5 | Frontend | Build ve geliştirme toolchain |
| **Java JRE** | 21 | Docker | Zemberek kütüphanesi için JVM |
| **Docker** | — | Deploy | Container image oluşturma |
| **DigitalOcean App Platform** | — | Deploy | Production hosting ve auto-deploy |
| **GitHub** | — | VCS | Kaynak kodu yönetimi |

---

## 3. Proje Dizin Yapısı

```
acu-chatbot/
├── Dockerfile                    # Production Docker image
├── app.yaml                      # DigitalOcean App Platform konfigürasyonu
├── docs/                         # Dökümanlar
│
├── backend/
│   ├── requirements.txt          # Python bağımlılıkları
│   ├── app/
│   │   ├── main.py               # FastAPI uygulama başlangıç noktası
│   │   ├── config.py             # Merkezi konfigürasyon (env vars)
│   │   ├── security.py           # Admin kimlik doğrulama
│   │   │
│   │   ├── api/endpoints/
│   │   │   ├── chat.py           # Ana chat endpoint'i
│   │   │   ├── chat_device.py    # Cihaz arama akışı
│   │   │   ├── analytics.py      # Kullanım analitiği
│   │   │   └── admin_intents.py  # Admin intent yönetimi
│   │   │
│   │   ├── core/
│   │   │   ├── classifier.py     # Intent sınıflandırma motoru
│   │   │   ├── nlp.py            # Türkçe NLP (Zemberek)
│   │   │   └── limiter.py        # Rate limiting
│   │   │
│   │   ├── schemas/
│   │   │   └── chat.py           # Pydantic request/response modelleri
│   │   │
│   │   ├── services/
│   │   │   ├── llm_client.py     # Google Gemini API client
│   │   │   ├── weather.py        # Hava durumu servisi
│   │   │   ├── cache.py          # Redis / in-memory cache
│   │   │   ├── session_store.py  # SQLite session yönetimi
│   │   │   ├── device_registry.py# Lab cihaz katalogu
│   │   │   └── web_scraper/
│   │   │       ├── manager.py    # Scraper orkestratörü
│   │   │       ├── food_scrapper.py
│   │   │       ├── duyurular_scraper.py
│   │   │       ├── sks_scrapper.py
│   │   │       ├── main_site_scrapper.py
│   │   │       ├── library_site_scraper.py
│   │   │       ├── calendar_scraper.py
│   │   │       └── lab_scrapper.py
│   │   │
│   │   ├── data/
│   │   │   ├── intents.json      # Intent tanımları (37 intent)
│   │   │   ├── devices.json      # Lab cihaz veritabanı
│   │   │   └── test_queries.json # Classifier test veri seti
│   │   │
│   │   └── tools/
│   │       ├── test_classifier.py    # Accuracy test scripti
│   │       └── validate_intents.py   # Intent JSON doğrulama
│   │
│   └── tests/                    # Pytest testleri
│
└── frontend/
    ├── package.json              # npm bağımlılıkları
    ├── public/
    │   ├── index.html            # SPA HTML kabuğu
    │   └── chatbot-widget.js     # Embed edilebilir widget
    └── src/
        ├── index.js              # React giriş noktası
        ├── App.js                # Ana chat bileşeni
        └── App.css               # Stiller
```

---

## 4. Uygulama Başlatma Akışı

Uygulama başladığında `main.py` içindeki `lifespan` fonksiyonu çalışır:

```python
# backend/app/main.py

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Uygulama baslatildi, background yukleme devam ediyor...")
    asyncio.create_task(_background_initialization())
    yield
    scheduler.shutdown()
```

`_background_initialization()` sıralı ve paralel olarak tüm servisleri yükler:

```python
async def _background_initialization() -> None:
    init_session_db()                      # 1. SQLite session DB oluştur
    await _load_nlp_module()               # 2. Zemberek JVM'i başlat
    await _load_intent_data_module()       # 3. intents.json + embeddingler yükle
    await asyncio.gather(                  # 4. Paralel:
        _load_device_registry(),           #    - Lab cihaz veritabanı
        _load_menu_data(),                 #    - Yemek menüsü scrape
    )
    _setup_scheduled_jobs()                # 5. Periyodik görevleri başlat
```

**Zamanlanmış görevler (APScheduler):**

```python
scheduler.add_job(update_device_database, 'interval', hours=24)   # Cihaz güncelle
scheduler.add_job(update_system_data, 'interval', hours=6)        # Web verileri güncelle
scheduler.add_job(prune_old_sessions, 'interval', hours=24)       # Eski sessionları temizle
```

---

## 5. Konfigürasyon Yönetimi

`config.py` pydantic-settings ile environment variable'ları yönetir:

```python
# backend/app/config.py

class Settings(BaseSettings):
    environment: str = Field(default="development", alias="ENVIRONMENT")
    google_api_key: Optional[str] = Field(default=None, alias="GOOGLE_API_KEY")
    openweather_api_key: Optional[str] = Field(default=None, alias="OPENWEATHER_API_KEY")
    use_embeddings: bool = Field(default=True, alias="USE_EMBEDDINGS")
    admin_secret_token: Optional[str] = Field(default=None, alias="ADMIN_SECRET_TOKEN")
    # ...

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = get_settings()  # Singleton
```

Production'da env var'lar DigitalOcean App Platform'dan, `app.yaml` tanımıyla gelir.

---

## 6. İstek İşleme Akışı (Bir Mesajın Yolculuğu)

Kullanıcı "bugün yemekte ne var" yazdığında:

### 6.1. Frontend → Backend

```javascript
// frontend/src/App.js
const res = await fetch(`${BACKEND_URL}/api/chat`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: userInput,
    session_id: sessionId,
    history: messages.map(m => ({ role: m.sender, text: m.text }))
  })
});
```

### 6.2. Request Doğrulama (Pydantic)

```python
# backend/app/schemas/chat.py

class HistoryItem(BaseModel):
    role: str = Field(..., pattern=r"^(user|bot|model)$")
    text: str = Field(..., max_length=2000)

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = Field(None, max_length=64)
    history: List[HistoryItem] = Field(default_factory=list, max_length=20)
```

### 6.3. Intent Sınıflandırma

`chat.py` → `classifier.py` → 3 aşamalı sınıflandırma:

```
Mesaj: "bugün yemekte ne var"
         │
         ▼
    [1. Keyword Eşleştirme]  ──match──▶ yemek_listesi (score=13)
         │ (eşleşmezse)
         ▼
    [2. Semantic Benzerlik]  ──match──▶ En yakın intent
         │ (eşleşmezse)
         ▼
    [3. Gemini LLM Fallback] ──────────▶ Serbest cevap
```

**Keyword eşleştirme** (`classifier.py`):

```python
def _classify_by_keywords(user_message: str) -> Optional[dict]:
    stems = preprocess_text(user_message)  # Zemberek ile kök bul

    # Phase 1: Çok kelimeli ifade eşleştirme ("hava durumu", "ders kaydı")
    for phrase, intent_weights in PHRASE_INTENT_WEIGHTS.items():
        if phrase in text_lower:
            for intent_name, w in intent_weights.items():
                scores[intent_name] += w

    # Phase 2: Tek kelime stem eşleştirme
    for stem in stems:
        intent_weights = STEM_INTENT_WEIGHTS.get(s)
        if intent_weights:
            for intent_name, w in intent_weights.items():
                scores[intent_name] += w

    # Phase 3: Uzun mesajlarda skor normalizasyonu
    if meaningful_count > 3:
        factor = 1.0 + 0.3 * math.log(meaningful_count / 3.0)
        scores = {k: v / factor for k, v in scores.items()}

    # Phase 4: Negatif keyword filtresi
    # Phase 5: Berabere durumda semantic tie-breaking
```

**Semantic eşleştirme** (`classifier.py`):

```python
def _classify_by_semantic_similarity(user_message: str) -> Optional[dict]:
    user_embedding = _encode_user_message(user_message)  # fastembed

    for intent in INTENTS_DATA:
        if intent.get("use_semantic") is False:
            continue
        max_sim = _cosine_similarity(user_embedding, INTENT_EMBEDDINGS[intent_name])
        # Intent'e özel threshold kontrolü
        threshold = intent.get("semantic_threshold") or SIMILARITY_THRESHOLD
        if max_sim >= threshold:
            return intent
```

### 6.4. Cevap Üretimi

Intent türüne göre farklı kaynaklardan cevap üretilir:

```python
# backend/app/api/endpoints/chat.py

if intent_name == "yemek_listesi":
    result = await _handle_food_query()         # Web scraping
elif intent_name == "hava_durumu":
    result = await _handle_weather_query()      # OpenWeatherMap API
elif intent_name == "cihaz_bilgisi":
    result = await handle_device_query(body, session_id)  # Cihaz katalogu
elif intent_name == "selamlasma":
    # intents.json'dan rastgele cevap
    text = random.choice(intent["response_content"])
elif response_type == "TEXT":
    # intents.json'daki sabit cevap
    text = intent["response_content"]
else:
    # Gemini LLM ile serbest cevap
    result_text = await asyncio.to_thread(get_llm_response, message, history)
```

---

## 7. Türkçe NLP Pipeline

`nlp.py` — Zemberek kütüphanesi ile Türkçe kelime kökü (stem) çıkarma:

```python
# backend/app/core/nlp.py

def preprocess_text(text: str) -> list[str]:
    normalized = _normalize_text(text)    # "Bugün ne yesem?" → "bugün ne yesem"
    words = _tokenize_text(normalized)    # ["bugün", "ne", "yesem"]
    stems = []
    morphology = get_morphology()         # Zemberek singleton (JVM)
    for word in words:
        stem = _analyze_word(word, morphology)  # "yesem" → "ye"
        stems.append(stem)
    return stems                          # ["bugün", "ne", "ye"]
```

Zemberek Java tabanlıdır, bu yüzden Docker image'ında `openjdk-21-jre-headless` kurulur:

```dockerfile
# Dockerfile
RUN apt-get install -y --no-install-recommends openjdk-21-jre-headless
```

---

## 8. Intent Tanım Sistemi

`intents.json` — 37 intent tanımı, her biri:

```json
{
  "intent_name": "yemek_listesi",
  "keywords": {
    "yemek": 7,
    "menü": 6,
    "yemekhane": 7,
    "açlıktan ölüyorum": 8,
    "karnım aç": 7
  },
  "negative_keywords": ["hava", "sıcaklık", "derece"],
  "examples": [
    "bugün yemekte ne var",
    "ya bugün ne yesem",
    "yemekhane açık mı",
    "... (toplam 19 örnek)"
  ],
  "use_semantic": true,
  "semantic_threshold": 0.65,
  "response_type": "TEXT",
  "response_content": "🍽️ ..."
}
```

| Alan | Açıklama |
|------|----------|
| `keywords` | Kelime → ağırlık. Yüksek ağırlık = güçlü sinyal |
| `negative_keywords` | Bu kelimeler mesajda geçerse intent diskalifiye olur |
| `examples` | Semantic embedding uzayını şekillendirir |
| `use_semantic` | Semantic benzerlik kullanılsın mı |
| `semantic_threshold` | Intent'e özel eşik değeri (0-1) |
| `response_type` | TEXT, RANDOM_TEXT, URL, CUSTOM_LOGIC |

---

## 9. Web Scraper Sistemi

### 9.1. Scraper Yöneticisi (`manager.py`)

intents.json'a atomic yazma ile veri günceller:

```python
# backend/app/services/web_scraper/manager.py

_json_lock = threading.RLock()

def _write_json_atomic(data: dict) -> None:
    with _json_lock:
        tmp_fd, tmp_path = tempfile.mkstemp(dir=DATA_FILE.parent, suffix=".tmp")
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, str(DATA_FILE))  # Atomic replace
```

### 9.2. Yemek Scraper (`food_scrapper.py`)

AÇÜ SKS web sitesinden günlük menüyü çeker (requests + BeautifulSoup):

```
https://yemekhane.artvin.edu.tr → HTML parse → Günlük menü metni
```

### 9.3. Lab Cihaz Scraper (`lab_scrapper.py`)

Selenium + headless Firefox ile üniversite lab sayfasını scrape eder:

```python
# backend/app/services/web_scraper/lab_scrapper.py

options = FirefoxOptions()
options.add_argument("--headless")
browser = webdriver.Firefox(service=service, options=options)
browser.set_page_load_timeout(30)
browser.get(url)
# ... tablo satırlarını parse et → devices.json
```

### 9.4. Diğer Scraperlar

| Dosya | Kaynak | Veri |
|-------|--------|------|
| `duyurular_scraper.py` | artvin.edu.tr/duyuru | Son duyurular |
| `main_site_scrapper.py` | artvin.edu.tr | Güncel haberler |
| `sks_scrapper.py` | artvin.edu.tr/sks | Etkinlikler |
| `library_site_scraper.py` | kutuphane.artvin.edu.tr | Kütüphane bilgileri |
| `calendar_scraper.py` | artvin.edu.tr | Akademik takvim tarihleri |

---

## 10. Google Gemini LLM Entegrasyonu

`llm_client.py` — Intent ile eşleşmeyen sorulara Gemini ile cevap üretir:

```python
# backend/app/services/llm_client.py

SYSTEM_PROMPT = """
Sen Artvin Çoruh Üniversitesi (AÇÜ) resmi asistanısın.
1. Yalnızca kesin olarak bildiğin bilgileri söyle. Uydurma.
2. Bilmediğin konuda "Bu konuda kesin bilgim yok" de.
3. Kısa ve net cevap ver.
...
"""

def stream_llm_response(user_message: str, history=None):
    safe_message = _sanitize_for_llm(user_message)  # Prompt injection filtresi
    chat = model.start_chat(history=gemini_history)
    response = chat.send_message(safe_message, stream=True)
    for chunk in response:
        yield chunk.text   # Token token stream
```

**Prompt injection koruması:**

```python
_INJECTION_PATTERNS = re.compile(
    r"(ignore\s+(previous|above|all)\s+(instructions?|prompts?|rules?))"
    r"|(system\s*prompt)"
    r"|(you\s+are\s+now)"
    r"|(forget\s+(everything|your\s+instructions?))",
    re.IGNORECASE,
)

def _sanitize_for_llm(text: str) -> str:
    return _INJECTION_PATTERNS.sub("[filtered]", text)
```

---

## 11. Cache Sistemi

`cache.py` — Redis varsa Redis, yoksa in-memory dict kullanır:

```python
# backend/app/services/cache.py

def cache_get(key: str) -> Optional[Any]:
    r = _get_redis()
    if r is not None:
        return json.loads(r.get(key))    # Redis'ten oku

    # Dict cache fallback
    entry = _dict_cache.get(key)
    if entry and time.time() <= entry[1]:  # TTL kontrolü
        return entry[0]
    return None
```

**Cache TTL değerleri:**

| Veri | TTL | Açıklama |
|------|-----|----------|
| Yemek menüsü | 24 saat | Gün bazlı key ile |
| Hava durumu | 30 dakika | Sık güncellenen veri |
| Duyurular | 1 saat | Orta sıklık |
| Kütüphane | 6 saat | Nadir değişen |
| SKS Etkinlikler | 6 saat | Nadir değişen |

---

## 12. Session Yönetimi

`session_store.py` — SQLite ile konuşma geçmişi saklar:

```python
# backend/app/services/session_store.py

def save_message(session_id: str, role: str, text: str):
    conn = _get_conn()
    with _lock:
        conn.execute(
            "INSERT INTO messages (session_id, role, text) VALUES (?, ?, ?)",
            (session_id, role, text)
        )
        conn.commit()

def get_or_fallback(session_id, client_history):
    # Sunucu tarafı geçmiş varsa onu kullan, yoksa client'ın gönderdiğini
```

Thread-safe bağlantı yönetimi: tek connection + `threading.Lock` + `PRAGMA busy_timeout=5000`.

---

## 13. Güvenlik Katmanı

### 13.1. Admin Token (`security.py`)

```python
# backend/app/security.py

def require_admin(credentials=Depends(admin_security)) -> None:
    token = settings.admin_secret_token
    if credentials is None or not hmac.compare_digest(credentials.credentials, token):
        raise HTTPException(status_code=401, detail="Geçersiz admin token.")
```

`hmac.compare_digest` timing side-channel saldırılarını önler.

### 13.2. Rate Limiting (`limiter.py`)

```python
# backend/app/core/limiter.py

def _get_rate_key(request: Request) -> str:
    ip = get_remote_address(request)
    session_id = request.headers.get("X-Session-Id", "").strip()
    if session_id and _SESSION_RE.match(session_id):
        return f"{ip}:{session_id}"
    return ip
```

### 13.3. CORS Kısıtlaması (`main.py`)

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-Session-Id"],
)
```

### 13.4. Input Doğrulama (`schemas/chat.py`)

- `message`: max 1000 karakter
- `session_id`: regex ile alfanümerik, max 64 karakter
- `history`: max 20 öğe, her öğe max 2000 karakter

---

## 14. Hava Durumu Servisi

`weather.py` — OpenWeatherMap API ile Artvin hava durumu:

```python
# backend/app/services/weather.py

def get_weather() -> str:
    if not OPENWEATHER_API_KEY:
        return "🌤️ Hava durumu servisi şu an aktif değil."

    resp = requests.get(API_URL, params={
        "q": "Artvin,TR",
        "appid": OPENWEATHER_API_KEY,
        "units": "metric",
        "lang": "tr",
    }, timeout=8)

    # Sıcaklık, nem, rüzgar, bulutluluk → Türkçe formatla
    return f"🌡️ Sıcaklık: {temp}°C, {condition_tr}, 💨 {wind_speed} km/h"
```

---

## 15. Lab Cihaz Arama

`device_registry.py` + `chat_device.py` — Fuzzy ve semantic arama:

```python
# backend/app/services/device_registry.py

def search_device(query: str) -> list[dict]:
    # 1. Exact match
    if query_lower in DEVICE_DB:
        return [DEVICE_DB[query_lower]]

    # 2. Fuzzy match (difflib)
    matches = get_close_matches(query_lower, DEVICE_DB.keys(), n=5, cutoff=0.5)

    # 3. Semantic search (fastembed cosine similarity)
    if not matches and _DEVICE_EMBEDDINGS:
        # ... embedding karşılaştırma
```

Kullanıcıyla çok adımlı etkileşim: "cihaz ara" → seçenekler sun → kullanıcı seçer → detay göster.

---

## 16. Frontend Mimarisi

### 16.1. Widget Olarak Embed

`index.js` kendi container'ını oluşturur, dış sitenin `#root`'u ile çakışmaz:

```javascript
// frontend/src/index.js
let container = document.getElementById('acu-chatbot-root');
if (!container) {
  container = document.createElement('div');
  container.id = 'acu-chatbot-root';
  document.body.appendChild(container);
}
const root = ReactDOM.createRoot(container);
root.render(<App />);
```

### 16.2. Chat Akışı (`App.js`)

```javascript
// frontend/src/App.js

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8000';

// Quick reply kategorileri
const QUICK_REPLY_CATEGORIES = [
  { label: 'Günlük', items: [
    { label: '🍽️ Bugünün menüsü', text: 'Bugün yemek ne?' },
    { label: '🌤️ Hava durumu', text: 'Artvin hava durumu' },
  ]},
  { label: 'Akademik', items: [
    { label: '📅 Akademik takvim', text: 'Akademik takvim' },
  ]},
  // ...
];
```

Streaming desteği: Backend SSE ile token token gönderir, frontend gerçek zamanlı gösterir.

---

## 17. Deploy ve Altyapı

### 17.1. Dockerfile

```dockerfile
FROM python:3.11-slim
RUN apt-get install -y openjdk-21-jre-headless   # Zemberek JVM
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/app /app/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

### 17.2. DigitalOcean App Platform (`app.yaml`)

```yaml
services:
  - name: acu-chatbot-backend
    github:
      repo: egemenulkerr/acu-chatbot
      branch: main
      deploy_on_push: true
    dockerfile_path: Dockerfile
    http_port: 8080
    envs:
      - key: GOOGLE_API_KEY
        scope: RUN_TIME
      - key: OPENWEATHER_API_KEY
        scope: RUN_TIME
      # ...
    health_check:
      http_path: /health
```

**Deploy akışı:**
```
git push → GitHub → DigitalOcean auto-deploy → Docker build → Container başlat
```

### 17.3. Health Check

```python
@app.get("/health")
def health_check() -> dict:
    return {
        "status": "ok",
        "components": {
            "nlp": _morph is not None,
            "embeddings": _model is not None,
            "intents_loaded": len(_intents),
            "devices_loaded": len(_devices),
            "gemini_configured": bool(_gkey),
        }
    }
```

---

## 18. Test Altyapısı

### 18.1. Classifier Accuracy Test

```bash
cd backend && python -m app.tools.test_classifier
```

98 test case, 37 intent'in tamamını kapsar. %80 altı accuracy → exit code 1.

### 18.2. Pytest

```bash
cd backend && pytest tests/
```

| Test Dosyası | Ne Test Eder |
|-------------|--------------|
| `test_api_endpoints.py` | HTTP API entegrasyonu |
| `test_analytics.py` | Analytics endpoint |
| `test_intent_classification.py` | Intent eşleştirme |
| `test_session_store.py` | SQLite session |

---

## 19. Veri Akış Diyagramı

```
Kullanıcı mesajı
    │
    ▼
[Pydantic Doğrulama] → Geçersizse 422 hata
    │
    ▼
[Rate Limit Kontrolü] → Aşılmışsa 429 hata
    │
    ▼
[Session Geçmişi Yükle] → SQLite veya client history
    │
    ▼
[Intent Sınıflandırma]
    ├── Keyword Match → intents.json keywords + phrases
    ├── Semantic Match → fastembed cosine similarity
    └── Eşleşme yok → Gemini LLM
    │
    ▼
[Cevap Üretimi]
    ├── TEXT → intents.json'dan sabit cevap
    ├── RANDOM_TEXT → Rastgele seçim
    ├── URL → Link döndür
    ├── CUSTOM_LOGIC:
    │   ├── WEATHER_LIVE → OpenWeatherMap API
    │   ├── DEVICE_REGISTRY → Cihaz katalogu
    │   ├── SKS_LIVE → Web scraping
    │   └── NEWS_LIVE → Web scraping
    └── LLM → Gemini streaming/sync
    │
    ▼
[Cache Yaz + Analytics Log + Session Kaydet]
    │
    ▼
[JSON Response → Frontend]
```

---

## 20. Özet

Bu proje hibrit bir yapay zeka chatbotudur:
- **Hızlı cevaplar:** Keyword + semantic intent eşleştirme ile milisaniyeler içinde
- **Güncel veriler:** Web scraping ile yemek, duyuru, hava durumu otomatik güncellenir
- **Akıllı fallback:** Eşleşmeyen sorular Gemini LLM'e yönlendirilir
- **Güvenli:** Rate limiting, input doğrulama, CORS, prompt injection filtresi
- **Otomatik deploy:** GitHub push → DigitalOcean auto-deploy
