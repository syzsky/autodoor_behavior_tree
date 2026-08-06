"""AI 助手状态管理"""
from enum import Enum
from typing import Dict, Any, Optional


class AssistantMode(Enum):
    """AI 助手工作模式"""

    CREATE = "create"
    ANALYZE = "analyze"


class AssistantState:
    """AI 助手面板状态

    管理多阶段流水线的状态流转，支持双模式：
    - CREATE：5 阶段。阶段编号：0=未开始, 1=意图分析, 2=节点选型,
      3=屏幕感知, 4=生成JSON, 5=试运行
    - ANALYZE：3 阶段。阶段编号：0=读取树, 1=意图, 2=方案, 3=应用
    """

    MAX_STAGE = 5

    def __init__(self):
        self.mode: AssistantMode = AssistantMode.CREATE
        self.stage: int = 0
        self.plan: Optional[Dict[str, Any]] = None
        self.structure: Optional[Dict[str, Any]] = None
        self.filled_structure: Optional[Dict[str, Any]] = None
        self.tree_data: Optional[Dict[str, Any]] = None
        self.test_report: Optional[Dict[str, Any]] = None
        self.is_processing: bool = False
        # ANALYZE 模式专用字段
        self.source_tree: Optional[Dict[str, Any]] = None
        self.modification_plan: Optional[Dict[str, Any]] = None
        self.analyze_result: Optional[Dict[str, Any]] = None
        # 瞬时下划线属性（后台线程写入的临时态，模式切换/重置前由 clear_transient 清理）
        self._suggestions: Optional[Any] = None
        self._dialogue_questions: Optional[Any] = None
        self._fixes: Optional[Any] = None
        self._errors: Optional[Any] = None
        self._error: Optional[Any] = None
        self._analysis: Optional[Any] = None

    def clear_transient(self) -> None:
        """清空瞬时下划线属性，保留 plan/structure/tree_data 等永久字段。

        永久字段（如 plan/structure/filled_structure/tree_data/test_report）
        由面板在模式切换时单独重置，此处不动。
        """
        self._suggestions = None
        self._dialogue_questions = None
        self._fixes = None
        self._errors = None
        self._error = None
        self._analysis = None

    def _max_stage(self) -> int:
        """返回当前模式的最大阶段编号"""
        if self.mode == AssistantMode.ANALYZE:
            return 3
        return self.MAX_STAGE

    def advance(self) -> int:
        """前进到下一阶段"""
        if self.stage < self._max_stage():
            self.stage += 1
        return self.stage

    def go_back(self) -> int:
        """回退到上一阶段"""
        if self.stage > 0:
            self.stage -= 1
        return self.stage

    def can_go_back(self) -> bool:
        """是否可回退"""
        return self.stage > 0

    def can_advance(self) -> bool:
        """是否可前进"""
        return self.stage < self._max_stage()

    def reset(self) -> None:
        """重置到初始状态"""
        self.mode = AssistantMode.CREATE
        self.stage = 0
        self.plan = None
        self.structure = None
        self.filled_structure = None
        self.tree_data = None
        self.test_report = None
        self.is_processing = False
        self.source_tree = None
        self.modification_plan = None
        self.analyze_result = None