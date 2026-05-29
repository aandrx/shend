# bot.py
import discord
from discord.ext import commands
import uuid
from datetime import datetime, timedelta
from pathlib import Path
import traceback

from config import settings
from database import get_db, init_db


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Track bot startup time for uptime calculation
BOT_START_TIME = datetime.utcnow()


@bot.event
async def on_ready():
    print(f"[BOT] Shend logged in as {bot.user}")
    try:
        print("[BOT] Initializing database...")
        await init_db()
        print("[BOT] Database initialized")
    except Exception as e:
        print(f"[BOT] Database init failed: {e}")
        import traceback
        traceback.print_exc()

    try:
        synced = await bot.tree.sync()
        print(f"[BOT] Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"[BOT] Command sync failed: {e}")
        import traceback
        traceback.print_exc()


@bot.tree.command(name="upload", description="Get a link to upload a video that embeds inline in chat")
async def upload(interaction: discord.Interaction):
    if interaction.user is None or interaction.channel is None:
        return

    print(f"[CMD] /upload triggered by {interaction.user.id}")
    
    try:
        await interaction.response.defer(ephemeral=True)
        print("[CMD] Deferred reply")
    except Exception as e:
        print(f"[CMD] deferReply failed: {e}")
        import traceback
        traceback.print_exc()
        return

    try:
        token = uuid.uuid4().hex
        expires = datetime.utcnow() + timedelta(minutes=15)

        db = await get_db()
        await db.execute(
            "INSERT INTO uploads (token, discord_user_id, channel_id, guild_id, expires_at, mode, interaction_token, application_id) VALUES (?,?,?,?,?,?,?,?)",
            (
                token,
                str(interaction.user.id),
                str(interaction.channel.id),
                str(interaction.guild_id) if interaction.guild_id is not None else None,
                expires,
                "embed",
                interaction.token,
                str(bot.application_id),
            ),
        )
        await db.commit()
        await db.close()

        url = f"{settings.base_url}/upload?token={token}"
        print(f"[CMD] Sending followup with URL: {url}")
        
        await interaction.followup.send(
            f"Upload your video here (expires in 15 min): {url}",
            ephemeral=True,
        )
        print("[CMD] Followup sent successfully")

    except Exception as e:
        print(f"[CMD] /upload failed: {e}")
        import traceback
        traceback.print_exc()
        try:
            await interaction.followup.send(
                f"Error: {e}",
                ephemeral=True,
            )
        except:
            pass


@bot.tree.command(name="downsize", description="Get a link to upload a large video and receive a compressed download")
async def downsize(interaction: discord.Interaction):
    if interaction.user is None or interaction.channel is None:
        return

    print(f"[CMD] /downsize triggered by {interaction.user.id}")
    
    try:
        await interaction.response.defer(ephemeral=True)
        print("[CMD] Deferred reply")
    except Exception as e:
        print(f"[CMD] deferReply failed: {e}")
        import traceback
        traceback.print_exc()
        return

    try:
        token = uuid.uuid4().hex
        expires = datetime.utcnow() + timedelta(minutes=15)

        db = await get_db()
        await db.execute(
            "INSERT INTO uploads (token, discord_user_id, channel_id, guild_id, expires_at, mode, interaction_token, application_id) VALUES (?,?,?,?,?,?,?,?)",
            (
                token,
                str(interaction.user.id),
                str(interaction.channel.id),
                str(interaction.guild_id) if interaction.guild_id is not None else None,
                expires,
                "download",
                interaction.token,
                str(bot.application_id),
            ),
        )
        await db.commit()
        await db.close()

        url = f"{settings.base_url}/upload?token={token}"
        print(f"[CMD] Sending followup with URL: {url}")
        
        await interaction.followup.send(
            f"Upload your video here to get a compressed download (expires in 15 min): {url}",
            ephemeral=True,
        )
        print("[CMD] Followup sent successfully")

    except Exception as e:
        print(f"[CMD] /downsize failed: {e}")
        import traceback
        traceback.print_exc()
        try:
            await interaction.followup.send(
                f"Error: {e}",
                ephemeral=True,
            )
        except:
            pass


async def get_bot_status(user_id: str | None = None):
    """Gather simple bot status metrics."""
    try:
        uptime = datetime.utcnow() - BOT_START_TIME
        uptime_str = f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds % 3600) // 60}m"

        storage_path = settings.storage_path
        total_size = sum(f.stat().st_size for f in storage_path.rglob("*") if f.is_file())
        used_gb = total_size / (1024 ** 3)
        max_gb = settings.max_storage_gb
        usage_percent = (used_gb / max_gb) * 100 if max_gb > 0 else 0

        db = await get_db()
        
        stats_row = await db.execute(
            "SELECT status, COUNT(*) as count FROM uploads GROUP BY status"
        )
        stats = await stats_row.fetchall()
        status_counts = {row[0]: row[1] for row in stats}
        
        total_videos = sum(status_counts.values())
        
        await db.close()

        return {
            "uptime": uptime_str,
            "storage_used_gb": round(used_gb, 2),
            "storage_max_gb": max_gb,
            "storage_percent": round(usage_percent, 1),
            "total_videos": total_videos,
            "videos_complete": status_counts.get("complete", 0),
        }
    except Exception as e:
        print(f"[STATUS] Error gathering metrics: {e}")
        traceback.print_exc()
        return None


@bot.tree.command(name="status", description="View bot status")
async def status(interaction: discord.Interaction):
    """Show a simple one-line bot status."""
    if interaction.user is None:
        return

    try:
        await interaction.response.defer()
        status_data = await get_bot_status()
        
        if not status_data:
            await interaction.followup.send("Failed to get status.")
            return

        msg = f"**Shend Status** - Uptime: {status_data['uptime']} | Storage: {status_data['storage_used_gb']}/{status_data['storage_max_gb']} GB ({status_data['storage_percent']}%) | Videos: {status_data['total_videos']} ({status_data['videos_complete']} complete)"
        await interaction.followup.send(msg)

    except Exception as e:
        await interaction.followup.send(f"Error: {e}")


def run_bot():
    bot.run(settings.bot_token)
