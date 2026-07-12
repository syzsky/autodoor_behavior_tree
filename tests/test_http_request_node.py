# tests/test_http_request_node.py
import os
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from unittest.mock import patch, MagicMock
import requests

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
        mock_get.assert_called_once_with(
            "http://example.com/api", headers=None, timeout=5.0
        )
        # 响应写入黑板
        self.assertEqual(ctx.blackboard.get("http_response_code"), 200)
        # 验证黑板 http_response 字典的完整结构
        http_response = ctx.blackboard.get("http_response")
        self.assertIsInstance(http_response, dict)
        self.assertEqual(http_response["status_code"], 200)
        self.assertEqual(http_response["text"], '{"code":0}')
        self.assertEqual(http_response["json"], {"code": 0})

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
        mock_post.assert_called_once_with(
            "http://example.com/api",
            headers={"Content-Type": "application/json"},
            timeout=5.0,
            data='{"k":"v"}',
        )
        # 验证黑板 http_response 字典的完整结构
        http_response = ctx.blackboard.get("http_response")
        self.assertIsInstance(http_response, dict)
        self.assertEqual(http_response["status_code"], 201)

    def test_empty_url_returns_failure(self):
        """空 url 返回 FAILURE"""
        from bt_nodes.network.http_request_node import HTTPRequestNode
        node = HTTPRequestNode(config=NodeConfig(name="http", extra={
            "url": "",
            "method": "GET",
        }))
        ctx = ExecutionContext()
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_unsupported_method_returns_failure(self):
        """不支持的方法（如 PATCH）返回 FAILURE"""
        from bt_nodes.network.http_request_node import HTTPRequestNode
        node = HTTPRequestNode(config=NodeConfig(name="http", extra={
            "url": "http://example.com/api",
            "method": "PATCH",
        }))
        ctx = ExecutionContext()
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_non_json_response(self):
        """非 JSON 响应时 _safe_json 返回 None"""
        from bt_nodes.network.http_request_node import HTTPRequestNode
        node = HTTPRequestNode(config=NodeConfig(name="http", extra={
            "url": "http://example.com/api",
            "method": "GET",
        }))
        ctx = ExecutionContext()

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.text = "not a json"
        fake_resp.json.side_effect = ValueError("Invalid JSON")

        with patch("bt_nodes.network.http_request_node.requests.get",
                   return_value=fake_resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        # _safe_json 应返回 None
        http_response = ctx.blackboard.get("http_response")
        self.assertIsNone(http_response["json"])

    def test_request_exception_returns_failure(self):
        """请求异常返回 FAILURE"""
        from bt_nodes.network.http_request_node import HTTPRequestNode
        node = HTTPRequestNode(config=NodeConfig(name="http", extra={
            "url": "http://example.com/api",
            "method": "GET",
        }))
        ctx = ExecutionContext()

        with patch("bt_nodes.network.http_request_node.requests.get",
                   side_effect=requests.ConnectionError("connection refused")):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)
        # 异常信息写入黑板
        http_response = ctx.blackboard.get("http_response")
        self.assertIsInstance(http_response, dict)
        self.assertIn("error", http_response)

    def test_expected_status_match_returns_success(self):
        """expected_status 匹配时返回 SUCCESS"""
        from bt_nodes.network.http_request_node import HTTPRequestNode
        node = HTTPRequestNode(config=NodeConfig(name="http", extra={
            "url": "http://example.com/api",
            "method": "GET",
            "expected_status": 200,
        }))
        ctx = ExecutionContext()

        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {}
        fake_resp.text = ""

        with patch("bt_nodes.network.http_request_node.requests.get",
                   return_value=fake_resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)


if __name__ == "__main__":
    unittest.main()
