FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FASTEMBED_CACHE_PATH=/app/.cache/fastembed

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    firefox-esr \
    wget \
    && GECKO_VER=$(wget -qO- https://api.github.com/repos/mozilla/geckodriver/releases/latest \
       | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])") \
    && wget -q "https://github.com/mozilla/geckodriver/releases/download/${GECKO_VER}/geckodriver-${GECKO_VER}-linux64.tar.gz" \
    && tar -xzf geckodriver-*.tar.gz -C /usr/local/bin/ \
    && rm geckodriver-*.tar.gz \
    && apt-get purge -y wget \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY backend/requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-compile --default-timeout=1000 -r requirements.txt

# Pre-download embedding model so startup doesn't need network
RUN python3 -c "from fastembed import TextEmbedding; \
    list(TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2').embed(['warmup']))"

COPY backend/app /app/app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
