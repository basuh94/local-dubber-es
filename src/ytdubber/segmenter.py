from __future__ import annotations
import re

CONNECTORS = {
    "and", "or", "but", "so", "when", "while", "that", "because", "if", "to", "the", "a", "an",
    "with", "for", "of", "in", "on", "as", "which", "who", "whose", "where", "then",
}


def normalize_words(words: list[dict]) -> str:
    return re.sub(r"\s+", " ", "".join(w["word"] for w in words).strip())


def _last_lexeme(text: str) -> str:
    parts = re.findall(r"[A-Za-z']+", text.lower())
    return parts[-1] if parts else ""


def build_blocks(words: list[dict], *, min_duration=2.0, target_duration=7.5,
                 max_duration=13.0, pause_threshold=0.55, soft_pause=0.28,
                 hard_max_duration=16.0) -> list[dict]:
    """Pause-aware segmentation with guards against cutting after conjunctions.

    Every preferred rule needs punctuation or a pause. Some ASR output has neither --
    unpunctuated, wall-to-wall speech -- and the connector guard can then veto every
    candidate, so ``hard_max_duration`` forces a cut at the roomiest point available.
    Without it a block can grow until its text overflows the TTS context.
    """
    blocks, current = [], []
    split: tuple[float, int] | None = None  # (gap, words to keep) for a forced cut
    for i, word in enumerate(words):
        current.append(word)
        start, end = current[0]["start"], current[-1]["end"]
        duration = end - start
        text = normalize_words(current)
        gap = (words[i + 1]["start"] - word["end"]) if i + 1 < len(words) else 999.0
        strong = bool(re.search(r'[.!?]["”\']?$', text))
        soft = bool(re.search(r'[,;:]["”\']?$', text))
        connector = _last_lexeme(text) in CONNECTORS
        should_cut = False

        # Remember the best place to break if we end up with no legal cut at all.
        # Widest gap wins; on a tie the later position, to keep blocks near full length.
        if duration >= min_duration and not connector and (split is None or (gap, len(current)) > split):
            split = (gap, len(current))

        if strong and duration >= 1.0:
            should_cut = True
        elif duration >= min_duration and gap >= pause_threshold and not connector:
            should_cut = True
        elif duration >= target_duration and (gap >= soft_pause or soft) and not connector:
            should_cut = True
        elif duration >= max_duration and gap >= 0.12 and not connector:
            should_cut = True

        if not should_cut and duration >= hard_max_duration:
            keep = split[1] if split else len(current)
            blocks.append(_make_block(current[:keep]))
            current = current[keep:]
            split = None
            continue

        if should_cut:
            blocks.append(_make_block(current))
            current = []
            split = None

    if current:
        blocks.append(_make_block(current))

    # Merge very short tail blocks where possible.
    merged = []
    for b in blocks:
        if merged and b["duration"] < 1.25 and merged[-1]["duration"] + b["duration"] < max_duration + 2:
            prev = merged.pop()
            merged.append({
                "start": prev["start"], "end": b["end"],
                "duration": b["end"] - prev["start"],
                "text": (prev["text"] + " " + b["text"]).strip(),
                "avg_probability": (prev["avg_probability"] + b["avg_probability"]) / 2,
            })
        else:
            merged.append(b)
    for i, b in enumerate(merged, 1):
        b["id"] = i
    return merged


def _make_block(words: list[dict]) -> dict:
    probs = [float(w.get("probability", 0.0)) for w in words]
    return {
        "start": float(words[0]["start"]),
        "end": float(words[-1]["end"]),
        "duration": float(words[-1]["end"] - words[0]["start"]),
        "text": normalize_words(words),
        "avg_probability": sum(probs) / max(1, len(probs)),
    }


def choose_voice_reference(blocks: list[dict], min_s=5.0, max_s=10.5) -> tuple[float, float]:
    candidates = [b for b in blocks if min_s <= b["duration"] <= max_s]
    if not candidates:
        candidates = sorted(blocks, key=lambda b: abs(b["duration"] - 7.0))[:5]
    if not candidates:
        return (0.0, 8.0)
    best = max(candidates, key=lambda b: (b.get("avg_probability", 0.0), -abs(b["duration"] - 7.0)))
    return best["start"], min(best["end"], best["start"] + max_s)
