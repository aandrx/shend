import magic
from datetime import datetime, timedelta
from config import settings
import aiosqlite
from database import DB_PATH


ALLOWED_MIMES = {"video/mp4", "video/quicktime", "video/x-msvideo"}


def validate_magic(file_bytes: bytes) -> bool:
    detected = magic.from_buffer(file_bytes, mime=True)
    return detected in ALLOWED_MIMES


async def check_rate_limit(user_id: str) -> bool:
    cutoff = datetime.utcnow() - timedelta(hours=1)
    async with aiosqlite.connect(DB_PATH) as db:
        row = await db.execute(
            "SELECT COUNT(*) FROM uploads WHERE discord_user_id = ? AND created_at > ? AND status = 'complete'",
            (user_id, cutoff),
        )
        result = await row.fetchone()
        count = result[0] if result is not None else 0
        return count < settings.rate_limit_per_hour


def check_disk_pressure() -> bool:
    total = sum(
        f.stat().st_size
        for f in settings.storage_path.rglob("*")
        if f.is_file()
    )
    used_gb = total / (1024 ** 3)
    return used_gb < (settings.max_storage_gb - 0.5)
