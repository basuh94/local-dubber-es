from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class Profile:
    name: str
    asr_model: str
    asr_compute_type: str
    ollama_model: str
    tts_v3: bool
    cfg_weight: float
    exaggeration: float
    # fit_audio applies min(required, max_speedup), so a higher cap costs nothing on the
    # blocks that already fit. Measured on a 20-minute talk: raising this from 1.12 to
    # 1.30 cut trimmed speech from 46 s to 9 s while the average speed-up actually applied
    # moved only from 1.09x to 1.14x.
    max_speedup: float
    # Chatterbox samples its speech tokens, so the same line comes out 18-30% longer or
    # shorter depending on the take. Drawing a few and keeping one that fits its window
    # recovers most of that spread instead of cutting the tail off.
    tts_takes: int = 3

PROFILES = {
    # Lowest latency / smallest model downloads.
    "fast": Profile(
        name="fast",
        asr_model="small",
        asr_compute_type="int8_float16",
        ollama_model="qwen3:4b",
        tts_v3=True,
        cfg_weight=0.0,
        exaggeration=0.45,
        max_speedup=1.35,
        tts_takes=2,
    ),
    # Recommended for RTX 3070 8 GB.
    "balanced": Profile(
        name="balanced",
        asr_model="large-v3-turbo",
        asr_compute_type="int8_float16",
        ollama_model="qwen3:8b",
        tts_v3=True,
        cfg_weight=0.0,
        exaggeration=0.50,
        max_speedup=1.30,
        tts_takes=3,
    ),
    # More accurate ASR; still fits 8 GB when stages run sequentially.
    "quality": Profile(
        name="quality",
        asr_model="large-v3",
        asr_compute_type="int8_float16",
        ollama_model="qwen3:8b",
        tts_v3=True,
        cfg_weight=0.0,
        exaggeration=0.50,
        max_speedup=1.25,
        tts_takes=4,
    ),
}

def get_profile(name: str) -> Profile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown profile {name!r}. Choose: {', '.join(PROFILES)}") from exc
