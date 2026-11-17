FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Version stamp (tools/deploy/build_images.ps1, deploy.py), reported by /api/health. Last, so a new stamp never
# invalidates the pip layer.
ARG BUILD_COMMIT=""
ARG BUILD_TIME=""
ENV SMARTLAB_BUILD_COMMIT=$BUILD_COMMIT SMARTLAB_BUILD_TIME=$BUILD_TIME

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD curl -fsS http://localhost:8000/api/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
