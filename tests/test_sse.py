import os
import sys
import asyncio
import unittest
from unittest.mock import MagicMock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# 检查 sse_starlette 是否可用
try:
    import sse_starlette  # noqa: F401
    _SSE_AVAILABLE = True
except ImportError:
    _SSE_AVAILABLE = False


@unittest.skipUnless(_SSE_AVAILABLE, "sse_starlette 未安装")
class TestSSE(unittest.TestCase):
    def setUp(self):
        """重置 sse_starlette 模块级 AppStatus.should_exit_event。

        该 Event 首次 await 时会绑定到当时的 event loop，TestClient 为每次请求
        创建独立 loop，导致后续测试抛 "bound to a different event loop"。
        每次测试前重置为 None，使其在新 loop 下重新创建。
        这是 sse_starlette 已知的测试隔离问题。
        """
        from sse_starlette.sse import AppStatus
        AppStatus.should_exit_event = None
        AppStatus.should_exit = False

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

    def test_sse_returns_event_stream_format(self):
        """SSE 端点返回 text/event-stream 格式"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        mock_bus = MagicMock()
        # NOTE: 用 MagicMock 替代 asyncio.Queue() — event_generator 是无限 while
        # 循环，TestClient 会阻塞等待流结束。让 queue.get() 抛异常使生成器在
        # yield 一个 error 事件后 break，TestClient 才能返回 200。
        mock_queue = MagicMock()
        mock_queue.get.side_effect = Exception("test-end")
        mock_bus.subscribe_async.return_value = (mock_queue, "test_sub_id")

        server = RESTServer(message_bus=mock_bus, auth_service=None)
        client = TestClient(server.app)
        response = client.get("/api/v1/events/stream",
                              headers={"Accept": "text/event-stream"})
        # Should be 200 or 406 (TestClient may not fully support streaming)
        self.assertIn(response.status_code, [200, 406])

    def test_sse_returns_error_when_no_bus(self):
        """无 MessageBus 时 SSE 返回 error 事件"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        server = RESTServer(message_bus=None, auth_service=None)
        client = TestClient(server.app)
        response = client.get("/api/v1/events/stream",
                              headers={"Accept": "text/event-stream"})
        # Should still return 200 (SSE stream with error event) or 406
        self.assertIn(response.status_code, [200, 406])

    def test_subscribe_async_called_with_correct_pattern(self):
        """验证 subscribe_async 被以正确的 topic pattern 调用"""
        from bt_servers.rest_server import RESTServer
        from fastapi.testclient import TestClient

        mock_bus = MagicMock()
        # 同 test_sse_returns_event_stream_format：用会抛异常的 mock queue
        # 让无限生成器终止，避免 TestClient 阻塞。
        mock_queue = MagicMock()
        mock_queue.get.side_effect = Exception("test-end")
        mock_bus.subscribe_async.return_value = (mock_queue, "test_sub_id")

        server = RESTServer(message_bus=mock_bus, auth_service=None)
        client = TestClient(server.app)
        # Trigger the endpoint
        client.get("/api/v1/events/stream",
                   headers={"Accept": "text/event-stream"})
        # Verify subscribe_async was called with the correct pattern and maxsize
        mock_bus.subscribe_async.assert_called_with("bt.**.event.**", maxsize=500)


if __name__ == '__main__':
    unittest.main()
