FROM python:3.9-slim-bookworm

WORKDIR /app

RUN rm -rf /var/lib/apt/lists/* && \
    apt-get update && \
    apt-get install -y \
    ffmpeg \
    git \
    --no-install-recommends

COPY requirements.txt .
RUN pip3 install --no-cache-dir --pre -r requirements.txt

COPY . .

CMD ["python3", "bot.py"]
