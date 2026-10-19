# Immagine base indicata qui (build.yaml è deprecato in Supervisor):
# Debian/glibc, richiesta dall'engine prebuilt di Needle (manylinux).
FROM python:3.13-slim

ENV NEEDLE_TELEMETRY=0 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/data/hf \
    NEEDLE_DATA_DIR=/data

WORKDIR /opt/needle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

CMD ["python", "-m", "app"]
