from bt_core.nodes import ConditionNode
from bt_core.config import NodeConfig
from typing import Dict, Any


class VariableConditionNode(ConditionNode):
    NODE_TYPE = "VariableConditionNode"

    def __init__(self, node_id: str = None, config: NodeConfig = None):
        super().__init__(node_id, config)
        self.variable_name = self.config.get("variable_name", "")
        self.comparison = self.config.get("comparison") or self.config.get("operator", "==")
        self.target_value = self.config.get("target_value") or self.config.get("compare_value", "")

    def _check_condition(self, context) -> bool:
        try:
            if not self.variable_name:
                self._log_condition_result(False, "未设置变量名")
                return False

            value = context.blackboard.get(self.variable_name)
            if value is None:
                self._log_condition_result(False, f"变量不存在: {self.variable_name}")
                return False

            result = self._compare_value(value)

            if result:
                self._log_condition_result(True, extra_info=f"值: {value}")
                return True
            else:
                self._log_condition_result(False,
                    f"变量比较失败: {value} {self.comparison} {self.target_value}")
                return False
        except Exception as e:
            from bt_utils.exception_handler import log_exception
            log_exception(e, f"VariableConditionNode '{self.name}'")
            self._log_condition_result(False, "检测异常，详情见终端日志")
            return False

    def _compare_value(self, value) -> bool:
        """比较变量值

        Args:
            value: 变量当前值

        Returns:
            比较结果
        """
        try:
            ops = {
                ">": lambda a, b: a > b,
                ">=": lambda a, b: a >= b,
                "<": lambda a, b: a < b,
                "<=": lambda a, b: a <= b,
                "==": lambda a, b: a == b,
                "!=": lambda a, b: a != b,
            }
            
            if self.comparison in ops:
                try:
                    num_value = float(value) if isinstance(value, str) else value
                    num_target = float(self.target_value) if isinstance(self.target_value, str) else self.target_value
                    
                    if isinstance(num_value, (int, float)) and isinstance(num_target, (int, float)):
                        return ops[self.comparison](num_value, num_target)
                except (ValueError, TypeError):
                    pass

            str_value = str(value)
            str_target = str(self.target_value)

            if self.comparison == "==":
                return str_value == str_target
            elif self.comparison == "!=":
                return str_value != str_target
            elif self.comparison == "contains":
                return str_target in str_value
            elif self.comparison == "not_contains":
                return str_target not in str_value
            elif self.comparison == "starts_with":
                return str_value.startswith(str_target)
            elif self.comparison == "ends_with":
                return str_value.endswith(str_target)
            else:
                return str_value == str_target
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data["config"]["variable_name"] = self.variable_name
        data["config"]["comparison"] = self.comparison
        data["config"]["target_value"] = self.target_value
        data["config"]["operator"] = self.comparison
        data["config"]["compare_value"] = self.target_value
        return data
