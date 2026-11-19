# local-dubber-es — YouTube to Spanish dubbing

Dub **YouTube videos** (or any local video) to **Spanish (Spain)** with voice cloning, fully
on your own PC. Optimized for **Windows 11 + NVIDIA RTX 3070 8 GB**.

Pipeline:

`YouTube/local video → faster-whisper → pause-aware blocks → Ollama/Qwen3 → Chatterbox V3 voice clone → timing → FFmpeg mix → video_es.mp4`

Processing is fully local: no paid API, no upload, no account. Only the source video and the
model weights are downloaded. All three models run on the local GPU, one at a time.

> Documentación en español: **`ARQUITECTURA.md`** (flujo completo con diagramas) y
> **`FUNCIONAL.md`** (qué hace el sistema, reglas de calidad y límites).

## Design decisions

- Word timestamps + VAD instead of blindly cutting Whisper segments.
- Avoids cuts immediately after conjunctions, with a hard duration cap so unpunctuated ASR
  output cannot produce an unbounded block.
- Gives the translator previous/next context but translates only the current block, with a
  character budget derived from the time actually available.
- Rejects/retries suspicious translations and keeps the *best* candidate, not the last one.
- **Never slows down** synthesized speech to fill a window. Short speech is padded with silence.
- Caps speed-up per profile, and applies `min(required, cap)` so blocks that already fit are
  untouched.
- Picks the voice reference by **speaking rate** among confidently-recognised candidates.
  Chatterbox clones the reference's pacing, so this is the single biggest quality lever —
  see *Voice reference* below.
- Sets Chatterbox Multilingual **V3** with `cfg_weight=0.0` for cross-language English→Spanish
  cloning, which reduces inherited English accent. It is raised only as a last resort on a
  block that would otherwise lose its tail.
- Unloads Ollama before TTS to free VRAM.
- Keeps the original soundtrack and ducks it underneath dubbed speech instead of deleting all
  music/effects.

## Requirements

- Windows 11
- NVIDIA GPU; target tested configuration is RTX 3070 8 GB class
- NVIDIA driver recent enough for CUDA 12.x
- Python **3.11.x**
- PowerShell + winget
- ~15–25 GB free disk space after model caches

## One-command setup

Clone the repository and run the setup script from PowerShell:

```powershell
git clone https://github.com/basuh94/local-dubber-es.git
cd local-dubber-es
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\setup_windows.ps1
```

The setup script installs/checks:

- FFmpeg / ffprobe
- Deno (avoids current yt-dlp YouTube JS-runtime warnings)
- 7-Zip (resolved off PATH if winget did not add it)
- Ollama
- Python 3.11 venv
- pinned Python packages (Chatterbox pinned to the official V3 release commit)
- PyTorch 2.6.0 + CUDA 12.6 wheels matching Chatterbox 0.1.7
- local cuBLAS/cuDNN CUDA 12 DLLs needed by CTranslate2/faster-whisper on Windows
  (the download is integrity-checked; a truncated archive is what produces the confusing
  `cublas64_12.dll is not found` much later)
- `qwen3:8b` in Ollama
- unit tests

## Verify installation

```powershell
.\.venv\Scripts\Activate.ps1
ytdubber doctor
```

You want CUDA=True, the RTX 3070 name, `cublas64_12.dll` present, Ollama reachable,
and successful faster-whisper/Chatterbox imports.

## Control panel

The quickest way in is the panel, started from the activated venv:

```powershell
ytdubber web            # or: .\scripts\panel.ps1
```

For a double-click launcher, build **`YouTube Dubber.exe`** once (it is not part of the
repository) with `.\scripts\build_launcher.ps1`. The executable starts Ollama if needed,
launches the panel and opens the browser.

The panel shows the seven pipeline stages, per-block progress during synthesis, timing
warnings and the live log, and lets you cancel a run. When a dub finishes it archives the
result and deletes the intermediates. Finished videos are listed with a thumbnail and can be
played, downloaded or deleted from there.

Only one dub runs at a time: the pipeline uses shared `work/` and `output/` directories.

Rebuild it after changing `scripts/launcher.py`:

```powershell
.\scripts\build_launcher.ps1
```

It builds in its own `.venv-build`, so the validated runtime venv is never touched.

## Dub from the command line

```powershell
ytdubber dub "https://www.youtube.com/watch?v=VIDEO_ID" --profile balanced --source-lang en
ytdubber dub "D:\Videos\input.mp4" --profile balanced
```

Useful flags: `--voice-ref`, `--original-speech-level`, and `--tts-takes` / `--max-speedup`
to override the profile without editing it.

