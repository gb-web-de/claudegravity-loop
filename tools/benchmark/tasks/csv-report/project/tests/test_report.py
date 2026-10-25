import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import datetime  # noqa: E402
from decimal import Decimal  # noqa: E402

from parse import read_sales  # noqa: E402
from report import format_report, totals_by_region  # noqa: E402

CSV = "datum;region;betrag\n2026-01-03;Nord;10,50\n\n2026-01-04;Süd;7,25\n2026-01-05;Nord;1,00\n"


class ReportTest(unittest.TestCase):
    def test_read_sales(self):
        rows = read_sales(CSV)
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0], {"datum": datetime.date(2026, 1, 3), "region": "Nord", "betrag": Decimal("10.50")})

    def test_bad_line_reports_number(self):
        with self.assertRaises(ValueError) as ctx:
            read_sales("datum;region;betrag\n2026-01-03;Nord;10,50\n2026-13-01;Süd;1,00\n")
        self.assertIn("3", str(ctx.exception))

    def test_totals(self):
        self.assertEqual(totals_by_region(read_sales(CSV)), {"Nord": Decimal("11.50"), "Süd": Decimal("7.25")})

    def test_format_sorted_descending(self):
        lines = format_report(read_sales(CSV)).splitlines()
        nord = next(i for i, line in enumerate(lines) if "Nord" in line)
        sued = next(i for i, line in enumerate(lines) if "Süd" in line)
        self.assertLess(nord, sued)
        self.assertIn("11,50", lines[nord])
