# bt_cli/ai/tree_modifier.py
"""分析模式核心 — 根据用户意图结构级修改已有行为树

读入一棵已有行为树（tree.json，nodes 为 dict 形态）+ 用户修改意图，
先精简要发送给 LLM 的树结构以控制 prompt 体积，交由 LLM 返回修改后的
整棵新树 + 人类可读改动清单，并经 TreeValidator 校验通过后返回。
校验失败时抛出 TreeModifyError。
"""
import json
import os
from typing import Dict, Any, List

from bt_cli.ai.llm_client import LLMClient
from bt_cli.ai.node_spec_exporter import NodeSpecExporter
from bt_cli.ai.tree_validator import TreeValidator


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
        # 精简树仅含 [{id,type,config,children}]，控制发送给 LLM 的 prompt 体积
        tree_summary = self._summarize_tree(tree_data)

        user_content = (
            f"## 现有行为树（精简结构）\n```json\n"
            f"{json.dumps(tree_summary, ensure_ascii=False, indent=2)}\n```\n\n"
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

        # 顶层必须是 dict，否则 data.get 会抛 AttributeError 而非 TreeModifyError
        if not isinstance(data, dict):
            raise TreeModifyError(
                f"LLM 返回的 JSON 顶层必须是对象，实际为 {type(data).__name__}: "
                f"{json.dumps(data, ensure_ascii=False)[:500]}"
            )

        tree = data.get("tree")
        if not tree:
            raise TreeModifyError("LLM 未返回修改后的行为树")
        # 防御：tree 必须是 dict 形态，否则下方 .get 会抛 AttributeError 而非 TreeModifyError
        if not isinstance(tree, dict):
            raise TreeModifyError("修改后的行为树格式错误")

        # 防御：nodes 必须是 dict 形态，否则 TreeValidator.validate 可能抛原生 TypeError
        if not isinstance(tree.get("nodes"), dict):
            raise TreeModifyError("修改后的行为树 nodes 格式错误")

        # 结构校验
        errors = TreeValidator().validate(tree)
        if errors:
            raise TreeModifyError("修改后的行为树校验失败: " + "; ".join(errors))

        changes = data.get("changes", [])
        if not isinstance(changes, list):
            changes = []
        summary = data.get("summary", "")
        if not isinstance(summary, str):
            summary = str(summary)

        return {
            "tree": tree,
            "changes": changes,
            "summary": summary,
        }

    def _summarize_tree(self, tree_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """精简行为树用于 AI 分析（真实 tree.json 的 nodes 为 dict 形态）

        返回 [{id, type, config, children}]，不含 name/enabled/position 等
        展示性字段，以控制发送给 LLM 的 prompt 体积。
        """
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