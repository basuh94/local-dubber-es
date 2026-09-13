from __future__ import annotations
import json
import urllib.request
from .utils import block_window, char_budget, contains_unexpected_script, sanitize_spanish


def _call_ollama(model: str, prompt: str, base_url: str = "http://127.0.0.1:11434") -> str:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "format": "json",
        "keep_alive": "5m",
        "options": {"temperature": 0.1, "num_ctx": 4096},
    }
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as response:
        result = json.loads(response.read().decode("utf-8"))
    return result["message"]["content"].strip()


def _score_candidate(text: str, ratio: float, target_lang: str, budget: int) -> float:
    """Rank retry candidates so the best one survives, not merely the last one.

    Completeness dominates: an over-long translation is penalised in proportion to the
    overrun, but never enough to prefer one that dropped half the sentence.
    """
    if not text:
        return -1.0
    # Completeness saturates once the translation is as long as the source: past that,
    # extra length is verbosity, not extra meaning, and must not outrank a tighter take.
    score = min(ratio, 1.0)
    if contains_unexpected_script(text, target_lang):
        score -= 2.0
    if budget and len(text) > budget:
        score -= min(0.8, (len(text) - budget) / budget)
    return score


def translate_blocks(blocks: list[dict], model: str, source_lang="en", target_lang="es",
                     max_speedup: float = 1.12,
                     chars_per_second: float | None = None) -> list[dict]:
    translated = []
    total = len(blocks)
    over_budget = 0
    for i, current in enumerate(blocks):
        prev_text = blocks[i-1]["text"] if i else ""
        next_text = blocks[i+1]["text"] if i + 1 < total else ""
        # Spanish runs longer than English, so ask for a rendering that will actually fit
        # the window this block has on screen. The budget uses the rate measured for this
        # run's voice reference, not a constant. Never squeeze below a floor that would
        # force the model to drop content.
        window = block_window(blocks, i)
        budget = max(char_budget(window, max_speedup, chars_per_second),
                     int(len(current["text"]) * 0.60))
        prompt = f'''You are a professional audiovisual translator for dubbing.
Translate ONLY CURRENT from {source_lang} into natural Spanish from Spain.
PREVIOUS and NEXT are context only: never translate or repeat them.

Rules:
- Return strict JSON: {{"translation":"..."}}
- Preserve every meaning-bearing detail in CURRENT; do not omit clauses.
- Make it natural spoken Spanish from Spain, concise enough for dubbing.
- LENGTH LIMIT: at most {budget} characters. If needed say the same thing more briefly
  (drop filler words, not meaning). Never drop a fact to meet the limit.
- Preserve names, brands, acronyms and product/model names.
- Use "ordenador" rather than "computadora" for Spain Spanish.
- Prefer "selfie/selfies" rather than "autofoto/autofotos".
- Do not invent punctuation-dependent meaning when ASR punctuation is uncertain.
- Do not output Cyrillic, Chinese, or commentary.
- Technical defaults: hinge=bisagra; spatial audio=audio espacial; reflections=reflejos;
  vapor-cooled=refrigerado por cámara de vapor; inner display=pantalla interior;
  outer display=pantalla exterior.

PREVIOUS: {prev_text}
CURRENT: {current['text']}
NEXT: {next_text}
'''
        best, best_score = "", -1.0
        for attempt in range(3):
            retry_hint = ""
            if attempt:
                retry_hint = ("\nIMPORTANT: the previous attempt omitted content, used an invalid "
                              f"script, or exceeded {budget} characters. Keep every fact "
                              "and stay within the limit.")
            raw = _call_ollama(model, prompt + retry_hint)
            try:
                obj = json.loads(raw)
                text = sanitize_spanish(str(obj.get("translation", "")))
            except json.JSONDecodeError:
                text = sanitize_spanish(raw)
            ratio = len(text) / max(1, len(current["text"]))
            acceptable = (bool(text) and not contains_unexpected_script(text, target_lang)
                          and ratio >= 0.38 and len(text) <= budget)
            # Keep the best candidate seen so far: a later retry can come back empty or
            # in the wrong script and must not overwrite an earlier usable translation.
            score = _score_candidate(text, ratio, target_lang, budget)
            if score > best_score:
                best, best_score = text, score
            if acceptable:
                break
        if not best:
            print(f"      [warn] block {current.get('id', i + 1)}: translation failed; keeping source text")
            best = current["text"]
        if len(best) > budget:
            over_budget += 1
        out = dict(current)
        out["source_text"] = current["text"]
        out["translated_text"] = best
        out["char_budget"] = budget
        translated.append(out)
    if over_budget:
        print(f"      [warn] {over_budget}/{total} blocks exceed their length budget and may be trimmed at synthesis.")
    return translated


def unload_ollama(model: str, base_url: str = "http://127.0.0.1:11434") -> None:
    payload = {"model": model, "prompt": "", "keep_alive": 0}
    req = urllib.request.Request(
        base_url.rstrip("/") + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=30).read()
    except Exception:
        pass
