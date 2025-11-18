# 1. Adım: Temel imaj olarak en güncel stabil sürüm olan Python 3.12'yi kullan
FROM python:3.12-slim

# 2. Adım: Zemberek için gerekli olan Java Runtime'ı (JRE) kur
# HATA DÜZELTMESİ: openjdk-17 de bulunamadı. en güncel LTS olan openjdk-21'i deniyoruz.
RUN apt-get update && \
    apt-get install -y openjdk-21-jre-headless && \
    rm -rf /var/lib/apt/lists/*

# 3. Adım: Konteyner içindeki çalışma dizinini /app olarak ayarla
WORKDIR /app

# 4. Adım: Bağımlılık dosyasını kopyala
COPY requirements.txt .

# 5. Adım: Bağımlılıkları KONTEYNER İÇİNE kur
RUN pip install --no-cache-dir -r requirements.txt

# 6. Adım: Geri kalan tüm proje kodlarını kopyala
COPY ./app /app/app

# 7. Adım: Konteyner başladığında çalışacak varsayılan komut
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]