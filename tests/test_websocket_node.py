# tests/test_websocket_node.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from unittest.mock import patch, MagicMock
from bt_core.context import ExecutionContext
from bt_core.config import NodeConfig
from bt_core.status import NodeStatus


class TestWebSocketNode(unittest.TestCase):
    """验证 WebSocket 客户端节点的连接与收发"""

    def test_send_message_on_tick(self):
        from bt_nodes.network.websocket_node import WebSocketNode
        node = WebSocketNode(config=NodeConfig(name="ws", extra={
            "url": "ws://127.0.0.1:8765",
            "action": "send",
            "message": '{"type":"ping"}',
        }))
        ctx = ExecutionContext()
        mock_ws = MagicMock()
        with patch.object(WebSocketNode, "_get_connection",
                          return_value=mock_ws):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        mock_ws.send.assert_called_once_with('{"type":"ping"}')

    def test_receive_message_writes_to_blackboard(self):
        from bt_nodes.network.websocket_node import WebSocketNode
        node = WebSocketNode(config=NodeConfig(name="ws", extra={
            "url": "ws://127.0.0.1:8765",
            "action": "recv",
            "payload_key": "ws_msg",
        }))
        ctx = ExecutionContext()
        mock_ws = MagicMock()
        mock_ws.recv.return_value = '{"v": 1}'
        with patch.object(WebSocketNode, "_get_connection",
                          return_value=mock_ws):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        self.assertEqual(ctx.blackboard.get("ws_msg"), {"v": 1})

    def test_recv_timeout_returns_failure(self):
        from bt_nodes.network.websocket_node import WebSocketNode
        node = WebSocketNode(config=NodeConfig(name="ws", extra={
            "url": "ws://127.0.0.1:8765",
            "action": "recv",
            "payload_key": "ws_msg",
        }))
        ctx = ExecutionContext()
        mock_ws = MagicMock()
        mock_ws.recv.side_effect = TimeoutError("no message")
        with patch.object(WebSocketNode, "_get_connection",
                          return_value=mock_ws):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)


class TestNodeRegistration(unittest.TestCase):
    """验证新节点已注册"""

    def test_all_new_nodes_importable(self):
        import importlib
        modules = [
            "bt_nodes.network.http_request_node",
            "bt_nodes.network.api_condition_node",
            "bt_nodes.network.websocket_node",
            "bt_nodes.message.publish_node",
            "bt_nodes.message.subscribe_node",
        ]
        for m in modules:
            mod = importlib.import_module(m)
            self.assertTrue(hasattr(mod, "__file__"), f"模块 {m} 未找到")


class TestSettingsManagerBusConfig(unittest.TestCase):
    """验证 settings_manager 新增消息总线配置项"""

    def test_default_config_has_bus_section(self):
        from config.settings_manager import SettingsManager
        sm = SettingsManager()
        cfg = sm.get_default_config()
        self.assertIn("message_bus", cfg)
        self.assertIn("rest_server", cfg)
        self.assertIn("websocket_server", cfg)
        self.assertEqual(cfg["rest_server"]["enabled"], False)
        self.assertEqual(cfg["rest_server"]["port"], 8080)
        self.assertEqual(cfg["websocket_server"]["enabled"], False)
        self.assertEqual(cfg["websocket_server"]["port"], 8765)


if __name__ == "__main__":
    unittest.main()
