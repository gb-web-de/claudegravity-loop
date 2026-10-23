import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from slug import slugify  # noqa: E402


class SlugTest(unittest.TestCase):
    def test_umlauts_and_spaces(self):
        self.assertEqual(slugify("Größe & Übermaß"), "groesse-uebermass")

    def test_trim_and_collapse(self):
        self.assertEqual(slugify("  --Hallo,   Welt!--  "), "hallo-welt")

    def test_digits(self):
        self.assertEqual(slugify("Version 2.0"), "version-2-0")
