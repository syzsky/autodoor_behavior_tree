# bt_cli/ai/node_selector.py
"""阶段② 节点选型 — 根据任务计划和节点规格选择节点并设计结构"""
import json
import os
from typing import Dict, Any

from bt_cli.ai.llm_client import LLMClient
from bt_cli.ai.node_spec_exporter import NodeSpecExporter
from bt_cli.ai.resource_path import get_resource_path
from bt_core.registry import NodeRegistry


class NodeSelectionError(Exception):
    """节点选型错误"""
    pass


class NodeSelector:
    """节点选型器

    根据任务计划 + 动态导出的节点规格，选择节点并设计连接结构。
    """

    PROMPT_FILE = get_resource_path(__file__, "prompts", "node_selection.md")

    def __init__(self, llm_client: LLMClient = None):
        self._llm = llm_client
        self._spec_exporter = NodeSpecExporter()

    def select(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """根据任务计划选择节点

        Args:
            plan: 任务计划（plan.json 格式）

        Returns:
            节点结构（structure.json 格式）

        Raises:
            NodeSelectionError: 选型失败
        """
        if self._llm is None:
            self._llm = LLMClient.from_config("llm")

        system_prompt = self._load_prompt()
        spec_text = self._spec_exporter.export_for_prompt()

        user_content = (
            f"## 任务计划\n```json\n{json.dumps(plan, ensure_ascii=False, indent=2)}\n```\n\n"
            f"## 可用节点规格\n{spec_text}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            result = self._llm.chat(
                messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise NodeSelectionError(f"LLM 请求失败: {e}") from e

        try:
            structure = json.loads(result["content"])
        except json.JSONDecodeError as e:
            raise NodeSelectionError(
                f"LLM 返回的 JSON 无效: {e}\n原始内容: {result['content'][:500]}"
            ) from e

        if not self._validate_structure(structure):
            raise NodeSelectionError(f"节点结构无效: {structure}")

        return structure

    def _load_prompt(self) -> str:
        with open(self.PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()

    def _validate_structure(self, structure: dict) -> bool:
        """验证节点结构基本完整性"""
        if "nodes" not in structure or not isinstance(structure["nodes"], list):
            return False
        if len(structure["nodes"]) == 0:
            return False

        # 检查根节点是 StartNode
        root = structure["nodes"][0]
        if not isinstance(root, dict) or root.get("type") != "StartNode":
            return False

        # 收集所有节点 ID 并检查唯一性
        ids_list = [n.get("id") for n in structure["nodes"]]
        if None in ids_list:
            return False
        if len(ids_list) != len(set(ids_list)):
            return False
        all_ids = set(ids_list)

        # 检查节点类型存在且 children 引用有效
        registered = NodeRegistry.list_types()
        for node in structure["nodes"]:
            if not isinstance(node, dict):
                return False
            node_type = node.get("type")
            if node_type is None or node_type not in registered:
                return False
            # 检查 children 引用有效
            children = node.get("children", [])
            if not isinstance(children, list):
                return False
            for child_id in children:
                if child_id not in all_ids:
                    return False

        return True
