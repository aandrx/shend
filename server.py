from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import uuid
from datetime import datetime, timedelta
import aiohttp

from config import settings
from database import init_db, get_db
from compress import compress_to_target
from validators import validate_magic, check_rate_limit, check_disk_pressure


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
templates = Jinja2Templates(directory="/app/templates")

Path("templates").mkdir(exist_ok=True)


@app.get("/upload", response_class=HTMLResponse)
async def upload_form(request: Request, token: str = Query(...)):
    db = await get_db()
    row = await db.execute(
        "SELECT * FROM uploads WHERE token = ? AND status = 'pending' AND expires_at > ?",
        (token, datetime.utcnow()),
    )
    upload = await row.fetchone()
    await db.close()

    if not upload:
        raise HTTPException(403, "Invalid or expired token")

    return templates.TemplateResponse(request=request, name="upload.html", context={"token": token})


@app.post("/upload")
async def upload_receive(token: str = Query(...), video: UploadFile = File(...)):
    db = await get_db()
    row = await db.execute(
        "SELECT * FROM uploads WHERE token = ? AND status = 'pending' AND expires_at > ?",
        (token, datetime.utcnow()),
    )
    job = await row.fetchone()

    if not job:
        await db.close()
        raise HTTPException(403, "Invalid or expired token")

    user_id = job[1]
    channel_id = job[2]
    mode = job[10]  # mode column index

    if not await check_rate_limit(user_id):
        await db.close()
        raise HTTPException(429, "Rate limit exceeded")

    if not check_disk_pressure():
        await db.close()
        raise HTTPException(507, "Storage full")

    temp_id = uuid.uuid4().hex
    temp_input = settings.storage_path / "temp" / f"{temp_id}_{video.filename}"
    temp_output = settings.storage_path / "temp" / f"{temp_id}_compressed.mp4"

    content = await video.read()
    if not validate_magic(content):
        await db.close()
        raise HTTPException(400, "Invalid file type")

    temp_input.write_bytes(content)

    # Compress
    try:
        await compress_to_target(temp_input, temp_output)
    except Exception as e:
        await db.execute("UPDATE uploads SET status = 'failed' WHERE token = ?", (token,))
        await db.commit()
        await db.close()
        temp_input.unlink(missing_ok=True)
        raise HTTPException(500, f"Compression failed: {e}")

    size = temp_output.stat().st_size

    # Branch based on mode
    if mode == "embed":
        # /upload: move to uploads dir, post viewer link in channel
        final_path = settings.storage_path / "uploads" / f"{token}.mp4"
        temp_output.rename(final_path)

        await db.execute(
            "UPDATE uploads SET status = 'complete', internal_path = ?, compressed_size_bytes = ?, is_temp = 0 WHERE token = ?",
            (str(final_path), size, token),
        )
        await db.commit()
        await db.close()

        await post_to_channel(channel_id, token)

    else:
        # /downsize: keep in temp, DM download link to user, mark for cleanup
        final_path = settings.storage_path / "temp" / f"{token}.mp4"
        temp_output.rename(final_path)

        await db.execute(
            "UPDATE uploads SET status = 'complete', internal_path = ?, compressed_size_bytes = ?, is_temp = 1 WHERE token = ?",
            (str(final_path), size, token),
        )
        await db.commit()
        await db.close()

        await dm_user(user_id, token, size)

    temp_input.unlink(missing_ok=True)

    return {"status": "complete", "url": f"{settings.base_url}/v/{token}" if mode == "embed" else f"{settings.base_url}/d/{token}"}


@app.get("/v/{token}", response_class=HTMLResponse)
async def viewer_page(token: str):
    db = await get_db()
    row = await db.execute(
        "SELECT * FROM uploads WHERE token = ? AND status = 'complete'",
        (token,),
    )
    upload = await row.fetchone()
    await db.close()

    if not upload:
        raise HTTPException(404)

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta property="og:type" content="video.other" />
        <meta property="og:video" content="{settings.base_url}/f/{token}.mp4" />
        <meta property="og:video:type" content="video/mp4" />
        <meta property="og:video:width" content="1280" />
        <meta property="og:video:height" content="720" />
        <meta property="og:title" content="Shared Video" />
        <meta name="twitter:card" content="player" />
    </head>
    <body>
        <video controls style="max-width:100%">
            <source src="/f/{token}.mp4" type="video/mp4" />
        </video>
    </body>
    </html>
    """


@app.get("/f/{token}.mp4")
async def serve_file(token: str):
    db = await get_db()
    row = await db.execute(
        "SELECT internal_path FROM uploads WHERE token = ? AND status = 'complete'",
        (token,),
    )
    result = await row.fetchone()
    await db.close()

    if not result:
        raise HTTPException(404)

    file_path = Path(result[0])
    if not file_path.exists():
        raise HTTPException(404)

    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=f"{token}.mp4",
        headers={"Accept-Ranges": "bytes"},
    )


@app.get("/d/{token}")
async def download_file(token: str):
    db = await get_db()
    row = await db.execute(
        "SELECT internal_path FROM uploads WHERE token = ? AND status = 'complete'",
        (token,),
    )
    result = await row.fetchone()
    await db.close()

    if not result:
        raise HTTPException(404)

    file_path = Path(result[0])
    if not file_path.exists():
        raise HTTPException(404)

    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=f"{token}.mp4",
        headers={"Content-Disposition": f'attachment; filename="{token}.mp4"'},
    )


async def post_to_channel(channel_id: str, token: str):
    url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {settings.bot_token}",
        "Content-Type": "application/json",
    }
    payload = {
        "content": f"{settings.base_url}/v/{token}",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status not in (200, 204):
                print(f"Failed to post to channel: {resp.status}")


async def dm_user(user_id: str, token: str, size: int):
    # Create DM channel first
    url = "https://discord.com/api/v10/users/@me/channels"
    headers = {
        "Authorization": f"Bot {settings.bot_token}",
        "Content-Type": "application/json",
    }
    payload = {"recipient_id": user_id}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status not in (200, 201):
                print(f"Failed to create DM: {resp.status}")
                return
            data = await resp.json()
            dm_channel_id = data["id"]

        # Send message with download link
        msg_url = f"https://discord.com/api/v10/channels/{dm_channel_id}/messages"
        msg_payload = {
            "content": f"Your compressed video is ready! ({size / 1024 / 1024:.1f}MB)\nDownload: {settings.base_url}/d/{token}\nLink expires in 1 hour.",
        }

        async with session.post(msg_url, headers=headers, json=msg_payload) as resp:
            if resp.status not in (200, 204):
                print(f"Failed to send DM: {resp.status}")
