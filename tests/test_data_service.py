# tests/test_data_service.py
import os
import sys
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestDataService(unittest.TestCase):
    def setUp(self):
        from bt_services.data_service import DataService
        from bt_core.blackboard import Blackboard
        self.blackboard = Blackboard()
        self.context = MagicMock()
        self.context.blackboard = self.blackboard
        self.service = DataService(self.context)

    def test_get_set(self):
        self.service.set("key1", "value1")
        self.assertEqual(self.service.get("key1"), "value1")

    def test_get_default(self):
        self.assertEqual(self.service.get("missing", "default"), "default")

    def test_delete(self):
        self.service.set("key2", "val")
        self.service.delete("key2")
        self.assertIsNone(self.service.get("key2"))

    def test_list_keys(self):
        self.service.set("k1", 1)
        self.service.set("k2", 2)
        keys = self.service.list_keys()
        self.assertIn("k1", keys)
        self.assertIn("k2", keys)


if __name__ == '__main__':
    unittest.main()
