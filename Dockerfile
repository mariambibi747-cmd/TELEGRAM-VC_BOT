# Python 3.9 Image use karenge
FROM python:3.9-slim-buster

# System packages update aur FFmpeg install
RUN apt-get update && apt-get upgrade -y
RUN apt-get install -y ffmpeg git

# Working directory set karein
WORKDIR /app

# Requirements copy aur install karein
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Baaki code copy karein
COPY . .

# Start command
CMD ["python3", "bot.py"]
