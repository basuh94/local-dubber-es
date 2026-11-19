from __future__ import annotations
from pathlib import Path
import subprocess


def _dub_end(block: dict) -> float:
    """End of the dubbed speech, which may run past the source block into the next pause."""
    voiced = float(block.get("timing", {}).get("duration", 0.0))
    return max(float(block["end"]), float(block["start"]) + voiced)


def _duck_expression(blocks: list[dict]) -> str:
    return "+".join(f"between(t,{b['start']:.3f},{_dub_end(b):.3f})" for b in blocks) or "0"


# Windows per volume filter. One expression listing every window is simpler, but ffmpeg's
# expression evaluator gives up on long ones: a 36-minute dub produced 414 terms and 11580
# characters and failed with "Error when evaluating the expression".
DUCK_CHUNK = 40


def duck_chain(blocks: list[dict], level: float) -> str:
    """A chain of volume filters, each ducking a slice of the blocks.

    Blocks never overlap -- synthesis guarantees each one ends before the next begins -- so
    any instant falls inside at most one slice and the attenuation is applied exactly once.
    """
    if not blocks:
        return "anull"
    stages = []
    for i in range(0, len(blocks), DUCK_CHUNK):
        expr = _duck_expression(blocks[i:i + DUCK_CHUNK])
        stages.append(f"volume={level}:enable='{expr}'")
    return ",".join(stages)


def make_final_video(source_video: Path, dub_wav: Path, blocks: list[dict], output: Path,
                     original_speech_level: float = 0.12) -> Path:
    """Keep original soundtrack but duck it under translated speech; video stream is copied."""
    # Original stays at 100% outside speech and is attenuated under dub windows.
    fc = (
        f"[0:a]{duck_chain(blocks, original_speech_level)}[bg];"
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
