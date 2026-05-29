# main.py
import asyncio
from bot import bot
from server import app
from cleanup import start_scheduler
import uvicorn
from config import settings


async def start_bot():
    await bot.start(settings.bot_token)


async def main():
    # Start cleanup scheduler
    start_scheduler()
    
    bot_task = asyncio.create_task(start_bot())
    server = uvicorn.Server(
        uvicorn.Config(app, host="0.0.0.0", port=7777, log_level="info")
    )
    server_task = asyncio.create_task(server.serve())
    await asyncio.gather(bot_task, server_task)


if __name__ == "__main__":
    asyncio.run(main())
