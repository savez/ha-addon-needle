# Immagine base indicata qui (build.yaml è deprecato in Supervisor):
# Debian/glibc, richiesta dall'engine prebuilt di Needle (manylinux).
FROM python:3.13-slim

ENV NEEDLE_TELEMETRY=0 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/data/hf \
    NEEDLE_DATA_DIR=/data

WORKDIR /opt/needle
COPY requirements.txt .
# llama-cpp-python (EmbeddingGemma) non ha wheel per aarch64: si compila qui.
# Sul Pi la prima build richiede diversi minuti.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake libgomp1 \
    && CMAKE_ARGS="-DGGML_NATIVE=OFF" pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y build-essential cmake \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*
COPY app ./app

CMD ["python", "-m", "app"]
