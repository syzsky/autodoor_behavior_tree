# bt_nodes/network/websocket_node.py
"""WebSocket 客户端节点：发送或接收 WebSocket 消息"""
import asyncio
import json as _json
import threading
from typing import Any, Dict

import websockets

from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from bt_utils.log_manager import LogManager


class WebSocketNode(ActionNode):
    """WebSocket 客户端节点

    配置项：
        url: ws:// 或 wss:// 地址
        action: send / recv
        message: send 模式下要发送的字符串
        payload_key: recv 模式下接收数据写入黑板的键名
        timeout_ms: recv 模式下的等待超时（默认 1000ms）
    """

    NODE_TYPE = "WebSocketNode"
    SKIP_WINDOW_SWITCH = True

    _connections: dict = {}
    _lock = threading.Lock()

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.url = self.config.get("url", "")
        self.action = self.config.get("action", "send")
        self.message = self.config.get("message", "")
        self.payload_key = self.config.get("payload_key", "ws_message")
        self.timeout_ms = self.config.get_int("timeout_ms", 1000) or 1000

    def _get_connection(self):
        """获取或创建到 URL 的 WebSocket 连接（同步封装）"""
        with WebSocketNode._lock:
            if self.url in WebSocketNode._connections:
                return WebSocketNode._connections[self.url]

        async def _connect():
            return await websockets.connect(self.url)

        try:
            ws = self._run_coro(_connect())
        except (OSError, ConnectionError) as e:
            LogManager.instance().log_failure(
                node_type="WebSocket节点",
                node_name=self.name,
                reason=f"连接失败: {e}"
            )
            return None

        with WebSocketNode._lock:
            WebSocketNode._connections[self.url] = ws
        return ws

    def _execute_action(self, context) -> NodeStatus:
        if not self.url:
            LogManager.instance().log_failure(
                node_type="WebSocket节点",
                node_name=self.name,
                reason="缺少 url"
            )
            return NodeStatus.FAILURE

        ws = self._get_connection()
        if ws is None:
            return NodeStatus.FAILURE

        try:
            if self.action == "send":
                self._send(ws, self.message)
                LogManager.instance().log_success(
                    node_type="WebSocket节点",
                    node_name=self.name
                )
                return NodeStatus.SUCCESS
            elif self.action == "recv":
                data = self._recv(ws, self.timeout_ms)
                if data is None:
                    LogManager.instance().log_failure(
                        node_type="WebSocket节点",
                        node_name=self.name,
                        reason="接收超时或无数据"
                    )
                    return NodeStatus.FAILURE
                try:
                    parsed = _json.loads(data)
                except (ValueError, TypeError):
                    parsed = data
                context.blackboard.set(self.payload_key, parsed)
                LogManager.instance().log_success(
                    node_type="WebSocket节点",
                    node_name=self.name
                )
                return NodeStatus.SUCCESS
            else:
                LogManager.instance().log_failure(
                    node_type="WebSocket节点",
                    node_name=self.name,
                    reason=f"不支持的操作: {self.action}"
                )
                return NodeStatus.FAILURE
        except (OSError, ConnectionError) as e:
            LogManager.instance().log_failure(
                node_type="WebSocket节点",
                node_name=self.name,
                reason=f"通信异常: {e}"
            )
            # 清理失效连接
            with WebSocketNode._lock:
                WebSocketNode._connections.pop(self.url, None)
            return NodeStatus.FAILURE

    @staticmethod
    def _send(ws, message: str) -> None:
        result = ws.send(message)
        if asyncio.iscoroutine(result):
            WebSocketNode._run_coro(result)

    @staticmethod
    def _recv(ws, timeout_ms: int):
        try:
            result = ws.recv()
        except TimeoutError:
            return None

        if not asyncio.iscoroutine(result):
            return result

        try:
            return WebSocketNode._run_coro(
                asyncio.wait_for(result, timeout=timeout_ms / 1000)
            )
        except TimeoutError:
            return None

    @staticmethod
    def _run_coro(coro):
        """在当前线程同步运行协程（有运行中的循环时借用，否则新建）"""
        try:
            loop = asyncio.get_running_loop()
            return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=5)
        except RuntimeError:
            return asyncio.run(coro)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WebSocketNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        return cls(node_id=data.get("id"), config=config)
