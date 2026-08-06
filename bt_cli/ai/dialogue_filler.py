# bt_cli/ai/dialogue_filler.py
"""阶段③ 语言补全 — VLM 不可用时引导用户用语言描述补全空参数"""
import json
import os
import copy
from typing import Dict, Any, List

from bt_cli.ai.llm_client import LLMClient


class DialogueFillError(Exception):
    """语言补全错误"""
    pass


class DialogueFiller:
    """语言补全器：VLM 不可用/跳过的回退方案"""

    PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "dialogue_fill.md")

    def __init__(self, llm_client: LLMClient = None):
        self._llm = llm_client

    def propose_questions(self, structure: Dict[str, Any],
                          task_context: str) -> List[Dict[str, Any]]:
        """列出所有空参数并生成引导问题

        Args:
            structure: 节点结构（含 empty_params）
            task_context: 任务上下文描述

        Returns:
            引导问题列表 [{"node_id", "node_type", "param", "question", "hint"}]

        Raises:
            DialogueFillError: 补全失败
        """
        if self._llm is None:
            self._llm = LLMClient.from_config("llm")
        fill_requests = self._extract_empty_params(structure)
        if not fill_requests:
            return []
        system_prompt = self._load_prompt()
        user_content = (
            f"## 任务上下文\n{task_context}\n\n"
            f"## 需要补全的参数清单\n"
            + "\n".join(f"- 节点 {r['node_id']} ({r['node_type']}): 参数 '{r['param']}'"
                        for r in fill_requests)
            + "\n\n请为每个参数生成一个引导用户用语言描述的问题。"
        )
        try:
            result = self._llm.chat(
                [{"role": "system", "content": system_prompt},
                 {"role": "user", "content": user_content}],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise DialogueFillError(f"LLM 请求失败: {e}") from e
        try:
            data = json.loads(result["content"])
            raw_questions = data.get("questions", [])
        except json.JSONDecodeError as e:
            raise DialogueFillError(f"LLM 返回的 JSON 无效: {e}") from e
        return self._backfill(raw_questions, fill_requests)

    def _backfill(self, questions: List[Dict[str, Any]],
                  fill_requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将 LLM 输出的问题回填为稳定的五字段契约。

        以 (node_id, param) 为键，从 fill_requests 中补齐 node_type；
        hint 缺失时生成默认引导提示。
        """
        meta = {(r["node_id"], r["param"]): r for r in fill_requests}
        for q in questions:
            if not isinstance(q, dict):
                continue
            node_id = q.get("node_id")
            param = q.get("param")
            req = meta.get((node_id, param), {})
            q.setdefault("node_type", req.get("node_type", ""))
            if not q.get("hint"):
                q["hint"] = "请描述该目标元素的位置或特征"
        return [q for q in questions if isinstance(q, dict)]

    def resolve_from_answers(self, structure: Dict[str, Any],
                             answers: List[Dict[str, Any]]) -> Dict[str, Any]:
        """根据用户/LLM 的建议值填充结构（复用 fill_structure 同构逻辑）

        Args:
            structure: 节点结构（AI 中间格式，nodes 为 list）
            answers: 答案列表 [{"node_id", "param", "suggested_value"}]

        Returns:
            填充后的节点结构（深拷贝）
        """
        filled = copy.deepcopy(structure)
        nodes = filled.get("nodes", [])
        node_map = {n.get("id"): n for n in nodes if isinstance(n, dict)}
        for ans in answers:
            if not isinstance(ans, dict):
                continue
            node_id = ans.get("node_id")
            param = ans.get("param")
            value = ans.get("suggested_value")
            if node_id is None or param is None or value is None:
                continue
            if node_id in node_map:
                node = node_map[node_id]
                node.setdefault("config", {})[param] = value
                if "empty_params" in node:
                    node["empty_params"] = [
                        p for p in node["empty_params"] if p != param
                    ]
        return filled

    def _extract_empty_params(self, structure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从节点结构中提取所有空参数（nodes 为 list 形态）"""
        requests = []
        for node in structure.get("nodes", []):
            if not isinstance(node, dict):
                continue
            for param in node.get("empty_params", []):
                requests.append({
                    "node_id": node.get("id", ""),
                    "param": param,
                    "node_type": node.get("type", ""),
                })
        return requests

    def _load_prompt(self) -> str:
        """加载系统提示词"""
        with open(self.PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()