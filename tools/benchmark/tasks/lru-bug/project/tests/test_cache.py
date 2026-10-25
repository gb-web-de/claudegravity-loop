import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cache import LRUCache  # noqa: E402


class LRUCacheTest(unittest.TestCase):
    def test_evicts_least_recently_used(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        self.assertEqual(c.get("a"), 1)
        c.put("c", 3)
        self.assertIsNone(c.get("b"))
        self.assertEqual((c.get("a"), c.get("c")), (1, 3))

    def test_update_existing_key_does_not_evict(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("a", 10)
        self.assertEqual(len(c), 2)
        self.assertEqual((c.get("a"), c.get("b")), (10, 2))

    def test_update_marks_as_recent(self):
        c = LRUCache(2)
        c.put("a", 1)
        c.put("b", 2)
        c.put("a", 3)
        c.put("c", 4)
        self.assertIsNone(c.get("b"))
        self.assertEqual(c.get("a"), 3)

    def test_default_and_capacity(self):
        self.assertEqual(LRUCache(1).get("x", "leer"), "leer")
        with self.assertRaises(ValueError):
            LRUCache(0)
