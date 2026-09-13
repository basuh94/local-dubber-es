import unittest
from unittest.mock import patch

from ytdubber.tts import MAX_RATE, MIN_RATE, measure_speaking_rate
from ytdubber.utils import TTS_CHARS_PER_SECOND, char_budget


class CharBudgetTests(unittest.TestCase):
    def test_uses_the_measured_rate_when_given(self):
        # 10 s window, cap 1.3, voice measured at 20 chars/s -> 260 characters.
        self.assertEqual(char_budget(10.0, 1.3, 20.0), 260)

    def test_falls_back_to_the_default_constant(self):
        expected = int(TTS_CHARS_PER_SECOND * 10.0 * 1.3)
        self.assertEqual(char_budget(10.0, 1.3), expected)
        self.assertEqual(char_budget(10.0, 1.3, None), expected)

    def test_ignores_a_nonsensical_rate(self):
        expected = int(TTS_CHARS_PER_SECOND * 10.0 * 1.3)
        for bad in (0.0, -5.0):
            with self.subTest(rate=bad):
                self.assertEqual(char_budget(10.0, 1.3, bad), expected)

    def test_a_faster_voice_earns_a_bigger_budget(self):
        self.assertGreater(char_budget(5.0, 1.3, 18.0), char_budget(5.0, 1.3, 12.0))

    def test_never_returns_zero(self):
        self.assertGreaterEqual(char_budget(0.001, 1.0, 1.0), 1)


class FakeWav:
    def __init__(self, samples):
        self.shape = (1, samples)


class FakeModel:
    """Speaks at a rate we control, so the probe's arithmetic can be checked exactly."""
    sr = 24000

    def __init__(self, chars_per_second):
        self.rate = chars_per_second
        self.calls = []

    def generate(self, text, **kw):
        self.calls.append((text, kw.get("cfg_weight"), kw.get("exaggeration")))
        return FakeWav(int(len(text) / self.rate * self.sr))


class MeasureSpeakingRateTests(unittest.TestCase):
    def _measure(self, rate, **kw):
        model = FakeModel(rate)
        with patch("chatterbox.mtl_tts.ChatterboxMultilingualTTS.from_pretrained",
                   return_value=model):
            got = measure_speaking_rate("ref.wav", 0.0, 0.5, **kw)
        return got, model

    def test_recovers_the_rate_it_was_given(self):
        got, model = self._measure(15.0)
        self.assertAlmostEqual(got, 15.0, places=1)
        self.assertGreaterEqual(len(model.calls), 2)

    def test_passes_the_profile_settings_to_the_model(self):
        _, model = self._measure(15.0)
        for _, cfg, exag in model.calls:
            self.assertEqual(cfg, 0.0)
            self.assertEqual(exag, 0.5)

    def test_absurdly_slow_measurement_falls_back(self):
        got, _ = self._measure(MIN_RATE / 2)
        self.assertEqual(got, TTS_CHARS_PER_SECOND)

    def test_absurdly_fast_measurement_falls_back(self):
        got, _ = self._measure(MAX_RATE * 2)
        self.assertEqual(got, TTS_CHARS_PER_SECOND)

    def test_rates_inside_the_guard_rails_are_kept(self):
        for rate in (MIN_RATE + 0.5, 15.0, MAX_RATE - 0.5):
            with self.subTest(rate=rate):
                got, _ = self._measure(rate)
                self.assertAlmostEqual(got, rate, places=1)

    def test_the_probe_lines_are_real_sentences(self):
        from ytdubber.tts import CALIBRATION_LINES
        self.assertGreaterEqual(len(CALIBRATION_LINES), 2)
        for line in CALIBRATION_LINES:
            self.assertGreater(len(line), 40)


if __name__ == "__main__":
    unittest.main()
