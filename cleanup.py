# cleanup.py
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
from pathlib import Path
import aiosqlite

from config import settings
from database import DB_PATH


async def cleanup_temp_files():
    """Delete temp files older than 1 hour."""
    cutoff = datetime.utcnow() - timedelta(hours=1)
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute(
            "SELECT token, internal_path FROM uploads WHERE is_temp = 1 AND created_at < ?",
            (cutoff,),
        )
        expired = list(await rows.fetchall())
        
        for token, path in expired:
            Path(path).unlink(missing_ok=True)
            await db.execute("DELETE FROM uploads WHERE token = ?", (token,))
        
        await db.commit()
        if expired:
            print(f"[CLEANUP] Deleted {len(expired)} expired temp files")


async def archive_old_uploads():
    """Move uploads older than 7 days to archive."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute(
            "SELECT token, internal_path FROM uploads WHERE is_temp = 0 AND created_at < ?",
            (cutoff,),
        )
        old = list(await rows.fetchall())
        
        for token, old_path in old:
            old_file = Path(old_path)
            if old_file.exists():
                archive_dir = settings.storage_path / "archive"
                archive_dir.mkdir(exist_ok=True)
                new_path = archive_dir / old_file.name
                old_file.rename(new_path)
                await db.execute(
                    "UPDATE uploads SET internal_path = ? WHERE token = ?",
                    (str(new_path), token),
                )
        
        await db.commit()
        if old:
            print(f"[CLEANUP] Archived {len(old)} old uploads")


async def purge_archive_on_pressure():
    """Delete oldest archive files if disk usage > 85%."""
    total = sum(f.stat().st_size for f in settings.storage_path.rglob("*") if f.is_file())
    used_gb = total / (1024 ** 3)
    cap_gb = settings.max_storage_gb
    
    if used_gb / cap_gb < 0.85:
        return
    
    print(f"[CLEANUP] Disk pressure: {used_gb:.1f}/{cap_gb} GB. Purging archive...")
    
    archive_path = settings.storage_path / "archive"
    if not archive_path.exists():
        return
    
    # Get files sorted by modification time (oldest first)
    files = sorted(
        [f for f in archive_path.rglob("*") if f.is_file()],
        key=lambda f: f.stat().st_mtime,
    )
    
    target_gb = cap_gb * 0.80
    freed = 0
    
    for f in files:
        if used_gb - freed <= target_gb:
            break
        size = f.stat().st_size
        f.unlink()
        freed += size / (1024 ** 3)
        
        # Also remove DB row
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM uploads WHERE internal_path = ?",
                (str(f),),
            )
            await db.commit()
    
    print(f"[CLEANUP] Freed {freed:.1f} GB from archive")


async def cleanup_orphans():
    """Remove DB rows for files that no longer exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute("SELECT token, internal_path FROM uploads")
        all_rows = await rows.fetchall()
        
        removed = 0
        for token, path in all_rows:
            if not Path(path).exists():
                await db.execute("DELETE FROM uploads WHERE token = ?", (token,))
                removed += 1
        
        await db.commit()
        if removed:
            print(f"[CLEANUP] Removed {removed} orphaned DB rows")


async def run_cleanup():
    """Run all cleanup tasks."""
    await cleanup_temp_files()
    await archive_old_uploads()
    await cleanup_orphans()
    await purge_archive_on_pressure()


def start_scheduler():
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_cleanup, "interval", hours=1)
    scheduler.start()
    print("[CLEANUP] Scheduler started (runs every hour)")
    return scheduler
