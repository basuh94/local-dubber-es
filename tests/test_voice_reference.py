import unittest

from ytdubber.segmenter import choose_voice_reference, speaking_rate


def block(start, duration, text, prob=0.95):
    return {"start": start, "end": start + duration, "duration": duration,
            "text": text, "avg_probability": prob}


class SpeakingRateTests(unittest.TestCase):
    def test_rate_is_chars_per_second(self):
        self.assertAlmostEqual(speaking_rate(block(0, 2.0, "a" * 30)), 15.0)

    def test_zero_duration_does_not_explode(self):
        self.assertGreater(speaking_rate({"duration": 0.0, "text": "hola"}), 0)


class ReferenceSelectionTests(unittest.TestCase):
    def test_prefers_the_brisker_delivery(self):
        # Chatterbox clones the reference's pacing, so a slow clip makes every dubbed line
        # overrun. Both candidates are equally confident here.
        blocks = [
            block(10.0, 6.0, "x" * 50),   # 8.3 c/s
            block(30.0, 6.0, "x" * 120),  # 20 c/s
        ]
        self.assertEqual(choose_voice_reference(blocks), (30.0, 36.0))

    def test_confidence_still_gates_the_choice(self):
        # The fast block is one the ASR barely understood: a bad voice sample.
        blocks = [
            block(10.0, 6.0, "x" * 50, prob=0.98),
            block(30.0, 6.0, "x" * 200, prob=0.40),
        ]
        self.assertEqual(choose_voice_reference(blocks), (10.0, 16.0))

    def test_respects_the_duration_window(self):
        blocks = [
            block(0.0, 2.0, "x" * 200),    # too short to clone from
            block(10.0, 7.0, "x" * 70),
            block(40.0, 40.0, "x" * 2000),  # too long
        ]
        start, end = choose_voice_reference(blocks)
        self.assertEqual(start, 10.0)
        self.assertLessEqual(end - start, 10.5)

    def test_caps_the_clip_length(self):
        blocks = [block(5.0, 10.0, "x" * 150)]
        start, end = choose_voice_reference(blocks)
        self.assertLessEqual(end - start, 10.5)

    def test_falls_back_when_nothing_matches_the_window(self):
        blocks = [block(0.0, 1.0, "corto"), block(5.0, 2.0, "tambien corto")]
        start, end = choose_voice_reference(blocks)
        self.assertGreaterEqual(start, 0.0)
        self.assertGreater(end, start)

    def test_no_blocks_at_all(self):
        self.assertEqual(choose_voice_reference([]), (0.0, 8.0))


if __name__ == "__main__":
    unittest.main()
