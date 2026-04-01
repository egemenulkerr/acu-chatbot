# AÇÜ Chatbot — Geliştirme Analizi ve Embedding Değerlendirmesi

Bu döküman projenin mevcut durumunu analiz eder, embedding (FastEmbed) katmanının işlevini değerlendirir ve yapılabilecek geliştirmeleri öncelik sırasıyla listeler.

---

## 1. Embedding (FastEmbed) Detaylı Analizi

### 1.1. Kullanılan Model

Projede `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` modeli kullanılıyor:

- **Tip:** 12 katmanlı MiniLM, çok dilli
- **Vektör boyutu:** 384 boyut
- **Runtime:** ONNX (fastembed==0.5.1)
- **Dil desteği:** Türkçe dahil 50+ dil

```python
# backend/app/core/classifier.py — load_model()
MODEL = TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
```

### 1.2. Tasarlanan Çalışma Akışı

Embedding sistemi, intent sınıflandırmada 3 noktada kullanılmak üzere tasarlanmış:

```
Kullanıcı Mesajı
       │
       ▼
[1. Keyword Eşleştirme]
       │
       ├── Eşleşme var → Intent döndür
       │
       ├── İki intent berabere → [Semantic Tie-breaking]
       │                          Embedding ile en yakını seç
       │
       └── Eşleşme yok ↓
                        │
                        ▼
              [2. Semantic Benzerlik]
              Kullanıcı mesajını embed et,
              tüm intent örnekleriyle cosine
              similarity hesapla
                        │
                        ├── Benzerlik >= threshold → Intent döndür
                        │
                        └── Düşük benzerlik ↓
                                              │
                                              ▼
                                    [3. Gemini LLM Fallback]
```

Ayrıca cihaz aramada da kullanılmak üzere tasarlanmış:

```
Cihaz Sorgusu → Exact Match → Fuzzy Match → Semantic Search (embedding)
```

### 1.3. Kritik Bulgu: Embedding Production'da Çalışmıyor

**`load_model()` fonksiyonu startup'ta hiç çağrılmıyor.**

`backend/app/main.py` dosyasındaki `_background_initialization()`:

```python
async def _background_initialization() -> None:
    init_session_db()
    await _load_nlp_module()           # Zemberek yükleniyor
    await _load_intent_data_module()   # intents.json yükleniyor
    await asyncio.gather(
        _load_device_registry(),
        _load_menu_data(),
    )
    _setup_scheduled_jobs()
    # load_model() BURADA YOK!
```

`load_model()` sadece `backend/app/tools/test_classifier.py` (manuel test scripti) tarafından çağrılıyor. Sonuç olarak:

| Bileşen | Beklenen Durum | Gerçek Durum |
|---------|----------------|--------------|
| `MODEL` değişkeni | TextEmbedding instance | `None` |
| `INTENT_EMBEDDINGS` | 37 intent'in embedding matrisleri | `{}` (boş) |
| `_DEVICE_EMBEDDINGS` | Cihaz adı embeddingleri | `{}` (boş) |
| Semantic sınıflandırma | Aktif | Devre dışı |
| Keyword tie-breaking | Aktif | Devre dışı |
| Cihaz semantic arama | Aktif | Devre dışı |

**Pratik etki:** Sınıflandırma tamamen keyword tabanlı çalışıyor. Keyword ile eşleşmeyen her sorgu doğrudan Gemini LLM'e gidiyor. Bu durumda:
- Öğrencilerin farklı kelimelerle sorduğu sorular kaçırılıyor
- LLM'e gereksiz yük bindiriliyor (her eşleşmeyen sorgu = API çağrısı + maliyet)
- `intents.json`'daki `use_semantic`, `semantic_threshold` ve 600+ örnek tamamen kullanılmıyor

### 1.4. Mevcut Verimsizlikler

1. **fastembed pip ile yüklü ama kullanılmıyor** — Docker image boyutunu gereksiz büyütüyor
2. **Root Dockerfile'da model warmup yok** — Eski `backend/Dockerfile`'da (artık silinmiş) warmup vardı:
   ```dockerfile
   # Eski backend/Dockerfile'dan (artık yok):
   RUN python3 -c "from fastembed import TextEmbedding; \
       list(TextEmbedding('...').embed(['warmup']))"
   ```
3. **Config tutarsızlığı** — `classifier.py` `settings.use_embeddings` kullanırken `device_registry.py` doğrudan `os.getenv("USE_EMBEDDINGS")` kullanıyor
4. **Per-intent embedding çağrısı** — `load_intent_data()` her intent için ayrı `MODEL.embed(examples)` çağrısı yapıyor; tüm örnekleri tek batch'te embed etmek daha hızlı
5. **Gereksiz embedding hesaplama** — `use_semantic: false` olan intent'ler (selamlasma, veda, kimim_ben) için de embedding hesaplanıyor
6. **Health check yanıltıcı** — `/health` endpoint'i `"embeddings": _model is not None` gösteriyor, `MODEL` hiç yüklenmediği için her zaman `false`

### 1.5. Düzeltme Planı

Embedding'i aktifleştirmek için gereken değişiklikler:

