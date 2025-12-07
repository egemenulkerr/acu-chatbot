FROM python:3.11-slim

# Install dependencies (minimal - only what's needed)
ENV GECKODRIVER_VERSION=0.33.0
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    firefox-esr \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* && \
    # Download and install geckodriver
    wget -q "https://github.com/mozilla/geckodriver/releases/download/v${GECKODRIVER_VERSION}/geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz" && \
    tar -xzf geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz -C /usr/local/bin/ && \
    rm geckodriver-v${GECKODRIVER_VERSION}-linux64.tar.gz && \
    chmod +x /usr/local/bin/geckodriver

WORKDIR /app

# Copy and install dependencies
COPY backend/requirements.txt .
RUN pip config set global.no-cache-dir true && \
    pip install --disable-pip-version-check --default-timeout=1000 --upgrade pip && \
    pip install --disable-pip-version-check --default-timeout=1000 -r requirements.txt && \
    find /usr/local/lib/python3.11/site-packages -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /usr/local/lib/python3.11/site-packages -type f -name "*.pyc" -delete && \
    find /usr/local/lib/python3.11/site-packages -type f -name "*.pyo" -delete && \
    rm -rf /root/.cache/pip

COPY backend/app /app/app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
