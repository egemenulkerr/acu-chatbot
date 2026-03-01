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
RUN pip install --upgrade pip && \
    pip install --default-timeout=1000 -r requirements.txt && \
    find /usr/local/lib/python3.11 -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true && \
    find /usr/local/lib/python3.11 -type f \( -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null; true

COPY backend/app /app/app

EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
