# bt_nodes/message/subscribe_node.py
"""消息订阅节点：等待消息总线上的消息并写入黑板"""
import time
from typing import Any, Dict, Optional

from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from bt_utils.log_manager import LogManager


class MessageSubscribeNode(ActionNode):
    """等待并接收消息总线上的消息

    配置项：
        topic: 订阅主题（支持通配符，如 bt.test.**）
        payload_key: 将消息 data 写入黑板的键名
        timeout_ms: 等待超时毫秒（仅在 blocking 模式下生效）
        wait_mode: blocking / nonblocking（默认 nonblocking）
            - nonblocking: 每次 tick 独立检查，收到消息即 SUCCESS，否则 FAILURE
            - blocking: 在 timeout_ms 内持续等待，超时返回 FAILURE
    """

    NODE_TYPE = "MessageSubscribeNode"
    SKIP_WINDOW_SWITCH = True

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.topic = self.config.get("topic", "")
        self.payload_key = self.config.get("payload_key", "last_message")
        self.timeout_ms = self.config.get_int("timeout_ms", 0)
        self.wait_mode = self.config.get("wait_mode", "nonblocking")
        self._bus = None
        self._last_message = None
        self._subscription_id = None
        self._start_wait_time: Optional[float] = None

    def set_bus(self, bus) -> None:
        """注入消息总线实例"""
        self._bus = bus

    def on_start(self, context) -> None:
        """节点开始执行时订阅主题"""
        self._last_message = None
        self._start_wait_time = time.perf_counter()
        bus = context.get_message_bus() or self._bus
        if bus and self._bus is None:
            self._bus = bus  # 缓存 bus 引用，供 reset() 使用
        if bus and self.topic and self._subscription_id is None:
            self._subscription_id = bus.subscribe(self.topic, self._on_message)

    def _on_message(self, message) -> None:
        self._last_message = message

    def _execute_action(self, context) -> NodeStatus:
        bus = context.get_message_bus() or self._bus
        if bus and self._bus is None:
            self._bus = bus  # 缓存 bus 引用，供 reset() 使用
        if not bus or not self.topic:
            LogManager.instance().log_failure(
                node_type="消息订阅节点",
                node_name=self.name,
                reason="未绑定消息总线或缺少 topic"
            )
            return NodeStatus.FAILURE

        # 懒订阅：首次 tick 时订阅（如未通过 on_start 订阅）
        if self._subscription_id is None:
            self._start_wait_time = time.perf_counter()
            self._subscription_id = bus.subscribe(self.topic, self._on_message)

        # 收到消息 → 写入黑板并返回 SUCCESS
        if self._last_message is not None:
            context.blackboard.set(self.payload_key, self._last_message.data)
            self._unsubscribe(bus)
            LogManager.instance().log_success(
                node_type="消息订阅节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS

        # 未收到消息
        if self.wait_mode == "blocking":
            # 阻塞模式：在 timeout_ms 内持续等待
            if self.timeout_ms > 0 and self._start_wait_time is not None:
                elapsed = (time.perf_counter() - self._start_wait_time) * 1000
                if elapsed >= self.timeout_ms:
                    self._unsubscribe(bus)
                    LogManager.instance().log_failure(
                        node_type="消息订阅节点",
                        node_name=self.name,
                        reason=f"等待超时 ({self.timeout_ms}ms)"
                    )
                    return NodeStatus.FAILURE
                return NodeStatus.RUNNING
            # 无超时配置或已超时
            self._unsubscribe(bus)
            LogManager.instance().log_failure(
                node_type="消息订阅节点",
                node_name=self.name,
                reason="阻塞模式下未收到消息且无有效超时"
            )
            return NodeStatus.FAILURE

        # 非阻塞模式（默认）：未收到消息立即返回 FAILURE
        self._unsubscribe(bus)
        LogManager.instance().log_failure(
            node_type="消息订阅节点",
            node_name=self.name,
            reason="非阻塞模式下未收到消息"
        )
        return NodeStatus.FAILURE

    def _unsubscribe(self, bus) -> None:
        if self._subscription_id:
            bus.unsubscribe(self._subscription_id)
            self._subscription_id = None

    def reset(self, reset_counters: bool = True) -> None:
        super().reset(reset_counters)
        if self._subscription_id and self._bus:
            self._bus.unsubscribe(self._subscription_id)
            self._subscription_id = None
        self._last_message = None
        self._start_wait_time = None

    def abort(self, context) -> None:
        bus = context.get_message_bus() or self._bus
        if bus:
            self._unsubscribe(bus)
        super().abort(context)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageSubscribeNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        return cls(node_id=data.get("id"), config=config)
