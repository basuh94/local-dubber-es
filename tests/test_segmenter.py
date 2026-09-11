import unittest
from ytdubber.segmenter import build_blocks, choose_voice_reference

class SegmenterTests(unittest.TestCase):
    def test_does_not_cut_after_connector(self):
        words = [
            {"start":0.0,"end":0.2,"word":" So","probability":.99},
            {"start":0.2,"end":0.4,"word":" when","probability":.99},
            {"start":0.4,"end":0.8,"word":" you","probability":.99},
            {"start":0.8,"end":1.2,"word":" open","probability":.99},
            {"start":1.2,"end":1.5,"word":" photos","probability":.99},
            {"start":2.2,"end":2.5,"word":" you","probability":.99},
            {"start":2.5,"end":2.8,"word":" see","probability":.99},
            {"start":2.8,"end":3.2,"word":" more.","probability":.99},
        ]
        blocks = build_blocks(words, min_duration=.5, target_duration=2, max_duration=8, pause_threshold=.5)
        self.assertEqual(blocks[-1]["text"], "So when you open photos you see more.")

    def test_reference_selection(self):
        blocks = [
            {"start":0,"end":2,"duration":2,"avg_probability":.9},
            {"start":3,"end":10,"duration":7,"avg_probability":.98},
        ]
        self.assertEqual(choose_voice_reference(blocks), (3,10))

if __name__ == '__main__': unittest.main()
