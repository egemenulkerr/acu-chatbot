FROM python:3.12-slim

# 1. Gerekli Paketleri Kur (Java 21 + Firefox + Temel Araçlar)
ENV GECKODRIVER_VERSION=0.33.0

RUN apt-get update && \
    apt-get install -y \
    openjdk-21-jre-headless \
    firefox-esr \
    wget \
    ca-certificates \
    tar \
    && rm -rf /var/lib/apt/lists/* \
    # geckodriver indir ve kur
    && wget -q "https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz" \
    && tar -xzf geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz \
    && mv geckodriver /usr/local/bin/ \
    && chmod +x /usr/local/bin/geckodriver \
    && rm geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]