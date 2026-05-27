import discord
from discord.ext import commands
import uuid
from datetime import datetime, timedelta

from config import settings
from database import get_db


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"Shend logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(e)


@bot.tree.command(name="upload", description="Get a link to upload a video that embeds inline in chat")
async def upload(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not interaction.user or not interaction.channel:
        raise ValueError("User and channel must be defined in interaction")

    token = uuid.uuid4().hex
    expires = datetime.utcnow() + timedelta(minutes=15)

    db = await get_db()
    await db.execute(
        "INSERT INTO uploads (token, discord_user_id, channel_id, guild_id, expires_at, mode) VALUES (?,?,?,?,?,?)",
        (token, str(interaction.user.id), str(interaction.channel.id), str(interaction.guild_id) if interaction.guild_id else None, expires, "embed"),
    )
    await db.commit()
    await db.close()

    url = f"{settings.base_url}/upload?token={token}"
    await interaction.followup.send(
        f"Upload your video here (expires in 15 min): {url}",
        ephemeral=True,
    )


@bot.tree.command(name="downsize", description="Get a link to upload a large video and receive a <10MB download")
async def downsize(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    if not interaction.user or not interaction.channel:
        raise ValueError("User and channel must be defined in interaction")

    token = uuid.uuid4().hex
    expires = datetime.utcnow() + timedelta(minutes=15)

    db = await get_db()
    await db.execute(
        "INSERT INTO uploads (token, discord_user_id, channel_id, guild_id, expires_at, mode) VALUES (?,?,?,?,?,?)",
        (token, str(interaction.user.id), str(interaction.channel.id), str(interaction.guild_id) if interaction.guild_id else None, expires, "download"),
    )
    await db.commit()
    await db.close()

    url = f"{settings.base_url}/upload?token={token}"
    await interaction.followup.send(
        f"Upload your video here to get a compressed download (expires in 15 min): {url}",
        ephemeral=True,
    )


def run_bot():
    bot.run(settings.bot_token)
