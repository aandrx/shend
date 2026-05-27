import asyncio
from pathlib import Path
from config import settings


async def compress_to_target(input_path: Path, output_path: Path) -> Path:
    target_mb = settings.target_compress_mb
    target_bits = target_mb * 8 * 1024 * 1024

    # Probe duration
    proc = await asyncio.create_subprocess_exec(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(input_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await proc.communicate()
    duration = float(stdout.decode().strip())

    audio_bps = 96_000
    video_bps = int((target_bits / duration) - audio_bps)

    # If bitrate is too low, drop to 480p
    scale = "scale=854:-2" if video_bps < 500_000 else "scale=1280:-2"
    passlog = str(output_path.with_suffix(".passlog"))

    # Pass 1
    p1 = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", scale,
        "-c:v", "libx264", "-b:v", str(video_bps),
        "-pass", "1", "-passlogfile", passlog,
        "-an", "-f", "null", "/dev/null",
    )
    await p1.communicate()

    # Pass 2
    p2 = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-i", str(input_path),
        "-vf", scale,
        "-c:v", "libx264", "-b:v", str(video_bps),
        "-pass", "2", "-passlogfile", passlog,
        "-c:a", "aac", "-b:a", str(audio_bps),
        "-movflags", "+faststart",
        str(output_path),
    )
    await p2.communicate()

    # Cleanup passlog files
    for ext in ["", ".mbtree"]:
        f = Path(passlog + "-0.log" + ext)
        if f.exists():
            f.unlink()

    return output_path
