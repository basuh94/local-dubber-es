import subprocess
import tempfile
import unittest
from pathlib import Path

from ytdubber.tts import ASSEMBLE_BATCH, assemble_dub
from ytdubber.utils import ffprobe_duration


def tone(path: Path, seconds=0.2, freq=440):
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}",
        "-ar", "24000", "-ac", "1", str(path),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class AssembleDubTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))

    def _blocks(self, count, spacing=0.5):
        clip = self.tmp / "clip.wav"
        tone(clip)
        return [{"id": i + 1, "start": i * spacing, "audio": str(clip)} for i in range(count)]

    def test_rejects_an_empty_list(self):
        with self.assertRaises(ValueError):
            assemble_dub([], self.tmp / "out.wav")

    def test_single_batch_places_clips_on_the_timeline(self):
        out = self.tmp / "single.wav"
        assemble_dub(self._blocks(3, spacing=1.0), out)
        # Last clip starts at 2.0 s and lasts 0.2 s.
        self.assertAlmostEqual(ffprobe_duration(out), 2.2, places=1)

    def test_many_blocks_do_not_blow_the_command_line(self):
        # The real failure: 414 clips in one ffmpeg call exceeded Windows' 32767-character
        # limit and raised WinError 206 after the whole synthesis had already run.
        count = ASSEMBLE_BATCH * 3 + 7
        out = self.tmp / "many.wav"
        assemble_dub(self._blocks(count, spacing=0.25), out)
        self.assertTrue(out.exists())
        expected = (count - 1) * 0.25 + 0.2
        self.assertAlmostEqual(ffprobe_duration(out), expected, places=1)

    def test_batched_and_unbatched_agree_on_duration(self):
        few = self._blocks(ASSEMBLE_BATCH - 1, spacing=0.25)
        many = self._blocks(ASSEMBLE_BATCH + 1, spacing=0.25)
        a, b = self.tmp / "a.wav", self.tmp / "b.wav"
        assemble_dub(few, a)
        assemble_dub(many, b)
        self.assertAlmostEqual(ffprobe_duration(a), (len(few) - 1) * 0.25 + 0.2, places=1)
        self.assertAlmostEqual(ffprobe_duration(b), (len(many) - 1) * 0.25 + 0.2, places=1)

    def test_leaves_no_temporary_parts_behind(self):
        from ytdubber.utils import WORK
        assemble_dub(self._blocks(ASSEMBLE_BATCH + 5, spacing=0.2), self.tmp / "out.wav")
        self.assertFalse((WORK / "dub_parts").exists())


if __name__ == "__main__":
    unittest.main()
