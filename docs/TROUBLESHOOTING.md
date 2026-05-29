# Shend — Troubleshooting

---

## Check bot logs

```bash
sudo journalctl -u shend -f
```

## Check container logs

```bash
docker logs -f shend
```

## Check container status

```bash
docker ps
```

## Restart manually

```bash
sudo systemctl restart shend
```

## Rebuild from scratch

```bash
cd /home/rue/shend
git pull origin main
sudo systemctl restart shend
```

---

## Common Issues

| Symptom | Cause | Fix |
|---|---|---|
| "Rate limit exceeded" | >10 uploads/hour | Wait 1 hour or increase `RATE_LIMIT_PER_HOUR` in `.env` |
| "Storage full" | >19.5GB used | Run cleanup or increase `MAX_STORAGE_GB` |
| 502 Bad Gateway | Container not running | `sudo systemctl restart shend` |
| 403 Invalid token | Token expired (15min) | Request new `/upload` or `/downsize` link |
| Compression fails | Corrupt/non-video file | Check file with `ffprobe` |
| Bot offline | Token invalid or Discord down | Check `docker logs shend`, verify `BOT_TOKEN` |