**Adım 1:** `main.py`'ye model yükleme ekle:
```python
async def _load_embedding_model() -> None:
    from .core.classifier import load_model
    await asyncio.to_thread(load_model)

async def _background_initialization() -> None:
    init_session_db()
    await _load_nlp_module()
    await _load_embedding_model()       # YENİ
    await _load_intent_data_module()
    # ...
```

**Adım 2:** Dockerfile'a model warmup ekle:
```dockerfile
ENV FASTEMBED_CACHE_PATH=/app/.cache/fastembed
RUN python3 -c "from fastembed import TextEmbedding; \
    list(TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2').embed(['warmup']))"
```

**Adım 3:** `device_registry.py`'deki `os.getenv` kullanımını `settings.use_embeddings` ile değiştir.

**Adım 4:** Embedding batch optimizasyonu — tüm intent örneklerini tek seferde embed et.

---

## 2. Yüksek Öncelikli Geliştirmeler

### 2.1. Embedding Modelinin Aktifleştirilmesi

| | |
|---|---|
| **Dosya** | `backend/app/main.py`, `Dockerfile` |
| **Sorun** | `load_model()` startup'ta çağrılmıyor, semantic katman tamamen devre dışı |
| **Çözüm** | `_background_initialization()`'a `load_model()` çağrısı ekle, Dockerfile'a warmup adımı ekle |
| **Etki** | Sınıflandırma doğruluğu artacak, LLM çağrıları azalacak |

### 2.2. Dockerfile'a Firefox/GeckoDriver Eklenmesi

| | |
|---|---|
| **Dosya** | `Dockerfile` |
| **Sorun** | Root Dockerfile'da Firefox ve geckodriver yok, lab cihaz scraper'ı (`lab_scrapper.py`) production'da çalışamaz |
| **Çözüm** | Firefox ESR + geckodriver'ı Dockerfile'a ekle veya scraping'i ayrı bir worker'a taşı |
| **Etki** | Cihaz veritabanı güncelleme işlevi düzelecek |

### 2.3. chat.py Kod Duplikasyonu

| | |
|---|---|
| **Dosya** | `backend/app/api/endpoints/chat.py` |
| **Sorun** | `handle_chat_message` ve `stream_chat_message` neredeyse aynı iş akışını tekrarlıyor (confirmation, device flow, intent dispatch) |
| **Çözüm** | Tek bir `process_message()` orkestratör fonksiyon çıkar, her iki endpoint bundan beslensin |
| **Etki** | Bakım kolaylığı, bir dalda yapılan değişikliğin diğerine yansımaması riski ortadan kalkar |

### 2.4. Health Check İyileştirmesi

| | |
|---|---|
| **Dosya** | `backend/app/main.py` |
| **Sorun** | Uygulama hazır olmadan `/health` 200 döndürüyor; NLP, intent, embedding yüklenmeden trafik alıyor |
| **Çözüm** | "ready" durumu ekle, kritik yüklemeler tamamlanmadan 503 döndür |
| **Etki** | DigitalOcean health check doğru çalışacak, yarım yüklü uygulama trafik almayacak |

### 2.5. llm_limiter Kullanılmıyor

| | |
|---|---|
| **Dosya** | `backend/app/core/limiter.py`, `backend/app/api/endpoints/chat.py` |
| **Sorun** | `llm_limiter` tanımlı ve `main.py`'de kayıtlı ama hiçbir endpoint'e uygulanmamış |
| **Çözüm** | `/chat/stream` ve LLM fallback dallarına sıkı rate limit ekle |
| **Etki** | Gemini API maliyetini kontrol altına al, kötü niyetli kullanımı sınırla |

### 2.6. Frontend X-Session-Id Header Eksikliği

| | |
|---|---|
| **Dosya** | `frontend/src/App.js` |
| **Sorun** | Stream isteklerinde `X-Session-Id` header'ı gönderilmiyor, backend rate limiter IP+session anahtarlamasını yapamıyor |
| **Çözüm** | Tüm fetch çağrılarına `'X-Session-Id': sessionId` header'ı ekle |
| **Etki** | Rate limiting doğru çalışacak |

---

## 3. Orta Öncelikli Geliştirmeler

### 3.1. Scraper Kırılganlığı

| | |
|---|---|
| **Dosyalar** | `backend/app/services/web_scraper/` altındaki tüm scraper'lar |
| **Sorun** | HTML yapısına (CSS selector, class adı) bağımlı; site güncellenince kırılır |
| **Çözüm** | Golden-file testler (kaydedilmiş HTML ile), boş sonuç döndüğünde alert mekanizması, stabil attribute'lara bağlanma |
| **Etki** | Scraper kırıldığında hızlı fark edilir |

### 3.2. Akademik Takvim Hardcoded Yıl

| | |
|---|---|
| **Dosya** | `backend/app/api/endpoints/chat.py` |
| **Sorun** | "2025-2026" metni kodda sabit yazılmış |
| **Çözüm** | `intents.json`'daki `extra_data` veya mevcut tarihten dinamik hesaplama |
| **Etki** | Her yıl manuel güncelleme gerekmez |