A CLI run leaves its artefacts in `output/`. Runs launched from the panel are archived into
`library/<date>_<title>/` instead, keeping the deliverables and removing the rest:

- `transcript_source.txt`, `subtitles_source.srt`, `words.json`
- `blocks_source.json`, `blocks_es.json`, `blocks_voiced.json`
- `subtitles_es.srt`, `transcript_es.txt`
- `dub_es.wav`
- **`video_es.mp4`**

`blocks_es.json` is the file to edit if you want to reword a line before re-running.

## Voice reference

Chatterbox does not only clone the timbre of the reference clip — **it clones its pace**,
close to proportionally. A reference taken from a slow passage makes every dubbed line run
long and get trimmed.

Measured on the same 20-minute talk, changing nothing else:

| reference | dub rate | speech trimmed |
|---|---|---|
| 8.7 chars/s | 9.9 chars/s | 693 s |
| 19.7 chars/s | 14.9 chars/s | 57 s |

So the automatic selection takes the **briskest** block among those the ASR recognised
confidently. If you supply your own reference, pick a clean 5–10 s WAV with one speaker
talking at a good pace, not one with pauses:

```powershell
ytdubber dub "URL" --voice-ref ".\input\my_clean_reference.wav"
```

If the reference is English and the target is Spanish, the default `cfg_weight=0.0`
intentionally lets the Spanish language model control pronunciation more strongly while
retaining speaker identity.

## Profiles

See `MODEL_GUIDE.md`.

| | ASR | translator | speed-up cap | TTS takes |
|---|---|---|---|---|
| `fast` | `small` | `qwen3:4b` | 1.35 | 2 |
| `balanced` ⭐ | `large-v3-turbo` | `qwen3:8b` | 1.30 | 3 |
| `quality` | `large-v3` | `qwen3:8b` | 1.25 | 4 |

`balanced` is the default and the recommendation for an RTX 3070 8 GB.

`quality` uses undistilled `large-v3`. It does not punctuate any better, but it transcribes
noticeably more accurately — on a technical talk, turbo heard "censorship" as "sensor shape"
and "Qwen" as "queen" — for 122 s instead of 28 s. Worth it on content with terminology that
matters.

## Important limitations

1. This is automatic dubbing. Proper studio-quality alignment/translation can still require manual edits.
2. The original soundtrack is ducked during translated speech. It is not true dialogue/music source separation.
3. Automatic reference selection cannot know whether music/noise is present. A clean manual reference gives better cloning.
4. Translation quality depends on ASR. Product names/proper nouns can be misheard; inspect `blocks_es.json` for important videos.
5. Some audio makes Whisper return unpunctuated, uncased text. Blocks are then cut by the
   clock rather than by meaning. Both `large-v3-turbo` and `large-v3` behave this way on the
   same material, so it is not a model choice.
6. Two runs of the same video can segment differently and pick different voice references. To
   compare configurations meaningfully, pin the reference with `--voice-ref`.
7. Use voice cloning only when you have the right to use the source voice/content.

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

Model-independent tests covering segmentation guards and the hard duration cap, voice
reference selection, translation retry scoring, TTS take selection, text splitting, SRT
formatting, library archiving and deletion, and real FFmpeg timing and A/V integration. No
model downloads, no network.

## Optional Qwen3-TTS

See `extras/qwen3_tts/README.md`. It is kept in a separate venv because its current package pins a
different Transformers stack from Chatterbox.

## Responsible use

This project is intended for personal and educational use.

- Respect copyright and the YouTube Terms of Service. Only download and dub content you own,
  that is licensed for it, or that you are otherwise permitted to use.
- Do not publish or redistribute dubbed videos without the original creator's permission.
- Do not clone anyone's voice without their consent, and never use cloned voices to
  impersonate or deceive.

You are solely responsible for how you use this software.

## Credits

This project orchestrates third-party tools, each under its own license:

- [faster-whisper](https://github.com/SYSTRAN/faster-whisper) — speech recognition
- [Chatterbox](https://github.com/resemble-ai/chatterbox) by Resemble AI — voice-cloning TTS
- [Qwen3](https://github.com/QwenLM/Qwen3) via [Ollama](https://ollama.com) — translation
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — video download
- [FFmpeg](https://ffmpeg.org) — audio/video processing

The NVIDIA cuBLAS/cuDNN DLLs are not included in this repository; `setup_windows.ps1`
downloads them from [whisper-standalone-win](https://github.com/Purfview/whisper-standalone-win).

## License

MIT — see [`LICENSE`](LICENSE).
