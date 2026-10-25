import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from roman import from_roman, to_roman  # noqa: E402


class RomanTest(unittest.TestCase):
    def test_to_roman(self):
        cases = {1: "I", 4: "IV", 9: "IX", 14: "XIV", 40: "XL", 90: "XC", 400: "CD", 1994: "MCMXCIV", 3999: "MMMCMXCIX"}
        for n, text in cases.items():
            self.assertEqual(to_roman(n), text)

    def test_round_trip(self):
        for n in range(1, 4000):
            self.assertEqual(from_roman(to_roman(n)), n)

    def test_invalid_numbers(self):
        for n in (0, -1, 4000):
            with self.assertRaises(ValueError):
                to_roman(n)

    def test_invalid_text(self):
        for text in ("", "IIII", "IC", "VX", "MMMM", "ABC", "iv"):
            with self.assertRaises(ValueError, msg=text):
                from_roman(text)
