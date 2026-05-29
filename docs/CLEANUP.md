# Shend — Cleanup & Maintenance Guide

> Quick reference for storage management, troubleshooting, and manual cleanup operations.

---

## Automated Cleanup (Runs Automatically)

The bot runs an APScheduler job every hour that performs the following:

| Task | Interval | What It Does |
|---|---|---|
| **Temp cleanup** | Every hour | Deletes `storage/temp/` files older than 1 hour + their DB rows |
| **Archive uploads** | Every hour | Moves `storage/uploads/` files older than 7 days to `storage/archive/` |
| **Disk pressure purge** | Every hour | If disk >85% full, deletes oldest archive files until <80% |
| **Orphan cleanup** | Every hour | Removes DB rows for files that no longer exist on disk |

You do not need to run these manually unless you want immediate cleanup.

---

## Check Storage Usage

### Inside the Docker Container

```bash
docker exec shend python -c "from maintenance import print_storage_stats; print_storage_stats()"
```

### On the Server (if Python deps installed locally)

```bash
cd /home/rue/shend
source venv/bin/activate
python -c "from maintenance import print_storage_stats; print_storage_stats()"
```

**Example output:**
```
=== Shend Storage Stats ===
Uploads:  9850.50 MB (12 files)
Archive:  0.00 MB (0 files)
Temp:     0.00 MB (0 files)
Total:    9.62 GB / 20.0 GB (48.1%)
===========================
```

---

## Manual Cleanup Commands

### Clear Temp Files Immediately

Deletes all files in `storage/temp/` regardless of age.

```bash
docker exec shend python -c "from maintenance import clear_temp; clear_temp()"
```

### Clear Uploads Older Than N Days

Default: 7 days.

```bash
docker exec shend python -c "from maintenance import clear_uploads_older_than; clear_uploads_older_than(7)"
```

### Clear Archive Older Than N Days

Default: 90 days.

```bash
docker exec shend python -c "from maintenance import clear_archive_older_than; clear_archive_older_than(90)"
```

### Clean Orphaned Database Rows

Removes DB entries for files that were deleted manually.

```bash
docker exec shend python -c "import asyncio; from maintenance import cleanup_database_orphans; asyncio.run(cleanup_database_orphans())"
```

### Full Cleanup (Everything at Once)

Runs: temp cleanup + old uploads + old archive + orphan cleanup + disk pressure check.

```bash
docker exec shend python -c "import asyncio; from maintenance import run_full_cleanup; asyncio.run(run_full_cleanup())"
```

---

## Container Management

### Check Container Status

```bash
docker ps
```

### View Live Logs

```bash
docker logs -f shend
```

### View Recent Logs (last 50 lines)

```bash
docker logs shend --tail 50
```

### Restart Container

```bash
sudo systemctl restart shend
```

### Rebuild from Scratch

```bash
cd /home/rue/shend
git pull origin main
sudo systemctl restart shend
```

### Enter Container Shell

```bash
docker exec -it shend /bin/bash
```

---

## Tailscale Funnel

### Check Funnel Status

```bash
tailscale status
```

### Restart Funnel

```bash
tailscale funnel --bg 7777
```

### Stop Funnel

```bash
tailscale funnel --https=443 off
```

---

## Database

### Inspect Database

```bash
docker exec shend sqlite3 /app/data/bot.db ".tables"
docker exec shend sqlite3 /app/data/bot.db "SELECT * FROM uploads LIMIT 5;"
```

### Backup Database

```bash
cp /home/rue/shend/data/bot.db /home/rue/shend/data/bot.db.backup.$(date +%F)
```

### Reset Database (Deletes All Data)

```bash
sudo rm /home/rue/shend/data/bot.db
sudo systemctl restart shend
```

---

## Storage Layout

```
/home/rue/shend/
├── storage/
│   ├── uploads/     # Public-facing files (auto-archived after 7 days)
│   ├── archive/     # Long-term storage (auto-purged if disk >85%)
│   └── temp/        # Working files (auto-deleted after 1 hour)
├── data/
│   └── bot.db       # SQLite database (WAL mode)
└── .env             # Environment variables
```

---

## Environment Variables Reference

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
