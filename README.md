# Shend — Discord Video Bot

Self-hosted Discord bot that compresses large videos to under 10MB and serves them back as inline embeds or direct downloads. Runs 24/7 on a home server with zero port forwarding.

## Stack

- Python 3.11
- discord.py 2.x
- FastAPI + uvicorn
- aiosqlite (SQLite WAL)
- FFmpeg (two-pass bitrate targeting)
- Tailscale Funnel (public HTTPS, no domain)

## Local Development

Requires Python 3.11+ and FFmpeg installed locally.

```bash
git clone https://github.com/YOURNAME/shend.git
cd shend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your BOT_TOKEN and BASE_URL (use ngrok for local testing)
python main.py

Server Deployment
The bot runs inside a Docker container. The docker-compose.yml lives outside the repo at ~/docker/shend/ to keep deployment config separate from source code.
Docker Compose File
Create ~/docker/shend/docker-compose.yml on your server:
yaml
Copy

services:
  shend:
    build:
      context: /home/rue/shend
      dockerfile: Dockerfile
    container_name: shend
    restart: unless-stopped
    ports:
      - "127.0.0.1:7777:7777"
    volumes:
      - /home/rue/shend/storage:/app/storage
      - /home/rue/shend/data:/app/data
      - /home/rue/shend/.env:/app/.env:ro
    environment:
      - PYTHONUNBUFFERED=1

Systemd Service
Save to /etc/systemd/system/shend.service:
ini
Copy

[Unit]
Description=Shend Discord Bot
After=network-online.target docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
WorkingDirectory=/home/rue/docker/shend
ExecStartPre=/usr/bin/tailscale funnel --bg 7777
ExecStart=/usr/bin/docker compose -f /home/rue/docker/shend/docker-compose.yml up -d --build
ExecStop=/usr/bin/docker compose -f /home/rue/docker/shend/docker-compose.yml down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target

First Deploy
bash
Copy

sudo systemctl daemon-reload
sudo systemctl enable --now shend

Update After Code Changes
bash
Copy

cd /home/rue/shend
git pull origin main
sudo systemctl restart shend

Commands
Table
Command	Purpose
/upload	DMs a private upload link. Video compresses and embeds inline in Discord chat.
/downsize	DMs a private upload link. Video compresses and DMs back a direct download link.
Environment Variables
Table
Variable	Description
BOT_TOKEN	Discord bot token
BASE_URL	Public HTTPS URL (Tailscale Funnel or ngrok)
STORAGE_PATH	Local storage directory
DATA_PATH	SQLite database directory
MAX_STORAGE_GB	Storage cap (default 20)
MAX_UPLOAD_MB	Max upload size (default 500)
TARGET_COMPRESS_MB	Compression target (default 9.5)
RATE_LIMIT_PER_HOUR	Uploads per user per hour (default 3)
plain
Copy


---

Copy the entire block above into `README.md` in your repo. It renders as one clean file with nested code blocks.
