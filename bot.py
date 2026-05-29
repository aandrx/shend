# bot.py
import discord
from discord.ext import commands
import uuid
from datetime import datetime, timedelta

from config import settings
from database import get_db, init_db


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


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


def run_bot():
    bot.run(settings.bot_token)
