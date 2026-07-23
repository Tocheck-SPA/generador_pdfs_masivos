# Worker de generación de PDF (Playwright + Chromium).
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

WORKDIR /app

# Dependencias primero (mejor caché de capas).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m playwright install chromium

# Código y plantillas.
COPY app ./app
COPY templates ./templates

# Los fixtures son opcionales en producción (SOURCE_ADAPTER=postgres).
# Para el modo demo se montan como volumen (ver docker-compose) en /fixtures.
ENV FIXTURES_DIR=/fixtures

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "app.main", "run"]
