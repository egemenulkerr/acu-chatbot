FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Minimal dependencies - no Firefox/geckodriver (scheduled jobs run separately)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    openjdk-21-jre-headless \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies with minimal overhead
COPY backend/requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install --default-timeout=1000 -r requirements.txt && \
    python -m pip cache purge && \
    find /usr/local/lib/python3.11 -type d -name __pycache__ -delete && \
    find /usr/local/lib/python3.11 -type f -name "*.pyc" -delete && \
    rm -rf /root/.cache /tmp/* /var/tmp/*

COPY backend/app /app/app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
