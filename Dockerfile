FROM python:3.9-slim-bookworm

WORKDIR /app

# Final Clean Install: Only essential packages
RUN rm -rf /var/lib/apt/lists/* && \
    apt-get update && \
    apt-get install -y \
    curl \
    gnupg \
    ffmpeg \
    git \
    build-essential \
    python3-dev \
    libffi-dev \
    libz-dev \
    --no-install-recommends

# Rust toolchain
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
ENV PATH="/root/.cargo/bin:${PATH}"

# Requirements copy karein
COPY requirements.txt .

# Guaranteed Install (Final Fix for Pip Path)
RUN python3 -m pip install --upgrade pip && python3 -m pip install --no-cache-dir --pre -r requirements.txt

COPY . .

CMD ["python3", "bot.py"]
