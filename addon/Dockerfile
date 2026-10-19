ARG BUILD_FROM=python:3.13-slim
FROM ${BUILD_FROM}

ENV NEEDLE_TELEMETRY=0 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/data/hf \
    NEEDLE_DATA_DIR=/data

WORKDIR /opt/needle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

CMD ["python", "-m", "app"]
