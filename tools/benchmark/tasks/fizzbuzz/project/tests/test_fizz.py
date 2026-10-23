import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fizz import fizzbuzz  # noqa: E402


class FizzTest(unittest.TestCase):
    def test_first_fifteen(self):
        self.assertEqual(fizzbuzz(15)[-1], "FizzBuzz")
        self.assertEqual(fizzbuzz(5), [1, 2, "Fizz", 4, "Buzz"])

    def test_empty(self):
        self.assertEqual(fizzbuzz(0), [])
