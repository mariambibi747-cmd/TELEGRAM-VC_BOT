# Python 3.10 is most stable for these bots
FROM python:3.10-slim

# 1. Install System Tools (FFmpeg + Git + Compilers)
# Git is added to handle complex installs if needed
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. Set Working Directory
WORKDIR /app

# 3. Upgrade Pip (Important step to avoid dependency errors)
RUN pip install --upgrade pip

# 4. Copy Requirements & Install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy Bot Code
COPY . .

# 6. Start Command (Confirm your file name is bot.py)
CMD ["python", "bot.py"]
