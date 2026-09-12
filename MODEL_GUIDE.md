# Model guide for RTX 3070 8 GB

## Recommended default: `balanced`

| Stage | Default | Why |
|---|---|---|
| ASR | `faster-whisper large-v3-turbo`, `int8_float16` | Multilingual, much faster than full large-v3, 8 GB friendly |
| Translation | `qwen3:8b` in Ollama (Q4_K_M, ~5.2 GB) | Best local generalist option in this project for context-aware EN→ES; run sequentially and unload before TTS |
| TTS / cloning | Chatterbox Multilingual V3 | 0.5B, Spanish supported, zero-shot voice cloning |
| Cross-language accent control | `cfg_weight=0.0` | Chatterbox explicitly recommends 0 when the reference clip language differs from target |

## The voice reference sets the dubbing speed

Chatterbox has no duration or speed parameter: T3 emits speech tokens at a fixed 25/s, so
the length of a line is a sampling outcome. What steers it is the reference clip — the model
clones its **pacing** close to proportionally, not just its timbre.

Measured on the same 20-minute talk, changing only the reference:

| reference rate | resulting dub rate | speech trimmed |
|---|---|---|
| 8.7 chars/s | 9.9 chars/s | 693 s |
| 19.7 chars/s | 14.9 chars/s | 57 s |

This matters more than any other model setting here. Automatic selection now prefers the
briskest confidently-recognised block; if you pass `--voice-ref`, choose a clip where the
speaker keeps a good pace.

`cfg_weight` is the only other lever that moves pace: 13.3 chars/s at 0.0, 15.3 at 0.3,
16.4 at 0.5. `exaggeration` and `temperature` do not affect it, and `repetition_penalty=1.0`
degenerates. The default stays at 0.0 to protect the accent, and rises only on a block that
would otherwise lose its tail.

## Profiles

### fast
- ASR: `small` / `int8_float16`
- Translator: `qwen3:4b` (~2.5 GB in Ollama)
- TTS: Chatterbox Multilingual V3

Use for previews or long videos where speed matters more than transcript fidelity.

### balanced (recommended)
- ASR: `large-v3-turbo` / `int8_float16`
- Translator: `qwen3:8b` (~5.2 GB)
- TTS: Chatterbox Multilingual V3

### quality
- ASR: `large-v3` / `int8_float16`
- Translator: `qwen3:8b`
- TTS: Chatterbox Multilingual V3

Full `large-v3` is slower but gives the most robust multilingual ASR of these presets.

## Alternative TTS

Qwen3-TTS 0.6B Base supports Spanish and 3-second voice cloning and is a strong alternative.
The 1.7B Base has better clone fidelity but is close to the practical VRAM ceiling of an 8 GB card.
Use the isolated environment under `extras/qwen3_tts/` to avoid dependency conflicts.

## Why not run everything at once?

The RTX 3070 has 8 GB VRAM. The project deliberately runs ASR → Ollama translation → TTS
sequentially and asks Ollama to unload before Chatterbox starts. This lets each stage use most
of the GPU without competing for memory.
