FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FASTEMBED_CACHE_PATH=/app/.cache/fastembed

ARG GECKODRIVER_VER=v0.35.0

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    firefox-esr \
    wget \
    && wget -q "https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VER}/geckodriver-${GECKODRIVER_VER}-linux64.tar.gz" \
    && tar -xzf geckodriver-*.tar.gz -C /usr/local/bin/ \
    && rm geckodriver-*.tar.gz \
    && apt-get purge -y wget \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-compile --default-timeout=1000 -r requirements.txt

RUN python3 -c "from fastembed import TextEmbedding; \
    list(TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2').embed(['warmup']))"

COPY backend/app /app/app

RUN useradd -r -s /bin/false appuser && \
    mkdir -p /app/.cache /app/data && \
    chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
