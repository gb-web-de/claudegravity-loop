import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from decimal import Decimal  # noqa: E402

from inventory import Inventory  # noqa: E402
from pricing import apply_discount  # noqa: E402


class InventoryTest(unittest.TestCase):
    def make(self):
        inv = Inventory()
        inv.add("Ball", 3, Decimal("19.99"))
        inv.add("Netz", 1, Decimal("5.00"))
        return inv

    def test_total_value(self):
        self.assertEqual(self.make().total_value(), Decimal("64.97"))

    def test_remove_never_negative(self):
        inv = self.make()
        with self.assertRaises(ValueError):
            inv.remove("Ball", 4)
        self.assertEqual(inv.stock["Ball"], 3)
        inv.remove("Ball", 3)
        self.assertEqual(inv.stock["Ball"], 0)
        with self.assertRaises(ValueError):
            inv.remove("Schläger", 1)

    def test_discount(self):
        self.assertEqual(apply_discount(Decimal("100"), 15), Decimal("85.00"))
        self.assertEqual(apply_discount(Decimal("0.05"), 50), Decimal("0.03"))
        self.assertEqual(self.make().total_value(10), Decimal("58.47"))
