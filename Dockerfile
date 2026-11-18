FROM python:3.12-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg tesseract-ocr fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt requirements-ml.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ml.txt

COPY gtaclips ./gtaclips

ENV GTACLIPS_DATA=/data \
    GTACLIPS_HOST=0.0.0.0 \
    GTACLIPS_PORT=8000 \
    PYTHONUNBUFFERED=1
VOLUME ["/data"]
EXPOSE 8000
CMD ["python", "-m", "gtaclips"]
