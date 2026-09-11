# Validation status

## Automated tests executed while packaging

The package was compiled and tested with its model-independent suite. These tests do not require
internet or AI model downloads and cover:

- pause-aware segmentation and connector guard
- automatic voice-reference selection
- SRT timestamp formatting
- detection of accidental Cyrillic/CJK in Spanish translation output
- Spanish cleanup rules
- real FFmpeg timing: short TTS is padded, never slowed
- real FFmpeg A/V integration: local video extraction, delayed dub assembly, ducked final mix

## GPU/model path

The project also includes `scripts/model_smoke_test.ps1` for the target Windows/NVIDIA machine.
It exercises the actual models end-to-end: Chatterbox Multilingual V3 -> faster-whisper CUDA -> Ollama Qwen3.

The core versions used here match the versions already validated interactively on an RTX 3070-class
Windows setup: Python 3.11, CUDA-enabled PyTorch 2.6.0/cu126, faster-whisper with CUDA 12 runtime DLLs,
and Chatterbox voice generation. Chatterbox is pinned to the official V3 release commit so the project
does not depend on whether the older PyPI wheel contains the newer V3 selector.
