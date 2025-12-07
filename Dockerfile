FROM python:3.11-slim

# Install only runtime dependencies, minimize image size
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    firefox-esr \
    && rm -rf /var/lib/apt/lists/*

# Get geckodriver from container registry to save disk space
RUN wget -q "https://github.com/mozilla/geckodriver/releases/download/v0.33.0/geckodriver-v0.33.0-linux64.tar.gz" -O /tmp/geckodriver.tar.gz && \
    tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin/ && \
    rm /tmp/geckodriver.tar.gz && \
    chmod +x /usr/local/bin/geckodriver

WORKDIR /app

# Copy and install dependencies - aggressive cache cleanup
COPY backend/requirements.txt .
RUN pip config set global.no-cache-dir true && \
    pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --default-timeout=1000 -r requirements.txt && \
    find /usr/local/lib/python3.11/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -type f -name "*.pyc" -delete && \
    find /usr/local/lib/python3.11/site-packages -type f -name "*.pyo" -delete && \
    rm -rf /root/.cache/pip /tmp/* /var/tmp/*

COPY backend/app /app/app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
