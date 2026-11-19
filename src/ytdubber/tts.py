from __future__ import annotations
from pathlib import Path
import re
import shutil
import subprocess
from .utils import OUTPUT, TTS_CHARS_PER_SECOND, WORK, block_window, ffprobe_duration


def extract_reference(video_path: Path, start: float, end: float, out: Path) -> Path:
    duration = max(1.0, end - start)
    subprocess.run([
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", str(video_path), "-t", f"{duration:.3f}",
        "-vn", "-ac", "1", "-ar", "24000", "-c:a", "pcm_s16le", str(out)
    ], check=True)
    return out


# Chatterbox T3 sizes its text position embedding at max_text_tokens (2048) + 2. Feeding
# it more indexes past the end of that table, which fails as an unrecoverable CUDA
# device-side assert that kills the whole run, so stay well inside the limit.
TTS_MAX_TEXT_TOKENS = 1000
_CHARS_PER_TOKEN = 1.35  # measured on Spanish output, used only if tokenizing fails


def _fits(text: str, model=None, language_id: str = "es",
          max_tokens: int = TTS_MAX_TEXT_TOKENS) -> bool:
    if model is not None:
        try:
            from chatterbox.mtl_tts import punc_norm

            tokens = model.tokenizer.text_to_tokens(punc_norm(text), language_id=language_id)
            return int(tokens.shape[-1]) <= max_tokens
        except Exception:
            pass
    return len(text) <= max_tokens * _CHARS_PER_TOKEN


def _pack(pieces: list[str], joiner: str, model, language_id: str, max_tokens: int) -> list[str]:
    """Greedily group pieces into the fewest chunks that each still fit."""
    chunks: list[str] = []
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        if chunks and _fits(chunks[-1] + joiner + piece, model, language_id, max_tokens):
            chunks[-1] = chunks[-1] + joiner + piece
        else:
            chunks.append(piece)
    return chunks


def split_for_tts(text: str, model=None, language_id: str = "es",
                  max_tokens: int = TTS_MAX_TEXT_TOKENS) -> list[str]:
    """Break text into pieces the TTS can hold, preferring sentence then clause breaks."""
    text = text.strip()
    if not text or _fits(text, model, language_id, max_tokens):
        return [text] if text else []

    for pattern, joiner in ((r"(?<=[.!?])\s+", " "), (r"(?<=[,;:])\s+", " ")):
        chunks = _pack(re.split(pattern, text), joiner, model, language_id, max_tokens)
        if chunks and all(_fits(c, model, language_id, max_tokens) for c in chunks):
            return chunks

    # No punctuation to lean on: fall back to word boundaries.
    return _pack(text.split(), " ", model, language_id, max_tokens) or [text]


