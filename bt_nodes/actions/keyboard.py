from bt_core.nodes import ActionNode, NodeStatus
from bt_core.config import NodeConfig
from typing import Dict, Any
from bt_utils.log_manager import LogManager
from bt_utils.helpers import get_random_duration


class KeyPressNode(ActionNode):
    NODE_TYPE = "KeyPressNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.key = self.config.get("key", "space")
        self.action = self.config.get("action", "press")
        self.duration = self.config.get_int("duration", 0)
        self.duration_random = self.config.get_int("duration_random", 0)

    def _execute_action(self, context) -> NodeStatus:
        try:
            if not self.key:
                LogManager.instance().log_failure(
                    node_type="按键节点",
                    node_name=self.name,
                    reason="未配置按键"
                )
                return NodeStatus.FAILURE
            
            actual_duration = get_random_duration(self.duration, self.duration_random)
            context.execute_key_press(self.key, self.action, actual_duration)
            
            LogManager.instance().log_success(
                node_type="按键节点",
                node_name=self.name
            )
            return NodeStatus.SUCCESS
        except Exception as e:
            LogManager.instance().log_failure(
                node_type="按键节点",
                node_name=self.name,
                reason=str(e)
            )
            return NodeStatus.FAILURE

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["config"]["key"] = self.key
        data["config"]["action"] = self.action
        data["config"]["duration"] = self.duration
        data["config"]["duration_random"] = self.duration_random
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "KeyPressNode":
        config = NodeConfig.from_dict(data.get("config", {}))
        node = cls(node_id=data.get("id"), config=config)
        node.key = config.get("key", "space")
        node.action = config.get("action", "press")
        node.duration = config.get_int("duration", 0)
        node.duration_random = config.get_int("duration_random", 0)
        return node
