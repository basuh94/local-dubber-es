"""Archive finished dubs into a per-video library and drop the intermediates.

The pipeline itself is unchanged: it still writes a single run into ``output/``.
Everything here runs *after* a successful run, so the CLI keeps working exactly as
before and the library is purely additive.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import shutil
from pathlib import Path

from .utils import OUTPUT, ROOT, WORK, ffprobe_duration, read_json, write_json

LIBRARY = ROOT / "library"

# Kept next to the finished video: the deliverable plus the small text/metadata files
# that let you inspect or re-edit a dub without re-running anything.
KEEP = (
    "video_es.mp4",
    "dub_es.wav",
    "subtitles_es.srt",
    "subtitles_source.srt",
    "transcript_es.txt",
    "transcript_source.txt",
    "blocks_es.json",
    "blocks_source.json",
    "blocks_voiced.json",
    "words.json",
    "transcription_meta.json",
)

# Regenerable bulk: 2 WAVs per block plus the staged download and 16 kHz working copy.
RESIDUAL_DIRS = ("dub_blocks",)
RESIDUAL_WORK_GLOBS = ("source.*", "audio_16k.wav", "voice_ref_auto.wav")


def _slug(text: str, limit: int = 60) -> str:
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip()
    text = re.sub(r"[\s_-]+", "-", text)
    return text[:limit].strip("-").lower() or "dub"


def clean_workspace() -> None:
    """Remove intermediates from output/ and work/ without touching the library."""
    for name in RESIDUAL_DIRS:
        shutil.rmtree(OUTPUT / name, ignore_errors=True)
    for item in OUTPUT.iterdir():
        if item.name == ".gitkeep":
            continue
        if item.is_dir():
            shutil.rmtree(item, ignore_errors=True)
        else:
            item.unlink(missing_ok=True)
    for pattern in RESIDUAL_WORK_GLOBS:
        for item in WORK.glob(pattern):
            item.unlink(missing_ok=True)


def freed_bytes() -> int:
    """Bytes currently sitting in the regenerable intermediates."""
    total = 0
    for name in RESIDUAL_DIRS:
        d = OUTPUT / name
        if d.is_dir():
            total += sum(f.stat().st_size for f in d.rglob("*") if f.is_file())
    for pattern in RESIDUAL_WORK_GLOBS:
        total += sum(f.stat().st_size for f in WORK.glob(pattern) if f.is_file())
    return total


def archive(source_url: str, title: str, profile: str, source_lang: str | None,
            thumbnail: bytes | None = None, elapsed: float | None = None) -> dict:
    """Move a finished run out of output/ into library/<id>/ and clean the rest."""
    video = OUTPUT / "video_es.mp4"
    if not video.exists():
        raise FileNotFoundError("output/video_es.mp4 not found; the run did not finish")

    LIBRARY.mkdir(parents=True, exist_ok=True)
    stamp = _dt.datetime.now()
    entry_id = f"{stamp:%Y%m%d-%H%M%S}_{_slug(title)}"
    dest = LIBRARY / entry_id
    dest.mkdir(parents=True, exist_ok=True)

    reclaimed = freed_bytes()
    duration = ffprobe_duration(video)

    for name in KEEP:
        src = OUTPUT / name
        if src.exists():
            shutil.move(str(src), str(dest / name))

    if thumbnail:
        (dest / "thumb.jpg").write_bytes(thumbnail)

    warnings: list[str] = []
    trimmed = 0
    voiced = dest / "blocks_voiced.json"
    if voiced.exists():
        blocks = read_json(voiced)
        trimmed = sum(1 for b in blocks if b.get("timing", {}).get("trimmed"))
        for b in blocks:
            t = b.get("timing", {})
            if t.get("trimmed"):
                warnings.append(
                    f"Bloque {b['id']}: {t['actual']:.2f}s de voz en una ventana de "
                    f"{t['window']:.2f}s; se recorto la cola."
                )

    meta = {
        "id": entry_id,
        "title": title,
        "url": source_url,
        "profile": profile,
        "source_lang": source_lang or "auto",
        "created": stamp.isoformat(timespec="seconds"),
        "duration": duration,
        "elapsed": elapsed,
        "blocks": len(read_json(dest / "blocks_es.json")) if (dest / "blocks_es.json").exists() else 0,
        "trimmed_blocks": trimmed,
        "warnings": warnings,
        "size": sum(f.stat().st_size for f in dest.rglob("*") if f.is_file()),
        "reclaimed": reclaimed,
        "has_thumb": bool(thumbnail),
    }
    write_json(dest / "meta.json", meta)
    clean_workspace()
    return meta


def entries() -> list[dict]:
    """Every archived dub, newest first."""
    if not LIBRARY.exists():
        return []
    out = []
    for d in LIBRARY.iterdir():
        meta_path = d / "meta.json"
        if not d.is_dir() or not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        meta["exists"] = (d / "video_es.mp4").exists()
        out.append(meta)
    return sorted(out, key=lambda m: m.get("created", ""), reverse=True)


def entry_dir(entry_id: str) -> Path:
    """Resolve an entry id to its directory, rejecting anything outside the library."""
    candidate = (LIBRARY / entry_id).resolve()
    if candidate.parent != LIBRARY.resolve() or not candidate.is_dir():
        raise KeyError(entry_id)
    return candidate


def delete(entry_id: str) -> None:
    shutil.rmtree(entry_dir(entry_id))
