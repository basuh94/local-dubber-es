from __future__ import annotations
from pathlib import Path
import json, os, sys, urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from ytdubber.utils import OUTPUT, activate_vendor_cuda

print("[1/4] PyTorch CUDA")
import torch
assert torch.cuda.is_available(), "CUDA is not available to PyTorch"
print(torch.__version__, torch.cuda.get_device_name(0))

print("[2/4] Chatterbox Multilingual V3 generation")
import torchaudio as ta
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
model = ChatterboxMultilingualTTS.from_pretrained(device="cuda", t3_model="v3")
wav = model.generate("Esta es una prueba corta en español.", language_id="es", cfg_weight=0.0)
OUTPUT.mkdir(exist_ok=True)
tts_path = OUTPUT / "smoke_tts_es.wav"
ta.save(str(tts_path), wav, model.sr)
del model; torch.cuda.empty_cache()
print(tts_path)

print("[3/4] faster-whisper CUDA transcription")
activate_vendor_cuda()
from faster_whisper import WhisperModel
asr = WhisperModel("small", device="cuda", compute_type="int8_float16")
segments, info = asr.transcribe(str(tts_path), language="es", beam_size=3)
text = " ".join(s.text.strip() for s in segments).strip()
assert text, "ASR returned empty text"
print("ASR:", text)
del asr; torch.cuda.empty_cache()

print("[4/4] Ollama qwen3:8b")
payload = {"model":"qwen3:8b","messages":[{"role":"user","content":"Return only: OK"}],"stream":False,"think":False,"keep_alive":0}
req = urllib.request.Request("http://127.0.0.1:11434/api/chat", data=json.dumps(payload).encode(), headers={"Content-Type":"application/json"}, method="POST")
with urllib.request.urlopen(req, timeout=180) as r:
    obj=json.loads(r.read().decode())
assert obj["message"]["content"].strip(), "Ollama returned empty content"
print("Ollama:", obj["message"]["content"].strip())
print("MODEL SMOKE TEST: PASS")
