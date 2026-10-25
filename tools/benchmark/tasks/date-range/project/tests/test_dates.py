import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import datetime  # noqa: E402

from dates import days_between, is_leap  # noqa: E402

D = datetime.date


class DatesTest(unittest.TestCase):
    def test_same_day_counts_one(self):
        self.assertEqual(days_between(D(2026, 5, 1), D(2026, 5, 1)), 1)

    def test_inclusive_range(self):
        self.assertEqual(days_between(D(2026, 1, 1), D(2026, 1, 31)), 31)

    def test_leap_years(self):
        self.assertTrue(is_leap(2000))
        self.assertFalse(is_leap(1900))
        self.assertTrue(is_leap(2024))
        self.assertEqual(days_between(D(1900, 2, 1), D(1900, 3, 1)), 29)
        self.assertEqual(days_between(D(2000, 2, 1), D(2000, 3, 1)), 30)

    def test_year_change(self):
        self.assertEqual(days_between(D(2025, 12, 30), D(2026, 1, 2)), 4)

    def test_reversed_raises(self):
        with self.assertRaises(ValueError):
            days_between(D(2026, 1, 2), D(2026, 1, 1))
