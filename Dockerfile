FROM python:3.10-slim

# Install system dependencies (FFmpeg and Git)
# This is where we are allowed to use 'apt' because it's inside Docker
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    libopus0 \
    libopus-dev \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy your files to the container
COPY . /app

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt

# Command to start the bot
# CHANGE 'main.py' to whatever your main bot file is named (e.g., bot.py, music.py)
CMD ["python", "bot.py"]