import aiosqlite
from config import settings

DB_PATH = settings.data_path / "bot.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode = WAL;")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS uploads (
                token TEXT PRIMARY KEY,
                discord_user_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                original_filename TEXT,
                internal_path TEXT,              -- REMOVED NOT NULL
                original_size_bytes INTEGER,
                compressed_size_bytes INTEGER,
                status TEXT DEFAULT 'pending',
                is_temp INTEGER DEFAULT 0,
                mode TEXT DEFAULT 'embed',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_uploads_user ON uploads(discord_user_id)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status)
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_uploads_expires ON uploads(expires_at)
        """)
        await db.commit()


async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    await db.execute("PRAGMA journal_mode = WAL;")
    return db
