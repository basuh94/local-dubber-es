# Model guide for RTX 3070 8 GB

## Recommended default: `balanced`

| Stage | Default | Why |
|---|---|---|
| ASR | `faster-whisper large-v3-turbo`, `int8_float16` | Multilingual, much faster than full large-v3, 8 GB friendly |
| Translation | `qwen3:8b` in Ollama (Q4_K_M, ~5.2 GB) | Best local generalist option in this project for context-aware EN→ES; run sequentially and unload before TTS |
| TTS / cloning | Chatterbox Multilingual V3 | 0.5B, Spanish supported, zero-shot voice cloning |
| Cross-language accent control | `cfg_weight=0.0` | Chatterbox explicitly recommends 0 when the reference clip language differs from target |

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
