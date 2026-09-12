# Validation status

Current version: **0.4.0**. Everything below was executed on the target machine
(Windows 11, RTX 3070 8 GB, driver 595.79), not inferred.

## Automated tests

45 tests, all green. They need no internet and download no models:

- pause-aware segmentation, connector guard, and the hard duration cap that keeps
  unpunctuated ASR output from producing an unbounded block
- voice-reference selection: prefers the briskest delivery, but confidence still vetoes a
  block the ASR barely understood
- translation retries: keeps the best candidate rather than the last, rejects stray
  Cyrillic/CJK, falls back to the source text when every attempt fails, and honours the
  per-block character budget
- TTS take selection: stops at the first take that fits, escalates `cfg_weight` only as a
  last resort, keeps the shortest take when nothing fits
- TTS text splitting: sentence → clause → word boundaries, without losing text
- real FFmpeg timing: short speech is padded, never slowed; speed-up is capped; trimming is
  reported
- real FFmpeg A/V integration: local video extraction, delayed dub assembly, ducked final mix
- library: archives the deliverables, removes the intermediates, refuses paths outside the
  library, and survives being cleaned twice

```powershell
.\scripts\run_tests.ps1
```

## GPU / model path

`scripts\model_smoke_test.ps1` — **PASS**. Exercises the real models end to end:
Chatterbox Multilingual V3 on CUDA → faster-whisper CUDA → Ollama Qwen3.

`ytdubber doctor` — all checks OK: Python 3.11.9, FFmpeg/ffprobe, RTX 3070 detected,
PyTorch 2.6.0+cu126 with CUDA available, `cublas64_12.dll` resolved from `vendor/cuda12`,
faster-whisper and Chatterbox importing, Ollama reachable with the profile's model.

Validated stack: Python 3.11.9, PyTorch 2.6.0+cu126, torchvision 0.21.0+cu126,
torchaudio 2.6.0+cu126, faster-whisper 1.2.1, CTranslate2 4.8.2, chatterbox-tts 0.1.7
(pinned to the official V3 release commit), yt-dlp 2026.8.19, Ollama 0.24.0 with
`qwen3:8b` and `qwen3:4b`.

Note: `pip check` reports that chatterbox-tts 0.1.7 pins `numpy<2.0.0` while the venv has
2.4.6. The pin is stale — Chatterbox predates numpy 2 — and does not bite in practice;
downgrading would risk the numba/librosa/pandas ABI for no observed benefit.

## End-to-end runs

Both source videos were dubbed in full and the resulting MP4 decoded end to end without
errors, with `moov` before `mdat`.

- 3-minute product video, profile `balanced`: 195 s total (download 3 s, ASR 7 s,
  segmentation <1 s, translation 42 s, reference 1 s, **synthesis 141 s**, mix 1 s).
  Re-transcribing the finished file detects Spanish at p=0.98.
- 20-minute technical talk, profile `balanced`: the pipeline's worst case — a fast speaker
  with no punctuation in the transcript. Final result: **1 block trimmed out of 78, 5 s of
  speech lost (0 % of the dub)**.

Peak VRAM: 7.3 GB of 8 GB, during translation, with ~2 GB already taken by the Windows
desktop. The sequential design is what makes it fit.

## Measured findings behind the current defaults

These are why the profiles look the way they do. Full numbers in `CHANGELOG.md`.

- **The voice reference governs the dub's speaking rate.** Chatterbox clones the reference's
  pacing close to proportionally. Isolating that single variable on the same video: an
  8.7 char/s reference produced a 9.9 char/s dub with 693 s trimmed; a 19.7 char/s reference
  produced 14.9 char/s with 57 s trimmed. This was also the source of the apparent
  run-to-run randomness.
- **A higher speed-up cap is nearly free.** `fit_audio` applies `min(required, cap)`, so
  raising it from 1.12 to 1.30 cut trimmed speech from 46 s to 9 s while the average
  speed-up actually applied moved only from 1.09x to 1.14x.
- **`cfg_weight` is Chatterbox's only real pacing knob**: 13.3 chars/s at 0.0, 15.3 at 0.3,
  16.4 at 0.5. `exaggeration` and `temperature` do not affect pace;
  `repetition_penalty=1.0` degenerates. Raising `cfg_weight` costs nothing in
  intelligibility (WER 0.000, p(es) 0.999 at 0.0/0.3/0.5) — but that measures words, not
  accent, which is why the default stays at 0.0 and only escalates as a last resort.
- **`large-v3` does not punctuate better than `large-v3-turbo`** (9 marks, 0 commas in
  3 885 words for both), so the missing punctuation is not a distillation artefact. It does
  transcribe more accurately and detect 3.7x more pauses.

## Methodological caveat

Two runs of the same video with the same settings gave 32 % and 8 % trimmed speech before
the reference-selection fix. **A single run does not demonstrate anything** about timing
quality in this pipeline. Pin the voice reference with `--voice-ref` when comparing
configurations.