def fit_audio(source: Path, destination: Path, target_duration: float, max_speedup: float,
              window_duration: float | None = None) -> dict:
    """Never slow TTS down. Pad if shorter; mildly speed up if longer; trim only as last resort.

    ``window_duration`` may extend past ``target_duration`` into the pause before the next
    block. Spanish is typically longer than English, so spending that silence at natural
    speed is preferable to compressing the sentence.
    """
    actual = ffprobe_duration(source)
    window = max(float(target_duration), float(window_duration or target_duration))
    if actual <= target_duration:
        af = f"apad=whole_dur={target_duration:.6f},atrim=duration={target_duration:.6f}"
        applied, trimmed, fitted = 1.0, False, target_duration
    elif actual <= window:
        # Fits in the source window plus the following pause: keep natural speed.
        af = "anull"
        applied, trimmed, fitted = 1.0, False, actual
    else:
        required = actual / max(window, 0.01)
        applied = min(required, max_speedup)
        af = f"atempo={applied:.6f},atrim=duration={window:.6f},apad=whole_dur={window:.6f}"
        trimmed = required > max_speedup
        fitted = window
    subprocess.run([
        "ffmpeg", "-y", "-i", str(source), "-af", af, "-ar", "24000", "-ac", "1", str(destination)
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"actual": actual, "target": target_duration, "window": window,
            "speed": applied, "trimmed": trimmed, "duration": fitted}


# Spoken while measuring how fast this particular cloned voice talks. Ordinary Spanish, no
# rare words, and roughly as long as a real dubbing block: a short probe carries
# proportionally more leading and trailing silence and would read as slower than reality.
CALIBRATION_LINES = (
    "Esta es una prueba para medir la velocidad de la voz antes de empezar el doblaje, "
    "de manera que la traducción se ajuste al tiempo disponible en cada bloque del vídeo.",
    "El sistema necesita saber cuántos caracteres por segundo pronuncia esta voz concreta, "
    "porque el ritmo depende del fragmento de referencia y cambia con cada vídeo nuevo.",
)
# Guard rails: a probe that lands outside this range means something went wrong, so fall
# back to the documented default rather than budgeting on nonsense.
MIN_RATE, MAX_RATE = 7.0, 26.0


def measure_speaking_rate(voice_ref: Path, cfg_weight: float, exaggeration: float,
                          lines: tuple[str, ...] = CALIBRATION_LINES) -> float:
    """Characters per second this reference voice actually produces.

    The rate is not a property of Chatterbox: it is a property of the reference clip, which
    changes with every video. Measuring it here lets the translator budget against the real
    delivery instead of a constant that goes stale the moment the reference changes.
    """
    import torch
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")
    try:
        chars = seconds = 0.0
        for line in lines:
            wav = model.generate(line, language_id="es", audio_prompt_path=str(voice_ref),
                                 exaggeration=exaggeration, cfg_weight=cfg_weight)
            chars += len(line)
            seconds += wav.shape[-1] / model.sr
        rate = chars / max(seconds, 0.01)
    finally:
        del model
        torch.cuda.empty_cache()

    if not MIN_RATE <= rate <= MAX_RATE:
        print(f"      [warn] ritmo medido fuera de rango ({rate:.2f} car/s); "
              f"se usa el valor por defecto {TTS_CHARS_PER_SECOND}")
        return TTS_CHARS_PER_SECOND
    return rate


def cfg_ladder(base: float, takes: int) -> list[float]:
    """cfg_weight to use on each successive take.

    The profile's value (0.0) is what keeps an English reference from dragging its accent
    into the Spanish, so the first takes keep it. Only once a block is heading for a
    truncated tail do later takes raise it, because a slightly stronger accent beats
    losing the end of the sentence outright.
    """
    ladder = [base, base, max(base, 0.3), max(base, 0.5)]
    while len(ladder) < takes:
        ladder.append(ladder[-1])
    return ladder[:max(1, takes)]


def _synthesize_once(model, pieces: list[str], voice_ref: Path, *, exaggeration: float,
                     cfg_weight: float):
    import torch

    parts = [
        model.generate(
            piece, language_id="es", audio_prompt_path=str(voice_ref),
            exaggeration=exaggeration, cfg_weight=cfg_weight,
        )
        for piece in pieces
    ]
    return parts[0] if len(parts) == 1 else torch.cat(parts, dim=-1)


def synthesize_chatterbox(blocks: list[dict], voice_ref: Path, cfg_weight: float,
                           exaggeration: float, max_speedup: float,
                           takes: int = 3) -> list[dict]:
    import torch
    import torchaudio as ta
    from chatterbox.mtl_tts import ChatterboxMultilingualTTS

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = ChatterboxMultilingualTTS.from_pretrained(device=device, t3_model="v3")
    blocks_dir = OUTPUT / "dub_blocks"
    blocks_dir.mkdir(parents=True, exist_ok=True)
    result = []
    total = len(blocks)
    over_budget = 0
    retakes = 0
    for i, b in enumerate(blocks):
        idx = int(b["id"])
        raw = blocks_dir / f"block_{idx:03d}_raw.wav"
        fitted = blocks_dir / f"block_{idx:03d}.wav"
        pieces = split_for_tts(b["translated_text"], model)
        if len(pieces) > 1:
            print(f"      [warn] block {idx}: el texto excede el contexto del TTS; "
                  f"sintetizado en {len(pieces)} partes")

        # Speech may run into the pause before the next block, but never over it.
        window = block_window(blocks, i)
        budget = window * max_speedup  # what fit_audio can absorb without trimming
        wav, best_dur, used_cfg = None, None, cfg_weight
        for take, take_cfg in enumerate(cfg_ladder(cfg_weight, takes)):
            candidate = _synthesize_once(model, pieces, voice_ref,
                                         exaggeration=exaggeration, cfg_weight=take_cfg)
            duration = candidate.shape[-1] / model.sr
            if best_dur is None or duration < best_dur:
                wav, best_dur, used_cfg = candidate, duration, take_cfg
            if duration <= budget:
                break
            retakes += 1
        ta.save(str(raw), wav, model.sr)
        stats = fit_audio(raw, fitted, b["duration"], max_speedup, window_duration=window)
        stats["cfg_weight"] = used_cfg
        if stats["trimmed"]:
            over_budget += 1
            print(f"      [warn] block {idx}: el espanol dura {stats['actual']:.2f}s y solo "
                  f"hay {stats['window']:.2f}s ni siquiera a {stats['speed']:.2f}x; se recorta "
                  f"la cola. Acorta esa linea en output/blocks_es.json para arreglarlo.")
        item = dict(b); item.update({"audio": str(fitted), "timing": stats})
        result.append(item)
    del model
    torch.cuda.empty_cache()
    if retakes:
        print(f"      {retakes} tomas extra para encajar bloques largos.")
    if over_budget:
        print(f"      [warn] {over_budget}/{total} bloques recortados; ver avisos arriba.")
    return result


# One ffmpeg call per this many clips. Windows caps a command line at 32767 characters and
# each clip costs roughly 100 of them between its -i path and its filter graph entry, so a
# long video used to die here with WinError 206 after the whole synthesis had already run.
ASSEMBLE_BATCH = 50


def _mix_at_offsets(clips: list[tuple[str, int]], destination: Path) -> Path:
    """Lay each clip on a shared timeline at its own millisecond offset and sum them."""
    inputs, filters, labels = [], [], []
    for i, (path, delay) in enumerate(clips):
        inputs += ["-i", str(path)]
        filters.append(f"[{i}:a]adelay={delay}:all=1[a{i}]")
        labels.append(f"[a{i}]")
    filter_complex = (";".join(filters) + ";" + "".join(labels) +
                      f"amix=inputs={len(clips)}:duration=longest:normalize=0[out]")
    subprocess.run([
        "ffmpeg", "-y", *inputs, "-filter_complex", filter_complex, "-map", "[out]",
        "-ar", "24000", "-ac", "1", str(destination)
    ], check=True)
    return destination


def assemble_dub(blocks: list[dict], final_path: Path) -> Path:
    if not blocks:
        raise ValueError("No blocks to assemble")
    clips = [(b["audio"], round(float(b["start"]) * 1000)) for b in blocks]
    if len(clips) <= ASSEMBLE_BATCH:
        return _mix_at_offsets(clips, final_path)

    # Mix in batches, then mix the batches. Each partial already carries the absolute
    # timeline because its clips were placed with adelay, so the second pass adds no
    # further offset.
    parts_dir = WORK / "dub_parts"
    shutil.rmtree(parts_dir, ignore_errors=True)
    parts_dir.mkdir(parents=True, exist_ok=True)
    try:
        parts = []
        for start in range(0, len(clips), ASSEMBLE_BATCH):
            part = parts_dir / f"part_{len(parts):03d}.wav"
            _mix_at_offsets(clips[start:start + ASSEMBLE_BATCH], part)
            parts.append((str(part), 0))
        print(f"      ensamblado en {len(parts)} lotes de hasta {ASSEMBLE_BATCH} bloques")
        return _mix_at_offsets(parts, final_path)
    finally:
        shutil.rmtree(parts_dir, ignore_errors=True)
