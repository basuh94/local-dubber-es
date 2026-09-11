"""Local control panel for the dubbing pipeline.

Runs the existing CLI as a subprocess (one job at a time, because the pipeline uses
shared work/ and output/ directories), streams its progress, then archives the result
into the library and deletes the intermediates.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel

from . import __version__, library
from .models import PROFILES
from .utils import OUTPUT, ROOT

WEB = Path(__file__).resolve().parent / "web"

STAGES = {
    1: "Descargando y extrayendo audio",
    2: "Transcribiendo (faster-whisper)",
    3: "Segmentando en bloques",
    4: "Traduciendo al espanol (Ollama)",
    5: "Preparando referencia de voz",
    6: "Sintetizando voz (Chatterbox) y ajustando tiempos",
    7: "Mezclando el video final",
}
TOTAL_STAGES = len(STAGES)

_STAGE_RE = re.compile(r"\[(\d)/7\]")
_WARN_RE = re.compile(r"\[warn\]\s*(.+)")
_LOG_LIMIT = 400

_lock = threading.Lock()
_job: dict | None = None
_process: subprocess.Popen | None = None


def _snapshot() -> dict:
    with _lock:
        if _job is None:
            return {"status": "idle"}
        job = dict(_job)
        job["log"] = list(job["log"])[-60:]
        job["warnings"] = list(job["warnings"])
        if job["status"] in {"preparing", "running", "archiving", "cancelling"}:
            job["elapsed"] = time.time() - job["started"]
        return job


def _set(**fields) -> None:
    with _lock:
        if _job is not None:
            _job.update(fields)


def _log(line: str) -> None:
    with _lock:
        if _job is None:
            return
        _job["log"].append(line)
        if len(_job["log"]) > _LOG_LIMIT:
            del _job["log"][:-_LOG_LIMIT]


def _probe_source(source: str) -> tuple[str, bytes | None]:
    """Title and thumbnail for a URL; falls back to the filename for local videos."""
    if Path(source).exists():
        return Path(source).stem, None
    try:
        import yt_dlp

        with yt_dlp.YoutubeDL({"quiet": True, "noplaylist": True, "skip_download": True}) as ydl:
            info = ydl.extract_info(source, download=False)
        title = info.get("title") or source
        thumb = None
        url = info.get("thumbnail")
        if url:
            try:
                with urllib.request.urlopen(url, timeout=15) as response:
                    thumb = response.read(4_000_000) or None
            except Exception:
                thumb = None
        return title, thumb
    except Exception as exc:
        _log(f"[aviso] no se pudo leer metadatos del origen: {exc}")
        return source, None


def _tts_progress() -> tuple[int, int]:
    """Blocks synthesized so far, so the longest stage shows real movement."""
    try:
        total = len(json.loads((OUTPUT / "blocks_es.json").read_text(encoding="utf-8")))
    except Exception:
        return 0, 0
    done = len(list((OUTPUT / "dub_blocks").glob("block_*[0-9].wav")))
    return min(done, total), total


def _run(source: str, profile: str, source_lang: str | None, voice_ref: str | None) -> None:
    global _process
    started = _snapshot().get("started", time.time())
    try:
        _set(status="preparing", stage_label="Leyendo metadatos del origen")
        title, thumb = _probe_source(source)
        _set(title=title)

        library.clean_workspace()

        cmd = [sys.executable, "-m", "ytdubber.cli", "dub", source, "--profile", profile]
        if source_lang:
            cmd += ["--source-lang", source_lang]
        if voice_ref:
            cmd += ["--voice-ref", voice_ref]

        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
        # Cancelling during the metadata probe has no subprocess to terminate yet, so
        # check here rather than launching a 3-minute run that would be thrown away.
        if _snapshot().get("status") == "cancelling":
            _set(status="cancelled", stage_label="Cancelado", elapsed=time.time() - started)
            return
        _set(status="running", stage=1, stage_label=STAGES[1])
        _log("$ " + " ".join(cmd))

        proc = subprocess.Popen(
            cmd, cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
        )
        with _lock:
            _process = proc

        stage_now = 1
        for raw in proc.stdout:
            line = raw.rstrip()
            if not line:
                continue
            _log(line)
            match = _STAGE_RE.search(line)
            if match:
                stage_now = int(match.group(1))
                _set(stage=stage_now, stage_label=STAGES.get(stage_now, ""),
                     tts_done=0, tts_total=0)
            warn = _WARN_RE.search(line)
            if warn:
                with _lock:
                    if _job is not None:
                        _job["warnings"].append(warn.group(1).strip())
            if stage_now == 6:
                done, total = _tts_progress()
                if total:
                    _set(tts_done=done, tts_total=total)

        code = proc.wait()
        with _lock:
            cancelled = _job is not None and _job.get("status") == "cancelling"
            _process = None

        if cancelled:
            library.clean_workspace()
            _set(status="cancelled", stage_label="Cancelado", elapsed=time.time() - started)
            return
        if code != 0:
            _set(status="error", error=f"El pipeline termino con codigo {code}",
                 stage_label="Error", elapsed=time.time() - started)
            return

        _set(status="archiving", stage=TOTAL_STAGES,
             stage_label="Archivando y limpiando residuos")
        elapsed = time.time() - started
        meta = library.archive(source, title, profile, source_lang, thumb, elapsed)
        _log(f"Archivado en library/{meta['id']} "
             f"({meta['reclaimed'] / 1e6:.0f} MB de residuo eliminados)")
        _set(status="done", stage_label="Terminado", entry_id=meta["id"], elapsed=elapsed)
    except Exception as exc:  # surfaced in the UI rather than dying silently
        _set(status="error", error=f"{type(exc).__name__}: {exc}", stage_label="Error")
        _log(f"[error] {type(exc).__name__}: {exc}")
    finally:
        with _lock:
            _process = None


class JobRequest(BaseModel):
    source: str
    profile: str = "balanced"
    source_lang: str | None = "en"
    voice_ref: str | None = None


app = FastAPI(title="YouTube Dubber")


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    return HTMLResponse((WEB / "index.html").read_text(encoding="utf-8"))


@app.get("/api/profiles")
def profiles() -> dict:
    return {
        name: {"asr": p.asr_model, "llm": p.ollama_model, "max_speedup": p.max_speedup}
        for name, p in PROFILES.items()
    }


@app.get("/api/system")
def system() -> dict:
    """GPU and VRAM, so the panel shows whether CUDA is really in play."""
    info: dict = {"version": __version__, "gpu": None, "vram_used": None, "vram_total": None}
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        ).stdout.strip().splitlines()
        if out:
            name, used, total = (p.strip() for p in out[0].split(","))
            info.update(gpu=name, vram_used=int(used), vram_total=int(total))
    except Exception:
        pass
    return info


@app.get("/api/job")
def job() -> dict:
    return _snapshot()


@app.post("/api/job")
def start(req: JobRequest) -> dict:
    global _job
    source = req.source.strip()
    if not source:
        raise HTTPException(400, "Indica una URL o la ruta de un video local.")
    if req.profile not in PROFILES:
        raise HTTPException(400, f"Perfil desconocido: {req.profile}")
    with _lock:
        busy = {"preparing", "running", "archiving", "cancelling"}
        if _job is not None and _job["status"] in busy:
            raise HTTPException(409, "Ya hay un doblaje en curso. El pipeline usa work/ y "
                                     "output/ compartidos, asi que solo puede ejecutarse uno "
                                     "cada vez.")
        _job = {
            "status": "preparing", "source": source, "title": source,
            "profile": req.profile, "source_lang": req.source_lang,
            "stage": 0, "stage_label": "Iniciando", "total_stages": TOTAL_STAGES,
            "tts_done": 0, "tts_total": 0, "started": time.time(), "elapsed": 0.0,
            "log": [], "warnings": [], "error": None, "entry_id": None,
        }
    threading.Thread(
        target=_run, args=(source, req.profile, req.source_lang, req.voice_ref), daemon=True
    ).start()
    return _snapshot()


@app.post("/api/job/cancel")
def cancel() -> dict:
    with _lock:
        if _job is None or _job["status"] not in {"preparing", "running"}:
            raise HTTPException(409, "No hay ningun doblaje en curso.")
        _job["status"] = "cancelling"
        _job["stage_label"] = "Cancelando..."
        proc = _process
    if proc is not None:
        proc.terminate()
    return _snapshot()


@app.get("/api/library")
def entries() -> list[dict]:
    return library.entries()


@app.delete("/api/library/{entry_id}")
def remove(entry_id: str) -> JSONResponse:
    try:
        library.delete(entry_id)
    except KeyError:
        raise HTTPException(404, "No existe ese video en la biblioteca.")
    return JSONResponse({"deleted": entry_id})


def _entry_file(entry_id: str, name: str) -> Path:
    try:
        path = library.entry_dir(entry_id) / name
    except KeyError:
        raise HTTPException(404, "No existe ese video en la biblioteca.")
    if not path.exists():
        raise HTTPException(404, f"{name} no esta disponible para este video.")
    return path


@app.get("/media/{entry_id}/video")
def video(entry_id: str) -> FileResponse:
    return FileResponse(_entry_file(entry_id, "video_es.mp4"), media_type="video/mp4")


@app.get("/media/{entry_id}/thumb")
def thumb(entry_id: str) -> FileResponse:
    return FileResponse(_entry_file(entry_id, "thumb.jpg"), media_type="image/jpeg")


@app.get("/media/{entry_id}/file/{name}")
def artifact(entry_id: str, name: str) -> FileResponse:
    if name not in library.KEEP:
        raise HTTPException(404, "Artefacto desconocido.")
    return FileResponse(_entry_file(entry_id, name), filename=name)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    print(f"Panel de control en http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="warning")
