from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File, HTTPException, Query
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import uuid
from datetime import datetime, timedelta
import aiohttp
import time

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
    start_time = time.time()
    print(f"[WEB] Upload started for token: {token}")
    print(f"[WEB] File: {video.filename}, size: {video.size} bytes")

    db = await get_db()
    row = await db.execute(
        "SELECT * FROM uploads WHERE token = ? AND status = 'pending' AND expires_at > ?",
        (token, datetime.utcnow()),
    )
    job = await row.fetchone()

    if not job:
        await db.close()
        print("[WEB] Token invalid or expired")
        raise HTTPException(403, "Invalid or expired token")

    user_id = job[1]
    channel_id = job[2]
    mode = job[12]  # mode column
    interaction_token = job[5]
    application_id = job[6]
    original_name = video.filename or "upload.mp4"

    print(f"[WEB] User: {user_id}, Mode: {mode}, Channel: {channel_id}")

    rate_ok = await check_rate_limit(user_id)
    print(f"[WEB] Rate limit check: allowed={rate_ok}")
    if not rate_ok:
        await db.close()
        raise HTTPException(429, "Rate limit exceeded")

    disk_ok = check_disk_pressure()
    print(f"[WEB] Disk pressure check: ok={disk_ok}")
    if not disk_ok:
        await db.close()
        raise HTTPException(507, "Storage full")

    temp_id = uuid.uuid4().hex
    temp_input = settings.storage_path / "temp" / f"{temp_id}_{original_name}"
    temp_output = settings.storage_path / "temp" / f"{temp_id}_compressed.mp4"

    print(f"[WEB] Saving to temp: {temp_input}")
    content = await video.read()
    print(f"[WEB] Read {len(content)} bytes from upload")

    if not validate_magic(content):
        await db.close()
        print("[WEB] Magic number validation failed")
        raise HTTPException(400, "Invalid file type")

    temp_input.write_bytes(content)
    print(f"[WEB] Saved temp file")

    print("[WEB] Starting FFmpeg compression...")
    compress_start = time.time()
    try:
        await compress_to_target(temp_input, temp_output)
    except Exception as e:
        print(f"[WEB] Compression failed: {e}")
        await db.execute("UPDATE uploads SET status = 'failed' WHERE token = ?", (token,))
        await db.commit()
        await db.close()
        temp_input.unlink(missing_ok=True)
        raise HTTPException(500, f"Compression failed: {e}")

    compress_time = time.time() - compress_start
    size = temp_output.stat().st_size
    print(f"[WEB] Compression complete in {compress_time:.1f}s: {size} bytes ({size / 1024 / 1024:.1f}MB)")

    # Preserve original name for download mode
    safe_name = "".join(c for c in original_name if c.isalnum() or c in "._-").rstrip()
    base_name = Path(safe_name).stem
    output_name = f"{base_name}_downsized.mp4"

    total_time = time.time() - start_time
    print(f"[WEB] Total processing time: {total_time:.1f}s")

    if mode == "embed":
        final_path = settings.storage_path / "uploads" / f"{token}.mp4"
        temp_output.rename(final_path)
        print(f"[WEB] Moved to uploads: {final_path}")

        await db.execute(
            "UPDATE uploads SET status = 'complete', internal_path = ?, compressed_size_bytes = ?, is_temp = 0, original_filename = ? WHERE token = ?",
            (str(final_path), size, original_name, token),
        )
        await db.commit()
        await db.close()

        print("[WEB] Posting viewer link to Discord channel")
        await post_to_channel(channel_id, token)

    else:
        final_path = settings.storage_path / "temp" / f"{token}_{output_name}"
        temp_output.rename(final_path)
        print(f"[WEB] Kept in temp for download: {final_path}")

        await db.execute(
            "UPDATE uploads SET status = 'complete', internal_path = ?, compressed_size_bytes = ?, is_temp = 1, original_filename = ? WHERE token = ?",
            (str(final_path), size, original_name, token),
        )
        await db.commit()
        await db.close()

        print("[WEB] Sending ephemeral download link")
        await post_downsize_ephemeral(interaction_token, application_id, user_id, token, output_name, size)

    temp_input.unlink(missing_ok=True)
    print("[WEB] Cleaned up temp input")

    result_url = f"{settings.base_url}/v/{token}" if mode == "embed" else f"{settings.base_url}/d/{token}"
    print(f"[WEB] Done. Result URL: {result_url}")
    return {"status": "complete", "url": result_url, "time_seconds": round(total_time, 1)}


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
        "SELECT internal_path, original_filename FROM uploads WHERE token = ? AND status = 'complete'",
        (token,),
    )
    result = await row.fetchone()
    await db.close()

    if not result:
        raise HTTPException(404)

    file_path = Path(result[0])
    original_name = result[1] or f"{token}.mp4"
    if not file_path.exists():
        raise HTTPException(404)

    safe_name = "".join(c for c in original_name if c.isalnum() or c in "._-").rstrip()
    base_name = Path(safe_name).stem
    download_name = f"{base_name}_downsized.mp4"

    return FileResponse(
        file_path,
        media_type="video/mp4",
        filename=download_name,
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
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
                print(f"[WEB] Failed to post to channel: {resp.status}")
            else:
                print(f"[WEB] Posted to channel successfully")


async def post_downsize_ephemeral(interaction_token: str, application_id: str, user_id: str, token: str, filename: str, size: int):
    """Send ephemeral followup message for /downsize using Discord's webhook."""
    url = f"https://discord.com/api/v10/webhooks/{application_id}/{interaction_token}"
    headers = {
        "Content-Type": "application/json",
    }
    
    payload = {
        "content": f"Your compressed video is ready! ({size / 1024 / 1024:.1f}MB)\nDownload: {settings.base_url}/d/{token}",
        "flags": 64,  # EPHEMERAL flag
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status not in (200, 204):
                print(f"[WEB] Failed to send ephemeral followup: {resp.status}")
                # Fallback: DM the user
                await dm_user(user_id, token, size)
            else:
                print(f"[WEB] Sent ephemeral followup successfully")


async def dm_user(user_id: str, token: str, size: int):
    """Fallback DM if ephemeral fails."""
    url = "https://discord.com/api/v10/users/@me/channels"
    headers = {
        "Authorization": f"Bot {settings.bot_token}",
        "Content-Type": "application/json",
    }
    payload = {"recipient_id": user_id}

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as resp:
            if resp.status not in (200, 201):
                print(f"[WEB] Failed to create DM: {resp.status}")
                return
            data = await resp.json()
            dm_channel_id = data["id"]

        msg_url = f"https://discord.com/api/v10/channels/{dm_channel_id}/messages"
        msg_payload = {
            "content": f"Your compressed video is ready! ({size / 1024 / 1024:.1f}MB)\nDownload: {settings.base_url}/d/{token}\nLink expires in 1 hour.",
        }

        async with session.post(msg_url, headers=headers, json=msg_payload) as resp:
            if resp.status not in (200, 204):
                print(f"[WEB] Failed to send DM: {resp.status}")
            else:
                print(f"[WEB] DM sent successfully")
