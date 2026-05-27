FROM python:3.11-slim

# System deps: FFmpeg + libmagic (required by python-magic)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure runtime directories exist inside container
RUN mkdir -p storage/uploads storage/archive storage/temp data

EXPOSE 7777

CMD ["python", "main.py"]
