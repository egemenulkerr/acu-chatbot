FROM python:3.11-slim

# Install dependencies (minimal - only what's needed)
ENV GECKODRIVER_VERSION=0.33.0
ENV PYTHONUNBUFFERED=1
# Pip root-user uyarısını kapat (Docker/build ve platform pip adımlarında root normal)
ENV PIP_ROOT_USER_ACTION=ignore
ENV FIREFOX_BIN=/usr/bin/firefox-esr
ENV GECKODRIVER_PATH=/usr/local/bin/geckodriver

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    "firefox-esr=115.*" \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* && \
    # Download and install geckodriver
    wget -q "https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz" && \
    tar -xzf geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz -C /usr/local/bin/ && \
    rm geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz && \
    chmod +x /usr/local/bin/geckodriver

# Create non-root user
RUN adduser --disabled-password --gecos '' appuser

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --disable-pip-version-check -r requirements.txt && \
    find /usr/local/lib/python3.11/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -type f -name "*.pyc" -delete && \
    find /usr/local/lib/python3.11/site-packages -type f -name "*.pyo" -delete

COPY ./app /app/app

# fastembed modelini build sırasında indir — runtime'da HF isteği atılmaz
# Model cache'i /app/.cache altına yazılır; appuser erişebilir
ENV FASTEMBED_CACHE_PATH=/app/.cache/fastembed
RUN pip install --no-cache-dir --quiet "fastembed==0.5.1" && \
    python3 -c "from fastembed import TextEmbedding; list(TextEmbedding('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2').embed(['warmup']))" && \
    echo "fastembed modeli hazir"

RUN chown -R appuser /app

USER appuser

# Aynı cache path'i runtime'da da kullan
ENV FASTEMBED_CACHE_PATH=/app/.cache/fastembed

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]