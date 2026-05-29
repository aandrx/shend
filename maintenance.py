# maintenance.py
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import aiosqlite

from config import settings
from database import DB_PATH


def get_storage_stats():
    """Return human-readable storage usage for all directories."""
    stats = {}
    for subdir in ["uploads", "archive", "temp"]:
        path = settings.storage_path / subdir
        if not path.exists():
            stats[subdir] = {"size_mb": 0, "files": 0}
            continue
        
        total_size = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        file_count = sum(1 for f in path.rglob("*") if f.is_file())
        
        stats[subdir] = {
            "size_mb": round(total_size / (1024 * 1024), 2),
            "size_gb": round(total_size / (1024 ** 3), 3),
            "files": file_count,
        }
    
    # Total
    total = sum(s["size_mb"] for s in stats.values())
    stats["total"] = {
        "size_mb": round(total, 2),
        "size_gb": round(total / 1024, 3),
        "cap_gb": settings.max_storage_gb,
        "percent": round((total / 1024) / settings.max_storage_gb * 100, 1),
    }
    
    return stats


def print_storage_stats():
    """Print storage stats to console."""
    stats = get_storage_stats()
    print("\n=== Shend Storage Stats ===")
    print(f"Uploads:  {stats['uploads']['size_mb']} MB ({stats['uploads']['files']} files)")
    print(f"Archive:  {stats['archive']['size_mb']} MB ({stats['archive']['files']} files)")
    print(f"Temp:     {stats['temp']['size_mb']} MB ({stats['temp']['files']} files)")
    print(f"Total:    {stats['total']['size_gb']} GB / {stats['total']['cap_gb']} GB ({stats['total']['percent']}%)")
    print("===========================\n")
    return stats


def clear_temp():
    """Delete all files in temp directory."""
    temp_path = settings.storage_path / "temp"
    if not temp_path.exists():
        print("Temp directory does not exist.")
        return
    
    deleted = 0
    freed_mb = 0
    
    for f in temp_path.rglob("*"):
        if f.is_file():
            size = f.stat().st_size
            f.unlink()
            deleted += 1
            freed_mb += size / (1024 * 1024)
    
    print(f"Cleared temp: {deleted} files, {freed_mb:.1f} MB freed")
    return {"deleted": deleted, "freed_mb": round(freed_mb, 2)}


def clear_uploads_older_than(days: int = 7):
    """Delete upload files older than N days."""
    uploads_path = settings.storage_path / "uploads"
    if not uploads_path.exists():
        return
    
    cutoff = datetime.now() - timedelta(days=days)
    deleted = 0
    freed_mb = 0
    
    for f in uploads_path.rglob("*"):
        if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            size = f.stat().st_size
            f.unlink()
            deleted += 1
            freed_mb += size / (1024 * 1024)
    
    print(f"Cleared uploads older than {days} days: {deleted} files, {freed_mb:.1f} MB freed")
    return {"deleted": deleted, "freed_mb": round(freed_mb, 2)}


def clear_archive_older_than(days: int = 90):
    """Delete archive files older than N days."""
    archive_path = settings.storage_path / "archive"
    if not archive_path.exists():
        return
    
    cutoff = datetime.now() - timedelta(days=days)
    deleted = 0
    freed_mb = 0
    
    for f in archive_path.rglob("*"):
        if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            size = f.stat().st_size
            f.unlink()
            deleted += 1
            freed_mb += size / (1024 * 1024)
    
    print(f"Cleared archive older than {days} days: {deleted} files, {freed_mb:.1f} MB freed")
    return {"deleted": deleted, "freed_mb": round(freed_mb, 2)}


async def cleanup_database_orphans():
    """Remove DB rows for files that no longer exist on disk."""
    async with aiosqlite.connect(DB_PATH) as db:
        rows = await db.execute("SELECT token, internal_path FROM uploads")
        all_rows = await rows.fetchall()
        
        removed = 0
        for token, path in all_rows:
            if not Path(path).exists():
                await db.execute("DELETE FROM uploads WHERE token = ?", (token,))
                removed += 1
        
        await db.commit()
        print(f"Cleaned {removed} orphaned database rows")
        return {"removed": removed}


async def run_full_cleanup():
    """Run all cleanup tasks."""
    print("\n=== Starting Full Cleanup ===")
    stats_before = get_storage_stats()
    
    clear_temp()
    clear_uploads_older_than(7)
    clear_archive_older_than(90)
    await cleanup_database_orphans()
    
    stats_after = get_storage_stats()
    freed = stats_before["total"]["size_mb"] - stats_after["total"]["size_mb"]
    
    print(f"\nCleanup complete. Freed {freed:.1f} MB total.")
    print_storage_stats()
    return {"freed_mb": round(freed, 2)}


if __name__ == "__main__":
    import asyncio
    print_storage_stats()
    # Uncomment to run full cleanup:
    # asyncio.run(run_full_cleanup())
