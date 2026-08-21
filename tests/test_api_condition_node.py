# tests/test_api_condition_node.py
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


class TestAPIConditionNode(unittest.TestCase):
    """验证 API 条件节点根据 HTTP 响应返回 SUCCESS/FAILURE"""

    def _make_resp(self, status_code=200, json_data=None, text=""):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data or {}
        resp.text = text
        return resp

    def test_json_path_match_returns_success(self):
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/health",
            "json_path": "status",
            "expected_value": "ok",
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(200, {"status": "ok"})
        with patch("bt_nodes.network.api_condition_node.requests.get",
                   return_value=resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)

    def test_json_path_mismatch_returns_failure(self):
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/health",
            "json_path": "status",
            "expected_value": "ok",
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(200, {"status": "error"})
        with patch("bt_nodes.network.api_condition_node.requests.get",
                   return_value=resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_status_code_condition(self):
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/health",
            "expected_status": 204,
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(204, {})
        with patch("bt_nodes.network.api_condition_node.requests.get",
                   return_value=resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)

    def test_nested_json_path(self):
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/api",
            "json_path": "data.code",
            "expected_value": 0,
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(200, {"data": {"code": 0}})
        with patch("bt_nodes.network.api_condition_node.requests.get",
                   return_value=resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)

    def test_empty_url_returns_failure(self):
        """空 url 返回 FAILURE"""
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "",
        }))
        ctx = ExecutionContext()
        status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_request_exception_returns_failure(self):
        """requests.ConnectionError 异常返回 FAILURE"""
        import requests
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/api",
        }))
        ctx = ExecutionContext()
        with patch("bt_nodes.network.api_condition_node.requests.get",
                   side_effect=requests.ConnectionError("connection refused")):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_non_json_response_returns_failure(self):
        """非 JSON 响应（json_path 设置时）返回 FAILURE"""
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/api",
            "json_path": "status",
            "expected_value": "ok",
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(200)
        resp.json.side_effect = ValueError("Invalid JSON")
        with patch("bt_nodes.network.api_condition_node.requests.get",
                   return_value=resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_expected_status_mismatch_returns_failure(self):
        """expected_status 不匹配返回 FAILURE"""
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/api",
            "expected_status": 200,
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(500, {})
        with patch("bt_nodes.network.api_condition_node.requests.get",
                   return_value=resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_json_path_not_found_returns_failure(self):
        """json_path 指向不存在的字段时返回 FAILURE（actual=None != expected_value）"""
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/api",
            "json_path": "missing_field",
            "expected_value": "ok",
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(200, {"status": "ok"})
        with patch("bt_nodes.network.api_condition_node.requests.get",
                   return_value=resp):
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.FAILURE)

    def test_post_method_with_body(self):
        """POST 方法带 body 的请求构造验证"""
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/api",
            "method": "POST",
            "body": '{"k":"v"}',
            "headers": {"Content-Type": "application/json"},
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(200, {})
        with patch("bt_nodes.network.api_condition_node.requests.post",
                   return_value=resp) as mock_post:
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        mock_post.assert_called_once_with(
            "http://example.com/api",
            headers={"Content-Type": "application/json"},
            timeout=5.0,
            data='{"k":"v"}',
        )

    def test_put_method_with_body(self):
        """PUT 方法带 body 的请求构造验证"""
        from bt_nodes.network.api_condition_node import APIConditionNode
        node = APIConditionNode(config=NodeConfig(name="cond", extra={
            "url": "http://example.com/api",
            "method": "PUT",
            "body": '{"k":"v"}',
            "headers": {"Content-Type": "application/json"},
        }))
        ctx = ExecutionContext()
        resp = self._make_resp(200, {})
        with patch("bt_nodes.network.api_condition_node.requests.request",
                   return_value=resp) as mock_request:
            status = node.tick(ctx)
        self.assertEqual(status, NodeStatus.SUCCESS)
        mock_request.assert_called_once_with(
            "PUT",
            "http://example.com/api",
            headers={"Content-Type": "application/json"},
            timeout=5.0,
            data='{"k":"v"}',
        )


if __name__ == "__main__":
    unittest.main()
