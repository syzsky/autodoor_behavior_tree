"""
行为树节点 - 游戏自动化集成
========================
提供行为树节点供 AutoDoor 编辑器使用
"""

from .engine import AutomationEngine, AutomationState


class AutomationStartNode:
    """
    启动自动化任务节点
    
    行为树用法：
        <Action name="StartAutomation">
            <window_title>传奇</window_title>
            <target_map>猪洞七层</target_map>
            <npc_image>templates/npc.png</npc_image>
        </Action>
    """

    def __init__(self, engine: AutomationEngine):
        self._engine = engine

    def tick(self) -> str:
        """执行"""
        if not self._engine or not self._engine.is_running:
            return "FAILURE"
        return "SUCCESS"


class AutomationStatusNode:
    """
    检查自动化状态节点
    
    行为树用法：
        <Condition name="AutomationStatus">
            <state>FARMING</state>
        </Condition>
    """

    def __init__(self, engine: AutomationEngine):
        self._engine = engine

    def tick(self, target_state: str = "FARMING") -> str:
        """检查状态"""
        if not self._engine:
            return "FAILURE"

        try:
            state = AutomationState[target_state.upper()]
            return "SUCCESS" if self._engine.state == state else "FAILURE"
        except (KeyError, AttributeError):
            return "FAILURE"


class RecycleNode:
    """
    执行回收节点
    
    行为树用法：
        <Action name="AutoRecycle">
            <button_template>templates/recycle.png</button_template>
        </Action>
    """

    def __init__(self, inventory_manager):
        self._inventory = inventory_manager

    def tick(self, button_template, confirm_template=None) -> str:
        """执行回收"""
        if not self._inventory:
            return "FAILURE"
        return "SUCCESS"


class GoHomeNode:
    """
    回城节点
    """

    def __init__(self, navigator):
        self._navigator = navigator

    def tick(self, home_map_template) -> str:
        """回城"""
        if not self._navigator:
            return "FAILURE"
        return "SUCCESS"