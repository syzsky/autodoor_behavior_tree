# tests/test_tree_service.py
import os
import sys
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestTreeService(unittest.TestCase):
    def setUp(self):
        from bt_services.tree_service import TreeService
        self.engine = MagicMock()
        self.context = MagicMock()
        self.tab_manager = MagicMock()
        self.context.get_tab_manager.return_value = self.tab_manager
        self.engine.get_status.return_value = {
            "running": False, "paused": False, "elapsed_time": 0.0, "tick_count": 0
        }
        self.service = TreeService(self.engine, self.context)

    def test_get_name(self):
        self.assertEqual(self.service.get_name(), "tree")

    def test_start_default_tree(self):
        result = self.service.start()
        self.engine.start.assert_called_once()
        self.assertEqual(result["status"], "started")

    def test_start_specific_tree(self):
        result = self.service.start(tree_id="tab2")
        self.tab_manager.start_tab.assert_called_once_with("tab2")
        self.assertEqual(result["tree_id"], "tab2")

    def test_stop_default(self):
        result = self.service.stop()
        self.engine.stop.assert_called_once()
        self.assertEqual(result["status"], "stopped")

    def test_stop_specific_tree(self):
        result = self.service.stop(tree_id="tab2")
        self.tab_manager.stop_tab.assert_called_once_with("tab2")

    def test_pause(self):
        result = self.service.pause()
        self.engine.pause.assert_called_once()
        self.assertEqual(result["status"], "paused")

    def test_resume(self):
        result = self.service.resume()
        self.engine.resume.assert_called_once()
        self.assertEqual(result["status"], "resumed")

    def test_get_status(self):
        self.engine.get_status.return_value = {
            "running": True, "paused": False, "elapsed_time": 0.0, "tick_count": 0
        }
        status = self.service.get_status()
        self.assertTrue(status["running"])
        self.assertFalse(status["paused"])


if __name__ == '__main__':
    unittest.main()
