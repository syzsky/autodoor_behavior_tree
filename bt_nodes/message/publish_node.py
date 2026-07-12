# bt_nodes/message/publish_node.py
"""消息发布节点：向消息总线发布消息"""
from typing import Any, Dict

from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from bt_utils.log_manager import LogManager


class MessagePublishNode(ActionNode):
    """向消息总线发布消息

    配置项：
        topic: 主题（可相对，配合 prefix_tree_id 自动加上 bt.{tree_id}. 前缀）
        payload: 静态负载字典
        payload_key: 黑板键名（若指定则用黑板值覆盖 payload）
        prefix_tree_id: 是否自动加上 bt.{tree_id}. 前缀（默认 True）
    """

    NODE_TYPE = "MessagePublishNode"
    SKIP_WINDOW_SWITCH = True

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.topic = self.config.get("topic", "")
        self.payload = self.config.get("payload", {})
        self.payload_key = self.config.get("payload_key", "")
        self.prefix_tree_id = self.config.get_bool("prefix_tree_id", True)
        self._bus = None

    def set_bus(self, bus) -> None:
        """注入消息总线实例"""
        self._bus = bus

    def _execute_action(self, context) -> NodeStatus:
        if not self._bus:
            LogManager.instance().log_failure(
                node_type="消息发布节点",
                node_name=self.name,
                reason="未绑定消息总线"
            )
            return NodeStatus.FAILURE
        if not self.topic:
            LogManager.instance().log_failure(
                node_type="消息发布节点",
                node_name=self.name,
                reason="缺少 topic"
            )
            return NodeStatus.FAILURE

        topic = self.topic
        if self.prefix_tree_id and not topic.startswith("bt."):
            tree_id = context.get_tree_id()
            topic = f"bt.{tree_id}.{topic}"

        payload = self.payload
        if self.payload_key:
            val = context.blackboard.get(self.payload_key)
            if val is not None:
                payload = val

        self._bus.publish(topic, payload)
        LogManager.instance().log_success(
            node_type="消息发布节点",
            node_name=self.name
        )
        return NodeStatus.SUCCESS

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessagePublishNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        return cls(node_id=data.get("id"), config=config)
