import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import copy  # noqa: E402

from merge import deep_merge  # noqa: E402


class MergeTest(unittest.TestCase):
    def test_nested(self):
        base = {"a": 1, "b": {"x": 1, "y": {"z": 1}}}
        self.assertEqual(deep_merge(base, {"b": {"y": {"z": 2, "w": 3}}}), {"a": 1, "b": {"x": 1, "y": {"z": 2, "w": 3}}})

    def test_lists_replace(self):
        self.assertEqual(deep_merge({"l": [1, 2]}, {"l": [3]}), {"l": [3]})

    def test_none_deletes(self):
        self.assertEqual(deep_merge({"a": 1, "b": {"c": 2, "d": 3}}, {"b": {"c": None}, "a": None}), {"b": {"d": 3}})

    def test_type_change(self):
        self.assertEqual(deep_merge({"a": {"b": 1}}, {"a": 5}), {"a": 5})
        self.assertEqual(deep_merge({"a": 5}, {"a": {"b": 1}}), {"a": {"b": 1}})

    def test_inputs_unchanged(self):
        base, override = {"a": {"b": [1]}}, {"a": {"c": 2}}
        saved = copy.deepcopy((base, override))
        result = deep_merge(base, override)
        result["a"]["b"].append(9)
        self.assertEqual((base, override), saved)
