import unittest
from unittest.mock import patch
from ytdubber.translator import translate_blocks
from ytdubber.utils import block_window, char_budget

SOURCE = "The hinge feels solid and the inner display is bright."
BLOCKS = [{"id": 1, "start": 0.0, "end": 2.0, "duration": 2.0, "text": SOURCE}]


def _budget():
    return max(char_budget(block_window(BLOCKS, 0), 1.12), int(len(SOURCE) * 0.60))


def _run(replies):
    with patch("ytdubber.translator._call_ollama", side_effect=replies):
        return translate_blocks(BLOCKS, "qwen3:8b", max_speedup=1.12)[0]


class TranslatorRetryTests(unittest.TestCase):
    def test_keeps_best_candidate_when_a_later_retry_is_worse(self):
        # First reply is too short to accept, so it retries; the retries come back empty
        # and must not overwrite the only usable translation seen.
        out = _run(['{"translation":"La bisagra."}', '{"translation":""}', '{"translation":""}'])
        self.assertEqual(out["translated_text"], "La bisagra.")

    def test_rejects_wrong_script_in_favour_of_earlier_spanish(self):
        cyrillic = '{"translation":"\u042d\u043a\u0440\u0430\u043d \u0431\u0438\u0441\u0430\u0433\u0440\u0430 \u0432\u043d\u0443\u0442\u0440\u0435\u043d\u043d\u0438\u0439"}'
        out = _run(['{"translation":"La bisagra."}', cyrillic, '{"translation":""}'])
        self.assertEqual(out["translated_text"], "La bisagra.")

    def test_falls_back_to_source_text_when_everything_fails(self):
        out = _run(['{"translation":""}'] * 3)
        self.assertEqual(out["translated_text"], SOURCE)


class TranslatorBudgetTests(unittest.TestCase):
    def test_budget_is_exposed_and_derived_from_the_block_window(self):
        out = _run(['{"translation":"La bisagra es solida."}'])
        self.assertEqual(out["char_budget"], _budget())

    def test_overlong_translation_is_retried_and_shorter_one_wins(self):
        long_one = '{"translation":"' + "La bisagra resulta muy solida y ademas la pantalla interior se ve realmente brillante." + '"}'
        short_one = '{"translation":"La bisagra es solida y la pantalla brilla."}'
        out = _run([long_one, short_one])
        self.assertEqual(out["translated_text"], "La bisagra es solida y la pantalla brilla.")
        self.assertLessEqual(len(out["translated_text"]), out["char_budget"])

    def test_overlong_but_complete_beats_truncated_when_nothing_fits(self):
        # Every candidate is over budget; the most complete one must still win.
        long_one = "La bisagra resulta muy solida y ademas la pantalla interior se ve realmente brillante."
        out = _run(['{"translation":"' + long_one + '"}'] * 3)
        self.assertEqual(out["translated_text"], long_one)


if __name__ == "__main__":
    unittest.main()
