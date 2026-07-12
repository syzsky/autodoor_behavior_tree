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


if __name__ == "__main__":
    unittest.main()
