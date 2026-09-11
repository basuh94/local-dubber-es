import unittest

from ytdubber.segmenter import build_blocks
from ytdubber.tts import split_for_tts


def _unpunctuated_speech(seconds=120.0, gap=0.0):
    """ASR output with no punctuation and no pauses, as some videos really produce."""
    words, t = [], 0.0
    vocab = ["so", "the", "model", "and", "you", "can", "see", "that", "it", "works"]
    i = 0
    while t < seconds:
        words.append({"start": t, "end": t + 0.3, "word": f" {vocab[i % len(vocab)]}",
                      "probability": 0.9})
        t += 0.3 + gap
        i += 1
    return words


class SegmenterHardCapTests(unittest.TestCase):
    def test_unpunctuated_gapless_speech_is_still_split(self):
        blocks = build_blocks(_unpunctuated_speech(120.0))
        self.assertGreater(len(blocks), 5)
        # Without the hard cap this produced a single ~120 s block.
        self.assertLessEqual(max(b["duration"] for b in blocks), 17.5)

    def test_hard_cap_is_configurable_and_respected(self):
        blocks = build_blocks(_unpunctuated_speech(60.0), hard_max_duration=8.0)
        self.assertLessEqual(max(b["duration"] for b in blocks), 9.0)

    def test_no_words_are_dropped_by_a_forced_cut(self):
        words = _unpunctuated_speech(60.0)
        blocks = build_blocks(words)
        joined = " ".join(b["text"] for b in blocks).split()
        self.assertEqual(joined, [w["word"].strip() for w in words])

    def test_punctuated_speech_still_cuts_on_sentences(self):
        words = [
            {"start": 0.0, "end": 0.5, "word": " Hola", "probability": 0.9},
            {"start": 0.5, "end": 1.2, "word": " mundo.", "probability": 0.9},
            {"start": 1.4, "end": 2.2, "word": " Otra", "probability": 0.9},
            {"start": 2.2, "end": 3.1, "word": " frase", "probability": 0.9},
            {"start": 3.1, "end": 3.9, "word": " completa.", "probability": 0.9},
        ]
        self.assertEqual([b["text"] for b in build_blocks(words)],
                         ["Hola mundo.", "Otra frase completa."])


class TtsSplitTests(unittest.TestCase):
    # Without a model split_for_tts falls back to a character budget.
    LIMIT = 20  # max_tokens; the char budget is LIMIT * 1.35 = 27 chars

    def test_short_text_is_not_split(self):
        self.assertEqual(split_for_tts("Hola mundo.", max_tokens=self.LIMIT), ["Hola mundo."])

    def test_empty_text_yields_nothing(self):
        self.assertEqual(split_for_tts("   ", max_tokens=self.LIMIT), [])

    def test_long_text_splits_on_sentence_boundaries(self):
        text = "Primera frase corta. Segunda frase corta. Tercera frase corta."
        parts = split_for_tts(text, max_tokens=self.LIMIT)
        self.assertGreater(len(parts), 1)
        for p in parts:
            self.assertLessEqual(len(p), self.LIMIT * 1.35)
        self.assertEqual(" ".join(parts), text)

    def test_falls_back_to_commas_then_words(self):
        text = "uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece"
        parts = split_for_tts(text, max_tokens=self.LIMIT)
        self.assertGreater(len(parts), 1)
        for p in parts:
            self.assertLessEqual(len(p), self.LIMIT * 1.35)
        self.assertEqual(" ".join(parts), text)

    def test_no_text_is_lost_when_splitting(self):
        text = "Una frase larga, con comas, que no cabe de ninguna manera en el limite."
        parts = split_for_tts(text, max_tokens=self.LIMIT)
        self.assertEqual("".join(parts).replace(" ", ""), text.replace(" ", ""))


if __name__ == "__main__":
    unittest.main()
