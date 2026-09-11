import unittest
from unittest.mock import patch

from ytdubber.models import PROFILES
from ytdubber.tts import cfg_ladder


class CfgLadderTests(unittest.TestCase):
    def test_first_takes_keep_the_profile_value(self):
        # cfg_weight=0.0 is the accent-safe setting for cross-language cloning; it must
        # not be traded away until a block is actually heading for a truncated tail.
        ladder = cfg_ladder(0.0, 4)
        self.assertEqual(ladder[:2], [0.0, 0.0])

    def test_later_takes_escalate(self):
        self.assertEqual(cfg_ladder(0.0, 4), [0.0, 0.0, 0.3, 0.5])

    def test_never_lowers_a_profile_that_already_asks_for_more(self):
        self.assertTrue(all(v >= 0.6 for v in cfg_ladder(0.6, 4)))

    def test_length_matches_requested_takes(self):
        for takes in (1, 2, 3, 4, 6):
            self.assertEqual(len(cfg_ladder(0.0, takes)), takes)

    def test_at_least_one_take_even_if_asked_for_none(self):
        self.assertEqual(len(cfg_ladder(0.0, 0)), 1)

    def test_every_profile_declares_a_usable_take_count(self):
        for name, profile in PROFILES.items():
            with self.subTest(profile=name):
                self.assertGreaterEqual(profile.tts_takes, 1)
                self.assertEqual(len(cfg_ladder(profile.cfg_weight, profile.tts_takes)),
                                 profile.tts_takes)


class TakeSelectionTests(unittest.TestCase):
    """synthesize_chatterbox should stop as soon as a take fits, and otherwise keep the
    shortest one it saw."""

    def _run(self, durations, takes=3, window=4.0, max_speedup=1.12):
        import numpy as np
        import torch

        calls = []
        sr = 24000

        class FakeModel:
            sr = 24000
            tokenizer = None

            def generate(self, text, **kw):
                n = len(calls)
                calls.append(kw["cfg_weight"])
                return torch.zeros(1, int(durations[n] * sr))

        blocks = [{"id": 1, "start": 0.0, "end": window, "duration": window,
                   "translated_text": "hola"}]

        saved = {}

        def fake_save(path, wav, rate):
            saved["dur"] = wav.shape[-1] / rate

        def fake_fit(src, dst, target, ms, window_duration=None):
            return {"actual": saved["dur"], "target": target, "window": window_duration,
                    "speed": 1.0, "trimmed": False, "duration": saved["dur"]}

        with patch("ytdubber.tts.split_for_tts", return_value=["hola"]), \
             patch("ytdubber.tts.fit_audio", side_effect=fake_fit), \
             patch("torchaudio.save", side_effect=fake_save), \
             patch("chatterbox.mtl_tts.ChatterboxMultilingualTTS.from_pretrained",
                   return_value=FakeModel()):
            from ytdubber.tts import synthesize_chatterbox
            out = synthesize_chatterbox(blocks, "ref.wav", cfg_weight=0.0,
                                        exaggeration=0.5, max_speedup=max_speedup,
                                        takes=takes)
        return calls, saved["dur"], out

    def test_stops_at_the_first_take_that_fits(self):
        # 3.0 s fits a 4 s window straight away: no retake, accent setting untouched.
        calls, dur, _ = self._run([3.0, 1.0, 1.0])
        self.assertEqual(calls, [0.0])
        self.assertAlmostEqual(dur, 3.0, places=2)

    def test_retakes_and_keeps_the_shortest_when_nothing_fits(self):
        calls, dur, _ = self._run([9.0, 7.0, 8.0])
        self.assertEqual(calls, [0.0, 0.0, 0.3])  # escalated on the last take
        self.assertAlmostEqual(dur, 7.0, places=2)  # shortest of the three

    def test_accepts_a_later_take_that_fits(self):
        calls, dur, _ = self._run([9.0, 4.2, 1.0])
        self.assertEqual(len(calls), 2)
        self.assertAlmostEqual(dur, 4.2, places=2)


if __name__ == "__main__":
    unittest.main()
