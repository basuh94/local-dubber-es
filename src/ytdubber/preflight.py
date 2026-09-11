from __future__ import annotations
import os
import platform
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from .utils import VENDOR_CUDA, activate_vendor_cuda


def _ok(label, value): print(f"[OK]   {label}: {value}")
def _bad(label, value): print(f"[FAIL] {label}: {value}")
def _warn(label, value): print(f"[WARN] {label}: {value}")


def run_preflight(ollama_model="qwen3:8b") -> bool:
    from . import __version__

    good = True
    print(f"=== YouTube Dubber preflight (v{__version__}) ===")
    if sys.version_info[:2] == (3, 11): _ok("Python", sys.version.split()[0])
    else: _bad("Python", f"{sys.version.split()[0]} (required: 3.11.x)"); good = False

    for cmd in ("ffmpeg", "ffprobe"):
        if shutil.which(cmd): _ok(cmd, shutil.which(cmd))
        else: _bad(cmd, "not found in PATH"); good = False

    if shutil.which("nvidia-smi"):
        cp = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"], capture_output=True, text=True)
        _ok("NVIDIA", cp.stdout.strip() or "detected")
    else:
        _bad("NVIDIA", "nvidia-smi not found"); good = False

    try:
        import torch
        if torch.cuda.is_available(): _ok("PyTorch CUDA", f"{torch.__version__}, {torch.cuda.get_device_name(0)}")
        else: _bad("PyTorch CUDA", torch.__version__); good = False
    except Exception as e:
        _bad("PyTorch", repr(e)); good = False

    activate_vendor_cuda()
    dll = VENDOR_CUDA / "cublas64_12.dll"
    if os.name == "nt":
        if dll.exists(): _ok("CTranslate2 CUDA DLLs", dll)
        else: _bad("CTranslate2 CUDA DLLs", f"missing {dll}; rerun scripts/setup_windows.ps1"); good = False
    try:
        from faster_whisper import WhisperModel  # noqa
        _ok("faster-whisper", "import")
    except Exception as e:
        _bad("faster-whisper", repr(e)); good = False
    try:
        from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # noqa
        _ok("Chatterbox", "import")
    except Exception as e:
        _bad("Chatterbox", repr(e)); good = False

    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as r:
            import json
            names = [m.get("name", "") for m in json.loads(r.read())["models"]]
        if any(n == ollama_model or n.startswith(ollama_model + ":") for n in names): _ok("Ollama", ollama_model)
        else: _warn("Ollama", f"running, but {ollama_model} not installed; run: ollama pull {ollama_model}")
    except Exception as e:
        _bad("Ollama", f"not reachable: {e}"); good = False
    return good
