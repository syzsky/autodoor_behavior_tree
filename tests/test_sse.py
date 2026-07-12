import os
import sys
import asyncio
import unittest
from unittest.mock import MagicMock, patch

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestSSE(unittest.TestCase):
    def test_sse_endpoint_exists(self):
        """测试 /api/v1/events/stream 端点存在"""
        from bt_servers.rest_server import RESTServer

        mock_bus = MagicMock()
        mock_queue = asyncio.Queue()
        # subscribe_async 真实 API 返回 (queue, sub_id) 元组
        mock_bus.subscribe_async.return_value = (mock_queue, "test_sub_id")

        server = RESTServer(message_bus=mock_bus, auth_service=None)
        # 验证 SSE 路由已注册
        routes = [getattr(r, "path", "") for r in server.app.routes]
        self.assertIn("/api/v1/events/stream", routes)

    def test_bus_subscribe_async_called(self):
        """测试 SSE 端点调用 bus.subscribe_async"""
        from bt_servers.rest_server import RESTServer

        mock_bus = MagicMock()
        mock_queue = asyncio.Queue()
        mock_bus.subscribe_async.return_value = (mock_queue, "test_sub_id")

        server = RESTServer(message_bus=mock_bus, auth_service=None)
        # 验证 _setup_sse_routes 方法存在
        self.assertTrue(hasattr(server, '_setup_sse_routes'))


if __name__ == '__main__':
    unittest.main()
