import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import inspect  # noqa: E402

import wrap as wrap_module  # noqa: E402
from wrap import wrap  # noqa: E402


class WrapTest(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(wrap("der schnelle braune Fuchs", 10), ["der", "schnelle", "braune", "Fuchs"])
        self.assertEqual(wrap("a b c d", 3), ["a b", "c d"])

    def test_spaces_collapse(self):
        self.assertEqual(wrap("a    b", 10), ["a b"])

    def test_long_word_is_split(self):
        self.assertEqual(wrap("Donaudampfschiff", 6), ["Donaud", "ampfsc", "hiff"])

    def test_paragraphs(self):
        self.assertEqual(wrap("eins zwei\n\ndrei", 9), ["eins zwei", "", "drei"])

    def test_invalid_width(self):
        with self.assertRaises(ValueError):
            wrap("x", 0)

    def test_no_textwrap(self):
        self.assertNotIn("textwrap", inspect.getsource(wrap_module))
