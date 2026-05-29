# Shend — Discord Video Bot

Self-hosted Discord bot that compresses large videos to under 10MB and serves them back as inline embeds or direct downloads. Runs 24/7 on a home server with zero port forwarding.

## Stack

- Python 3.11
- discord.py 2.x
- FastAPI + uvicorn
- aiosqlite (SQLite WAL)
- FFmpeg (two-pass bitrate targeting)
- Tailscale Funnel (public HTTPS, no domain)
- Docker Compose

## Features

| Command | Purpose |
|---|---|
| `/upload` | DMs a private upload link. Video compresses and embeds inline in Discord chat. |
| `/downsize` | DMs a private upload link. Video compresses and returns a download link privately in the same channel. |

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
```

## Server Deployment

The bot runs inside a Docker container. The `docker-compose.yml` lives outside the repo at `~/docker/shend/` to keep deployment config separate from source code.

### Prerequisites

- Docker + Docker Compose plugin
- Tailscale installed and logged in
- Discord bot token

### Environment Variables

Create `.env` from `.env.example`:

```bash
cp .env.example .env
nano .env
```

#### `.env.example`

```bash
BOT_TOKEN=your_discord_bot_token_here
BASE_URL=https://your-server.tailxxxxx.ts.net
STORAGE_PATH=./storage
DATA_PATH=./data
MAX_STORAGE_GB=20
MAX_UPLOAD_MB=500
TARGET_COMPRESS_MB=9.5
RATE_LIMIT_PER_HOUR=10
```

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | — | Discord bot token (required) |
| `BASE_URL` | — | Public HTTPS URL from Tailscale Funnel (required) |
| `STORAGE_PATH` | `./storage` | Local storage directory |
| `DATA_PATH` | `./data` | SQLite database directory |
| `MAX_STORAGE_GB` | `20` | Storage cap in gigabytes |
| `MAX_UPLOAD_MB` | `500` | Max upload size in megabytes |
| `TARGET_COMPRESS_MB` | `9.5` | Target compressed file size |
| `RATE_LIMIT_PER_HOUR` | `10` | Max uploads per user per hour |

### Docker Compose File

Create `~/docker/shend/docker-compose.yml` on your server:

```yaml
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
```

### Systemd Service

Save to `/etc/systemd/system/shend.service`:

```ini
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
```

### First Deploy

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now shend
```

### Update After Code Changes

```bash
cd /home/rue/shend
git pull origin main
sudo systemctl restart shend
```

## Maintenance

See [CLEANUP.md](CLEANUP.md) for full maintenance instructions.

### Quick Commands

```bash
# Check storage usage
docker exec shend python -c "from maintenance import print_storage_stats; print_storage_stats()"

# Clear temp files
docker exec shend python -c "from maintenance import clear_temp; clear_temp()"

# Full cleanup
docker exec shend python -c "import asyncio; from maintenance import run_full_cleanup; asyncio.run(run_full_cleanup())"
```

### Automated Cleanup

The bot runs an APScheduler job every hour that:
- Deletes temp files older than 1 hour
- Moves uploads older than 7 days to archive
- Deletes archive files if disk usage exceeds 85%
- Removes orphaned database rows

## Storage Layout

```
storage/
├── uploads/    # Public-facing files (7-day retention, auto-archived)
├── archive/    # Long-term storage (90-day retention, disk-pressure purge)
└── temp/       # Working files (1-hour retention)

data/
└── bot.db      # SQLite database (WAL mode)
```

## Security

- File type validation via magic numbers (not extensions)
- Per-user rate limiting (default: 10 uploads/hour)
- Disk pressure guard (rejects uploads if >19.5GB used)
- Single-use upload tokens (expire in 15 minutes)
- Files stored as UUIDs internally; original names only in DB
- Container runs unprivileged; host mounts with `noexec,nosuid,nodev`

## Troubleshooting

### Check bot logs
```bash
sudo journalctl -u shend -f
```

### Check container logs
```bash
docker logs -f shend
```

### Check container status
```bash
docker ps
```

### Restart manually
```bash
sudo systemctl restart shend
```

### Rebuild from scratch
```bash
cd /home/rue/shend
git pull origin main
sudo systemctl restart shend
```

## Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| "Rate limit exceeded" | >10 uploads/hour | Wait 1 hour or increase `RATE_LIMIT_PER_HOUR` in `.env` |
| "Storage full" | >19.5GB used | Run cleanup or increase `MAX_STORAGE_GB` |
| 502 Bad Gateway | Container not running | `sudo systemctl restart shend` |
| 403 Invalid token | Token expired (15min) | Request new `/upload` or `/downsize` link |
| Compression fails | Corrupt/non-video file | Check file with `ffprobe` |
| Bot offline | Token invalid or Discord down | Check `docker logs shend`, verify `BOT_TOKEN` |
