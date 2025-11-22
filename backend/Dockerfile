FROM python:3.12-slim

# 1. Gerekli Paketleri Kur (Java 21 + Firefox + Temel Araçlar)
RUN apt-get update && \
    apt-get install -y \
    openjdk-21-jre-headless \
    firefox-esr \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]