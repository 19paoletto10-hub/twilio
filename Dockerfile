FROM python:3.12-slim AS builder

FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /wheels

# Install build dependencies to compile wheels
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential gcc libffi-dev make curl \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /tmp/requirements.txt

# Build wheels for all dependencies in an isolated directory
RUN pip install --upgrade pip setuptools wheel && pip wheel --no-cache-dir --no-deps -r /tmp/requirements.txt -w /wheels


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Minimal runtime packages
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# Copy wheels from builder and install them without accessing the network
COPY --from=builder /wheels /wheels
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r /app/requirements.txt

# Copy application
COPY . /app

# Create non-root user and fix permissions
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
ENV PYTHONDONTWRITEBYTECODE=1 \
