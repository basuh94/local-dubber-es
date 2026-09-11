# YouTube Dubber Win

Local YouTube/video dubbing to **Spanish (Spain)**, optimized for **Windows 11 + NVIDIA RTX 3070 8 GB**.

Pipeline:

`YouTube/local video → faster-whisper → pause-aware blocks → Ollama/Qwen3 → Chatterbox V3 voice clone → timing → FFmpeg mix → video_es.mp4`

## What this version fixes

- Uses word timestamps + VAD instead of blindly cutting Whisper segments.
- Avoids cuts immediately after conjunctions when possible.
- Gives the translator previous/next context but translates only the current block.
- Rejects/retries suspicious translations (very short output or stray Cyrillic/CJK in Spanish).
- **Never slows down** synthesized speech to fill a window. Short speech is padded with silence.
- Caps speed-up; aggressive time compression is avoided.
- Sets Chatterbox Multilingual **V3** and `cfg_weight=0.0` for cross-language English→Spanish cloning, which reduces inherited English accent.
- Unloads Ollama before TTS to free VRAM.
- Keeps the original soundtrack and ducks it underneath dubbed speech instead of deleting all music/effects.

## Requirements

- Windows 11
- NVIDIA GPU; target tested configuration is RTX 3070 8 GB class
- NVIDIA driver recent enough for CUDA 12.x
- Python **3.11.x**
- PowerShell + winget
- ~15–25 GB free disk space after model caches

## One-command setup

Open PowerShell in the extracted folder:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
```

The setup script installs/checks:

- FFmpeg / ffprobe
- Deno (avoids current yt-dlp YouTube JS-runtime warnings)
- 7-Zip
- Ollama
- Python 3.11 venv
- pinned Python packages (Chatterbox pinned to the official V3 release commit)
- PyTorch 2.6.0 + CUDA 12.6 wheels matching Chatterbox 0.1.7
- local cuBLAS/cuDNN CUDA 12 DLLs needed by CTranslate2/faster-whisper on Windows
- `qwen3:8b` in Ollama
- unit tests

## Verify installation

```powershell
.\.venv\Scripts\Activate.ps1
ytdubber doctor
```

You want CUDA=True, the RTX 3070 name, `cublas64_12.dll` present, Ollama reachable,
and successful faster-whisper/Chatterbox imports.

## Dub a video

Recommended:

```powershell
ytdubber dub "https://www.youtube.com/watch?v=VIDEO_ID" --profile balanced --source-lang en
```

Or a local file:

```powershell
ytdubber dub "D:\Videos\input.mp4" --profile balanced
```

Outputs appear under `output/`:

- `transcript_source.txt`
- `subtitles_source.srt`
- `words.json`
- `blocks_source.json`
- `blocks_es.json`
- `subtitles_es.srt`
- `transcript_es.txt`
- `dub_blocks/`
- `dub_es.wav`
- **`video_es.mp4`**

## Voice reference

By default the program chooses a reasonably long/high-confidence speech block and extracts it as
automatic reference. For better cloning, provide a clean 5–10 s WAV containing one speaker:

```powershell
ytdubber dub "URL" --voice-ref ".\input\my_clean_reference.wav"
```

If the reference is English and target is Spanish, the default `cfg_weight=0.0` intentionally lets
the Spanish language model control pronunciation more strongly while retaining speaker identity.

## Profiles

See `MODEL_GUIDE.md`.

- `fast`: `small` ASR + `qwen3:4b`
- `balanced`: `large-v3-turbo` + `qwen3:8b` **(recommended for RTX 3070 8 GB)**
- `quality`: `large-v3` + `qwen3:8b`

## Important limitations

1. This is automatic dubbing. Proper studio-quality alignment/translation can still require manual edits.
2. The original soundtrack is ducked during translated speech. It is not true dialogue/music source separation.
3. Automatic reference selection cannot know whether music/noise is present. A clean manual reference gives better cloning.
4. Translation quality depends on ASR. Product names/proper nouns can be misheard; inspect `blocks_es.json` for important videos.
5. Use voice cloning only when you have the right to use the source voice/content.

## Full model smoke test

After setup, you can perform a real GPU/model test (downloads model weights on first run):

```powershell
.\scripts\model_smoke_test.ps1
```

It generates Spanish audio with Chatterbox V3, transcribes it with faster-whisper CUDA, and calls `qwen3:8b` through Ollama.

## Tests

```powershell
.\scripts\run_tests.ps1
```

The included tests cover segmentation guards, timestamp formatting, script validation, and FFmpeg
audio timing behavior without downloading large AI models.

## Optional Qwen3-TTS

See `extras/qwen3_tts/README.md`. It is kept in a separate venv because its current package pins a
different Transformers stack from Chatterbox.
