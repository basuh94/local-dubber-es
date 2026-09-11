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
    max_speedup: float

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
        max_speedup=1.15,
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
        max_speedup=1.12,
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
        max_speedup=1.10,
    ),
}

def get_profile(name: str) -> Profile:
    try:
        return PROFILES[name]
    except KeyError as exc:
        raise ValueError(f"Unknown profile {name!r}. Choose: {', '.join(PROFILES)}") from exc
