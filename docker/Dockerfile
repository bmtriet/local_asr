# Multi-stage GPU-accelerated Dockerfile for Qwen3-ASR Server
FROM nvidia/cuda:12.4.1-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    MODEL_NAME="Qwen/Qwen3-ASR-0.6B" \
    DEVICE="cuda" \
    TORCH_DTYPE="bfloat16" \
    PORT=8000 \
    HOST="0.0.0.0"

# Install system runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-dev \
    git \
    ffmpeg \
    libsndfile1 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip
RUN python3 -m pip install --no-cache-dir --upgrade pip

# Install PyTorch with CUDA 12.4
RUN pip install --no-cache-dir torch torchaudio --index-url https://download.pytorch.org/whl/cu124

# Copy and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application script
COPY app.py .

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python3", "app.py"]
