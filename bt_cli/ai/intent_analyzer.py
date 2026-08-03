# bt_cli/ai/intent_analyzer.py
"""阶段① 意图分析 — 将自然语言描述解析为结构化任务计划"""
import json
import os
from typing import Dict, Any

from bt_cli.ai.llm_client import LLMClient


class IntentAnalysisError(Exception):
    """意图分析错误"""
    pass


class IntentAnalyzer:
    """意图分析器

    将用户自然语言描述解析为结构化任务计划（plan.json）。
    """

    PROMPT_FILE = os.path.join(os.path.dirname(__file__), "prompts", "intent_analysis.md")

    def __init__(self, llm_client: LLMClient = None):
        self._llm = llm_client

    def analyze(self, description: str) -> Dict[str, Any]:
        """分析用户描述，输出任务计划

        Args:
            description: 用户的自然语言任务描述

        Returns:
            结构化任务计划字典（plan.json 格式）

        Raises:
            IntentAnalysisError: 分析失败
        """
        if self._llm is None:
            self._llm = LLMClient.from_config("llm")

        system_prompt = self._load_prompt()
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": description},
        ]

        try:
            result = self._llm.chat(
                messages,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        except Exception as e:
            raise IntentAnalysisError(f"LLM 请求失败: {e}") from e

        try:
            plan = json.loads(result["content"])
        except json.JSONDecodeError as e:
            raise IntentAnalysisError(
                f"LLM 返回的 JSON 无效: {e}\n原始内容: {result['content'][:500]}"
            ) from e

        if not self._validate_plan(plan):
            raise IntentAnalysisError(f"任务计划结构不完整: {plan}")

        return plan

    def _load_prompt(self) -> str:
        """加载系统提示词"""
        with open(self.PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()

    def _validate_plan(self, plan: dict) -> bool:
        """验证任务计划结构"""
        required_keys = {"task_summary", "loop", "phases", "window"}
        if not required_keys.issubset(plan.keys()):
            return False
        if not isinstance(plan["phases"], list) or len(plan["phases"]) == 0:
            return False
        return True
