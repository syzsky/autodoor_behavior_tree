# tests/test_http_request_node.py
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


class TestHTTPRequestNode(unittest.TestCase):
    """验证 HTTP 请求节点的执行与错误处理"""

    def test_success_returns_success(self):
        from bt_nodes.network.http_request_node import HTTPRequestNode
        node = HTTPRequestNode(config=NodeConfig(name="http", extra={
            "url": "http://example.com/api",
            "method": "GET",
            "timeout_ms": 5000,
        }))
        ctx = ExecutionContext()

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {"code": 0}
        fake_resp.text = '{"code":0}'

        with patch("bt_nodes.network.http_request_node.requests.get",
                   return_value=fake_resp) as mock_get:
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        mock_get.assert_called_once()
        # 响应写入黑板
        self.assertEqual(ctx.blackboard.get("http_response_code"), 200)

    def test_failure_returns_failure(self):
        from bt_nodes.network.http_request_node import HTTPRequestNode
        node = HTTPRequestNode(config=NodeConfig(name="http", extra={
            "url": "http://example.com/api",
            "method": "GET",
            "expected_status": 200,
        }))
        ctx = ExecutionContext()

        fake_resp = MagicMock()
        fake_resp.status_code = 500
        fake_resp.json.return_value = {}
        fake_resp.text = ""

        with patch("bt_nodes.network.http_request_node.requests.get",
                   return_value=fake_resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_post_method_with_body(self):
        from bt_nodes.network.http_request_node import HTTPRequestNode
        node = HTTPRequestNode(config=NodeConfig(name="http", extra={
            "url": "http://example.com/api",
            "method": "POST",
            "body": '{"k":"v"}',
            "headers": {"Content-Type": "application/json"},
        }))
        ctx = ExecutionContext()
        fake_resp = MagicMock()
        fake_resp.status_code = 201
        fake_resp.json.return_value = {}
        fake_resp.text = ""
        with patch("bt_nodes.network.http_request_node.requests.post",
                   return_value=fake_resp) as mock_post:
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        mock_post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
