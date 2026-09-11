from __future__ import annotations
from pathlib import Path
import subprocess
from .models import get_profile
from .utils import OUTPUT, WORK, ensure_dirs, read_json, write_json, seconds_to_srt
from .downloader import download_source
from .transcriber import transcribe
from .segmenter import build_blocks, choose_voice_reference
from .translator import translate_blocks, unload_ollama
from .tts import extract_reference, synthesize_chatterbox, assemble_dub
from .mixer import make_final_video


def _write_target_subtitles(blocks: list[dict]) -> None:
    srt = []
    for i, b in enumerate(blocks, 1):
        srt += [str(i), f"{seconds_to_srt(b['start'])} --> {seconds_to_srt(b['end'])}", b['translated_text'], ""]
    (OUTPUT / "subtitles_es.srt").write_text("\n".join(srt), encoding="utf-8")
    (OUTPUT / "transcript_es.txt").write_text("\n".join(b["translated_text"] for b in blocks), encoding="utf-8")


def run_pipeline(source: str, profile_name="balanced", source_lang: str | None = None,
                 voice_ref: str | None = None, original_speech_level: float = 0.12,
                 tts_takes: int | None = None, max_speedup: float | None = None) -> Path:
    ensure_dirs()
    profile = get_profile(profile_name)
    takes = profile.tts_takes if tts_takes is None else max(1, tts_takes)
    speed_cap = profile.max_speedup if max_speedup is None else max_speedup
    print(f"[profile] {profile.name}: ASR={profile.asr_model} / LLM={profile.ollama_model} / TTS=Chatterbox V3")
    if takes != profile.tts_takes or speed_cap != profile.max_speedup:
        print(f"[override] tomas={takes} max_speedup={speed_cap}")

    print("[1/7] Download/extract")
    video, audio16 = download_source(source)

    print("[2/7] Transcribe")
    tr = transcribe(audio16, profile.asr_model, profile.asr_compute_type, source_lang)

    print("[3/7] Segment")
    blocks = build_blocks(tr["words"])
    write_json(OUTPUT / "blocks_source.json", blocks)

    print("[4/7] Translate with Ollama")
    translated = translate_blocks(blocks, profile.ollama_model, tr["meta"]["language"], "es",
                                  max_speedup=speed_cap)
    write_json(OUTPUT / "blocks_es.json", translated)
    _write_target_subtitles(translated)
    unload_ollama(profile.ollama_model)  # Free VRAM before TTS.

    print("[5/7] Prepare voice reference")
    if voice_ref:
        ref = Path(voice_ref).resolve()
        if not ref.exists():
            raise FileNotFoundError(ref)
    else:
        start, end = choose_voice_reference(blocks)
        ref = WORK / "voice_ref_auto.wav"
        extract_reference(video, start, end, ref)
        print(f"      auto reference: {start:.2f}s -> {end:.2f}s")

    print("[6/7] Synthesize + timing")
    voiced = synthesize_chatterbox(
        translated, ref, cfg_weight=profile.cfg_weight,
        exaggeration=profile.exaggeration, max_speedup=speed_cap,
        takes=takes,
    )
    write_json(OUTPUT / "blocks_voiced.json", voiced)
    dub = assemble_dub(voiced, OUTPUT / "dub_es.wav")

    print("[7/7] Final video mix")
    final = make_final_video(video, dub, voiced, OUTPUT / "video_es.mp4", original_speech_level)
    print(f"DONE: {final}")
    return final
