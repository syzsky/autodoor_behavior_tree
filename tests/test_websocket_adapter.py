# tests/test_websocket_adapter.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestWebSocketAdapter(unittest.TestCase):
    def test_is_available(self):
        from bt_adapters.websocket_adapter import WebSocketAdapter
        # 依赖未安装时返回 False，安装后 True
        self.assertIsInstance(WebSocketAdapter.is_available(), bool)

    def test_adapter_level_remote(self):
        from bt_adapters.websocket_adapter import WebSocketAdapter
        from bt_adapters.base import AdapterLevel
        self.assertEqual(WebSocketAdapter.get_adapter_level(),
                         AdapterLevel.REMOTE)

    def test_status_not_running_initially(self):
        from bt_adapters.websocket_adapter import WebSocketAdapter
        adapter = WebSocketAdapter()
        status = adapter.get_status()
        self.assertFalse(status.running)

    def test_get_name(self):
        from bt_adapters.websocket_adapter import WebSocketAdapter
        adapter = WebSocketAdapter()
        self.assertEqual(adapter.get_name(), "websocket")


if __name__ == '__main__':
    unittest.main()