### 3.3. Analytics Veri Kalıcılığı

| | |
|---|---|
| **Dosya** | `backend/app/api/endpoints/chat.py`, `analytics.py` |
| **Sorun** | `analytics.jsonl` ephemeral diskte, container restart'ta kaybolabilir |
| **Çözüm** | Managed log store'a (ör. DigitalOcean Spaces, S3) gönder veya persistent volume kullan |
| **Etki** | Kullanım verileri kaybolmaz |

### 3.4. Frontend Markdown Rendering

| | |
|---|---|
| **Dosya** | `frontend/src/App.js` |
| **Sorun** | Homemade `renderMarkdown` fonksiyonu — başlık, tablo, nested liste desteği yok; regex tabanlı link parsing hatalı olabilir |
| **Çözüm** | Küçük bir markdown kütüphanesi (ör. `marked` + DOMPurify) veya mevcut regex'i genişlet |
| **Etki** | Bot cevapları daha düzgün render edilir |

### 3.5. Session Store Optimizasyonu

| | |
|---|---|
| **Dosya** | `backend/app/services/session_store.py` |
| **Sorun** | Her `save_message` çağrısında INSERT + DELETE alt sorgusu çalışıyor |
| **Çözüm** | Temizlemeyi ayrı bir periyodik job'a taşı (zaten `prune_old_sessions` var, ama her write'ta da yapılıyor) |
| **Etki** | Yazma performansı artar |

### 3.6. Manager.py Race Condition

| | |
|---|---|
| **Dosya** | `backend/app/services/web_scraper/manager.py` |
| **Sorun** | Scheduler `intents.json`'ı yazarken deploy veya admin editi çakışabilir |
| **Çözüm** | Tüm read-modify-write işlemlerini aynı `_json_lock` altına al; production'da repo JSON'ını mutasyona uğratmak yerine DB veya object storage kullanmayı düşün |
| **Etki** | Veri bütünlüğü korunur |

### 3.7. Frontend .env.production URL Tutarsızlığı

| | |
|---|---|
| **Dosya** | `frontend/.env.production` |
| **Sorun** | `REACT_APP_BACKEND_URL` eski DigitalOcean URL'ini gösteriyor olabilir |
| **Çözüm** | Güncel backend URL'i ile eşitle |
| **Etki** | Frontend doğru backend'e bağlanır |

---

## 4. Düşük Öncelikli / Gelecek Özellikler

### 4.1. RAG (Retrieval Augmented Generation)

Üniversite yönetmelikleri, PDF dökümanları ve web sayfaları için embedding tabanlı belge arama. Kullanıcı sorusu → en ilgili belge parçalarını bul → Gemini'ye context olarak ver. Bu, mevcut embedding altyapısının en güçlü genişletmesi olurdu.

### 4.2. Çok Dilli Destek

Uluslararası öğrenciler için İngilizce mod. Intent'lere İngilizce örnekler eklenebilir (paraphrase-multilingual model zaten çok dilli).

### 4.3. ÖSYM/YÖK Entegrasyonu

Yeni öğrenci kayıt takvimi, tercih bilgisi, YÖK Atlas bağlantıları.

### 4.4. OBS Read-Only Entegrasyonu

Kimlik doğrulama ile öğrencinin kendi not/transkript bilgisine erişim (karmaşık ama yüksek değer).

### 4.5. Canlı Destek Yönlendirmesi

Chatbot'un çözemediği sorularda insan operatöre yönlendirme mekanizması.

### 4.6. Push Bildirim

Önemli duyurularda proaktif bildirim gönderme (web push notification API).

### 4.7. Prometheus Metrikleri

Request süreleri, intent dağılımı, scraper başarı/hata oranı, LLM çağrı sayısı gibi metrikler için Prometheus endpoint'i. DigitalOcean monitoring ile entegre edilebilir.

### 4.8. Otomatik Test Pipeline

GitHub Actions ile CI/CD: her push'ta lint, pytest, classifier accuracy testi çalıştır. Accuracy %80'in altına düşerse PR'ı engelle.

---

## 5. Öncelik Matrisi

```
                    Etki
                    ▲
             Yüksek │  Embedding    Dockerfile
                    │  Aktifleşme   Firefox
                    │
                    │  chat.py      Health
                    │  Refactor     Check
              Orta  │
                    │  Scraper      llm_limiter
                    │  Testleri     Uygula
                    │
             Düşük  │  Analytics    RAG
                    │  Kalıcılık    Sistemi
                    │
                    └──────────────────────────▶
                    Düşük    Orta    Yüksek
                              Aciliyet
```

**Önerilen uygulama sırası:**

1. Embedding aktifleştirme (en kritik — mevcut altyapıyı kullanıma sokar)
2. Dockerfile'a Firefox/geckodriver ekleme (cihaz güncelleme düzelir)
3. Health check iyileştirmesi (deploy güvenliği)
4. llm_limiter uygulama (maliyet kontrolü)
5. chat.py refactor (bakım kolaylığı)
6. Scraper testleri (güvenilirlik)
7. Frontend iyileştirmeleri (UX)
8. RAG ve ileri özellikler (uzun vadeli)
