# bt_nodes/network/http_request_node.py
"""HTTP 请求节点：发起 HTTP 调用并将结果写入黑板"""
from typing import Dict, Any

import requests

from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from bt_utils.log_manager import LogManager


class HTTPRequestNode(ActionNode):
    """发起 HTTP 请求，将响应写入黑板

    配置项：
        url: 请求 URL
        method: GET / POST / PUT / DELETE（默认 GET）
        body: 请求体（POST/PUT 时使用）
        headers: 请求头字典
        timeout_ms: 超时毫秒（默认 5000）
        expected_status: 期望的 HTTP 状态码（不匹配则 FAILURE）
        response_key: 黑板键名（默认 http_response）
    """

    NODE_TYPE = "HTTPRequestNode"
    SKIP_WINDOW_SWITCH = True  # 网络节点不需要窗口切换

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.url = self.config.get("url", "")
        self.method = self.config.get("method", "GET").upper()
        self.body = self.config.get("body", "")
        self.headers: Dict[str, str] = self.config.get("headers", {})
        self.timeout_ms = self.config.get_int("timeout_ms", 5000) or 5000
        self.expected_status = self.config.get_int("expected_status", 0)
        self.response_key = self.config.get("response_key", "http_response")

    def _execute_action(self, context) -> NodeStatus:
        if not self.url:
            LogManager.instance().log_failure(
                node_type="HTTP请求节点",
                node_name=self.name,
                reason="缺少 url"
            )
            return NodeStatus.FAILURE

        adapter_mgr = context.get_adapter_manager()
        if adapter_mgr:
            return self._execute_with_adapter(context, adapter_mgr)
        else:
            return self._execute_with_direct_requests(context)

    def _execute_with_adapter(self, context, adapter_mgr) -> NodeStatus:
        try:
            adapter = adapter_mgr.get_adapter("http")
            body = self.body
            if body and isinstance(body, str):
                try:
                    import json
                    body = json.loads(body)
                except ValueError:
                    pass

            resp = adapter.call(
                method=self.method,
                url=self.url,
                headers=self.headers or None,
                body=body,
                timeout_ms=self.timeout_ms
            )

            context.blackboard.set(self.response_key, {
                "status_code": resp.status_code,
                "text": resp.text,
                "json": resp.json,
            })
            context.blackboard.set("http_response_code", resp.status_code)

            if self.expected_status and resp.status_code != self.expected_status:
                LogManager.instance().log_failure(
                    node_type="HTTP请求节点",
                    node_name=self.name,
                    reason=f"HTTP {self.url} 期望 {self.expected_status} 实际 {resp.status_code}"
                )
                return NodeStatus.FAILURE

            LogManager.instance().log_success(
                node_type="HTTP请求节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS
        except requests.RequestException as e:
            LogManager.instance().log_failure(
                node_type="HTTP请求节点",
                node_name=self.name,
                reason=f"HTTP 请求异常: {e}"
            )
            context.blackboard.set(self.response_key, {"error": str(e)})
            return NodeStatus.FAILURE

    def _execute_with_direct_requests(self, context) -> NodeStatus:
        try:
            kwargs = {
                "headers": self.headers or None,
                "timeout": self.timeout_ms / 1000.0,
            }
            if self.method == "GET":
                resp = requests.get(self.url, **kwargs)
            elif self.method == "POST":
                kwargs["data"] = self.body or None
                resp = requests.post(self.url, **kwargs)
            elif self.method == "PUT":
                kwargs["data"] = self.body or None
                resp = requests.put(self.url, **kwargs)
            elif self.method == "DELETE":
                resp = requests.delete(self.url, **kwargs)
            else:
                LogManager.instance().log_failure(
                    node_type="HTTP请求节点",
                    node_name=self.name,
                    reason=f"不支持的方法: {self.method}"
                )
                return NodeStatus.FAILURE
        except requests.RequestException as e:
            LogManager.instance().log_failure(
                node_type="HTTP请求节点",
                node_name=self.name,
                reason=f"HTTP 请求异常: {e}"
            )
            context.blackboard.set(self.response_key, {"error": str(e)})
            return NodeStatus.FAILURE

        context.blackboard.set(self.response_key, {
            "status_code": resp.status_code,
            "text": resp.text,
            "json": self._safe_json(resp),
        })
        context.blackboard.set("http_response_code", resp.status_code)

        if self.expected_status and resp.status_code != self.expected_status:
            LogManager.instance().log_failure(
                node_type="HTTP请求节点",
                node_name=self.name,
                reason=f"HTTP {self.url} 期望 {self.expected_status} 实际 {resp.status_code}"
            )
            return NodeStatus.FAILURE

        LogManager.instance().log_success(
            node_type="HTTP请求节点",
            node_name=self.name
        )
        return NodeStatus.SUCCESS

    @staticmethod
    def _safe_json(resp):
        try:
            return resp.json()
        except ValueError:
            return None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HTTPRequestNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        return node
