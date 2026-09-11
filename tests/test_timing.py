import unittest
from pathlib import Path
import tempfile, subprocess
from ytdubber.tts import fit_audio
from ytdubber.utils import ffprobe_duration

class TimingTests(unittest.TestCase):
    def test_short_audio_is_padded_not_slowed(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)/"a.wav"; out = Path(d)/"b.wav"
            subprocess.run(["ffmpeg","-y","-f","lavfi","-i","sine=frequency=440:duration=1","-ar","24000",str(src)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            stats = fit_audio(src, out, 2.0, 1.12)
            self.assertEqual(stats["speed"], 1.0)
            self.assertAlmostEqual(ffprobe_duration(out), 2.0, places=1)

    def test_long_audio_uses_following_pause_before_speeding_up(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)/"a.wav"; out = Path(d)/"b.wav"
            subprocess.run(["ffmpeg","-y","-f","lavfi","-i","sine=frequency=440:duration=3","-ar","24000",str(src)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # 3s of speech in a 2s block, but the next block starts 4s later.
            stats = fit_audio(src, out, 2.0, 1.12, window_duration=4.0)
            self.assertEqual(stats["speed"], 1.0)
            self.assertFalse(stats["trimmed"])
            self.assertAlmostEqual(ffprobe_duration(out), 3.0, places=1)

    def test_speedup_is_capped_and_trim_is_reported(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d)/"a.wav"; out = Path(d)/"b.wav"
            subprocess.run(["ffmpeg","-y","-f","lavfi","-i","sine=frequency=440:duration=4","-ar","24000",str(src)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            stats = fit_audio(src, out, 2.0, 1.12, window_duration=2.0)
            self.assertAlmostEqual(stats["speed"], 1.12, places=3)
            self.assertTrue(stats["trimmed"])
            self.assertAlmostEqual(ffprobe_duration(out), 2.0, places=1)

if __name__ == '__main__': unittest.main()
