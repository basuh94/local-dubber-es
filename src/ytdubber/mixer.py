from __future__ import annotations
from pathlib import Path
import subprocess


def _dub_end(block: dict) -> float:
    """End of the dubbed speech, which may run past the source block into the next pause."""
    voiced = float(block.get("timing", {}).get("duration", 0.0))
    return max(float(block["end"]), float(block["start"]) + voiced)


def _duck_expression(blocks: list[dict]) -> str:
    return "+".join(f"between(t,{b['start']:.3f},{_dub_end(b):.3f})" for b in blocks) or "0"


def make_final_video(source_video: Path, dub_wav: Path, blocks: list[dict], output: Path,
                     original_speech_level: float = 0.12) -> Path:
    """Keep original soundtrack but duck it under translated speech; video stream is copied."""
    expr = _duck_expression(blocks)
    # Original stays at 100% outside speech and is attenuated under dub windows.
    fc = (
        f"[0:a]volume={original_speech_level}:enable='{expr}'[bg];"
        f"[1:a]aresample=48000,volume=1.0[dub];"
        f"[bg][dub]amix=inputs=2:duration=first:normalize=0[aout]"
    )
    subprocess.run([
        "ffmpeg", "-y", "-i", str(source_video), "-i", str(dub_wav),
        "-filter_complex", fc, "-map", "0:v:0", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        str(output)
    ], check=True)
    return output
