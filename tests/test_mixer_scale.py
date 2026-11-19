import subprocess
import tempfile
import unittest
from pathlib import Path

from ytdubber.mixer import DUCK_CHUNK, duck_chain, make_final_video
from ytdubber.utils import ffprobe_duration


def blocks(count, spacing=0.4, length=0.2):
    return [{"id": i + 1, "start": i * spacing, "end": i * spacing + length,
             "duration": length, "timing": {"duration": length}} for i in range(count)]


class DuckChainTests(unittest.TestCase):
    def test_no_blocks_is_a_passthrough(self):
        self.assertEqual(duck_chain([], 0.12), "anull")

    def test_one_stage_while_under_the_chunk_size(self):
        chain = duck_chain(blocks(DUCK_CHUNK), 0.12)
        self.assertEqual(chain.count("volume="), 1)

    def test_splits_into_several_stages_beyond_it(self):
        chain = duck_chain(blocks(DUCK_CHUNK * 3 + 1), 0.12)
        self.assertEqual(chain.count("volume="), 4)

    def test_every_window_survives_the_split(self):
        n = DUCK_CHUNK * 2 + 5
        self.assertEqual(duck_chain(blocks(n), 0.12).count("between("), n)

    def test_no_single_expression_grows_unbounded(self):
        # The real failure was one expression of 11580 characters.
        for expr in duck_chain(blocks(500), 0.12).split(","):
            self.assertLess(len(expr), 2000)

    def test_the_level_reaches_every_stage(self):
        chain = duck_chain(blocks(DUCK_CHUNK * 2), 0.2)
        self.assertEqual(chain.count("volume=0.2:"), 2)


class ManyBlockMixTests(unittest.TestCase):
    def test_ffmpeg_accepts_a_chain_with_many_windows(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            src, dub, out = d / "src.mp4", d / "dub.wav", d / "out.mp4"
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x120:d=60:r=10",
                "-f", "lavfi", "-i", "sine=frequency=220:duration=60", "-shortest",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(src),
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=60",
                "-ar", "24000", "-ac", "1", str(dub),
            ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

            # More windows than one expression handled before.
            make_final_video(src, dub, blocks(120, spacing=0.5, length=0.2), out, 0.12)
            self.assertTrue(out.exists())
            self.assertAlmostEqual(ffprobe_duration(out), 60.0, places=0)


if __name__ == "__main__":
    unittest.main()
