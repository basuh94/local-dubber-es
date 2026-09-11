# Optional Qwen3-TTS backend

This is intentionally isolated from the main Chatterbox environment because the current
`qwen-tts` package pins a different Transformers stack than `chatterbox-tts`.

For an RTX 3070 8 GB:

- `Qwen/Qwen3-TTS-12Hz-0.6B-Base`: safest option; Spanish + voice cloning; lower VRAM.
- `Qwen/Qwen3-TTS-12Hz-1.7B-Base`: higher clone quality, but much tighter on 8 GB.

Create a separate environment:

```powershell
py -3.11 -m venv .venv-qwen
.\.venv-qwen\Scripts\Activate.ps1
pip install -r extras\qwen3_tts\requirements.txt
```

The main project defaults to Chatterbox Multilingual V3 because that exact stack has a
clean Windows/Python 3.11 path and runs sequentially with faster-whisper and Ollama.
