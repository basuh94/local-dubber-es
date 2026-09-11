from __future__ import annotations
from pathlib import Path
from .utils import OUTPUT, activate_vendor_cuda, seconds_to_srt, write_json


def transcribe(audio_path: Path, model_name: str, compute_type: str, language: str | None = None) -> dict:
    activate_vendor_cuda()
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cuda", compute_type=compute_type)
    segments, info = model.transcribe(
        str(audio_path),
        language=language,
        beam_size=5,
        word_timestamps=True,
        vad_filter=True,
        condition_on_previous_text=True,
    )

    words = []
    srt = []
    transcript = []
    idx = 1
    for seg in segments:
        text = seg.text.strip()
        if not text:
            continue
        transcript.append(text)
        srt.extend([str(idx), f"{seconds_to_srt(seg.start)} --> {seconds_to_srt(seg.end)}", text, ""])
        if seg.words:
            for w in seg.words:
                if w.start is None or w.end is None:
                    continue
                words.append({
                    "start": float(w.start), "end": float(w.end), "word": w.word,
                    "probability": float(w.probability or 0.0),
                })
        idx += 1

    (OUTPUT / "transcript_source.txt").write_text("\n".join(transcript), encoding="utf-8")
    (OUTPUT / "subtitles_source.srt").write_text("\n".join(srt), encoding="utf-8")
    write_json(OUTPUT / "words.json", words)
    meta = {"language": info.language, "language_probability": info.language_probability, "model": model_name}
    write_json(OUTPUT / "transcription_meta.json", meta)
    return {"words": words, "meta": meta}
