FROM python:3.9-slim-bookworm

WORKDIR /app

# System dependencies for FFmpeg and build tools
RUN apt-get update && \
    apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    python3-dev \
    libffi-dev \
    libssl-dev \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Upgrade pip and install requirements (--pre for py-tgcalls dev version)
RUN python3 -m pip install --upgrade pip setuptools wheel && \
    python3 -m pip install --no-cache-dir --pre -r requirements.txt

# Copy bot code
COPY . .

# Render will provide PORT env variable
EXPOSE 10000

CMD ["python3", "bot.py"]
