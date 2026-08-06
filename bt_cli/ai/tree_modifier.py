# bt_cli/ai/tree_modifier.py
"""分析模式核心 — 根据用户意图结构级修改已有行为树

读入一棵已有行为树（tree.json，nodes 为 dict 形态）+ 用户修改意图，
交由 LLM 返回修改后的整棵新树 + 人类可读改动清单，并经 TreeValidator
校验通过后返回。校验失败时抛出 TreeModifyError。
"""
import json
import os
from typing import Dict, Any, List

from bt_cli.ai.llm_client import LLMClient
from bt_cli.ai.node_spec_exporter import NodeSpecExporter


class TreeModifyError(Exception):
    """行为树修改错误"""
    pass


class TreeModifier:
    """行为树修改器：读已有树 + 用户意图 → 返回整棵新树"""

    PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "tree_modify.md")

    def __init__(self, llm_client: LLMClient = None):
        self._llm = llm_client
        self._spec_exporter = NodeSpecExporter()

    def modify(self, tree_data: Dict[str, Any], intent: str,
               task_context: str = "") -> Dict[str, Any]:
        """根据用户意图修改已有行为树

        Args:
            tree_data: 已有行为树（tree.json 格式，nodes 为 dict）
            intent: 用户修改意图
            task_context: 任务上下文

        Returns:
            {"tree", "changes", "summary"}

        Raises:
            TreeModifyError: LLM 请求/JSON 解析/结构校验失败
        """
        if self._llm is None:
            self._llm = LLMClient.from_config("llm")

        system_prompt = self._load_prompt()
        spec_text = self._spec_exporter.export_for_prompt()

        user_content = (
            f"## 现有行为树\n```json\n"
            f"{json.dumps(tree_data, ensure_ascii=False, indent=2)}\n```\n\n"
            f"## 用户修改意图\n{intent}\n\n"
            f"## 任务上下文\n{task_context}\n\n"
            f"## 可用节点规格\n{spec_text}\n\n"
            "请返回修改后的完整行为树 tree.json 和改动清单。"
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
            raise TreeModifyError(f"LLM 请求失败: {e}") from e

        try:
            data = json.loads(result["content"])
        except json.JSONDecodeError as e:
            raise TreeModifyError(
                f"LLM 返回的 JSON 无效: {e}\n原始内容: {result['content'][:500]}"
            ) from e

        tree = data.get("tree")
        if not tree:
            raise TreeModifyError("LLM 未返回修改后的行为树")

        # 结构校验
        from bt_cli.ai.tree_validator import TreeValidator
        errors = TreeValidator().validate(tree)
        if errors:
            raise TreeModifyError("修改后的行为树校验失败: " + "; ".join(errors))

        return {
            "tree": tree,
            "changes": data.get("changes", []),
            "summary": data.get("summary", ""),
        }

    def _summarize_tree(self, tree_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """精简行为树用于 AI 分析（真实 tree.json 的 nodes 为 dict 形态）"""
        summary = []
        for node_id, node in tree_data.get("nodes", {}).items():
            summary.append({
                "id": node_id,
                "type": node.get("type"),
                "config": node.get("config", {}),
                "children": node.get("children", []),
            })
        return summary

    def _load_prompt(self) -> str:
        """加载系统提示词"""
        with open(self.PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()