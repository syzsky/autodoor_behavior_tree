# bt_nodes/network/api_condition_node.py
"""API 条件节点：根据 HTTP 响应内容判断条件是否成立"""
from typing import Any, Dict

import requests

from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from bt_utils.log_manager import LogManager


def _extract_json_path(data: Any, path: str) -> Any:
    """从嵌套字典中按点分路径取值

    Args:
        data: 数据源（字典或列表）
        path: 点分路径，例如 "data.code" 或 "items.0.name"

    Returns:
        路径对应的值；若路径无效则返回 None
    """
    if not path:
        return data
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
            cur = cur[int(part)]
        else:
            return None
    return cur


class APIConditionNode(ActionNode):
    """根据 HTTP 响应内容判断条件是否成立

    配置项：
        url: 请求 URL
        method: 默认 GET
        expected_status: 期望的 HTTP 状态码（0 表示不检查）
        json_path: 响应 JSON 中要取的字段（点分路径，如 data.code）
        expected_value: 期望的字段值（与 json_path 配合使用）
        timeout_ms: 超时毫秒（默认 5000，0 自动转为 5000）
        headers: 请求头字典
        body: POST 请求体
    """

    NODE_TYPE = "APIConditionNode"
    SKIP_WINDOW_SWITCH = True  # 网络节点不需要窗口切换

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.url = self.config.get("url", "")
        self.method = self.config.get("method", "GET").upper()
        self.expected_status = self.config.get_int("expected_status", 0)
        self.json_path = self.config.get("json_path", "")
        self.expected_value = self.config.get("expected_value", None)
        # timeout_ms 是 NodeConfig 已知字段，默认值为 0；需要 or 5000 兜底
        self.timeout_ms = self.config.get_int("timeout_ms", 5000) or 5000
        self.headers: Dict[str, str] = self.config.get("headers", {})

    def _execute_action(self, context) -> NodeStatus:
        if not self.url:
            LogManager.instance().log_failure(
                node_type="API条件节点",
                node_name=self.name,
                reason="缺少 url"
            )
            return NodeStatus.FAILURE

        try:
            kwargs = {
                "headers": self.headers or None,
                "timeout": self.timeout_ms / 1000.0,
            }
            if self.method == "GET":
                resp = requests.get(self.url, **kwargs)
            elif self.method == "POST":
                kwargs["data"] = self.config.get("body", "")
                resp = requests.post(self.url, **kwargs)
            else:
                resp = requests.request(self.method, self.url, **kwargs)
        except requests.RequestException as e:
            LogManager.instance().log_failure(
                node_type="API条件节点",
                node_name=self.name,
                reason=f"请求异常: {e}"
            )
            return NodeStatus.FAILURE

        if self.expected_status and resp.status_code != self.expected_status:
            LogManager.instance().log_failure(
                node_type="API条件节点",
                node_name=self.name,
                reason=f"状态码不匹配: 期望 {self.expected_status} 实际 {resp.status_code}"
            )
            return NodeStatus.FAILURE

        if self.json_path:
            try:
                data = resp.json()
            except ValueError:
                LogManager.instance().log_failure(
                    node_type="API条件节点",
                    node_name=self.name,
                    reason="响应非 JSON 格式"
                )
                return NodeStatus.FAILURE
            actual = _extract_json_path(data, self.json_path)
            if actual != self.expected_value:
                LogManager.instance().log_failure(
                    node_type="API条件节点",
                    node_name=self.name,
                    reason=f"JSON 路径 {self.json_path} 值不匹配: 期望 {self.expected_value!r} 实际 {actual!r}"
                )
                return NodeStatus.FAILURE

        LogManager.instance().log_success(
            node_type="API条件节点",
            node_name=self.name
        )
        return NodeStatus.SUCCESS


    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "APIConditionNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        return cls(node_id=data.get("id"), config=config)
