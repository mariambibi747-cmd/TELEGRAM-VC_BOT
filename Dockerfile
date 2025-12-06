FROM python:3.9-slim-bookworm

WORKDIR /app

# System dependencies
RUN apt-get update && \
    apt-get install -y \
    curl \
    gnupg \
    ffmpeg \
    git \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    libz-dev \
    libjpeg-dev \
    zlib1g-dev \
    libwebp-dev \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Rust toolchain (required for cryptg)
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Copy requirements
COPY requirements.txt .

# Upgrade pip and install requirements (with --pre for dev versions)
RUN python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install --no-cache-dir --pre -r requirements.txt

COPY . .

CMD ["python3", "bot.py"]
