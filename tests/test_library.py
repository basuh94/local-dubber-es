import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ytdubber import library


def _tiny_video(path: Path) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=black:s=160x120:d=1:r=10",
        "-f", "lavfi", "-i", "sine=frequency=220:duration=1", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path),
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        self.out = self.tmp / "output"
        self.work = self.tmp / "work"
        self.lib = self.tmp / "library"
        for d in (self.out, self.work, self.lib):
            d.mkdir()
        # The module reads these at call time, so patching the names is enough.
        for target in ("OUTPUT", "WORK", "LIBRARY"):
            p = patch.object(library, target, {"OUTPUT": self.out, "WORK": self.work,
                                               "LIBRARY": self.lib}[target])
            p.start()
            self.addCleanup(p.stop)

    def _stage_finished_run(self):
        _tiny_video(self.out / "video_es.mp4")
        (self.out / "subtitles_es.srt").write_text("1\n", encoding="utf-8")
        (self.out / "blocks_es.json").write_text('[{"id":1}]', encoding="utf-8")
        (self.out / "blocks_voiced.json").write_text(
            '[{"id":1,"timing":{"trimmed":true,"actual":3.0,"window":2.0}}]', encoding="utf-8")
        blocks = self.out / "dub_blocks"
        blocks.mkdir()
        (blocks / "block_001.wav").write_bytes(b"x" * 2048)
        (self.work / "audio_16k.wav").write_bytes(b"y" * 1024)
        (self.work / "source.mp4").write_bytes(b"z" * 512)

    def test_archive_keeps_deliverables_and_removes_intermediates(self):
        self._stage_finished_run()
        meta = library.archive("http://example/v", "Mi Video de Prueba", "balanced", "en")

        entry = self.lib / meta["id"]
        self.assertTrue((entry / "video_es.mp4").exists())
        self.assertTrue((entry / "subtitles_es.srt").exists())
        self.assertTrue((entry / "meta.json").exists())
        # Intermediates are gone from both scratch directories.
        self.assertFalse((self.out / "dub_blocks").exists())
        self.assertFalse((self.work / "audio_16k.wav").exists())
        self.assertFalse((self.work / "source.mp4").exists())
        self.assertEqual([p.name for p in self.out.iterdir()], [])
        # Reported reclaimed space covers the block wavs plus the staged source.
        self.assertGreaterEqual(meta["reclaimed"], 2048 + 1024 + 512)
        self.assertEqual(meta["trimmed_blocks"], 1)
        self.assertEqual(len(meta["warnings"]), 1)
        self.assertIn("mi-video-de-prueba", meta["id"])

    def test_entries_then_delete_round_trip(self):
        self._stage_finished_run()
        meta = library.archive("http://example/v", "Prueba", "fast", None)
        self.assertEqual([e["id"] for e in library.entries()], [meta["id"]])

        library.delete(meta["id"])
        self.assertEqual(library.entries(), [])
        self.assertFalse((self.lib / meta["id"]).exists())

    def test_entry_dir_rejects_paths_outside_the_library(self):
        for bad in ("..", "../..", "nope"):
            with self.assertRaises(KeyError):
                library.entry_dir(bad)

    def test_clean_workspace_is_safe_to_call_twice(self):
        self._stage_finished_run()
        library.clean_workspace()
        library.clean_workspace()
        self.assertEqual(list(self.out.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
