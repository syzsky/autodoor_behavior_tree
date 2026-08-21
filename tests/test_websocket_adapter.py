# tests/test_websocket_adapter.py
import asyncio
import os
import sys
import time
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

    def test_connect_starts_thread(self):
        """验证 connect() 启动线程"""
        from bt_adapters.websocket_adapter import WebSocketAdapter

        adapter = WebSocketAdapter()
        # 缩短重连间隔，避免测试长时间挂起
        adapter._reconnect_interval_ms = 10
        adapter.start()
        try:
            # 连接到不存在的端口，会快速失败并进入重连循环
            adapter.connect("ws://127.0.0.1:1/test")
            # 给线程启动的时间
            time.sleep(0.2)
            self.assertIsNotNone(adapter._thread)
            self.assertTrue(adapter._thread.is_alive())
        finally:
            adapter.stop()

    def test_connect_twice_raises(self):
        """验证多次 connect() 抛 RuntimeError（C3 修复）"""
        from bt_adapters.websocket_adapter import WebSocketAdapter

        adapter = WebSocketAdapter()
        adapter._reconnect_interval_ms = 10
        adapter.start()
        try:
            adapter.connect("ws://127.0.0.1:1/test")
            time.sleep(0.2)
            with self.assertRaises(RuntimeError):
                adapter.connect("ws://127.0.0.1:1/test")
        finally:
            adapter.stop()

    def test_stop_clears_ws(self):
        """验证 stop() 清理 _ws 引用（C2 修复）"""
        from bt_adapters.websocket_adapter import WebSocketAdapter

        adapter = WebSocketAdapter()
        # 模拟已连接的 ws
        adapter._ws = object()
        adapter.stop()
        self.assertIsNone(adapter._ws)

    def test_send_raises_when_not_connected(self):
        """验证 send() 在 _ws=None 时抛 RuntimeError（C4 修复）"""
        from bt_adapters.websocket_adapter import WebSocketAdapter

        adapter = WebSocketAdapter()
        self.assertIsNone(adapter._ws)
        with self.assertRaises(RuntimeError):
            asyncio.run(adapter.send("hello"))


if __name__ == '__main__':
    unittest.main()
