from __future__ import annotations
from pathlib import Path
import json
import os
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "work"
OUTPUT = ROOT / "output"
INPUT = ROOT / "input"
VENDOR_CUDA = ROOT / "vendor" / "cuda12"


def ensure_dirs() -> None:
    for p in (WORK, OUTPUT, INPUT, VENDOR_CUDA):
        p.mkdir(parents=True, exist_ok=True)


def activate_vendor_cuda() -> None:
    """Make local CTranslate2 CUDA DLLs discoverable on Windows before import."""
    if os.name != "nt":
        return
    dll = VENDOR_CUDA / "cublas64_12.dll"
    if dll.exists():
        os.environ["PATH"] = str(VENDOR_CUDA) + os.pathsep + os.environ.get("PATH", "")
        try:
            os.add_dll_directory(str(VENDOR_CUDA))
        except (AttributeError, OSError):
            pass


def run(cmd: list[str], *, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [str(x) for x in cmd],
        check=check,
        text=True,
        capture_output=capture,
    )


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def ffprobe_duration(path: Path) -> float:
    cp = run([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path)
    ], capture=True)
    return float(cp.stdout.strip())


def write_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


# Dubbed speech may run past its source block into the following pause, but must leave
# a little silence before the next block starts. The last block has nothing after it.
GAP_GUARD = 0.12
TAIL_ALLOWANCE = 1.50
# Measured median speaking rate of Chatterbox V3 Spanish output, used to predict whether
# a translation will fit its window before it is synthesized.
TTS_CHARS_PER_SECOND = 12.5


def block_window(blocks: list[dict], index: int) -> float:
    """Seconds of audio available to block ``index`` before the next block must start."""
    block = blocks[index]
    if index + 1 < len(blocks):
        return max(float(block["duration"]),
                   float(blocks[index + 1]["start"]) - float(block["start"]) - GAP_GUARD)
    return float(block["duration"]) + TAIL_ALLOWANCE


def char_budget(window: float, max_speedup: float) -> int:
    """Characters of Spanish that fit in ``window`` once the speed-up cap is applied."""
    return max(1, int(TTS_CHARS_PER_SECOND * window * max_speedup))


def seconds_to_srt(seconds: float) -> str:
    total_ms = max(0, round(seconds * 1000))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def contains_unexpected_script(text: str, target_lang: str = "es") -> bool:
    # Common failure observed with LLM translation: stray Cyrillic/CJK in Spanish output.
    if target_lang == "es":
        return bool(re.search(r"[\u0400-\u04FF\u4E00-\u9FFF]", text))
    return False


def sanitize_spanish(text: str) -> str:
    replacements = {
        "computadora": "ordenador",
        "autofotos": "selfies",
        "reflejaciones": "reflejos",
        "las reflejos": "los reflejos",
    }
    out = text.strip()
    for a, b in replacements.items():
        out = out.replace(a, b)
    out = out.replace("una ordenador", "un ordenador").replace("la ordenador", "el ordenador")
    out = re.sub(r"\s+", " ", out)
    return out
