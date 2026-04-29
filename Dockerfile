FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered logging for GCP Cloud Logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir celery[redis]

COPY . .

CMD ["celery", "-A", "app.tasks.grading.celery_app", "worker", "--loglevel=info", "--concurrency=1"]
