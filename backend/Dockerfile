# API and CPU worker image (the same image runs `uvicorn` or `celery`).
FROM python:3.12-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY worker ./worker
COPY models ./models

RUN useradd --system --uid 10001 vrv && mkdir -p /data && chown vrv /data
USER vrv
ENV VRV_MODEL_DIR=/srv/models \
    VRV_UPLOAD_STAGING_DIR=/data/uploads \
    VRV_WORK_DIR=/data/work \
    VRV_LOCAL_STORAGE_DIR=/data/objects

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
