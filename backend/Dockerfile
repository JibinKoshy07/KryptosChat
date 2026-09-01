# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/venv/bin:$PATH"

WORKDIR /app

RUN python -m venv /venv && \
    /venv/bin/pip install --no-cache-dir --upgrade pip setuptools wheel

COPY requirements.txt .
RUN /venv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user for security.
RUN useradd --create-home --uid 10001 appuser && \
    mkdir -p /data/media && \
    chown -R appuser /data /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 --start-period=20s \
    CMD ["/venv/bin/python", "-c", "import httpx; httpx.get('http://localhost:8000/api/v1/health', timeout=3).raise_for_status()"]

CMD ["/venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]