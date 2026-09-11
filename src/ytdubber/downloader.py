from __future__ import annotations
from pathlib import Path
import shutil
import subprocess
from .utils import WORK, ensure_dirs


def download_source(source: str) -> tuple[Path, Path]:
    """Return (video_path, audio_16k_path). source may be a URL or local video file."""
    ensure_dirs()
    local = Path(source)
    if local.exists():
        video_path = WORK / ("source" + local.suffix.lower())
        shutil.copy2(local, video_path)
    else:
        import yt_dlp
        # The output template is a fixed name, not keyed by URL, so a leftover source.*
        # from an earlier run (or from the FFmpeg integration test) would make yt-dlp
        # report "has already been downloaded" and silently dub the wrong video.
        for stale in WORK.glob("source.*"):
            stale.unlink()
        template = str(WORK / "source.%(ext)s")
        opts = {
            "format": "bv*[height<=1080]+ba/b[height<=1080]/b",
            "outtmpl": template,
            "merge_output_format": "mp4",
            "noplaylist": True,
            "quiet": False,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(source, download=True)
            # yt-dlp can merge to mp4 regardless of the prepared pre-merge filename.
            candidates = sorted(WORK.glob("source.*"), key=lambda p: p.stat().st_mtime, reverse=True)
            candidates = [p for p in candidates if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
            if not candidates:
                raise RuntimeError("yt-dlp finished but no source video was found")
            video_path = candidates[0]

    audio16 = WORK / "audio_16k.wav"
    subprocess.run([
        "ffmpeg", "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", str(audio16)
    ], check=True)
    return video_path, audio16
