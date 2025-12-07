FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . /app

ENV APP_HOST=0.0.0.0 \
    APP_PORT=3000

EXPOSE 3000

# Run with gunicorn for production; `run.py` exposes `app` as module-level variable
CMD ["gunicorn", "--bind", "0.0.0.0:3000", "run:app", "--workers", "2", "--threads", "4"]
