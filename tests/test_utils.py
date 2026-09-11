import unittest
from ytdubber.utils import seconds_to_srt, contains_unexpected_script, sanitize_spanish

class UtilsTests(unittest.TestCase):
    def test_srt(self): self.assertEqual(seconds_to_srt(61.234), "00:01:01,234")
    def test_script_detection(self):
        self.assertTrue(contains_unexpected_script("pantalla экран", "es"))
        self.assertFalse(contains_unexpected_script("pantalla interior", "es"))
    def test_spanish_sanitize(self): self.assertEqual(sanitize_spanish("una computadora"), "un ordenador")

if __name__ == '__main__': unittest.main()
