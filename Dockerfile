# Naya Base Image: Python 3.9 on Debian 12 (Bookworm) - Best Choice
FROM python:3.9-slim-bookworm

# Working directory set karein
WORKDIR /app

# System packages update aur FFmpeg install
# Bookworm par repositories perfectly kaam karte hain.
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Requirements copy aur install karein
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Baaki code copy karein
COPY . .

# Start command
CMD ["python3", "bot.py"]
