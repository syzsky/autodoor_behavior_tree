# bt_nodes/network/http_request_node.py
"""HTTP 请求节点：发起 HTTP 调用并将结果写入黑板"""
import logging
from typing import Dict

import requests

from bt_core.nodes import Node
from bt_core.status import NodeStatus
from bt_core.config import NodeConfig

logger = logging.getLogger(__name__)


class HTTPRequestNode(Node):
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

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.url = self.config.get("url", "")
        self.method = self.config.get("method", "GET").upper()
        self.body = self.config.get("body", "")
        self.headers: Dict[str, str] = self.config.get("headers", {}) or {}
        self.timeout_ms = self.config.get_int("timeout_ms", 5000)
        self.expected_status = self.config.get_int("expected_status", 0)
        self.response_key = self.config.get("response_key", "http_response")

    def tick(self, context) -> NodeStatus:
        if not self.url:
            logger.error("HTTPRequestNode %s 缺少 url", self.name)
            return NodeStatus.FAILURE
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
                logger.error("不支持的方法: %s", self.method)
                return NodeStatus.FAILURE
        except Exception as e:
            logger.exception("HTTP 请求异常: %s", e)
            context.blackboard.set(self.response_key, {"error": str(e)})
            return NodeStatus.FAILURE

        context.blackboard.set(self.response_key, {
            "status_code": resp.status_code,
            "text": resp.text,
            "json": self._safe_json(resp),
        })
        context.blackboard.set("http_response_code", resp.status_code)

        if self.expected_status and resp.status_code != self.expected_status:
            logger.warning("HTTP %s 期望 %d 实际 %d",
                           self.url, self.expected_status, resp.status_code)
            return NodeStatus.FAILURE
        return NodeStatus.SUCCESS

    @staticmethod
    def _safe_json(resp):
        try:
            return resp.json()
        except ValueError:
            return None
