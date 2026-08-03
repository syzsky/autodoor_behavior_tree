"""AI 助手状态管理"""
from typing import Dict, Any, Optional


class AssistantState:
    """AI 助手面板状态

    管理 5 阶段流水线的状态流转。
    阶段编号：0=未开始, 1=意图分析, 2=节点选型,
    3=屏幕感知, 4=生成JSON, 5=试运行
    """

    MAX_STAGE = 5

    def __init__(self):
        self.stage: int = 0
        self.plan: Optional[Dict[str, Any]] = None
        self.structure: Optional[Dict[str, Any]] = None
        self.filled_structure: Optional[Dict[str, Any]] = None
        self.tree_data: Optional[Dict[str, Any]] = None
        self.test_report: Optional[Dict[str, Any]] = None
        self.is_processing: bool = False

    def advance(self) -> int:
        """前进到下一阶段"""
        if self.stage < self.MAX_STAGE:
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
        return self.stage < self.MAX_STAGE

    def reset(self) -> None:
        """重置到初始状态"""
        self.stage = 0
        self.plan = None
        self.structure = None
        self.filled_structure = None
        self.tree_data = None
        self.test_report = None
        self.is_processing = False
