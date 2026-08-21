# bt_cli/ai/tree_validator.py
"""行为树结构校验器

在 AI 生成 tree.json 后进行结构校验，确保可被 Serializer 正确加载。
"""
from typing import List, Dict, Any


class TreeValidator:
    """行为树 JSON 结构校验器"""

    # 条件节点类型（必须有子节点）
    CONDITION_TYPES = {
        "OCRConditionNode", "ImageConditionNode", "ColorConditionNode",
        "NumberConditionNode", "VariableConditionNode", "TextExtractNode",
    }

    def validate(self, tree_data: Dict[str, Any]) -> List[str]:
        """校验行为树结构

        Args:
            tree_data: tree.json 字典

        Returns:
            错误列表（空列表表示通过）
        """
        errors = []

        # 1. 基本结构检查
        if not isinstance(tree_data, dict):
            return ["tree_data 不是字典"]

        if "nodes" not in tree_data:
            errors.append("缺少 nodes 字段")
            return errors

        nodes = tree_data.get("nodes", {})
        root_id = tree_data.get("root_node")

        # 2. 根节点检查
        if not root_id:
            errors.append("缺少 root_node 字段")
        elif root_id not in nodes:
            errors.append(f"root_node '{root_id}' 在 nodes 中不存在")
        else:
            root_node = nodes[root_id]
            if root_node.get("type") != "StartNode":
                errors.append(f"根节点必须是 StartNode，当前为 {root_node.get('type')}")

        # 3. 节点 ID 唯一性（nodes 字典的 key 就是 ID，天然唯一）
        # 但检查 children 中的自引用
        for node_id, node in nodes.items():
            children = node.get("children", [])
            if node_id in children:
                errors.append(f"节点 {node_id} 自引用为子节点")

        # 4. 条件节点必须有子节点
        for node_id, node in nodes.items():
            node_type = node.get("type", "")
            if node_type in self.CONDITION_TYPES:
                children = node.get("children", [])
                if len(children) == 0:
                    errors.append(f"条件节点 {node_id} ({node_type}) 必须有至少一个子节点")

        # 5. connections 完整性
        connections = tree_data.get("connections", [])
        for conn in connections:
            parent_id = conn.get("parent_id")
            child_id = conn.get("child_id")
            if parent_id not in nodes:
                errors.append(f"connection 的 parent_id '{parent_id}' 不存在")
            if child_id not in nodes:
                errors.append(f"connection 的 child_id '{child_id}' 不存在")

        # 6. children 引用一致性
        for node_id, node in nodes.items():
            children = node.get("children", [])
            for child_id in children:
                if child_id not in nodes:
                    errors.append(f"节点 {node_id} 的子节点 '{child_id}' 不存在")

        return errors

    def validate_with_serializer(self, tree_data: Dict[str, Any]) -> List[str]:
        """使用 Serializer 进行往返校验

        Args:
            tree_data: tree.json 字典

        Returns:
            错误列表
        """
        errors = self.validate(tree_data)
        if errors:
            return errors

        try:
            from bt_core.serializer import Serializer
            from bt_core.registry import register_all_nodes
            register_all_nodes()
            result = Serializer.deserialize(tree_data)
            if result is None or (isinstance(result, tuple) and result[0] is None):
                errors.append("Serializer.deserialize 返回 None，反序列化失败")
        except Exception as e:
            errors.append(f"Serializer 反序列化失败: {e}")

        return errors
