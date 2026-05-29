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
| `/downsize` | DMs a private upload link. Video compresses and posts a download link in the original channel. |

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

## Environment Variables

| Variable | Description |
|---|---|
| `BOT_TOKEN` | Discord bot token |
| `BASE_URL` | Public HTTPS URL (Tailscale Funnel or ngrok) |
| `STORAGE_PATH` | Local storage directory |
| `DATA_PATH` | SQLite database directory |
| `MAX_STORAGE_GB` | Storage cap (default 20) |
| `MAX_UPLOAD_MB` | Max upload size (default 500) |
| `TARGET_COMPRESS_MB` | Compression target (default 9.5) |
| `RATE_LIMIT_PER_HOUR` | Uploads per user per hour (default 3) |

## Maintenance

Run maintenance commands inside the container or locally.

### Check Storage Usage

```bash
cd /home/rue/shend
source venv/bin/activate  # Skip if running in container
python -c "from maintenance import print_storage_stats; print_storage_stats()"
```

### Clear Temp Files

```bash
python -c "from maintenance import clear_temp; clear_temp()"
```

### Clear Old Uploads (default: older than 7 days)

```bash
python -c "from maintenance import clear_uploads_older_than; clear_uploads_older_than(7)"
```

### Clear Old Archive (default: older than 90 days)

```bash
python -c "from maintenance import clear_archive_older_than; clear_archive_older_than(90)"
```

### Full Cleanup (temp + old uploads + old archive + orphan DB rows)

```bash
python -c "import asyncio; from maintenance import run_full_cleanup; asyncio.run(run_full_cleanup())"
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
- Per-user rate limiting (3 uploads/hour)
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
