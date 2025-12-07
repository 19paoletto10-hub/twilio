FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies, install python deps, then remove build deps to keep image small
RUN apt-get update \
 && apt-get install -y --no-install-recommends gcc libffi-dev musl-dev make build-essential curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt || true

# Copy application
COPY . /app

# Create non-root user
RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app \
 && chown -R app:app /app

ENV APP_HOST=0.0.0.0 \
    APP_PORT=3000

USER app

EXPOSE 3000

# Healthcheck uses the /api/health endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 CMD curl -f http://localhost:3000/api/health || exit 1

# Run with gunicorn for production; `run.py` exposes `app` as module-level variable
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "run:app", "--workers", "2", "--threads", "4"]
