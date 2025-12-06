FROM python:3.9-slim-bookworm

WORKDIR /app

# Sabhi zaroori system dependencies ko ek hi RUN command mein install karein
RUN rm -rf /var/lib/apt/lists/* && \
    apt-get update && \
    apt-get install -y \
    ffmpeg \
    git \
    build-essential \
    python3-dev \
    libffi-dev \
    libz-dev \
    --no-install-recommends

# Python dependencies install karein (pre-releases ke saath)
COPY requirements.txt .
RUN pip3 install --no-cache-dir --pre -r requirements.txt

COPY . .

CMD ["python3", "bot.py"]
