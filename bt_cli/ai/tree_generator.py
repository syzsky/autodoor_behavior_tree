# bt_cli/ai/tree_generator.py
"""阶段④ JSON 生成 — 将节点结构转换为 tree.json 格式"""
import json
from typing import Dict, Any, List
from datetime import datetime


class TreeGenerator:
    """行为树 JSON 生成器

    将节点结构（structure.json）转换为 tree.json v2.1 格式，
    自动计算布局坐标。
    """

    def generate(self, structure: Dict[str, Any],
                 canvas_name: str = "AI生成流程",
                 description: str = "") -> Dict[str, Any]:
        """生成 tree.json

        Args:
            structure: 节点结构（structure_filled.json 格式）
            canvas_name: 画布名称
            description: 描述

        Returns:
            tree.json 格式字典
        """
        nodes_list = structure.get("nodes", [])
        if not nodes_list:
            raise ValueError("节点结构为空")

        # 构建节点查找表
        node_map = {n["id"]: n for n in nodes_list}

        # 计算布局
        layout = self._compute_layout(nodes_list)

        # 转换为 tree.json 节点格式
        nodes_dict = {}
        connections = []

        for node in nodes_list:
            node_id = node["id"]
            pos = layout[node_id]

            nodes_dict[node_id] = {
                "id": node_id,
                "type": node["type"],
                "name": self._generate_name(node),
                "enabled": True,
                "config": node.get("config", {}),
                "position": {"x": pos[0], "y": pos[1]},
                "children": node.get("children", []),
            }

            # 添加 connections
            for child_id in node.get("children", []):
                connections.append({
                    "parent_id": node_id,
                    "child_id": child_id,
                })

        tree_data = {
            "version": "2.1",
            "format_type": "behavior_tree",
            "metadata": {
                "created_at": datetime.now().isoformat(),
                "modified_at": datetime.now().isoformat(),
                "app_version": "ai-generated",
            },
            "canvas": {
                "name": canvas_name,
                "description": description,
                "viewport": {"zoom": 1.0, "offset_x": 0, "offset_y": 0},
            },
            "root_node": nodes_list[0]["id"],
            "nodes": nodes_dict,
            "connections": connections,
        }

        return tree_data

    def generate_and_validate(self, structure: Dict[str, Any],
                              **kwargs) -> tuple:
        """生成并校验

        Returns:
            (tree_data, errors) 元组
        """
        from bt_cli.ai.tree_validator import TreeValidator

        tree_data = self.generate(structure, **kwargs)
        validator = TreeValidator()
        errors = validator.validate(tree_data)
        return tree_data, errors

    def _compute_layout(self, nodes_list: List[Dict]) -> Dict[str, tuple]:
        """计算节点布局坐标

        规则：同级节点横向排列，父子节点纵向排列。
        根节点 Y=50，每层 Y+=100，同级 X 间距 200。
        """
        layout = {}
        node_map = {n["id"]: n for n in nodes_list}
        root_id = nodes_list[0]["id"]

        # BFS 遍历计算层级
        levels = {}  # node_id -> level
        queue = [(root_id, 0)]
        while queue:
            node_id, level = queue.pop(0)
            if node_id in levels:
                continue
            levels[node_id] = level
            for child_id in node_map.get(node_id, {}).get("children", []):
                if child_id not in levels:
                    queue.append((child_id, level + 1))

        # 按层级分组
        level_nodes = {}
        for node_id, level in levels.items():
            if level not in level_nodes:
                level_nodes[level] = []
            level_nodes[level].append(node_id)

        # 计算坐标
        for level, node_ids in level_nodes.items():
            y = 50 + level * 100
            count = len(node_ids)
            for i, node_id in enumerate(node_ids):
                x = 400 + (i - (count - 1) / 2) * 200
                layout[node_id] = (int(x), y)

        # 未遍历到的节点（孤立节点）
        for node in nodes_list:
            if node["id"] not in layout:
                layout[node["id"]] = (400, 50)

        return layout

    def _generate_name(self, node: Dict) -> str:
        """生成节点显示名称"""
        type_names = {
            "StartNode": "开始",
            "SequenceNode": "顺序执行",
            "SelectorNode": "选择执行",
            "ParallelNode": "并行执行",
            "RandomNode": "随机执行",
            "SubtreeNode": "子树",
            "DelayNode": "延时",
            "MouseClickNode": "鼠标点击",
            "MouseMoveNode": "鼠标移动",
            "MouseScrollNode": "鼠标滚轮",
            "KeyPressNode": "键盘按键",
            "TextInputNode": "文本输入",
            "SetVariableNode": "设置变量",
            "AlarmNode": "报警",
            "ScriptNode": "执行脚本",
            "CodeNode": "执行代码",
            "OCRConditionNode": "OCR识别",
            "ImageConditionNode": "图像匹配",
            "ColorConditionNode": "颜色检测",
            "NumberConditionNode": "数字比较",
            "VariableConditionNode": "变量判断",
            "TextExtractNode": "文本提取",
        }
        return type_names.get(node["type"], node["type"])
